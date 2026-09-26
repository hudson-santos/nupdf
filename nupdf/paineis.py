"""Painéis laterais: miniaturas, propriedades do documento e assinaturas digitais."""

import re

import pymupdf
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QPushButton, QScrollArea, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import ui
from .documento import Documento
from .icones import icone


def _cabecalho(titulo: str, maiusculas: bool = True) -> QLabel:
    lb = QLabel(titulo.upper() if maiusculas else titulo)
    lb.setObjectName("tituloPainel")
    return lb


class PainelMiniaturas(QWidget):
    paginaEscolhida = Signal(int)
    LARGURA = 128

    def __init__(self, doc: Documento):
        super().__init__()
        self.doc = doc
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 14, 8, 8)
        # título centralizado sobre as miniaturas (a margem direita compensa a
        # barra de rolagem, que fica à direita da coluna de miniaturas)
        titulo = _cabecalho("Páginas", maiusculas=False)
        titulo.setAlignment(Qt.AlignHCenter)
        titulo.setContentsMargins(0, 0, 8, 0)
        lay.addWidget(titulo)
        self.lista = QListWidget()
        self.lista.setViewMode(QListView.IconMode)
        self.lista.setFlow(QListView.TopToBottom)
        self.lista.setWrapping(False)
        self.lista.setMovement(QListView.Static)
        self.lista.setResizeMode(QListView.Adjust)
        self.lista.setIconSize(QSize(self.LARGURA, int(self.LARGURA * 1.42)))
        self.lista.setSpacing(4)
        self.lista.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # só rolagem vertical
        lay.addWidget(self.lista, 1)
        branco = QPixmap(self.LARGURA, int(self.LARGURA * 1.414))
        branco.fill(QColor("#ffffff"))
        for i in range(doc.n_paginas):
            it = QListWidgetItem(QIcon(branco), str(i + 1))
            it.setTextAlignment(Qt.AlignHCenter)
            self.lista.addItem(it)
        self.lista.currentRowChanged.connect(self._escolhida)
        self._proxima = 0
        self._timer = QTimer(self, interval=0, timeout=self._renderizar_lote)
        self._bloquear = False

    def iniciar(self):
        if self._proxima < self.doc.n_paginas and not self._timer.isActive():
            self._timer.start()

    def _renderizar_lote(self):
        dpr = self.devicePixelRatioF()
        for _ in range(4):
            i = self._proxima
            if i >= self.doc.n_paginas:
                self._timer.stop()
                return
            try:
                pg = self.doc.doc[i]
                s = self.LARGURA * dpr / max(pg.rect.width, 1)
                pm = pg.get_pixmap(matrix=pymupdf.Matrix(s, s), alpha=False)
                img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888).copy()
                pix = QPixmap.fromImage(img)
                pix.setDevicePixelRatio(dpr)
                self.lista.item(i).setIcon(QIcon(pix))
            except Exception:
                pass
            self._proxima += 1

    def _escolhida(self, i: int):
        if i >= 0 and not self._bloquear:
            self.paginaEscolhida.emit(i)

    def marcar(self, i: int):
        self._bloquear = True
        self.lista.setCurrentRow(i)
        self.lista.scrollToItem(self.lista.item(i))
        self._bloquear = False


def _data_pdf(valor: str) -> str:
    """'D:20260928103000-03'00'' -> '28/09/2026 10:30'."""
    m = re.match(r"^(?:D:)?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?", valor or "")
    if not m:
        return valor or ""
    ano, mes, dia, hora, minuto = (g or "" for g in m.groups())
    texto = "/".join(x for x in (dia, mes, ano) if x)
    if hora:
        texto += f" {hora}:{minuto or '00'}"
    return texto


def _tamanho_arquivo(n: int) -> str:
    for unidade in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n} bytes" if unidade == "bytes" else f"{n:.1f} {unidade}".replace(".", ",")
        n /= 1024


def _formato_pagina(larg_pt: float, alt_pt: float) -> str:
    mm = lambda pt: pt * 25.4 / 72
    w, h = sorted((mm(larg_pt), mm(alt_pt)))
    nomes = {"A4": (210, 297), "A3": (297, 420), "A5": (148, 210), "Carta": (215.9, 279.4),
             "Ofício": (215.9, 355.6)}
    nome = next((n for n, (a, b) in nomes.items() if abs(w - a) < 3 and abs(h - b) < 3), "")
    orient = "paisagem" if larg_pt > alt_pt else "retrato"
    medida = f"{mm(larg_pt):.0f} × {mm(alt_pt):.0f} mm"
    return f"{nome} ({orient}) · {medida}" if nome else f"{medida} ({orient})"


