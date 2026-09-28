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

COR_DESTAQUE = (1.0, 0.92, 0.23)  # amarelo marca-texto


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
    def __init__(self, caminho: str, senha: str | None = None):
        self.caminho = Path(caminho)
        self.dados = self.caminho.read_bytes()
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
        # destaques (marca-texto) feitos nesta sessão: página -> retângulos das linhas.
        # Ficam no documento exibido e são regravados numa cópia só ao salvar/imprimir.
        self.destaques: dict[int, list[pymupdf.Rect]] = {}

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
    def _aplicar_destaque(pg: pymupdf.Page, rets: list[pymupdf.Rect]):
        # mesmo sistema de coordenadas das palavras (vale também em página com /Rotate)
        annot = pg.add_highlight_annot(quads=[pymupdf.Rect(r).quad for r in rets])
        annot.set_colors(stroke=COR_DESTAQUE)
        annot.update()

    def destacar(self, i: int, rets: list[pymupdf.Rect]):
        """Marca-texto amarelo sobre os retângulos (um por linha) da página i."""
        if not rets:
            return
        self._aplicar_destaque(self.doc[i], rets)
        self.destaques.setdefault(i, []).extend(pymupdf.Rect(r) for r in rets)

    def bytes_editados(self, rotacoes: dict[int, int]) -> bytes:
        """PDF como está na tela: rotação da visualização gravada nas páginas
        (/Rotate) e destaques feitos nesta sessão. Sem nenhuma alteração, devolve
        os bytes originais intactos (preserva assinaturas)."""
        rotacoes = {i: r % 360 for i, r in rotacoes.items() if r % 360}
        if not rotacoes and not self.destaques:
            return self.dados
        copia = pymupdf.open(stream=self.dados, filetype="pdf")
        try:
            if copia.needs_pass:
                copia.authenticate(self.senha or "")
            for i, rets in self.destaques.items():
                self._aplicar_destaque(copia[i], rets)
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
