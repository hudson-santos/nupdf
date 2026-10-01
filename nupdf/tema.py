"""Paletas claro/escuro, fonte e folha de estilo (QSS) do NuPDF."""

from pathlib import Path
from string import Template

FONTE = "Google Sans"
_PASTA_FONTES = Path(__file__).resolve().parents[1] / "assets" / "fonts"
_fontes_carregadas = False


def carregar_fontes():
    """Registra a Google Sans embutida em assets/fonts (licença OFL) - assim o
    app fica igual em máquinas que não têm a fonte instalada. Sem o arquivo,
    o QSS cai para Segoe UI."""
    global _fontes_carregadas
    if _fontes_carregadas:
        return
    _fontes_carregadas = True
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    for arq in _PASTA_FONTES.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(arq))
    if FONTE in QFontDatabase.families():
        fonte = QFont(FONTE, 10)
        fonte.setHintingPreference(QFont.PreferNoHinting)
        QApplication.setFont(fonte)

ESCURO = {
    "janela": "#17181b",
    "barra": "#1f2023",
    "superficie": "#26272b",
    "superficie2": "#303136",
    "hover": "#34363b",
    "borda": "#34363b",
    "canvas": "#2b2c31",
    "rolagem": "#5c5f67",        # alça da barra de rolagem (visível sobre o canvas)
    "rolagem_hover": "#80838c",
    "texto": "#e7e7ea",
    "texto2": "#a1a3aa",
    "texto3": "#6f727a",
    "destaque": "#e5484d",
    "destaque_hover": "#ec5d61",
    "destaque_suave": "#3b2023",
    "ok": "#3fb950",
    "aviso": "#d29922",
    "erro": "#f85149",
    "selecao": "#3b82f6",
    "sombra": "#000000",
}

CLARO = {
    "janela": "#f4f4f6",
    "barra": "#ffffff",
    "superficie": "#ffffff",
    "superficie2": "#f1f1f4",
    "hover": "#ebebef",
    "borda": "#e3e3e8",
    "canvas": "#e8e8ec",
    "rolagem": "#a6a9b1",        # alça da barra de rolagem (visível sobre o canvas)
    "rolagem_hover": "#878b94",
    "texto": "#1d1f24",
    "texto2": "#5d6068",
    "texto3": "#9a9ca3",
    "destaque": "#e5484d",
    "destaque_hover": "#d63e43",
    "destaque_suave": "#fde8e9",
    "ok": "#1a7f37",
    "aviso": "#9a6700",
    "erro": "#cf222e",
    "selecao": "#2563eb",
    "sombra": "#6b7280",
}

