"""Janela principal do NuPDF."""

import subprocess
from pathlib import Path

import pymupdf
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressDialog, QPushButton,
                               QStackedWidget, QTabBar, QToolButton, QVBoxLayout, QWidget)

from . import leitor_padrao, tema, ui
from .aba import AbaDocumento
from .config import Config
from .documento import Documento, SenhaNecessaria
from .icones import icone, icone_app, pixmap_logo
from .versao import NOME_APP, VERSAO


class _LinhaRecente(QFrame):
    """Item da lista de recentes: mostra só o nome do arquivo; clique abre.
    Ao passar o mouse aparecem "abrir pasta" (Explorer com o arquivo
    selecionado) e a lixeira (remove da lista - o arquivo não é apagado)."""

    def __init__(self, tela: "TelaInicial", caminho: str):
        super().__init__()
        self.setObjectName("linhaRecente")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.tela, self.caminho = tela, caminho
        p = Path(caminho)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(0)
        abrir = QPushButton()
        abrir.setObjectName("link")
        nome = abrir.fontMetrics().elidedText(p.stem, Qt.ElideMiddle, 400)
        abrir.setText(f"  {nome}")
        ui.aplicar_icone(abrir, "arquivo", 16)
        abrir.setCursor(Qt.PointingHandCursor)
        abrir.clicked.connect(lambda: tela.janela.abrir_arquivo(caminho))
        lay.addWidget(abrir, 1)
        self.pasta = ui.botao("pasta", "Abrir a Pasta do Arquivo", tamanho=15)
        self.pasta.clicked.connect(self.abrir_pasta)
        self.remover = ui.botao("lixeira", "Remover da Lista de Recentes", tamanho=15)
        self.remover.clicked.connect(lambda: tela.remover(caminho))
        for b in (self.pasta, self.remover):
            politica = b.sizePolicy()
            politica.setRetainSizeWhenHidden(True)
            b.setSizePolicy(politica)
            b.hide()
            lay.addWidget(b)

    def abrir_pasta(self):
        # Explorer com o arquivo já selecionado (funciona também em caminhos de rede)
        subprocess.Popen(f'explorer /select,"{Path(self.caminho)}"')

    def enterEvent(self, e):
        self.pasta.show()
        self.remover.show()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.pasta.hide()
        self.remover.hide()
        super().leaveEvent(e)

    def contextMenuEvent(self, e):
        m = QMenu(self)
        a_abrir = m.addAction("Abrir")
        a_pasta = m.addAction("Abrir a Pasta do Arquivo")
        a_remover = m.addAction("Remover da lista")
        m.addSeparator()
        a_limpar = m.addAction("Limpar todos os recentes")
        esc = m.exec(e.globalPos())
        if esc is a_abrir:
            self.tela.janela.abrir_arquivo(self.caminho)
        elif esc is a_pasta:
            self.abrir_pasta()
        elif esc is a_remover:
            self.tela.remover(self.caminho)
        elif esc is a_limpar:
            self.tela.limpar_tudo()


class TelaInicial(QWidget):
    def __init__(self, janela: "JanelaPrincipal"):
        super().__init__()
        self.janela = janela
        self.setObjectName("inicio")
        self.setAttribute(Qt.WA_StyledBackground, True)
        externo = QVBoxLayout(self)
        externo.addStretch(1)
        linha = QHBoxLayout()
        linha.addStretch(1)
        cartao = QFrame()
        cartao.setObjectName("cartaoInicio")
        cartao.setFixedWidth(560)
        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(36, 32, 36, 28)
        lay.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(pixmap_logo(56))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        titulo = QLabel(NOME_APP)
        titulo.setObjectName("tituloInicio")
        titulo.setAlignment(Qt.AlignCenter)
        lay.addWidget(titulo)
        sub = QLabel("Leia PDFs, Copie Dados e Assine Digitalmente com Certificado ICP-Brasil")
        sub.setObjectName("sub")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        lay.addSpacing(10)

        zona = QFrame()
        zona.setObjectName("zonaSoltar")
        zl = QVBoxLayout(zona)
        zl.setContentsMargins(20, 26, 20, 26)
        zl.setSpacing(10)
        bt = QPushButton("  Abrir PDF")
        bt.setObjectName("primario")
        bt.setIcon(icone("abrir", "#ffffff", 18))
        bt.setIconSize(QSize(18, 18))
        bt.setCursor(Qt.PointingHandCursor)
        bt.setMinimumHeight(40)
        bt.setFixedWidth(200)
        bt.clicked.connect(janela.abrir_dialogo)
        zl.addWidget(bt, 0, Qt.AlignCenter)
        # Linhas separadas: o espaçamento do layout (10px) fica igual
        # entre o botão e o "ou" e entre o "ou" e a instrução.
        for texto in ("ou", "Arraste um Arquivo para esta Janela"):
            dica = QLabel(texto)
            dica.setObjectName("sub3")
            dica.setAlignment(Qt.AlignCenter)
            zl.addWidget(dica)
        lay.addWidget(zona)

        lay.addSpacing(8)
        self.cab_recentes = QWidget()
        cab = QHBoxLayout(self.cab_recentes)
        cab.setContentsMargins(0, 0, 0, 0)
        titulo_recentes = QLabel("Arquivos Recentes")
        titulo_recentes.setObjectName("tituloPainel")
        cab.addWidget(titulo_recentes)
        cab.addStretch(1)
        limpar = QPushButton("Limpar Tudo")
        limpar.setObjectName("linkPequeno")
        limpar.setCursor(Qt.PointingHandCursor)
        limpar.setToolTip("Limpar a Lista de Arquivos Recentes ( os Arquivos não são Apagados )")
        limpar.clicked.connect(self.limpar_tudo)
        cab.addWidget(limpar)
        lay.addWidget(self.cab_recentes)
        self.recentes = QVBoxLayout()
        self.recentes.setSpacing(0)
        lay.addLayout(self.recentes)

        linha.addWidget(cartao)
        linha.addStretch(1)
        externo.addLayout(linha)
        externo.addStretch(2)

    def atualizar(self, recentes: list[str]):
        while self.recentes.count():
            w = self.recentes.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        existentes = [c for c in recentes if Path(c).is_file()][:6]
        self.cab_recentes.setVisible(bool(existentes))
        for c in existentes:
            self.recentes.addWidget(_LinhaRecente(self, c))

    def remover(self, caminho: str):
        self.janela.config.remover_recente(caminho)
        self.atualizar(self.janela.config.recentes())

    def limpar_tudo(self):
        self.janela.config.limpar_recentes()
        self.atualizar([])


