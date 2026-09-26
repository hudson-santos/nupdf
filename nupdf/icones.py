"""Ícones vetoriais (traço fino, estilo Lucide) coloridos conforme o tema."""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG = {
    "abrir": '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "imprimir": '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
    "salvar": '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    "zoom_mais": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/>',
    "zoom_menos": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M8 11h6"/>',
    "buscar": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "largura": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 12h10M9 10l-2 2 2 2M15 10l2 2-2 2"/>',
    "pagina": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    "girar": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    "cursor": '<path d="M17 22h-1a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4h1"/><path d="M7 22h1a4 4 0 0 0 4-4v-1"/><path d="M7 2h1a4 4 0 0 1 4 4v1"/>',
    "mao": '<path d="M18 11V6a2 2 0 0 0-4 0"/><path d="M14 10V4a2 2 0 0 0-4 0v2"/><path d="M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',
    "assinar": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "miniaturas": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    "dados": '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4M12 16h4M8 11h.01M8 16h.01"/>',
    "escudo": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "escudo_alerta": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4M12 16h.01"/>',
    "escudo_x": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m14.5 9.5-5 5M9.5 9.5l5 5"/>',
    "recentes": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "copiar": '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "atualizar": '<path d="M12 13v8"/><path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2"/><path d="m8 17 4 4 4-4"/>',
    "lixeira": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6M14 11v6"/>',
    "fechar": '<path d="M18 6 6 18M6 6l12 12"/>',
    "primeira": '<path d="m17 18-6-6 6-6"/><path d="M7 6v12"/>',
    "anterior": '<path d="m15 18-6-6 6-6"/>',
    "proxima": '<path d="m9 18 6-6-6-6"/>',
    "ultima": '<path d="m7 18 6-6-6-6"/><path d="M17 6v12"/>',
    "acima": '<path d="m18 15-6-6-6 6"/>',
    "abaixo": '<path d="m6 9 6 6 6-6"/>',
    "sol": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    "lua": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "arquivo": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8M16 17H8M10 9H8"/>',
    "mais": '<path d="M12 5v14M5 12h14"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "chave": '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
    "token": '<rect x="2" y="7" width="15" height="10" rx="2"/><path d="M17 10h3a2 2 0 0 1 2 2v0a2 2 0 0 1-2 2h-3"/><path d="M6 12h5"/>',
}

_LOGO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<defs>
<linearGradient id="f" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#F2656A"/><stop offset="1" stop-color="#D93A40"/>
</linearGradient>
</defs>
<rect x="3" y="3" width="58" height="58" rx="15" fill="url(#f)"/>
<path d="M21 13h15.5L46 22.5V47a4 4 0 0 1-4 4H21a4 4 0 0 1-4-4V17a4 4 0 0 1 4-4z" fill="#FFFFFF"/>
<path d="M36.5 13v6.5a3 3 0 0 0 3 3H46z" fill="#FBC6C8"/>
<path d="M23 25h9M23 31h16" stroke="#F4B3B6" stroke-width="2.6" stroke-linecap="round"/>
<path d="M22.5 43c2.2-4.6 4.4-6.4 5.6-4.9 1.1 1.4-1.4 5.6.4 5.8 1.7.2 3.3-4.6 5-4.2 1.3.3.4 3.1 1.8 3.2 1.2.1 2.4-1.3 4.2-1.6"
 fill="none" stroke="#E5484D" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

_cache: dict = {}


def _render(svg: bytes, tamanho: int, escala: int = 2) -> QPixmap:
    ren = QSvgRenderer(QByteArray(svg))
    pix = QPixmap(tamanho * escala, tamanho * escala)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    ren.render(p, QRectF(0, 0, tamanho * escala, tamanho * escala))
    p.end()
    pix.setDevicePixelRatio(escala)
    return pix


def icone(nome: str, cor: str, tamanho: int = 20) -> QIcon:
    chave = (nome, cor, tamanho)
    if chave not in _cache:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{cor}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f"{_SVG[nome]}</svg>"
        ).encode()
        _cache[chave] = QIcon(_render(svg, tamanho))
    return _cache[chave]


def pixmap_logo(tamanho: int = 64) -> QPixmap:
    return _render(_LOGO.encode(), tamanho)


def icone_app() -> QIcon:
    ic = QIcon()
    for t in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(_render(_LOGO.encode(), t, 1))
    return ic
