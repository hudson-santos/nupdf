"""Detecção de dados copiáveis no texto do PDF (CPF, CNPJ, datas, valores...)."""

import re
from dataclasses import dataclass

from .documento import Documento

MAX_PAGINAS = 300


@dataclass
class Dado:
    categoria: str
    rotulo: str   # texto exibido à esquerda (ex.: "Proprietário" ou o próprio valor)
    valor: str    # o que vai para a área de transferência
    pagina: int


def _dv_cpf_ok(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def _dv_cnpj_ok(c: str) -> bool:
    # Suporta o CNPJ alfanumérico (valor do caractere = ord - 48).
    if len(c) != 14 or not c[12:].isdigit() or c == c[0] * 14:
        return False
    v = [ord(ch) - 48 for ch in c]
    for n in (12, 13):
        pesos = list(range(n - 7, 1, -1)) + list(range(9, 1, -1))
        s = sum(v[i] * pesos[i] for i in range(n))
        dv = 0 if s % 11 < 2 else 11 - s % 11
        if dv != v[n]:
            return False
    return True


_PADROES = [
    ("CNPJ", re.compile(r"\b[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}\b"),
     lambda s: _dv_cnpj_ok(re.sub(r"[./-]", "", s))),
    ("CPF", re.compile(r"(?<![\d.])\d{3}\.\d{3}\.\d{3}-\d{2}(?![\d])"),
     lambda s: _dv_cpf_ok(re.sub(r"\D", "", s))),
    ("Chave de acesso (NF-e/CT-e)", re.compile(r"(?<!\d)(?:\d{4}[ .]?){10}\d{4}(?!\d)"),
     lambda s: len(re.sub(r"\D", "", s)) == 44),
    ("Linha digitável", re.compile(
        r"(?<!\d)\d{5}\.?\d{5}\s?\d{5}\.?\d{6}\s?\d{5}\.?\d{6}\s?\d\s?\d{14}(?!\d)"
        r"|(?<!\d)\d{11}-?\d\s?\d{11}-?\d\s?\d{11}-?\d\s?\d{11}-?\d(?!\d)"), None),
    ("Valores", re.compile(r"R\$\s?-?\d{1,3}(?:\.\d{3})*,\d{2}"), None),
    ("Datas", re.compile(r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}(?!\d)"), None),
    ("E-mails", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), None),
    ("Telefones", re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-\d{4}\b"), None),
    ("CEP", re.compile(r"(?<![\d.])\d{2}\.?\d{3}-\d{3}(?![\d])"), None),
]

ORDEM_CATEGORIAS = ["Campos"] + [p[0] for p in _PADROES]


def _campos_da_linha(linha, pagina: int) -> list[Dado]:
    """Divide uma linha visual em segmentos (por espaços grandes) e extrai pares
    'Rótulo: valor'. Ex.: 'Proprietário:  HUGO STRELOW JUNIOR'."""
    if not linha:
        return []
    segmentos, atual = [], [linha[0]]
    for ant, w in zip(linha, linha[1:]):
        altura = max(ant[3] - ant[1], w[3] - w[1], 1)
        if w[0] - ant[2] > 0.6 * altura:
            segmentos.append(atual)
            atual = []
        atual.append(w)
    segmentos.append(atual)

    dados, rotulo_pendente = [], None
    for seg in segmentos:
        palavras = [w[4] for w in seg]
        idx = next((k for k, p in enumerate(palavras) if p.endswith(":") and len(p) > 1), None)
        if idx is None:
            if rotulo_pendente:
                dados.append(Dado("Campos", rotulo_pendente, " ".join(palavras), pagina))
                rotulo_pendente = None
            continue
        rotulo = " ".join(palavras[: idx + 1])[:-1].strip()
        valor = " ".join(palavras[idx + 1:]).strip()
        if len(rotulo) > 40 or len(rotulo.split()) > 5:
            rotulo_pendente = None
            continue
        if valor:
            dados.append(Dado("Campos", rotulo, valor, pagina))
            rotulo_pendente = None
        else:
            rotulo_pendente = rotulo
    return dados


def extrair(doc: Documento) -> list[Dado]:
    vistos: set = set()
    saida: list[Dado] = []

    def add(d: Dado):
        chave = (d.categoria, d.rotulo, d.valor)
        if chave not in vistos:
            vistos.add(chave)
            saida.append(d)

    for i in range(min(doc.n_paginas, MAX_PAGINAS)):
        for linha in doc.linhas(i):
            for d in _campos_da_linha(linha, i):
                add(d)
        texto = doc.texto_pagina(i)
        for categoria, regex, validar in _PADROES:
            for m in regex.finditer(texto):
                valor = m.group(0).strip()
                if validar and not validar(valor):
                    continue
                add(Dado(categoria, valor, valor, i))
    return saida
