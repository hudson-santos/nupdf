"""Edição do conteúdo do PDF (Editor de PDF e Editor de Metadados).

Cada função recebe um pymupdf.Document (a CÓPIA do documento como está na tela -
ver Documento.com_edicao) e o altera no lugar. As coordenadas são as do resto do
NuPDF: espaço da página NÃO rotacionado (o mesmo das palavras e dos destaques).

Remoção usa "redaction" do MuPDF: o texto/imagem/desenho sob a área sai de fato do
arquivo (não é só coberto). Texto incluído usa Helvetica (fonte padrão do PDF, com
os acentos do português).
"""

import datetime

import pymupdf

# cores do texto incluído: chave -> (rótulo, RGB 0-1)
CORES_TEXTO = {
    "preto": ("Preto", (0, 0, 0)),
    "azul": ("Azul", (0.05, 0.25, 0.65)),
    "vermelho": ("Vermelho", (0.78, 0.1, 0.1)),
    "cinza": ("Cinza", (0.4, 0.4, 0.4)),
}

CAMPOS_METADADOS = (  # chave do PyMuPDF, rótulo
    ("title", "Título"),
    ("author", "Autor"),
    ("subject", "Assunto"),
    ("keywords", "Palavras-chave"),
    ("creator", "Aplicativo de Origem"),
    ("producer", "Produtor do PDF"),
)


def _encolher(r: pymupdf.Rect) -> pymupdf.Rect:
    """Área de texto um pouco menor na vertical: a redaction remove todo caractere que
    toca a área - sem isso, linhas vizinhas muito juntas perdiam letras."""
    r = pymupdf.Rect(r)
    folga = r.height * 0.18
    return pymupdf.Rect(r.x0 + 0.3, r.y0 + folga, r.x1 - 0.3, r.y1 - folga)


def _aplicar_redacoes(pg: pymupdf.Page, so_texto: bool):
    if so_texto:  # trocar/remover texto: imagens e linhas (tabelas, sublinhados) ficam
        pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    else:  # remover área: tudo o que estiver dentro sai (imagens só nos pixels cobertos)
        pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)


def remover_area(doc: pymupdf.Document, i: int, area: pymupdf.Rect):
    """Apaga tudo dentro da área (texto, imagens, desenhos) - fica fundo branco."""
    pg = doc[i]
    pg.add_redact_annot(pymupdf.Rect(area), fill=(1, 1, 1))
    _aplicar_redacoes(pg, so_texto=False)


def remover_texto(doc: pymupdf.Document, i: int, rets: list[pymupdf.Rect]):
    """Remove o texto sob os retângulos (um por linha), mantendo o fundo da página."""
    pg = doc[i]
    for r in rets:
        pg.add_redact_annot(_encolher(r), fill=False)
    _aplicar_redacoes(pg, so_texto=True)


def estilo_em(pg: pymupdf.Page, r: pymupdf.Rect) -> dict:
    """Tamanho, cor, negrito e origem (início da linha de base) do texto sob r - o
    trecho que mais se sobrepõe -, para o texto novo ficar parecido com o que substitui."""
    r = pymupdf.Rect(r)
    melhor, area = None, 0.0
    for bloco in pg.get_text("dict", clip=r + (-2, -2, 2, 2))["blocks"]:
        for linha in bloco.get("lines", []):
            for span in linha["spans"]:
                inter = pymupdf.Rect(span["bbox"]) & r
                if not inter.is_empty and inter.get_area() > area:
                    melhor, area = span, inter.get_area()
    if melhor is None:
        # sem trecho de texto: linha de base estimada no retângulo, no sentido da tela
        rd = (r * pg.rotation_matrix).normalize()
        origem = pymupdf.Point(rd.x0, rd.y1 - rd.height * 0.22) * pg.derotation_matrix
        return {"tamanho": max(4.0, round(rd.height / 1.25, 1)), "cor": (0, 0, 0), "negrito": False,
                "origem": origem}
    c = melhor["color"]
    cor = ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)
    negrito = bool(melhor["flags"] & 16) or "bold" in melhor["font"].lower()
    origem = pymupdf.Point(melhor["origin"])
    # o trecho pode começar antes do retângulo (palavra no meio da linha): começa no retângulo
    tela, rd = origem * pg.rotation_matrix, (r * pg.rotation_matrix).normalize()
    origem = pymupdf.Point(max(tela.x, rd.x0), tela.y) * pg.derotation_matrix
    return {"tamanho": round(melhor["size"], 1), "cor": cor, "negrito": negrito, "origem": origem}


