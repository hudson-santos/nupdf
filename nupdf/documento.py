"""Documento PDF aberto (PyMuPDF) com cache de palavras em ordem visual.

O arquivo é lido inteiro para a memória: assim o NuPDF não mantém o PDF
travado no Windows (dá para mover/renomear/sobrescrever enquanto está aberto)
e os mesmos bytes servem para a assinatura digital.
"""

from pathlib import Path

import pymupdf

pymupdf.TOOLS.mupdf_display_errors(False)


class SenhaNecessaria(Exception):
    pass


# (x0, y0, x1, y1, texto, linha) - coordenadas no espaço NÃO rotacionado da página
Palavra = tuple

# cores do marca-texto: chave -> (rótulo no menu, RGB). Tons claros: o destaque é
# desenhado em "multiply", então o texto continua legível por baixo.
CORES_DESTAQUE = {
    "azul": ("Azul - Prioridade Baixa", (0.55, 0.78, 1.0)),
    "amarelo": ("Amarelo - Prioridade Média", (1.0, 0.92, 0.23)),
    "vermelho": ("Vermelho - Prioridade Alta", (1.0, 0.55, 0.55)),
    "verde": ("Verde - Resolvido", (0.56, 0.9, 0.56)),
}
COR_PADRAO = "amarelo"


