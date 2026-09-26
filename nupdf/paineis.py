"""Painéis laterais: miniaturas, dados copiáveis e assinaturas digitais."""

import pymupdf
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
                               QListWidgetItem, QPushButton, QScrollArea, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import dados as mod_dados
from . import ui
from .documento import Documento
from .icones import icone


def _cabecalho(titulo: str) -> QLabel:
    lb = QLabel(titulo.upper())
    lb.setObjectName("tituloPainel")
    return lb


class PainelMiniaturas(QWidget):
    paginaEscolhida = Signal(int)
    LARGURA = 128

    def __init__(self, doc: Documento):
        super().__init__()
        self.doc = doc
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 8, 8)
        lay.addWidget(_cabecalho("Páginas"))
        self.lista = QListWidget()
        self.lista.setViewMode(QListView.IconMode)
        self.lista.setFlow(QListView.TopToBottom)
        self.lista.setWrapping(False)
        self.lista.setMovement(QListView.Static)
        self.lista.setResizeMode(QListView.Adjust)
        self.lista.setIconSize(QSize(self.LARGURA, int(self.LARGURA * 1.42)))
        self.lista.setSpacing(4)
        self.lista.setVerticalScrollMode(QListWidget.ScrollPerPixel)
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


class PainelDados(QWidget):
    copiado = Signal(str)
    localizar = Signal(int, str)  # página, texto

    def __init__(self, doc: Documento):
        super().__init__()
        self.doc = doc
        self._carregado = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(_cabecalho("Dados do documento"))
        dica = QLabel("Clique em um item para copiar.")
        dica.setObjectName("sub3")
        lay.addWidget(dica)
        self.filtro = QLineEdit(placeholderText="Filtrar…", clearButtonEnabled=True)
        self.filtro.textChanged.connect(self._filtrar)
        lay.addWidget(self.filtro)
        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        self.arvore.setIndentation(12)
        self.arvore.setWordWrap(True)
        self.arvore.itemClicked.connect(self._clicado)
        lay.addWidget(self.arvore, 1)
        self.vazio = QLabel("Nenhum dado reconhecido.\nO PDF pode ser digitalizado (imagem).")
        self.vazio.setObjectName("sub")
        self.vazio.setAlignment(Qt.AlignCenter)
        self.vazio.setWordWrap(True)
        self.vazio.hide()
        lay.addWidget(self.vazio)
        bt = QPushButton("Copiar todo o texto")
        ui.aplicar_icone(bt, "copiar", 16)
        bt.clicked.connect(self._copiar_tudo)
        lay.addWidget(bt)

    def carregar(self):
        if self._carregado:
            return
        self._carregado = True
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            itens = mod_dados.extrair(self.doc)
        finally:
            QGuiApplication.restoreOverrideCursor()
        grupos: dict[str, QTreeWidgetItem] = {}
        for cat in mod_dados.ORDEM_CATEGORIAS:
            doscat = [d for d in itens if d.categoria == cat]
            if not doscat:
                continue
            g = QTreeWidgetItem([f"{cat}  ({len(doscat)})"])
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            g.setFlags(Qt.ItemIsEnabled)
            self.arvore.addTopLevelItem(g)
            grupos[cat] = g
            for d in doscat:
                texto = f"{d.rotulo}: {d.valor}" if d.rotulo != d.valor else d.valor
                it = QTreeWidgetItem([texto])
                it.setToolTip(0, f"{texto}\nPágina {d.pagina + 1} — clique para copiar")
                it.setData(0, Qt.UserRole, (d.valor, d.pagina))
                g.addChild(it)
            g.setExpanded(True)
        self.vazio.setVisible(not grupos)
        self.arvore.setVisible(bool(grupos))

    def _filtrar(self, termo: str):
        termo = termo.lower().strip()
        for gi in range(self.arvore.topLevelItemCount()):
            g = self.arvore.topLevelItem(gi)
            visiveis = 0
            for ci in range(g.childCount()):
                c = g.child(ci)
                ok = not termo or termo in c.text(0).lower()
                c.setHidden(not ok)
                visiveis += ok
            g.setHidden(visiveis == 0)

    def _clicado(self, it: QTreeWidgetItem):
        dado = it.data(0, Qt.UserRole)
        if not dado:
            return
        valor, pagina = dado
        QGuiApplication.clipboard().setText(valor)
        self.copiado.emit(valor)
        self.localizar.emit(pagina, valor)

    def _copiar_tudo(self):
        QGuiApplication.clipboard().setText(self.doc.texto_completo())
        self.copiado.emit("todo o texto do documento")


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
        lay.addWidget(_cabecalho("Assinaturas digitais"))
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
