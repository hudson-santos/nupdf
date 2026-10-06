"""Fonte do texto incluído/alterado pelo Editor de PDF: a mesma do documento.

Ordem de escolha para o texto novo (família e estilo do trecho original):
  1. a fonte EMBUTIDA no próprio PDF, se tiver todos os caracteres do texto novo -
     fica idêntica (a maioria dos PDFs embute só um subconjunto: as letras usadas);
  2. a fonte instalada no Windows com o mesmo nome (Arial, Calibri, Times New Roman...);
     Helvetica/Times/Courier (padrão do PDF) usam as fontes internas equivalentes;
  3. baixa e instala a fonte (só para o usuário, sem administrador) do catálogo
     Fontsource (fontes livres do Google Fonts), quando ela existir lá;
  4. Helvetica (fonte padrão do PDF).
"""

import json
import os
import re
import urllib.request
from pathlib import Path

import pymupdf

# PDF base-14 -> fontes internas do PyMuPDF (normal, negrito, itálico, negrito itálico)
_BASE14 = {
    "helvetica": ("helv", "hebo", "heit", "hebi"),
    "arial": None,  # Arial existe no Windows (preferível: métricas idênticas às do PDF)
    "times": ("tiro", "tibo", "tiit", "tibi"),
    "timesroman": ("tiro", "tibo", "tiit", "tibi"),
    "courier": ("cour", "cobo", "coit", "cobi"),
}
_SUFIXOS = ("psmt", "mt", "ps")  # TimesNewRomanPSMT, ArialMT (só um deles é removido)
_DIR_USUARIO = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
_URL_CATALOGO = "https://api.fontsource.org/v1/fonts/{id}"
_URL_ARQUIVO = "https://cdn.jsdelivr.net/fontsource/fonts/{id}@latest/latin-{peso}-{estilo}.ttf"
TIMEOUT = 10


def _abrir(url: str):
    # sem User-Agent o catálogo da Fontsource responde 403
    from .versao import VERSAO
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": f"NuPDF/{VERSAO}"}),
                                  timeout=TIMEOUT)


def _simples(nome: str) -> str:
    return re.sub(r"[^a-z0-9]", "", nome.lower())


def familia_e_estilo(nome_pdf: str, flags: int = 0) -> tuple[str, bool, bool]:
    """'ABCDEF+Arial-BoldItalicMT' -> ('arial', negrito, itálico). Também usa os flags
    do trecho (negrito = 16, itálico = 2)."""
    nome = nome_pdf.split("+", 1)[-1]
    partes = re.split(r"[-,]", nome, maxsplit=1)
    familia, estilo = partes[0], (partes[1] if len(partes) > 1 else "")
    baixo = (nome + " " + estilo).lower()
    negrito = bool(flags & 16) or any(p in baixo for p in ("bold", "black", "heavy", "semibold", "demi"))
    italico = bool(flags & 2) or "italic" in baixo or "oblique" in baixo
    fam = _simples(familia)
    for s in _SUFIXOS:
        if fam.endswith(s) and len(fam) > len(s) + 2:
            fam = fam[: -len(s)]
            break
    # "CalibriBold", "ArialBold" (sem hífen)
    for s in ("bolditalic", "boldoblique", "bold", "italic", "oblique", "regular"):
        if fam.endswith(s) and len(fam) > len(s) + 2:
            fam = fam[: -len(s)]
    return fam, negrito, italico


_ESTILOS = r"(Bold|Italic|Oblique|Regular|Light|Medium|SemiBold|Semibold|DemiBold|ExtraBold|Black|Heavy|Thin|MT|PSMT|PS)"


def nome_familia(nome_pdf: str) -> str:
    """'ABCDEF+OpenSans-SemiBold' / 'Roboto Bold' -> 'Open Sans' / 'Roboto' (para o catálogo
    e para mostrar ao usuário)."""
    nome = nome_pdf.split("+", 1)[-1].split(",")[0]
    nome = nome.split("-")[0]
    nome = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", nome)  # OpenSans -> Open Sans
    palavras = [p for p in nome.split() if not re.fullmatch(_ESTILOS, p)]
    return " ".join(palavras) or nome.strip()