_QSS = Template("""
* { font-family: "Google Sans", "Segoe UI", sans-serif; font-size: 13px; color: $texto; }
QMainWindow, QDialog { background: $janela; }
QToolTip { background: $superficie2; color: $texto; border: 1px solid $borda; padding: 4px 8px; border-radius: 6px; }

#topo { background: $barra; border-bottom: 1px solid $borda; }
#ferramentas { background: $barra; border-bottom: 1px solid $borda; }
#sep { background: $borda; }
#logoTexto { font-size: 16px; font-weight: 700; }
#logoTexto[destaque="true"] { color: $destaque; }

QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: $texto2; padding: 7px 10px 7px 14px; margin: 0 2px;
               border-top-left-radius: 8px; border-top-right-radius: 8px; min-width: 60px; max-width: 240px; }
QTabBar::tab:selected { background: $janela; color: $texto; }
QTabBar::tab:hover:!selected { background: $superficie2; }

QToolButton { background: transparent; border: none; border-radius: 8px; padding: 6px; }
QToolButton:hover { background: $hover; }
QToolButton:pressed, QToolButton:checked { background: $superficie2; }
QToolButton#trilho:checked { background: $destaque_suave; }
QToolButton#comMenu::menu-indicator { image: none; width: 0; }
QToolButton#abaFechar { padding: 2px; border-radius: 5px; }

QPushButton { background: $superficie2; border: 1px solid $borda; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: $hover; }
QPushButton:disabled { color: $texto3; }
QPushButton#fechar { background: #4b4d53; border: 1px solid #4b4d53; color: #ffffff; font-weight: 600; }
QPushButton#fechar:hover { background: #5b5d64; }
QPushButton#perigo { background: #c62828; border: 1px solid #c62828; color: #ffffff; font-weight: 600; }
QPushButton#perigo:hover { background: #b71c1c; }
QPushButton#primario { background: $destaque; border: 1px solid $destaque; color: #ffffff; font-weight: 600; }
QPushButton#primario:hover { background: $destaque_hover; }
QPushButton#primario:disabled { background: $superficie2; border-color: $borda; color: $texto3; }
QPushButton#avisoPadrao { background: $destaque_suave; border: none; border-radius: 12px; color: $destaque;
    font-size: 12px; font-weight: 600; padding: 4px 12px; margin-right: 6px; min-height: 16px; }
QPushButton#avisoPadrao:hover { background: $destaque; color: #ffffff; }
QPushButton#link { background: transparent; border: none; color: $texto2; text-align: left; padding: 6px 8px; }
QPushButton#link:hover { background: $hover; color: $texto; }
#linhaRecente { border-radius: 8px; }
#linhaRecente:hover { background: $hover; }
#linhaRecente QPushButton#link:hover { background: transparent; }
QPushButton#linkCartao { background: transparent; border: none; color: $destaque; font-weight: 600; padding: 4px 0; }
QPushButton#linkCartao:hover { text-decoration: underline; }
QPushButton#linkPequeno { background: transparent; border: none; color: $texto3; font-size: 12px; padding: 2px 6px; }
QPushButton#linkPequeno:hover { color: $destaque; }

QLineEdit, QComboBox, QSpinBox { background: $superficie; border: 1px solid $borda; border-radius: 7px;
                                 padding: 6px 8px; }
/* azul só para texto selecionado em campos de digitação; listas usam o cinza do tema */
QLineEdit, QSpinBox { selection-background-color: $selecao; }
QComboBox { selection-background-color: $hover; selection-color: $texto;
            combobox-popup: 0; }  /* lista abre abaixo do campo, com rolagem (maxVisibleItems) */
QLineEdit:focus, QComboBox:focus { border: 1px solid $destaque; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: $superficie; border: 1px solid $borda;
                              selection-background-color: $hover; selection-color: $texto; outline: none; }
QComboBox QAbstractItemView::item { padding: 6px 8px; }
QComboBox QAbstractItemView::item:selected, QComboBox QAbstractItemView::item:hover { background: $hover; color: $texto; }

QCheckBox, QRadioButton { spacing: 8px; }
/* tamanho total 18px (conteúdo + borda) nos dois estados, para ficarem redondos */
QRadioButton::indicator { width: 14px; height: 14px; border: 2px solid $texto3; border-radius: 9px;
                          background: $superficie; }
QRadioButton::indicator:hover { border-color: $destaque; }
QRadioButton::indicator:checked { width: 8px; height: 8px; border: 5px solid $destaque; background: #ffffff; }
QCheckBox::indicator { width: 14px; height: 14px; border: 2px solid $texto3; border-radius: 4px;
                       background: $superficie; }
QCheckBox::indicator:hover { border-color: $destaque; }
QCheckBox::indicator:checked { border-color: $destaque; background: $destaque; image: url($check); }
QGroupBox { border: 1px solid $borda; border-radius: 10px; margin-top: 14px; padding: 12px 10px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: $texto2; }

#trilhoLateral { background: $barra; border-right: 1px solid $borda; }
#painelLateral { background: $barra; border-right: 1px solid $borda; }
#tituloPainel { font-size: 12px; font-weight: 700; color: $texto2; letter-spacing: 0.5px; }

QListWidget, QTreeWidget { background: transparent; border: none; outline: none; }
QListWidget::item, QTreeWidget::item { border-radius: 6px; padding: 4px; }
QListWidget::item:hover, QTreeWidget::item:hover { background: $hover; }
QListWidget::item:selected, QTreeWidget::item:selected { background: $destaque_suave; color: $texto; }
QTreeWidget::branch { background: transparent; }
QHeaderView::section { background: transparent; border: none; color: $texto2; padding: 4px; }

QScrollArea { background: $canvas; border: none; }
QScrollBar:vertical { background: transparent; width: 14px; margin: 2px; }
QScrollBar::handle:vertical { background: $rolagem; border-radius: 5px; min-height: 48px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:vertical:pressed { background: $rolagem_hover; }
QScrollBar:horizontal { background: transparent; height: 14px; margin: 2px; }
QScrollBar::handle:horizontal { background: $rolagem; border-radius: 5px; min-width: 48px; }
QScrollBar::handle:horizontal:hover, QScrollBar::handle:horizontal:pressed { background: $rolagem_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

#flutuante { background: $superficie; border: 1px solid $borda; border-radius: 12px; }
#flutuante QLineEdit { background: $superficie2; border: none; }
#botaoCopiar { background: #202124; color: #ffffff; border: none; border-radius: 8px;
               padding: 6px 12px; font-weight: 600; }
#botaoCopiar:hover { background: #33353a; }
#aviso { background: $destaque; color: #ffffff; border-radius: 10px; padding: 8px 14px; font-weight: 600; }
#toast { background: $superficie2; color: $texto; border: 1px solid $borda; border-radius: 10px; padding: 8px 14px; }

#inicio { background: $janela; }
#cartaoInicio { background: $superficie; border: 1px solid $borda; border-radius: 16px; }
#zonaSoltar { border: 2px dashed $borda; border-radius: 12px; }
#tituloInicio { font-size: 22px; font-weight: 700; }
#sub { color: $texto2; }
#sub3 { color: $texto3; font-size: 12px; }

#linhaSoltar { background: $destaque; border-radius: 1px; }
#itemDestaque { background: $superficie2; border: 1px solid $borda; border-radius: 6px; }
#itemDestaque:hover { background: $hover; }
#cartao { background: $superficie2; border: 1px solid $borda; border-radius: 10px; }
#cartao[destaque="true"] { border: 1px solid $destaque; }
#cartaoTitulo { font-weight: 600; }
#statusOk { color: $ok; font-weight: 600; }
#statusAviso { color: $aviso; font-weight: 600; }
#statusErro { color: $erro; font-weight: 600; }

QMenu { background: $superficie; border: 1px solid $borda; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; border-radius: 5px; }
QMenu::item:selected { background: $hover; }
QMenu::separator { height: 1px; background: $borda; margin: 4px 6px; }
QProgressBar { border: 1px solid $borda; border-radius: 6px; background: $superficie2; text-align: center; }
QProgressBar::chunk { background: $destaque; border-radius: 5px; }
QTabWidget::pane { border: 1px solid $borda; border-radius: 10px; top: -1px; }
QTabWidget > QTabBar::tab { margin-top: 0; padding: 8px 14px; }
QTabWidget > QTabBar::tab:selected { background: $superficie2; }
""")


def paleta(escuro: bool) -> dict:
    return ESCURO if escuro else CLARO


def aplicar(app, escuro: bool):
    """Folha de estilo + paleta do tema. A cor de destaque (Highlight) da paleta
    vira o cinza do tema - o azul padrão do Qt aparecia em listas suspensas."""
    from PySide6.QtGui import QColor, QPalette
    c = paleta(escuro)
    pal = app.palette()
    for grupo in (QPalette.Active, QPalette.Inactive):
        pal.setColor(grupo, QPalette.Highlight, QColor(c["hover"]))
        pal.setColor(grupo, QPalette.HighlightedText, QColor(c["texto"]))
    app.setPalette(pal)
    app.setStyleSheet(qss(escuro))


def qss(escuro: bool) -> str:
    # caminho com "/" (o QSS não aceita "\\" do Windows)
    check = (Path(__file__).resolve().parents[1] / "assets" / "check.svg").as_posix()
    return _QSS.substitute(paleta(escuro), check=check)
