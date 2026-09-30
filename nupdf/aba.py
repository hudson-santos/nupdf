"""Aba de um documento: painel lateral + visualizador com barras flutuantes."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIntValidator
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QStackedWidget,
                               QToolButton, QWidget)

from . import ui
from .documento import Documento
from .paineis import PainelAssinaturas, PainelDestaques, PainelMiniaturas, PainelPropriedades
from .visualizador import Visualizador

PAINEIS = ("miniaturas", "dados", "assinaturas", "destaques")
LARGURA_PAINEL = 280
LARGURA_MINIATURAS = 172  # só a coluna de miniaturas + rolagem, sem sobra à direita


class BarraNavegacao(QFrame):
    def __init__(self, v: Visualizador):
        super().__init__()
        self.setObjectName("flutuante")
        self.v = v
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(2)
        n = v.doc.n_paginas
        self.b_primeira = ui.botao("primeira", "Primeira Página", tamanho=16)
        self.b_anterior = ui.botao("anterior", "Página Anterior", tamanho=16)
        self.pagina = QLineEdit("1")
        self.pagina.setFixedWidth(46)
        self.pagina.setAlignment(Qt.AlignCenter)
        self.pagina.setValidator(QIntValidator(1, max(n, 1)))
        self.total = QLabel(f"/ {n}")
        self.total.setObjectName("sub")
        self.b_proxima = ui.botao("proxima", "Próxima Página", tamanho=16)
        self.b_ultima = ui.botao("ultima", "Última Página", tamanho=16)
        self.b_menos = ui.botao("zoom_menos", "Diminuir Zoom (Ctrl -)", tamanho=16)
        self.zoom = QToolButton()
        self.zoom.setObjectName("comMenu")  # seta ao lado do texto, como no botão Girar
        self.zoom.setText("100%")
        self.zoom.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoom.setLayoutDirection(Qt.RightToLeft)  # ícone (seta) à direita do texto
        ui.aplicar_icone(self.zoom, "seta_menu", 10)
        self.zoom.setPopupMode(QToolButton.InstantPopup)
        self.zoom.setMinimumWidth(64)
        self.zoom.setCursor(Qt.PointingHandCursor)
        menu = QMenu(self.zoom)
        for z in (50, 75, 100, 125, 150, 200, 300, 400):
            menu.addAction(f"{z}%", lambda z=z: v.definir_zoom(z / 100))
        menu.addSeparator()
        menu.addAction("Ajustar à Largura", lambda: v.ajustar("largura"))
        menu.addAction("Página Inteira", lambda: v.ajustar("pagina"))
        self.zoom.setMenu(menu)
        self.b_mais = ui.botao("zoom_mais", "Aumentar Zoom (Ctrl +)", tamanho=16)

        for w in (self.b_primeira, self.b_anterior, self.pagina, self.total, self.b_proxima, self.b_ultima):
            lay.addWidget(w)
        lay.addSpacing(6)
        lay.addWidget(ui.separador_vertical(20))
        lay.addSpacing(6)
        for w in (self.b_menos, self.zoom, self.b_mais):
            lay.addWidget(w)

        self.b_primeira.clicked.connect(lambda: v.ir_para_pagina(0))
        self.b_anterior.clicked.connect(lambda: v.ir_para_pagina(v.pagina_atual - 1))
        self.b_proxima.clicked.connect(lambda: v.ir_para_pagina(v.pagina_atual + 1))
        self.b_ultima.clicked.connect(lambda: v.ir_para_pagina(n - 1))
        self.pagina.returnPressed.connect(self._ir)
        self.b_menos.clicked.connect(v.afastar)
        self.b_mais.clicked.connect(v.aproximar)
        v.paginaMudou.connect(lambda i: self.pagina.setText(str(i + 1)))
        v.zoomMudou.connect(lambda z: self.zoom.setText(f"{round(z * 100)}%"))

    def _ir(self):
        if self.pagina.text().isdigit():
            self.v.ir_para_pagina(int(self.pagina.text()) - 1)
            self.v._pag.setFocus()


class BarraBusca(QFrame):
    fechada = Signal()

    def __init__(self, v: Visualizador):
        super().__init__()
        self.setObjectName("flutuante")
        self.v = v
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 6, 5)
        lay.setSpacing(2)
        self.campo = QLineEdit(placeholderText="Buscar no documento")
        self.campo.setMinimumWidth(220)
        self.contador = QLabel("")
        self.contador.setObjectName("sub3")
        self.contador.setMinimumWidth(52)
        self.contador.setAlignment(Qt.AlignCenter)
        acima = ui.botao("acima", "Anterior (Shift+Enter)", tamanho=16)
        abaixo = ui.botao("abaixo", "Próximo (Enter)", tamanho=16)
        fechar = ui.botao("fechar", "Fechar (Esc)", tamanho=16)
        for w in (self.campo, self.contador, acima, abaixo, fechar):
            lay.addWidget(w)
        self._timer = QTimer(self, singleShot=True, interval=280, timeout=self._buscar)
        self.campo.textChanged.connect(lambda: self._timer.start())
        self.campo.returnPressed.connect(self._enter)
        acima.clicked.connect(lambda: self._passo(-1))
        abaixo.clicked.connect(lambda: self._passo(1))
        fechar.clicked.connect(self.fechar)
        self._ultimo = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.fechar()
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() & Qt.ShiftModifier:
            self._passo(-1)
            return
        super().keyPressEvent(e)

    def abrir(self, texto: str = ""):
        self.show()
        self.raise_()
        if texto:
            self.campo.setText(texto)
        self.campo.setFocus()
        self.campo.selectAll()

    def fechar(self):
        self.hide()
        self.v.limpar_busca()
        self._ultimo = None
        self.v._pag.setFocus()
        self.fechada.emit()

    def _buscar(self):
        termo = self.campo.text()
        self._ultimo = termo
        n = self.v.buscar(termo)
        self._contar(n)

    def _contar(self, n=None):
        n = len(self.v.resultados) if n is None else n
        if not self.campo.text().strip():
            self.contador.setText("")
        elif n == 0:
            self.contador.setText("0")
        else:
            self.contador.setText(f"{self.v.resultado_atual + 1}/{n}")

    def _enter(self):
        if self._timer.isActive() or self._ultimo != self.campo.text():
            self._timer.stop()
            self._buscar()
        else:
            self._passo(1)

    def _passo(self, d: int):
        self.v.proximo_resultado(d)
        self._contar()


class _Area(QWidget):
    """Contém o visualizador e posiciona as barras flutuantes sobre ele."""

    def __init__(self, v: Visualizador):
        super().__init__()
        self.v = v
        v.setParent(self)
        self.nav = BarraNavegacao(v)
        self.nav.setParent(self)
        self.busca = BarraBusca(v)
        self.busca.setParent(self)
        self.busca.hide()
        self.aviso = QLabel(self)
        self.aviso.setObjectName("aviso")
        self.aviso.hide()
        self.toast = ui.Toast(self)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.reposicionar()

    def reposicionar(self):
        w, h = self.width(), self.height()
        self.v.setGeometry(0, 0, w, h)
        self.nav.adjustSize()
        self.nav.move((w - self.nav.width()) // 2, h - self.nav.height() - 18)
        self.busca.adjustSize()
        self.busca.move(w - self.busca.width() - 26, 12)
        self.aviso.adjustSize()
        self.aviso.move((w - self.aviso.width()) // 2, 14)
        self.nav.raise_()
        self.busca.raise_()


class AbaDocumento(QWidget):
    painelMudou = Signal(object)
    excluirPagina = Signal(int)  # pedido pela página ou pela miniatura (a janela executa)
    moverPagina = Signal(int, int)  # reordenar pelas miniaturas (a janela executa)

    def __init__(self, documento: Documento):
        super().__init__()
        self.doc = documento
        self.cfg_pendente = None  # assinatura aguardando posicionamento
        # Ctrl+Z: retratos do documento antes de cada alteração (o mais recente no fim)
        self.historico: list[dict] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.lateral = QStackedWidget()
        self.lateral.setObjectName("painelLateral")
        self.lateral.setFixedWidth(LARGURA_PAINEL)
        self.lateral.hide()
        self.miniaturas = PainelMiniaturas(documento)
        self.dados = PainelPropriedades(documento)  # chave "dados" mantida (preferência salva)
        self.assinaturas = PainelAssinaturas(documento)
        self.destaques = PainelDestaques(documento)
        for p in (self.miniaturas, self.dados, self.assinaturas, self.destaques):
            self.lateral.addWidget(p)
        lay.addWidget(self.lateral)

        self.visualizador = Visualizador(documento, ui.cores())
        self.area = _Area(self.visualizador)
        lay.addWidget(self.area, 1)
        self._painel = None

        v = self.visualizador
        self.miniaturas.paginaEscolhida.connect(v.ir_para_pagina)
        self.miniaturas.rotacao_de = v._rot  # miniaturas acompanham a página girada na tela
        self.miniaturas.girarPagina.connect(v.girar_pagina)
        self.miniaturas.excluirPagina.connect(self.excluirPagina)
        self.miniaturas.moverPagina.connect(self.moverPagina)
        v.excluirPagina.connect(self.excluirPagina)
        v.rotacaoMudou.connect(self.miniaturas.rotacao_mudou)
        v.paginaMudou.connect(self._pagina_mudou)
        v.copiadoPeloBotao.connect(lambda _t: self.toast("Texto Copiado"))
        v.vaiAlterar.connect(self.registrar)
        # "Marcadores": vai até o destaque clicado e acompanha as alterações
        self.destaques.destaqueEscolhido.connect(self._ir_para_destaque)
        self.destaques.removerDestaque.connect(lambda pg, xref: v.remover_destaque((pg, xref)))
        for sinal in (v.destaqueFeito, v.destaqueRemovido, v.corDestaqueAlterada, v.edicaoRestaurada):
            sinal.connect(self._destaques_mudaram)
        v.destaqueFeito.connect(lambda: self.toast("Texto Destacado"))
        v.destaqueRemovido.connect(lambda: self.toast("Destaque Removido"))
        v.corDestaqueAlterada.connect(lambda: self.toast("Cor do Destaque Alterada"))
        v.assinaturaClicada.connect(self._assinatura_clicada)

    # ------------------------------------------------------------------ desfazer
    LIMITE_HISTORICO = 50

    def retrato(self) -> dict:
        """Estado atual do documento na tela: conteúdo (muda ao excluir página),
        pendências herdadas, destaques e rotação."""
        return {"dados": self.doc.dados, "pendencias": list(self.doc.pendencias_herdadas),
                "edicao": self.doc.estado_edicao(), "rotacao": self.visualizador.estado_rotacao()}

    def registrar(self):
        self.historico.append(self.retrato())
        del self.historico[:-self.LIMITE_HISTORICO]

    # ------------------------------------------------------------------ painéis
    @property
    def painel(self):
        return self._painel

    def mostrar_painel(self, nome: str | None):
        if nome == self._painel or nome is None:
            self._painel = None
            self.lateral.hide()
        else:
            self._painel = nome
            w = {"miniaturas": self.miniaturas, "dados": self.dados, "assinaturas": self.assinaturas,
                 "destaques": self.destaques}[nome]
            self.lateral.setCurrentWidget(w)
            self.lateral.setFixedWidth(LARGURA_MINIATURAS if nome == "miniaturas" else LARGURA_PAINEL)
            self.lateral.show()
            if nome == "miniaturas":
                self.miniaturas.iniciar()
                self.miniaturas.marcar(self.visualizador.pagina_atual)
            elif nome == "dados":
                self.dados.carregar()
            elif nome == "destaques":
                self.destaques.carregar()
            else:
                self.assinaturas.carregar()
        self.painelMudou.emit(self._painel)

    def _destaques_mudaram(self):
        if self._painel == "destaques":
            self.destaques.carregar()

    def _ir_para_destaque(self, pagina: int, area):
        v = self.visualizador
        v.ir_para_pagina(pagina)
        v.mostrar_retangulo(pagina, area, realcar=True)

    def _assinatura_clicada(self, campo: str):
        if self._painel != "assinaturas":
            self.mostrar_painel("assinaturas")
        self.assinaturas.destacar(campo)

    def _pagina_mudou(self, i: int):
        if self._painel == "miniaturas":
            self.miniaturas.marcar(i)

    # ------------------------------------------------------------------ utilidades
    def toast(self, texto: str, ms: int = 1800):
        self.area.toast.mostrar(texto, ms)

    def mostrar_aviso(self, texto: str):
        self.area.aviso.setText(texto)
        self.area.aviso.adjustSize()
        self.area.aviso.move((self.area.width() - self.area.aviso.width()) // 2, 14)
        self.area.aviso.show()
        self.area.aviso.raise_()

    def esconder_aviso(self):
        self.area.aviso.hide()

    def buscar(self):
        texto = self.visualizador.texto_selecionado() if self.visualizador.tem_selecao() else ""
        self.area.busca.abrir(texto if len(texto) < 80 and "\n" not in texto else "")
        self.area.reposicionar()

    def atualizar_cores(self):
        self.visualizador.atualizar_cores(ui.cores())
        self.assinaturas.redesenhar()