def _ordenar_visual(palavras) -> list[Palavra]:
    """Agrupa palavras em linhas visuais (sobreposição vertical) e ordena
    de cima para baixo / esquerda para direita. Funciona melhor que a ordem do
    fluxo de conteúdo em formulários e certidões, onde rótulo e valor ficam em
    blocos diferentes na mesma linha."""
    ws = sorted(palavras, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    linhas: list[list] = []
    faixas: list[tuple[float, float]] = []
    for w in ws:
        h = max(w[3] - w[1], 0.1)
        if faixas:
            y0, y1 = faixas[-1]
            sobre = min(y1, w[3]) - max(y0, w[1])
            if sobre >= 0.5 * min(h, y1 - y0):
                linhas[-1].append(w)
                continue
        linhas.append([w])
        faixas.append((w[1], w[3]))
    saida = []
    for n, linha in enumerate(linhas):
        for w in sorted(linha, key=lambda w: w[0]):
            saida.append((w[0], w[1], w[2], w[3], w[4], n))
    return saida


class Documento:
    def __init__(self, caminho: str, senha: str | None = None, dados: bytes | None = None,
                 pendencias: list[str] | None = None):
        """`dados`: conteúdo já em memória (ex.: depois de excluir uma página), no lugar
        do arquivo em `caminho`; `pendencias`: alterações ainda não salvas que vieram
        junto (descrições, como "páginas excluídas")."""
        self.caminho = Path(caminho)
        self.dados = dados if dados is not None else self.caminho.read_bytes()
        self.pendencias_herdadas: list[str] = list(pendencias or [])
        self.doc = pymupdf.open(stream=self.dados, filetype="pdf")
        self.senha = None
        if self.doc.needs_pass:
            if not senha or not self.doc.authenticate(senha):
                self.doc.close()
                raise SenhaNecessaria()
            self.senha = senha
        self._palavras: dict[int, list[Palavra]] = {}
        self._links: dict[int, list] = {}
        self._assinaturas_pag: dict[int, list] = {}
        # destaques (marca-texto): ficam no documento exibido e só são aplicados numa
        # cópia ao salvar/imprimir. Os feitos nesta sessão: xref da anotação na tela ->
        # (página, retângulos das linhas); os que já vinham no PDF e foram removidos:
        # (página, xref) - os xrefs são os mesmos na cópia aberta dos mesmos bytes.
        self._destaques_novos: dict[int, tuple[int, list[pymupdf.Rect], str]] = {}
        self._destaques_removidos: set[tuple[int, int]] = set()
        self._cores_alteradas: dict[tuple[int, int], str] = {}  # destaques do PDF recoloridos
        self._estado_salvo = self._estado_destaques()

    @property
    def nome(self) -> str:
        # sem a extensão: o NuPDF só abre PDF (aba, título, impressão...)
        return self.caminho.stem

    @property
    def n_paginas(self) -> int:
        return self.doc.page_count

    def palavras(self, i: int) -> list[Palavra]:
        if i not in self._palavras:
            brutas = self.doc[i].get_text("words", sort=False)
            self._palavras[i] = _ordenar_visual(brutas)
        return self._palavras[i]

    def links(self, i: int) -> list:
        if i not in self._links:
            try:
                self._links[i] = self.doc[i].get_links()
            except Exception:
                self._links[i] = []
        return self._links[i]

    def assinaturas_visiveis(self, i: int) -> list[tuple[pymupdf.Rect, str]]:
        """Campos de assinatura com aparência na página i: (retângulo, nome do campo).
        O retângulo segue o mesmo sistema dos links (página já com /Rotate aplicado)."""
        if i not in self._assinaturas_pag:
            achados = []
            try:
                pg = self.doc[i]
                for w in pg.widgets(types=[pymupdf.PDF_WIDGET_TYPE_SIGNATURE]) or []:
                    r = (w.rect * pg.rotation_matrix).normalize()
                    if r.width > 1 and r.height > 1:
                        achados.append((r, w.field_name or ""))
            except Exception:
                pass
            self._assinaturas_pag[i] = achados
        return self._assinaturas_pag[i]

    def linhas(self, i: int) -> list[list[Palavra]]:
        linhas: dict[int, list] = {}
        for w in self.palavras(i):
            linhas.setdefault(w[5], []).append(w)
        return [linhas[k] for k in sorted(linhas)]

    def texto_pagina(self, i: int) -> str:
        return "\n".join(" ".join(w[4] for w in linha) for linha in self.linhas(i))

    def texto_completo(self) -> str:
        return "\n\n".join(self.texto_pagina(i) for i in range(self.n_paginas))

    @property
    def tem_assinaturas(self) -> bool:
        try:
            return self.doc.get_sigflags() > 0
        except Exception:
            return False

    @staticmethod
    def _pintar(annot, cor: str):
        rotulo_curto = CORES_DESTAQUE[cor][0].split(" - ", 1)[1]  # "Prioridade Alta", "Resolvido"...
        annot.set_colors(stroke=CORES_DESTAQUE[cor][1])
        annot.set_info(content=rotulo_curto)  # outros leitores mostram a prioridade ao passar o mouse
        annot.update()

    @classmethod
    def _aplicar_destaque(cls, pg: pymupdf.Page, rets: list[pymupdf.Rect], cor: str) -> int:
        # mesmo sistema de coordenadas das palavras (vale também em página com /Rotate)
        annot = pg.add_highlight_annot(quads=[pymupdf.Rect(r).quad for r in rets])
        cls._pintar(annot, cor)
        return annot.xref

    def destacar(self, i: int, rets: list[pymupdf.Rect], cor: str = COR_PADRAO):
        """Marca-texto na cor escolhida sobre os retângulos (um por linha) da página i."""
        if not rets:
            return
        rets = [pymupdf.Rect(r) for r in rets]
        xref = self._aplicar_destaque(self.doc[i], rets, cor)
        self._destaques_novos[xref] = (i, rets, cor)

    def destaque_em(self, i: int, p: pymupdf.Point) -> int | None:
        """xref do destaque (marca-texto) sob o ponto p da página i, se houver."""
        pg = self.doc[i]  # referenciada enquanto as anotações são lidas
        for annot in pg.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]):
            vs = annot.vertices or []
            for k in range(0, len(vs) - 3, 4):
                if pymupdf.Quad(vs[k:k + 4]).rect.contains(p):
                    return annot.xref
        return None

    def cor_do_destaque(self, i: int, xref: int) -> str | None:
        """Chave de CORES_DESTAQUE mais próxima da cor do destaque (None se nenhuma bater)."""
        if xref in self._destaques_novos:
            return self._destaques_novos[xref][2]
        if (i, xref) in self._cores_alteradas:
            return self._cores_alteradas[(i, xref)]
        pg = self.doc[i]
        rgb = (pg.load_annot(xref).colors or {}).get("stroke")
        if not rgb:
            return None
        dist = {k: sum((a - b) ** 2 for a, b in zip(rgb, v[1])) for k, v in CORES_DESTAQUE.items()}
        k = min(dist, key=dist.get)
        return k if dist[k] < 0.02 else None

    def mudar_cor_destaque(self, i: int, xref: int, cor: str):
        pg = self.doc[i]
        self._pintar(pg.load_annot(xref), cor)
        if xref in self._destaques_novos:
            _, rets, _ = self._destaques_novos[xref]
            self._destaques_novos[xref] = (i, rets, cor)
        else:
            self._cores_alteradas[(i, xref)] = cor

    def remover_destaque(self, i: int, xref: int):
        """Remove o destaque: um desta sessão ou um que já vinha no PDF."""
        pg = self.doc[i]
        pg.delete_annot(pg.load_annot(xref))
        if xref in self._destaques_novos:
            del self._destaques_novos[xref]
        else:
            self._cores_alteradas.pop((i, xref), None)
            self._destaques_removidos.add((i, xref))

    def _estado_destaques(self):
        return (frozenset((x, v[2]) for x, v in self._destaques_novos.items()),
                frozenset(self._destaques_removidos), frozenset(self._cores_alteradas.items()))

    @property
    def destaques_editados(self) -> bool:
        """Há destaques incluídos, removidos ou recoloridos em relação ao arquivo aberto."""
        return bool(self._destaques_novos or self._destaques_removidos or self._cores_alteradas)

    @property
    def destaques_pendentes(self) -> bool:
        """Destaques mudaram desde o último "Salvar" (destacar e remover o mesmo não conta)."""
        return self._estado_destaques() != self._estado_salvo

    def marcar_salvo(self):
        self._estado_salvo = self._estado_destaques()
        self.pendencias_herdadas = []

    def sem_pagina(self, i: int, rotacoes: dict[int, int]) -> bytes:
        """Bytes do documento como está na tela (rotação e destaques) sem a página i."""
        copia = pymupdf.open(stream=self.bytes_editados(rotacoes), filetype="pdf")
        try:
            if copia.needs_pass:
                copia.authenticate(self.senha or "")
            copia.delete_page(i)
            return copia.tobytes()
        finally:
            copia.close()

    def bytes_editados(self, rotacoes: dict[int, int]) -> bytes:
        """PDF como está na tela: rotação da visualização gravada nas páginas
        (/Rotate) e destaques incluídos/removidos/recoloridos. Sem nenhuma
        alteração, devolve os bytes originais intactos (preserva assinaturas)."""
        rotacoes = {i: r % 360 for i, r in rotacoes.items() if r % 360}
        if not rotacoes and not self.destaques_editados:
            return self.dados
        copia = pymupdf.open(stream=self.dados, filetype="pdf")
        try:
            if copia.needs_pass:
                copia.authenticate(self.senha or "")
            for i, xref in self._destaques_removidos:
                pg = copia[i]
                pg.delete_annot(pg.load_annot(xref))
            for (i, xref), cor in self._cores_alteradas.items():
                pg = copia[i]
                self._pintar(pg.load_annot(xref), cor)
            for i, rets, cor in self._destaques_novos.values():
                self._aplicar_destaque(copia[i], rets, cor)
            for i, r in rotacoes.items():
                pg = copia[i]
                pg.set_rotation((pg.rotation + r) % 360)
            return copia.tobytes()
        finally:
            copia.close()

    def fechar(self):
        try:
            self.doc.close()
        except Exception:
            pass