class JanelaPrincipal(QMainWindow):
    def __init__(self, verificar_atualizacao: bool = False):
        super().__init__()
        self.config = Config()
        self.escuro = bool(self.config.get("tema_escuro", True))
        tema.carregar_fontes()
        ui.definir_cores(tema.paleta(self.escuro))
        tema.aplicar(QApplication.instance(), self.escuro)
        self.setWindowTitle(NOME_APP)
        self.setWindowIcon(icone_app())
        self.setAcceptDrops(True)
        self.resize(1320, 860)
        self.abas: list[AbaDocumento] = []

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._criar_topo())
        v.addWidget(self._criar_ferramentas())
        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)
        corpo.addWidget(self._criar_trilho())
        self.pilha = QStackedWidget()
        self.inicio = TelaInicial(self)
        self.pilha.addWidget(self.inicio)
        corpo.addWidget(self.pilha, 1)
        v.addLayout(corpo, 1)
        self.setCentralWidget(central)
        self._criar_atalhos()
        self.toast = ui.Toast(self)
        self._atualizar_estado()
        self._conferir_leitor_padrao()
        self._release_nova = None
        self._mostrar_nova_versao(self.config.get("atualizacao/versao_disponivel", ""))
        if verificar_atualizacao:
            # consulta discreta, no máximo 1x por dia (a hora é conferida de hora em
            # hora, para o NuPDF que fica aberto por dias); nunca abre janela sozinha
            QTimer.singleShot(4000, self._checar_atualizacao_diaria)
            self._timer_atualizacao = QTimer(self)
            self._timer_atualizacao.timeout.connect(self._checar_atualizacao_diaria)
            self._timer_atualizacao.start(60 * 60 * 1000)

    # ================================================================== montagem
    def _criar_topo(self) -> QWidget:
        topo = QFrame()
        topo.setObjectName("topo")
        topo.setFixedHeight(46)
        lay = QHBoxLayout(topo)
        lay.setContentsMargins(14, 0, 10, 0)
        lay.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(pixmap_logo(24))
        lay.addWidget(logo)
        nome = QLabel("Nu")
        nome.setObjectName("logoTexto")
        nome2 = QLabel("PDF")
        nome2.setObjectName("logoTexto")
        nome2.setProperty("destaque", True)
        caixa_nome = QHBoxLayout()
        caixa_nome.setSpacing(0)
        caixa_nome.addWidget(nome)
        caixa_nome.addWidget(nome2)
        lay.addLayout(caixa_nome)
        lay.addSpacing(18)

        self.tabbar = QTabBar()
        self.tabbar.setDocumentMode(True)
        self.tabbar.setExpanding(False)
        self.tabbar.setMovable(True)
        self.tabbar.setElideMode(Qt.ElideMiddle)
        self.tabbar.setDrawBase(False)
        self.tabbar.currentChanged.connect(self._aba_trocada)
        self.tabbar.tabMoved.connect(self._aba_movida)
        lay.addWidget(self.tabbar, 0, Qt.AlignBottom)
        # O "+" ocupa a mesma faixa vertical das abas (alinhadas embaixo) para
        # ficar centralizado com o texto delas.
        self.faixa_mais = QWidget()
        fm = QVBoxLayout(self.faixa_mais)
        fm.setContentsMargins(0, 0, 0, 0)
        nova = ui.botao("mais", "Abrir PDF (Ctrl+O)", tamanho=16)
        nova.clicked.connect(self.abrir_dialogo)
        fm.addWidget(nova, 0, Qt.AlignCenter)
        lay.addWidget(self.faixa_mais, 0, Qt.AlignBottom)
        lay.addStretch(1)
        # aviso quando o NuPDF não é o leitor de PDF padrão (conferido ao ativar a janela)
        self.b_padrao = QPushButton("O NuPDF não é o Leitor de PDF Padrão")
        self.b_padrao.setObjectName("avisoPadrao")
        self.b_padrao.setCursor(Qt.PointingHandCursor)
        self.b_padrao.setToolTip("Tornar o NuPDF o Leitor de PDF Padrão")
        self.b_padrao.clicked.connect(self.definir_leitor_padrao)
        self.b_padrao.hide()
        lay.addWidget(self.b_padrao)
        # nova versão encontrada pela verificação diária: um clique já atualiza
        self.b_nova_versao = QPushButton()
        self.b_nova_versao.setObjectName("avisoPadrao")  # mesmo visual do aviso de leitor padrão
        self.b_nova_versao.setCursor(Qt.PointingHandCursor)
        self.b_nova_versao.clicked.connect(self._atualizar_agora)
        self.b_nova_versao.hide()
        lay.addWidget(self.b_nova_versao)
        self.b_atualizacao = ui.botao("atualizar", "Verificar Atualizações")
        self.b_atualizacao.clicked.connect(self.verificar_atualizacoes)
        lay.addWidget(self.b_atualizacao)
        self.b_tema = ui.botao("sol" if self.escuro else "lua", "Alternar Tema Claro/Escuro")
        self.b_tema.clicked.connect(self.alternar_tema)
        lay.addWidget(self.b_tema)
        sobre = ui.botao("info", "Sobre o NuPDF")
        sobre.clicked.connect(self._sobre)
        lay.addWidget(sobre)
        return topo

    def _criar_ferramentas(self) -> QWidget:
        barra = QFrame()
        barra.setObjectName("ferramentas")
        self.barra_ferramentas = barra  # só aparece com documento aberto
        barra.setFixedHeight(50)
        lay = QHBoxLayout(barra)
        lay.setContentsMargins(12, 0, 14, 0)
        lay.setSpacing(4)

        # Salvar/Imprimir só aparecem com documento aberto; o espaço deles fica
        # reservado para as ferramentas do centro não mudarem de lugar.
        self.b_salvar = ui.botao("salvar", "Salvar uma Cópia (Ctrl+S)")
        self.b_imprimir = ui.botao("imprimir", "Imprimir (Ctrl+P)")
        for b in (self.b_salvar, self.b_imprimir):
            politica = b.sizePolicy()
            politica.setRetainSizeWhenHidden(True)
            b.setSizePolicy(politica)
            lay.addWidget(b)
        lay.addStretch(1)

        self.b_largura = ui.botao("largura", "Ajustar à Largura (Ctrl+1)")
        self.b_pagina = ui.botao("pagina", "Página Inteira (Ctrl+2)")
        self.b_girar = ui.botao("girar+seta", "Girar", obj="comMenu")  # seta ao lado, não no canto
        self.b_girar.setPopupMode(QToolButton.InstantPopup)  # menu com as duas opções
        menu_girar = QMenu(self.b_girar)
        menu_girar.addAction("Girar Página Atual	Ctrl+Shift+R",
                             lambda: self._no_visualizador(lambda v: v.girar_pagina()))
        menu_girar.addAction("Girar Todas as Páginas	Ctrl+R",
                             lambda: self._no_visualizador(lambda v: v.girar()))
        self.b_girar.setMenu(menu_girar)
        self.b_buscar = ui.botao("buscar", "Buscar (Ctrl+F)")
        # Ações de documento: só visíveis quando há um PDF aberto (ver _atualizar_estado)
        self._acoes_documento = [self.b_largura,
                                 self.b_pagina, self.b_girar, ui.separador_vertical(), self.b_buscar]
        for w in self._acoes_documento:
            lay.addWidget(w)
        lay.addStretch(1)

        self.b_assinar = QPushButton("  Assinar com Certificado Digital")
        self.b_assinar.setObjectName("primario")
        self.b_assinar.setIcon(icone("assinar", "#ffffff", 16))
        self.b_assinar.setCursor(Qt.PointingHandCursor)
        self.b_assinar.setToolTip("Assinar digitalmente com certificado ICP-Brasil")
        lay.addWidget(self.b_assinar)
        self._acoes_documento.append(self.b_assinar)

        self.b_salvar.clicked.connect(lambda: self.salvar_copia())
        self.b_imprimir.clicked.connect(self.imprimir)
        self.b_largura.clicked.connect(lambda: self._no_visualizador(lambda v: v.ajustar("largura")))
        self.b_pagina.clicked.connect(lambda: self._no_visualizador(lambda v: v.ajustar("pagina")))
        self.b_buscar.clicked.connect(self.buscar)
        self.b_assinar.clicked.connect(self.assinar)
        return barra

    def _criar_trilho(self) -> QWidget:
        trilho = QFrame()
        self.trilho = trilho  # só aparece com documento aberto (ver _atualizar_estado)
        trilho.setObjectName("trilhoLateral")
        trilho.setFixedWidth(52)
        lay = QVBoxLayout(trilho)
        lay.setContentsMargins(6, 10, 6, 10)
        lay.setSpacing(6)
        self.b_paineis = {}
        for nome, ic, dica in (("miniaturas", "miniaturas", "Páginas"),
                               ("dados", "propriedades", "Propriedades do Documento"),
                               ("assinaturas", "escudo", "Assinaturas Digitais")):
            b = ui.botao(ic, dica, checavel=True, tamanho=20, obj="trilho")
            b.clicked.connect(lambda _=False, n=nome: self._alternar_painel(n))
            lay.addWidget(b, 0, Qt.AlignHCenter)
            self.b_paineis[nome] = b
        lay.addStretch(1)
        return trilho

    def _criar_atalhos(self):
        def atalho(teclas, fn):
            a = QAction(self)
            a.setShortcuts([QKeySequence(t) for t in (teclas if isinstance(teclas, list) else [teclas])])
            a.triggered.connect(fn)
            self.addAction(a)

        atalho("Ctrl+O", self.abrir_dialogo)
        atalho(["Ctrl+W", "Ctrl+F4"], lambda: self.fechar_aba(self.tabbar.currentIndex()))
        atalho(["Ctrl+S", "Ctrl+Shift+S"], self.salvar_copia)
        atalho("Ctrl+Z", self.desfazer)
        atalho("Ctrl+P", self.imprimir)
        atalho("Ctrl+F", self.buscar)
        atalho(["Ctrl++", "Ctrl+="], lambda: self._no_visualizador(lambda v: v.aproximar()))
        atalho("Ctrl+-", lambda: self._no_visualizador(lambda v: v.afastar()))
        atalho("Ctrl+0", lambda: self._no_visualizador(lambda v: v.definir_zoom(1.0)))
        atalho("Ctrl+1", lambda: self._no_visualizador(lambda v: v.ajustar("largura")))
        atalho("Ctrl+2", lambda: self._no_visualizador(lambda v: v.ajustar("pagina")))
        atalho("Ctrl+R", lambda: self._no_visualizador(lambda v: v.girar()))
        atalho("Ctrl+Shift+R", lambda: self._no_visualizador(lambda v: v.girar_pagina()))
        atalho("Ctrl+Tab", lambda: self._trocar_aba(1))
        atalho("Ctrl+Shift+Tab", lambda: self._trocar_aba(-1))
        atalho("F11", self._tela_cheia)

    # ================================================================== abas
    def aba_atual(self) -> AbaDocumento | None:
        i = self.tabbar.currentIndex()
        return self.abas[i] if 0 <= i < len(self.abas) else None

    def _no_visualizador(self, fn):
        aba = self.aba_atual()
        if aba:
            fn(aba.visualizador)

    def _aba_trocada(self, i: int):
        if 0 <= i < len(self.abas):
            self.pilha.setCurrentWidget(self.abas[i])
        else:
            self.pilha.setCurrentWidget(self.inicio)
        self._atualizar_estado()

    def _aba_movida(self, de: int, para: int):
        self.abas.insert(para, self.abas.pop(de))

    def _trocar_aba(self, d: int):
        n = self.tabbar.count()
        if n:
            self.tabbar.setCurrentIndex((self.tabbar.currentIndex() + d) % n)

    def fechar_aba(self, i: int, confirmar: bool = True) -> bool:
        """Fecha a aba i. Com `confirmar`, pergunta antes de descartar alterações não
        salvas - páginas giradas, destaques (as recargas internas - depois de
        salvar/assinar - não perguntam).
        Devolve False se o usuário desistiu."""
        if not (0 <= i < len(self.abas)):
            return True
        if confirmar and self._pendencias(self.abas[i]):
            aba = self.abas[i]
            resposta = self._perguntar_alteracoes(aba)
            if resposta == "cancelar":
                return False
            if resposta == "salvar":
                aba = self.salvar_copia(aba)
                if aba is None:  # desistiu na janela de salvar
                    return False
                i = self.abas.index(aba)  # salvar no próprio arquivo recarrega a aba
        aba = self.abas.pop(i)
        self.tabbar.removeTab(i)
        self.pilha.removeWidget(aba)
        aba.doc.fechar()
        aba.deleteLater()
        self._aba_trocada(self.tabbar.currentIndex())
        return True

    @staticmethod
    def _pendencias(aba) -> list[str]:
        """Alterações feitas desde o último "Salvar" (vazio = pode fechar sem perguntar)."""
        pend = list(aba.doc.pendencias_herdadas)  # de antes de excluir uma página
        if aba.visualizador.rotacoes_pendentes and "páginas giradas" not in pend:
            pend.append("páginas giradas")
        if aba.doc.destaques_pendentes and "texto destacado" not in pend:
            pend.append("texto destacado")
        return pend

    def _perguntar_alteracoes(self, aba) -> str:
        """'salvar', 'descartar' ou 'cancelar' para uma aba com alterações não salvas."""
        self.tabbar.setCurrentIndex(self.abas.index(aba))
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Alterações Não Salvas")
        caixa.setIcon(QMessageBox.NoIcon)
        pend = self._pendencias(aba)
        quais = pend[0] if len(pend) == 1 else ", ".join(pend[:-1]) + " e " + pend[-1]
        if not self._salvar_bloqueado(aba):
            caixa.setText(f"O documento <b>{aba.doc.nome}</b> tem alterações que ainda não foram salvas "
                          f"({quais}).<br><br>Deseja Salvar antes de Fechar ?")
            salvar = caixa.addButton("Salvar", QMessageBox.AcceptRole)
            descartar = caixa.addButton("Não Salvar", QMessageBox.DestructiveRole)
            estilos = ((salvar, "primario"), (descartar, "fechar"))  # "fechar" = cinza escuro
        else:
            # assinado: salvar invalidaria as assinaturas, então só dá para descartar
            caixa.setText(f"O documento <b>{aba.doc.nome}</b> tem alterações que não foram salvas "
                          f"({quais}).<br><br>Por ter assinatura digital, elas não podem ser salvas "
                          "(as assinaturas seriam invalidadas).<br><br>Deseja Fechar mesmo assim ?")
            salvar = None
            descartar = caixa.addButton("Fechar sem Salvar", QMessageBox.AcceptRole)
            estilos = ((descartar, "primario"),)
        if salvar is not None:
            # "Fechar" (vermelho) fecha só esta janela: a aba continua aberta, como o Esc
            cancelar = caixa.addButton("Fechar", QMessageBox.RejectRole)
            estilos += ((cancelar, "perigo"),)
        else:
            cancelar = caixa.addButton("Cancelar", QMessageBox.RejectRole)
            estilos += ((cancelar, "fechar"),)
        for botao, nome in estilos:
            botao.setObjectName(nome)
            botao.setCursor(Qt.PointingHandCursor)
            botao.style().unpolish(botao)  # reaplica o QSS com o novo objectName
            botao.style().polish(botao)
        caixa.setDefaultButton(salvar or descartar)
        caixa.setEscapeButton(cancelar)
        caixa.exec()
        clicado = caixa.clickedButton()
        if salvar is not None and clicado is salvar:
            return "salvar"
        return "descartar" if clicado is descartar else "cancelar"

    def _atualizar_estado(self):
        aba = self.aba_atual()
        tem = aba is not None
        for b in self.b_paineis.values():
            b.setEnabled(tem)
        for w in (self.b_salvar, self.b_imprimir, *self._acoes_documento):
            w.setVisible(tem)
        # PDF assinado: pode girar, mas não salvar girado (invalidaria as assinaturas)
        bloqueado = self._salvar_bloqueado(aba)
        self.b_salvar.setEnabled(not bloqueado)
        self.b_salvar.setToolTip(
            "Documento com assinatura digital: não é possível salvar com páginas giradas ou texto "
            "destacado (as assinaturas seriam invalidadas)" if bloqueado else "Salvar uma Cópia (Ctrl+S)")
        self.barra_ferramentas.setVisible(tem)
        self.faixa_mais.setVisible(tem)  # "+" só com documento aberto (sem documento, usa o botão central)
        self.trilho.setVisible(tem)
        painel = aba.painel if aba else None
        for nome, b in self.b_paineis.items():
            b.setChecked(nome == painel)
        if aba:
            self.setWindowTitle(f"{NOME_APP} - Versão: {VERSAO} - {aba.doc.nome}")
        else:
            self.setWindowTitle(f"{NOME_APP} - Versão: {VERSAO}")
            self.inicio.atualizar(self.config.recentes())

    def _alternar_painel(self, nome: str):
        aba = self.aba_atual()
        if aba:
            aba.mostrar_painel(nome)
            self.config.set("painel", aba.painel or "")

    # ================================================================== abrir / salvar
    def abrir_dialogo(self):
        pasta = self.config.get("ultima_pasta", str(Path.home() / "Documents"))
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Abrir PDF", pasta, "Documentos PDF (*.pdf);;Todos (*)")
        for a in arquivos:
            self.abrir_arquivo(a)

    def abrir_arquivo(self, caminho: str, painel: str | None = None) -> AbaDocumento | None:
        p = Path(caminho)
        try:
            resolvido = p.resolve()
        except OSError:
            resolvido = p
        for i, aba in enumerate(self.abas):
            if aba.doc.caminho.resolve() == resolvido:
                self.tabbar.setCurrentIndex(i)
                return aba
        if not p.is_file():
            QMessageBox.warning(self, NOME_APP, f"Arquivo não encontrado:\n{p}")
            self.config.remover_recente(str(p))
            self._atualizar_estado()
            return None

        senha = None
        while True:
            try:
                doc = Documento(str(resolvido), senha)
                break
            except SenhaNecessaria:
                senha, ok = QInputDialog.getText(
                    self, "Documento protegido",
                    f"{p.stem} está protegido por senha.\n{'Senha incorreta. ' if senha else ''}Digite a senha:",
                    QLineEdit.Password)
                if not ok:
                    return None
            except Exception as e:
                QMessageBox.critical(self, NOME_APP, f"Não foi possível abrir o arquivo:\n{p}\n\n{e}")
                return None

        aba = self._criar_aba(doc)
        self.config.adicionar_recente(str(resolvido))
        self.config.set("ultima_pasta", str(resolvido.parent))
        painel = painel if painel is not None else (self.config.get("painel", "") or None)
        if painel:
            aba.mostrar_painel(painel)
        aba.visualizador._pag.setFocus()
        return aba

    def _criar_aba(self, doc: Documento, indice: int | None = None) -> AbaDocumento:
        """Aba para o documento, no fim da barra ou na posição `indice`."""
        aba = AbaDocumento(doc)
        aba.excluirPagina.connect(lambda i, a=aba: self.excluir_pagina(a, i))
        aba.painelMudou.connect(lambda _: self._atualizar_estado())
        aba.visualizador.rotacaoMudou.connect(self._atualizar_estado)
        aba.visualizador.destaqueFeito.connect(self._atualizar_estado)
        aba.visualizador.destaqueRemovido.connect(self._atualizar_estado)
        aba.visualizador.corDestaqueAlterada.connect(self._atualizar_estado)
        # última cor do "Destacar": vale para todas as abas e fica nas preferências
        aba.visualizador.definir_cor_destaque(self.config.get("destaque/cor", "amarelo"))
        aba.visualizador.corDestaqueEscolhida.connect(self._cor_destaque_escolhida)
        aba.visualizador.retanguloDesenhado.connect(lambda pg, r, a=aba: self._posicionado(a, pg, r))
        aba.visualizador.posicionamentoCancelado.connect(lambda a=aba: self._posicionamento_cancelado(a))
        indice = len(self.abas) if indice is None else indice
        self.abas.insert(indice, aba)
        self.pilha.addWidget(aba)
        idx = self.tabbar.insertTab(indice, icone("arquivo", ui.cores()["texto2"], 14), doc.nome)
        self.tabbar.setTabToolTip(idx, doc.nome)
        fechar = ui.botao("fechar", "Fechar (Ctrl+W)", tamanho=12, obj="abaFechar")
        fechar.clicked.connect(lambda _=False, a=aba: self.fechar_aba(self.abas.index(a)) if a in self.abas else None)
        # Margens só na horizontal: afasta o X da borda direita da aba e do nome
        # (sem margem vertical, o Qt continua centralizando na altura da aba).
        caixa_fechar = QWidget()
        cf = QHBoxLayout(caixa_fechar)
        cf.setContentsMargins(4, 0, 8, 0)
        cf.addWidget(fechar)
        self.tabbar.setTabButton(idx, QTabBar.RightSide, caixa_fechar)
        self.faixa_mais.setFixedHeight(self.tabbar.tabRect(idx).height())
        self.tabbar.setCurrentIndex(idx)
        self._aba_trocada(idx)
        return aba

    def _confirmar_exclusao(self, i: int) -> bool:
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Excluir Página")
        caixa.setIcon(QMessageBox.NoIcon)
        caixa.setText(f"Deseja Excluir a Página {i + 1} ?<br><br>"
                      "O arquivo só é alterado ao Salvar.")
        excluir = caixa.addButton("Excluir", QMessageBox.AcceptRole)
        cancelar = caixa.addButton("Cancelar", QMessageBox.RejectRole)
        for botao, nome in ((excluir, "perigo"), (cancelar, "fechar")):  # vermelho / cinza escuro
            botao.setObjectName(nome)
            botao.setCursor(Qt.PointingHandCursor)
            botao.style().unpolish(botao)  # reaplica o QSS com o novo objectName
            botao.style().polish(botao)
        caixa.setDefaultButton(cancelar)  # Enter não exclui por engano
        caixa.setEscapeButton(cancelar)
        caixa.exec()
        return caixa.clickedButton() is excluir

    def excluir_pagina(self, aba: AbaDocumento, i: int):
        """Exclui a página i. O documento continua em memória (o arquivo só muda ao
        salvar): a aba é refeita, no mesmo lugar, a partir do conteúdo sem a página."""
        if aba not in self.abas:
            return
        if aba.doc.tem_assinaturas:
            aba.toast("Documento assinado: não é possível excluir páginas (as assinaturas seriam invalidadas)", 3200)
            return
        n = aba.doc.n_paginas
        if n <= 1:
            aba.toast("O documento precisa ter pelo menos uma página", 2500)
            return
        if not self._confirmar_exclusao(i):
            return
        v = aba.visualizador
        antes = aba.retrato()  # para o Ctrl+Z
        try:
            dados = aba.doc.sem_pagina(i, v.rotacoes())
            pendencias = [p for p in self._pendencias(aba) if p != "páginas excluídas"] + ["páginas excluídas"]
            doc = Documento(str(aba.doc.caminho), aba.doc.senha, dados=dados, pendencias=pendencias)
        except Exception as e:
            QMessageBox.critical(self, NOME_APP, f"Não foi possível excluir a página:\n{e}")
            return
        atual = v.pagina_atual
        atual = min(atual - 1 if i < atual else atual, n - 2)
        nova = self._substituir_aba(aba, doc, aba.historico + [antes], atual)
        nova.toast(f"Página {i + 1} Excluída")
        self._atualizar_estado()

    def _substituir_aba(self, aba: AbaDocumento, doc: Documento, historico: list, pagina: int,
                        rotacao: tuple | None = None) -> AbaDocumento:
        """Refaz a aba, no mesmo lugar, com outro conteúdo (excluir página / desfazer):
        continua de onde estava - mesmo painel, zoom, página e histórico do Ctrl+Z."""
        v = aba.visualizador
        painel, ajuste, zoom = aba.painel, v.ajuste, v.zoom
        indice = self.abas.index(aba)
        self.fechar_aba(indice, confirmar=False)
        nova = self._criar_aba(doc, indice)
        nova.historico = historico
        if painel:
            nova.mostrar_painel(painel)
        nv = nova.visualizador
        if rotacao is not None:
            QTimer.singleShot(0, lambda: nv.restaurar_edicao(rotacao))
        if ajuste:
            QTimer.singleShot(0, lambda: nv.ajustar(*ajuste))
        else:
            QTimer.singleShot(0, lambda: nv.definir_zoom(zoom, manual=True))
        QTimer.singleShot(0, lambda: nv.ir_para_pagina(min(pagina, doc.n_paginas - 1)))
        return nova

    def desfazer(self):
        """Ctrl+Z: volta o documento ao estado anterior à última alteração (destaque,
        cor, remoção de destaque, giro ou exclusão de página)."""
        aba = self.aba_atual()
        if not aba or aba.visualizador.modo == "posicionar":
            return
        if not aba.historico:
            aba.toast("Nada para Desfazer")
            return
        antes = aba.historico.pop()
        if antes["dados"] is aba.doc.dados:
            # mesmo conteúdo: só destaques e rotação mudaram - restaura na própria aba
            aba.doc.pendencias_herdadas = list(antes["pendencias"])
            aba.doc.restaurar_edicao(antes["edicao"])
            aba.visualizador.restaurar_edicao(antes["rotacao"])
        else:
            # desfaz uma exclusão de página: reabre o conteúdo de antes
            try:
                doc = Documento(str(aba.doc.caminho), aba.doc.senha, dados=antes["dados"],
                                pendencias=antes["pendencias"])
                doc.restaurar_edicao(antes["edicao"])
            except Exception as e:
                QMessageBox.critical(self, NOME_APP, f"Não foi possível desfazer:\n{e}")
                return
            aba = self._substituir_aba(aba, doc, aba.historico, aba.visualizador.pagina_atual,
                                       antes["rotacao"])
        aba.toast("Alteração Desfeita")
        self._atualizar_estado()

    def _cor_destaque_escolhida(self, cor: str):
        self.config.set("destaque/cor", cor)
        for aba in self.abas:
            aba.visualizador.definir_cor_destaque(cor)

    @staticmethod
    def _salvar_bloqueado(aba) -> bool:
        return bool(aba and aba.doc.tem_assinaturas and (aba.visualizador.rotacoes() or aba.doc.destaques_editados))

    def salvar_copia(self, aba=None):
        """Salva a aba (a atual, por padrão). Devolve a aba com o documento salvo -
        uma nova, quando salvar no próprio arquivo recarrega - ou None se não salvou."""
        aba = aba or self.aba_atual()
        if not aba:
            return None
        if self._salvar_bloqueado(aba):  # também pelo Ctrl+S
            aba.toast("Documento assinado: não é possível salvar com páginas giradas ou texto destacado", 3000)
            return None
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar uma Cópia", str(aba.doc.caminho),
                                                 "Documentos PDF (*.pdf)")
        if not destino:
            return None
        # grava o documento como está na tela (páginas giradas e destaques incluídos)
        rotacoes = aba.visualizador.rotacoes()
        editado = bool(rotacoes or aba.doc.destaques_editados)
        try:
            Path(destino).write_bytes(aba.doc.bytes_editados(rotacoes))
        except Exception as e:
            QMessageBox.critical(self, NOME_APP, f"Não foi possível salvar:\n{e}")
            return None
        aba.doc.marcar_salvo()
        aba.visualizador.marcar_rotacoes_salvas()
        mesmo_arquivo = Path(destino).resolve() == aba.doc.caminho.resolve()
        if mesmo_arquivo and editado:
            # recarrega: o que está na tela passa a ser exatamente o arquivo salvo
            painel = aba.painel
            self.fechar_aba(self.abas.index(aba), confirmar=False)
            aba = self.abrir_arquivo(destino, painel=painel or "")
        if aba:
            aba.toast("Documento salvo" if mesmo_arquivo else "Cópia salva")
        return aba

    # ================================================================== busca / impressão
    def buscar(self):
        aba = self.aba_atual()
        if aba:
            aba.buscar()

    def imprimir(self):
        """Janela própria + envio em segundo plano: uma impressora inacessível
        (ex.: rede/WSD desligada) não trava mais o NuPDF - ver impressao.py."""
        aba = self.aba_atual()
        if not aba:
            return
        from .impressao import DialogoImpressao, TrabalhoImpressao
        v = aba.visualizador
        dlg = DialogoImpressao(aba.doc.n_paginas, v.pagina_atual,
                               self.config.get("impressao/impressora", ""), self)
        if dlg.exec() != QDialog.Accepted:
            return
        self.config.set("impressao/impressora", dlg.nome_impressora)
        trabalho = TrabalhoImpressao(
            aba.doc.bytes_editados(v.rotacoes()),  # imprime como está na tela
            aba.doc.senha, dlg.paginas, dlg.nome_impressora, dlg.copias.value(), aba.doc.nome)
        prog = QProgressDialog(f"Conectando à impressora {dlg.nome_impressora}…", "Cancelar",
                               0, len(dlg.paginas), self)
        prog.setWindowTitle("Imprimir")
        bt_cancelar = QPushButton("Cancelar")
        bt_cancelar.setObjectName("fechar")  # cinza escuro, mesmo visual do "Fechar"
        bt_cancelar.setCursor(Qt.PointingHandCursor)
        prog.setCancelButton(bt_cancelar)
        prog.setWindowModality(Qt.NonModal)  # o NuPDF continua utilizável durante a impressão
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        prog.canceled.connect(trabalho.cancelar)

        def andamento(feitas, total):
            prog.setLabelText(f"Enviando para {dlg.nome_impressora}… ({feitas} de {total})")
            prog.setValue(feitas)

        def ok():
            prog.close()
            if not prog.wasCanceled():
                aba.toast("Documento enviado para a impressora", 2500)

        def erro(msg):
            prog.close()
            QMessageBox.warning(self, NOME_APP, f"Não foi possível imprimir em {dlg.nome_impressora}:\n\n{msg}")

        trabalho.progresso.connect(andamento)
        trabalho.concluido.connect(ok)
        trabalho.falhou.connect(erro)
        self._impressoes = getattr(self, "_impressoes", set())
        self._impressoes.add(trabalho)
        trabalho.finished.connect(lambda: self._impressoes.discard(trabalho))
        prog.show()
        trabalho.start()

    # ================================================================== assinatura
    def assinar(self):
        aba = self.aba_atual()
        if not aba:
            return
        from .dialogos import DialogoAssinatura
        dlg = DialogoAssinatura(self.config, self)
        if dlg.exec() != DialogoAssinatura.Accepted:
            return
        cfg = dlg.config_assinatura()
        if cfg.visivel:
            aba.cfg_pendente = cfg
            aba.mostrar_aviso("Clique ou Arraste na Página para Posicionar a Assinatura   •   ESC - Cancela")
            aba.visualizador.iniciar_posicionamento()
        else:
            self._executar_assinatura(aba, cfg)

    def _posicionamento_cancelado(self, aba: AbaDocumento):
        aba.cfg_pendente = None
        aba.esconder_aviso()

    def _posicionado(self, aba: AbaDocumento, pagina: int, r: pymupdf.Rect):
        aba.esconder_aviso()
        cfg, aba.cfg_pendente = aba.cfg_pendente, None
        if cfg is None:
            return
        pg = aba.doc.doc[pagina]
        pdf = (r * ~pg.transformation_matrix).normalize()
        cfg.pagina = pagina
        cfg.rotacao = pg.rotation
        cfg.caixa = (pdf.x0, pdf.y0, pdf.x1, pdf.y1)
        self._executar_assinatura(aba, cfg)

    def _executar_assinatura(self, aba: AbaDocumento, cfg):
        orig = aba.doc.caminho
        sugerido = orig.with_name(f"{orig.stem}_assinado.pdf")
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar documento assinado", str(sugerido),
                                                 "Documentos PDF (*.pdf)")
        if not destino:
            return
        destino = Path(destino)
        prog = QProgressDialog("Assinando documento…", None, 0, 0, self)
        prog.setWindowTitle(NOME_APP)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.show()

        from .assinatura.assinador import assinar_pdf
        tarefa = ui.Tarefa(assinar_pdf, aba.doc.dados, cfg, aba.doc.senha)

        def ok(dados: bytes):
            prog.close()
            try:
                destino.write_bytes(dados)
            except OSError as e:
                QMessageBox.critical(self, NOME_APP, f"Documento assinado, mas não foi possível salvar em:\n"
                                                     f"{destino}\n\n{e}")
                return
            # se sobrescreveu o próprio arquivo aberto, recarrega a aba
            if aba in self.abas and aba.doc.caminho.resolve() == destino.resolve():
                self.fechar_aba(self.abas.index(aba), confirmar=False)
            nova = self.abrir_arquivo(str(destino), painel="assinaturas")
            if nova:
                nova.toast("Documento assinado com sucesso", 2500)

        def erro(msg: str):
            prog.close()
            QMessageBox.critical(self, "Falha na assinatura", msg)

        tarefa.concluida.connect(ok)
        tarefa.falhou.connect(erro)
        tarefa.start()

    # ================================================================== diversos
    def alternar_tema(self):
        self.escuro = not self.escuro
        self.config.set("tema_escuro", self.escuro)
        ui.definir_cores(tema.paleta(self.escuro))
        tema.aplicar(QApplication.instance(), self.escuro)
        ui.aplicar_icone(self.b_tema, "sol" if self.escuro else "lua")
        for aba in self.abas:
            aba.atualizar_cores()
        for i in range(self.tabbar.count()):
            self.tabbar.setTabIcon(i, icone("arquivo", ui.cores()["texto2"], 14))

    def verificar_atualizacoes(self):
        from .dialogo_atualizacao import DialogoAtualizacao
        DialogoAtualizacao(self).exec()

    # ------------------------------------------------------------------ leitor padrão
    def _conferir_leitor_padrao(self):
        self.b_padrao.setVisible(leitor_padrao.e_padrao() is False)

    def definir_leitor_padrao(self):
        leitor_padrao.DialogoLeitorPadrao(self).exec()
        self._conferir_leitor_padrao()

    def changeEvent(self, e):
        # a escolha pode mudar fora do NuPDF (Configurações, "Abrir com"): confere ao voltar
        if e.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._conferir_leitor_padrao()
        super().changeEvent(e)

    # ------------------------------------------------------------------ atualização diária
    INTERVALO_VERIFICACAO = 24 * 60 * 60  # segundos

    def _checar_atualizacao_diaria(self):
        import time
        from . import atualizacao

        try:
            ultima = float(self.config.get("atualizacao/ultima_verificacao", 0) or 0)
        except (TypeError, ValueError):
            ultima = 0
        if time.time() - ultima < self.INTERVALO_VERIFICACAO:
            return
        if getattr(self, "_tarefa_atualizacao", None) is not None and self._tarefa_atualizacao.isRunning():
            return

        def verificar():
            rel = atualizacao.ultima_release()
            return rel if atualizacao.eh_mais_nova(rel.versao) else None

        self._tarefa_atualizacao = ui.Tarefa(verificar)
        self._tarefa_atualizacao.concluida.connect(self._verificacao_concluida)
        self._tarefa_atualizacao.start()  # falha (sem internet etc.) é ignorada: tenta na próxima hora

    def _verificacao_concluida(self, release):
        import time
        self.config.set("atualizacao/ultima_verificacao", time.time())
        self._release_nova = release
        versao = release.versao if release is not None else ""
        self.config.set("atualizacao/versao_disponivel", versao)
        self._mostrar_nova_versao(versao)

    def _mostrar_nova_versao(self, versao: str):
        from . import atualizacao
        if versao and atualizacao.eh_mais_nova(versao):
            self.b_nova_versao.setText(f"Nova Versão {versao} Disponível - Atualizar")
            self.b_nova_versao.setToolTip(f"Baixar e Instalar a Versão {versao} do NuPDF")
            self.b_nova_versao.show()
        else:
            self.b_nova_versao.hide()

    def _atualizar_agora(self):
        from .dialogo_atualizacao import DialogoAtualizacao
        # sem a release em memória (encontrada em outro dia), o diálogo consulta de novo
        DialogoAtualizacao(self, release=self._release_nova, iniciar=True).exec()

    def _tela_cheia(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _sobre(self):
        caixa = QMessageBox(self)
        caixa.setWindowTitle(f"Sobre o {NOME_APP}")
        caixa.setIconPixmap(pixmap_logo(64))
        descricao = "Leia PDFs, Copie Dados e Assine Digitalmente com Certificado ICP-Brasil."
        caixa.setText(
            f"<h3>{NOME_APP} {VERSAO}</h3>"
            f'<p style="white-space:nowrap;">{descricao}</p>'
            "<p>Componentes: PySide6 (Qt), PyMuPDF, pyHanko.</p>")
        # a caixa padrão limita a largura do texto; alarga para a descrição caber numa linha
        rotulo = caixa.findChild(QLabel, "qt_msgbox_label")
        if rotulo is not None:
            rotulo.setMinimumWidth(rotulo.fontMetrics().horizontalAdvance(descricao) + 24)
        ok = caixa.addButton(QMessageBox.Ok)
        ok.setObjectName("primario")  # cor de destaque, como os demais botões principais
        ok.style().unpolish(ok)  # reaplica o QSS com o novo objectName
        ok.style().polish(ok)
        ok.setMinimumWidth(90)
        ok.setCursor(Qt.PointingHandCursor)
        caixa.exec()

    # ================================================================== arrastar e soltar
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".pdf") for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            c = u.toLocalFile()
            if c.lower().endswith(".pdf"):
                self.abrir_arquivo(c)

    def closeEvent(self, e):
        # alterações não salvas: pergunta aba por aba (Fechar/Esc mantém o NuPDF aberto)
        for aba in [a for a in self.abas if self._pendencias(a)]:
            resposta = self._perguntar_alteracoes(aba)
            if resposta == "cancelar" or (resposta == "salvar" and self.salvar_copia(aba) is None):
                e.ignore()
                return
        for aba in self.abas:
            aba.doc.fechar()
        super().closeEvent(e)