def _escrever(pg: pymupdf.Page, origem: pymupdf.Point, linhas: list[str], tamanho: float,
              cor, negrito: bool):
    """Escreve as linhas a partir de `origem` (início da linha de base da 1ª linha, no
    espaço não rotacionado), de pé para quem lê: em página girada (/Rotate) o texto e o
    avanço das linhas seguem a rotação."""
    fonte = "hebo" if negrito else "helv"
    tela = pymupdf.Point(origem) * pg.rotation_matrix  # na tela, as linhas descem em y
    for n, linha in enumerate(linhas):
        if not linha:
            continue
        ponto = pymupdf.Point(tela.x, tela.y + n * tamanho * 1.2) * pg.derotation_matrix
        pg.insert_text(ponto, linha, fontname=fonte, fontsize=tamanho, color=cor, rotate=pg.rotation)


def _linhas(texto: str) -> list[str]:
    return texto.replace("\r\n", "\n").split("\n")


def inserir_texto(doc: pymupdf.Document, i: int, ponto: pymupdf.Point, texto: str, tamanho: float,
                  cor=(0, 0, 0), negrito: bool = False):
    """Texto novo com o canto superior esquerdo (na tela) em `ponto`; cada quebra de
    linha do texto é uma linha."""
    pg = doc[i]
    tela = pymupdf.Point(ponto) * pg.rotation_matrix
    origem = pymupdf.Point(tela.x, tela.y + tamanho * 0.8) * pg.derotation_matrix
    _escrever(pg, origem, _linhas(texto), tamanho, cor, negrito)


def substituir_texto(doc: pymupdf.Document, i: int, rets: list[pymupdf.Rect], novo: str):
    """Troca o texto sob os retângulos (linhas da seleção) por `novo`, no lugar e no
    estilo (tamanho, cor, negrito) do texto original."""
    rets = [pymupdf.Rect(r) for r in rets]
    estilo = estilo_em(doc[i], rets[0])
    remover_texto(doc, i, rets)
    _escrever(doc[i], estilo["origem"], _linhas(novo), estilo["tamanho"], estilo["cor"], estilo["negrito"])


def substituir_todos(doc: pymupdf.Document, busca: str, novo: str) -> int:
    """Localizar e substituir em todas as páginas. Devolve quantas ocorrências trocou."""
    total = 0
    for i in range(doc.page_count):
        pg = doc[i]
        achados = pg.search_for(busca)
        if not achados:
            continue
        estilos = [estilo_em(pg, r) for r in achados]
        for r in achados:
            pg.add_redact_annot(_encolher(r), fill=False)
        _aplicar_redacoes(pg, so_texto=True)
        if novo:
            for est in estilos:
                _escrever(pg, est["origem"], [novo], est["tamanho"], est["cor"], est["negrito"])
        total += len(achados)
    return total


def alterar_metadados(doc: pymupdf.Document, valores: dict[str, str]):
    """Grava título, autor etc. (dicionário Info) e a data de modificação. O XMP antigo
    sai: outros leitores dão preferência a ele e mostrariam os valores antigos."""
    meta = dict(doc.metadata or {})
    for chave, _ in CAMPOS_METADADOS:
        if chave in valores:
            meta[chave] = (valores[chave] or "").strip()
    agora = datetime.datetime.now().astimezone()
    fuso = agora.strftime("%z")
    meta["modDate"] = agora.strftime("D:%Y%m%d%H%M%S") + (f"{fuso[:3]}'{fuso[3:]}'" if fuso else "")
    meta = {k: v for k, v in meta.items() if k not in ("format", "encryption")}
    doc.set_metadata(meta)
    try:
        doc.del_xml_metadata()
    except Exception:
        pass