# ---------------------------------------------------------------- fontes do Windows
_indice: dict[str, str] | None = None


def _indice_windows() -> dict[str, str]:
    """'arialbold' -> caminho do arquivo, pelo registro (HKLM e HKCU) - rápido, sem abrir
    os arquivos de fonte."""
    global _indice
    if _indice is not None:
        return _indice
    _indice = {}
    try:
        import winreg
    except ImportError:
        return _indice
    pasta_win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for raiz in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            k = winreg.OpenKey(raiz, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        except OSError:
            continue
        with k:
            for i in range(winreg.QueryInfoKey(k)[1]):
                try:
                    nome, arquivo, _ = winreg.EnumValue(k, i)
                except OSError:
                    continue
                if not str(arquivo).lower().endswith((".ttf", ".otf")):
                    continue  # .ttc (coleções) e fontes bitmap ficam de fora
                caminho = Path(arquivo) if os.path.isabs(arquivo) else pasta_win / arquivo
                nome = re.sub(r"\((truetype|opentype)\)", "", nome, flags=re.I)
                _indice.setdefault(_simples(nome), str(caminho))
    return _indice


def _chaves(fam: str, negrito: bool, italico: bool) -> list[str]:
    estilo = ("bold" if negrito else "") + ("italic" if italico else "")
    if estilo:
        return [fam + estilo, fam + estilo.replace("italic", "oblique")]
    return [fam, fam + "regular"]


def fonte_windows(fam: str, negrito: bool, italico: bool) -> str | None:
    indice = _indice_windows()
    for chave in _chaves(fam, negrito, italico):
        if chave in indice and os.path.isfile(indice[chave]):
            return indice[chave]
    return None


# ---------------------------------------------------------------- download (Fontsource)
def baixar_e_instalar(fam_nome: str, negrito: bool, italico: bool) -> str | None:
    """Baixa a fonte livre do catálogo Fontsource e instala só para o usuário
    (%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts + registro HKCU, sem administrador).
    Devolve o caminho do arquivo, ou None se a fonte não existir no catálogo."""
    ident = re.sub(r"[^a-z0-9]+", "-", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", fam_nome).lower()).strip("-")
    if not ident:
        return None
    try:
        with _abrir(_URL_CATALOGO.format(id=ident)) as r:
            info = json.load(r)
    except Exception:
        return None
    pesos = info.get("weights") or [400]
    peso = 700 if negrito and 700 in pesos else (400 if 400 in pesos else pesos[0])
    estilo = "italic" if italico and "italic" in (info.get("styles") or []) else "normal"
    familia = info.get("family") or fam_nome
    nome_arq = f"{_simples(familia)}-{peso}-{estilo}.ttf"
    destino = _DIR_USUARIO / nome_arq
    try:
        # já baixada antes (o arquivo fica em uso pelo Windows depois de instalada): reaproveita
        if not (destino.is_file() and destino.stat().st_size > 0):
            with _abrir(_URL_ARQUIVO.format(id=ident, peso=peso, estilo=estilo)) as r:
                dados = r.read()
            if not dados.startswith((b"\x00\x01\x00\x00", b"OTTO", b"true")):
                return None
            _DIR_USUARIO.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(dados)
        rotulo = familia + (" Bold" if peso >= 700 else "") + (" Italic" if estilo == "italic" else "")
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as k:
            winreg.SetValueEx(k, f"{rotulo} (TrueType)", 0, winreg.REG_SZ, str(destino))
        try:  # avisa os programas abertos que há fonte nova
            import ctypes
            ctypes.windll.gdi32.AddFontResourceW(str(destino))
            ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 0x0002, 1000, None)
        except Exception:
            pass
    except Exception:
        return None
    global _indice
    _indice = None  # a fonte nova entra no índice na próxima busca
    return str(destino)


# ---------------------------------------------------------------- escolha
def _fonte_embutida(doc: pymupdf.Document, pg: pymupdf.Page, nome_pdf: str, texto: str):
    """Buffer da fonte embutida no PDF com esse nome, se tiver todos os caracteres."""
    alvo = nome_pdf.split("+", 1)[-1]  # o texto traz o nome sem o prefixo de subconjunto
    for xref, ext, tipo, base, _ref, _enc in pg.get_fonts(full=False):
        if base.split("+", 1)[-1] != alvo or ext in ("n/a", "") or tipo == "Type3":
            continue
        try:
            buffer = doc.extract_font(xref)[3]
            if not buffer:
                continue
            f = pymupdf.Font(fontbuffer=buffer)
            if all(f.has_glyph(ord(c)) for c in set(texto) if not c.isspace()):
                return buffer
        except Exception:
            continue
    return None


def escolher(doc: pymupdf.Document, pg: pymupdf.Page, nome_pdf: str | None, flags: int, texto: str,
             negrito: bool | None = None, baixar: bool = True) -> dict:
    """Parâmetros de fonte para page.insert_text: {"fontname": ..., e "fontfile" ou
    "fontbuffer"} + "origem" (embutida/windows/baixada/padrao) para o aviso na tela."""
    if not nome_pdf:
        return {"fontname": "hebo" if negrito else "helv", "origem": "padrao"}
    fam, neg, ita = familia_e_estilo(nome_pdf, flags)
    if negrito is not None:
        neg = negrito
    # 1) a própria fonte do PDF (estilo do trecho original, sem forçar negrito)
    if negrito is None or negrito == familia_e_estilo(nome_pdf, flags)[1]:
        buffer = _fonte_embutida(doc, pg, nome_pdf, texto)
        if buffer:
            return {"fontname": "NE" + _simples(nome_pdf)[:20], "fontbuffer": buffer, "origem": "embutida"}
    # 2) fontes padrão do PDF / instaladas no Windows
    if _BASE14.get(fam):
        return {"fontname": _BASE14[fam][(1 if neg else 0) + (2 if ita else 0)], "origem": "padrao"}
    caminho = fonte_windows(fam, neg, ita) or (fonte_windows(fam, neg, False) if ita else None)
    if caminho:
        return {"fontname": "NW" + Path(caminho).stem[:20], "fontfile": caminho, "origem": "windows"}
    # 3) baixa e instala
    if baixar:
        caminho = baixar_e_instalar(nome_familia(nome_pdf), neg, ita)
        if caminho:
            return {"fontname": "NB" + Path(caminho).stem[:20], "fontfile": caminho, "origem": "baixada"}
    # 4) Helvetica
    return {"fontname": _BASE14["helvetica"][(1 if neg else 0) + (2 if ita else 0)], "origem": "padrao"}


def fonte_predominante(pg: pymupdf.Page) -> tuple[str | None, int]:
    """Fonte com mais caracteres na página (nome no PDF, flags) - para Inserir Texto."""
    contagem: dict[tuple[str, int], int] = {}
    for bloco in pg.get_text("dict")["blocks"]:
        for linha in bloco.get("lines", []):
            for span in linha["spans"]:
                chave = (span["font"], span["flags"] & ~16 & ~2)  # estilo vem do diálogo
                contagem[chave] = contagem.get(chave, 0) + len(span["text"].strip())
    if not contagem:
        return None, 0
    return max(contagem, key=contagem.get)


def familias_do_documento(doc: pymupdf.Document, limite_paginas: int = 30) -> list[str]:
    """Nomes de fonte (sem o prefixo de subconjunto) usados no texto do documento."""
    nomes: dict[str, int] = {}
    for i in range(min(doc.page_count, limite_paginas)):
        for bloco in doc[i].get_text("dict")["blocks"]:
            for linha in bloco.get("lines", []):
                for span in linha["spans"]:
                    nomes[span["font"]] = nomes.get(span["font"], 0) + len(span["text"])
    return sorted(nomes, key=nomes.get, reverse=True)