class PainelPropriedades(QWidget):
    """Propriedades (metadados) do PDF: arquivo, descrição, origem e segurança."""

    def __init__(self, doc: Documento):
        super().__init__()
        self.doc = doc
        self._carregado = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(_cabecalho("Propriedades do Documento", maiusculas=False))
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setStyleSheet("QScrollArea { background: transparent; }")
        self.conteudo = QWidget()
        self.conteudo.setStyleSheet("background: transparent;")
        self.lista = QVBoxLayout(self.conteudo)
        self.lista.setContentsMargins(0, 4, 4, 0)
        self.lista.setSpacing(10)
        area.setWidget(self.conteudo)
        lay.addWidget(area, 1)

    def _secao(self, titulo: str, itens: list[tuple[str, str]]):
        itens = [(r, v) for r, v in itens if v]
        if not itens:
            return
        cab = QLabel(titulo)
        cab.setStyleSheet("font-weight: 700;")
        self.lista.addWidget(cab)
        for rotulo, valor in itens:
            r = QLabel(rotulo)
            r.setObjectName("sub3")
            v = QLabel(valor)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)  # dá para selecionar e copiar
            bloco = QVBoxLayout()
            bloco.setSpacing(1)
            bloco.addWidget(r)
            bloco.addWidget(v)
            self.lista.addLayout(bloco)
        self.lista.addSpacing(6)

    def carregar(self):
        if self._carregado:
            return
        self._carregado = True
        d, m = self.doc, self.doc.doc.metadata or {}
        pg = d.doc[0].rect if d.n_paginas else None
        cript = m.get("encryption")
        self._secao("Arquivo", [
            ("Nome", d.nome),
            ("Tamanho", _tamanho_arquivo(len(d.dados))),
            ("Páginas", str(d.n_paginas)),
            ("Tamanho da página", _formato_pagina(pg.width, pg.height) if pg else ""),
            ("Versão do PDF", (m.get("format") or "").replace("PDF ", "")),
        ])
        self._secao("Descrição", [
            ("Título", m.get("title", "")),
            ("Autor", m.get("author", "")),
            ("Assunto", m.get("subject", "")),
            ("Palavras-chave", m.get("keywords", "")),
        ])
        self._secao("Origem", [
            ("Aplicativo de criação", m.get("creator", "")),
            ("Gerador do PDF", m.get("producer", "")),
            ("Criado em", _data_pdf(m.get("creationDate", ""))),
            ("Modificado em", _data_pdf(m.get("modDate", ""))),
        ])
        self._secao("Segurança", [
            ("Proteção", f"Protegido ({cript})" if cript else "Sem proteção"),
        ])
        self.lista.addStretch(1)


class _CartaoAssinatura(QFrame):
    def __init__(self, r):
        super().__init__()
        self.setObjectName("cartao")
        c = ui.cores()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)
        topo = QHBoxLayout()
        topo.setSpacing(8)
        ic = QLabel()
        nome_ic, cor, status, obj = {
            "ok": ("escudo", c["ok"], "Assinatura válida", "statusOk"),
            "aviso": ("escudo_alerta", c["aviso"], "Válida, com ressalvas", "statusAviso"),
            "erro": ("escudo_x", c["erro"], "Assinatura inválida", "statusErro"),
        }[r.nivel]
        ic.setPixmap(icone(nome_ic, cor, 22).pixmap(22, 22))
        topo.addWidget(ic)
        st = QLabel(status)
        st.setObjectName(obj)
        topo.addWidget(st, 1)
        lay.addLayout(topo)
        nome = QLabel(r.titular)
        nome.setObjectName("cartaoTitulo")
        nome.setWordWrap(True)
        nome.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(nome)
        linhas = []
        if r.documento:
            linhas.append(r.documento)
        if r.data:
            linhas.append("Assinado em " + r.data.astimezone().strftime("%d/%m/%Y %H:%M:%S")
                          + (" (carimbo de tempo)" if r.carimbo_tempo else ""))
        if r.emissor:
            linhas.append("Emissor: " + r.emissor)
        if r.motivo:
            linhas.append("Motivo: " + r.motivo)
        if r.local:
            linhas.append("Local: " + r.local)
        info = QLabel("\n".join(linhas))
        info.setObjectName("sub")
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(info)
        if r.observacao:
            obs = QLabel(r.observacao)
            obs.setObjectName("sub3")
            obs.setWordWrap(True)
            lay.addWidget(obs)


class PainelAssinaturas(QWidget):
    assinar = Signal()

    def __init__(self, doc: Documento):
        super().__init__()
        self.doc = doc
        self._carregado = False
        self._resultados = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(_cabecalho("Assinaturas Digitais", maiusculas=False))
        self.status = QLabel("")
        self.status.setObjectName("sub")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setStyleSheet("QScrollArea { background: transparent; }")
        self.conteudo = QWidget()
        self.conteudo.setStyleSheet("background: transparent;")
        self.lista = QVBoxLayout(self.conteudo)
        self.lista.setContentsMargins(0, 0, 4, 0)
        self.lista.setSpacing(8)
        self.lista.addStretch(1)
        area.setWidget(self.conteudo)
        lay.addWidget(area, 1)
        bt = QPushButton("  Assinar documento")
        bt.setObjectName("primario")
        bt.setIcon(icone("assinar", "#ffffff", 16))
        bt.setCursor(Qt.PointingHandCursor)
        bt.clicked.connect(self.assinar)
        lay.addWidget(bt)

    def redesenhar(self):
        if self._resultados is not None:
            self._exibir(self._resultados)

    def carregar(self, forcar=False):
        if self._carregado and not forcar:
            return
        self._carregado = True
        self.status.setText("Verificando assinaturas…")
        from .assinatura.validador import validar
        self._tarefa = ui.Tarefa(validar, self.doc.dados)
        self._tarefa.concluida.connect(self._exibir)
        self._tarefa.falhou.connect(lambda e: self.status.setText(f"Não foi possível verificar: {e}"))
        self._tarefa.start()

    def _exibir(self, resultados):
        self._resultados = resultados
        while self.lista.count() > 1:
            w = self.lista.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        if not resultados:
            self.status.setText("Este documento não possui assinaturas digitais.")
            return
        n = len(resultados)
        self.status.setText(f"{n} assinatura{'s' if n > 1 else ''} encontrada{'s' if n > 1 else ''}.")
        for r in resultados:
            self.lista.insertWidget(self.lista.count() - 1, _CartaoAssinatura(r))
