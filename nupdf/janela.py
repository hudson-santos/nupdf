"""Janela principal do NuPDF."""

from pathlib import Path

import pymupdf
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QImage, QKeySequence, QPainter
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressDialog, QPushButton,
                               QStackedWidget, QTabBar, QVBoxLayout, QWidget)

from . import tema, ui
from .aba import AbaDocumento
from .config import Config
from .documento import Documento, SenhaNecessaria
from .icones import icone, icone_app, pixmap_logo
from .versao import NOME_APP, VERSAO


class _LinhaRecente(QFrame):
    """Item da lista de recentes: clique abre; o X (visível ao passar o mouse)
    ou o menu do botão direito removem da lista - o arquivo não é apagado."""

    def __init__(self, tela: "TelaInicial", caminho: str):
        super().__init__()
        self.setObjectName("linhaRecente")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.tela, self.caminho = tela, caminho
        p = Path(caminho)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(0)
        abrir = QPushButton(f"  {p.name}   ·   {p.parent.name or p.parent}")
        abrir.setObjectName("link")
        abrir.setToolTip(str(p))
        ui.aplicar_icone(abrir, "arquivo", 16)
        abrir.setCursor(Qt.PointingHandCursor)
        abrir.clicked.connect(lambda: tela.janela.abrir_arquivo(caminho))
        lay.addWidget(abrir, 1)
        self.remover = ui.botao("lixeira", "Remover da lista de recentes", tamanho=15)
        self.remover.clicked.connect(lambda: tela.remover(caminho))
        politica = self.remover.sizePolicy()
        politica.setRetainSizeWhenHidden(True)
        self.remover.setSizePolicy(politica)
        self.remover.hide()
        lay.addWidget(self.remover)

    def enterEvent(self, e):
        self.remover.show()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.remover.hide()
        super().leaveEvent(e)

    def contextMenuEvent(self, e):
        m = QMenu(self)
        a_abrir = m.addAction("Abrir")
        a_remover = m.addAction("Remover da lista")
        m.addSeparator()
        a_limpar = m.addAction("Limpar todos os recentes")
        esc = m.exec(e.globalPos())
        if esc is a_abrir:
            self.tela.janela.abrir_arquivo(self.caminho)
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
        titulo_recentes = QLabel("RECENTES")
        titulo_recentes.setObjectName("tituloPainel")
        cab.addWidget(titulo_recentes)
        cab.addStretch(1)
        limpar = QPushButton("Limpar tudo")
        limpar.setObjectName("linkPequeno")
        limpar.setCursor(Qt.PointingHandCursor)
        limpar.setToolTip("Limpar a lista de arquivos recentes (os arquivos não são apagados)")
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
        QApplication.instance().setStyleSheet(tema.qss(self.escuro))
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
        if verificar_atualizacao:
            # consulta discreta: só destaca o botão, não abre janela sozinha
            QTimer.singleShot(4000, self._checar_atualizacao_em_segundo_plano)

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
        self.b_atualizacao = ui.botao("atualizar", "Verificar atualizações")
        self.b_atualizacao.clicked.connect(self.verificar_atualizacoes)
        lay.addWidget(self.b_atualizacao)
        self.b_tema = ui.botao("sol" if self.escuro else "lua", "Alternar tema claro/escuro")
        self.b_tema.clicked.connect(self.alternar_tema)
        lay.addWidget(self.b_tema)
        sobre = ui.botao("info", "Sobre o NuPDF")
        sobre.clicked.connect(self._sobre)
        lay.addWidget(sobre)
        return topo

    def _criar_ferramentas(self) -> QWidget:
        barra = QFrame()
        barra.setObjectName("ferramentas")
        barra.setFixedHeight(50)
        lay = QHBoxLayout(barra)
        lay.setContentsMargins(12, 0, 14, 0)
        lay.setSpacing(4)

        self.b_abrir = ui.botao("abrir", "Abrir (Ctrl+O)")
        self.b_salvar = ui.botao("salvar", "Salvar uma cópia (Ctrl+S)")
        self.b_imprimir = ui.botao("imprimir", "Imprimir (Ctrl+P)")
        for b in (self.b_abrir, self.b_salvar, self.b_imprimir):
            lay.addWidget(b)
        lay.addStretch(1)

        self.b_cursor = ui.botao("cursor", "Selecionar texto (Alt+arrastar = seleção retangular)", checavel=True)
        self.b_mao = ui.botao("mao", "Mover a página (ou botão do meio do mouse)", checavel=True)
        self.b_cursor.setChecked(True)
        self.b_largura = ui.botao("largura", "Ajustar à largura (Ctrl+1)")
        self.b_pagina = ui.botao("pagina", "Página inteira (Ctrl+2)")
        self.b_girar = ui.botao("girar", "Girar visualização (Ctrl+R)")
        self.b_buscar = ui.botao("buscar", "Buscar (Ctrl+F)")
        for w in (self.b_cursor, self.b_mao, ui.separador_vertical(), self.b_largura, self.b_pagina,
                  self.b_girar, ui.separador_vertical(), self.b_buscar):
            lay.addWidget(w)
        lay.addStretch(1)

        self.b_assinar = QPushButton("  Assinar com Certificado Digital")
        self.b_assinar.setObjectName("primario")
        self.b_assinar.setIcon(icone("assinar", "#ffffff", 16))
        self.b_assinar.setCursor(Qt.PointingHandCursor)
        self.b_assinar.setToolTip("Assinar digitalmente com certificado ICP-Brasil")
        lay.addWidget(self.b_assinar)

        self.b_abrir.clicked.connect(self.abrir_dialogo)
        self.b_salvar.clicked.connect(self.salvar_copia)
        self.b_imprimir.clicked.connect(self.imprimir)
        self.b_cursor.clicked.connect(lambda: self._modo("texto"))
        self.b_mao.clicked.connect(lambda: self._modo("mao"))
        self.b_largura.clicked.connect(lambda: self._no_visualizador(lambda v: v.ajustar("largura")))
        self.b_pagina.clicked.connect(lambda: self._no_visualizador(lambda v: v.ajustar("pagina")))
        self.b_girar.clicked.connect(lambda: self._no_visualizador(lambda v: v.girar()))
        self.b_buscar.clicked.connect(self.buscar)
        self.b_assinar.clicked.connect(self.assinar)
        return barra

    def _criar_trilho(self) -> QWidget:
        trilho = QFrame()
        trilho.setObjectName("trilhoLateral")
        trilho.setFixedWidth(52)
        lay = QVBoxLayout(trilho)
        lay.setContentsMargins(6, 10, 6, 10)
        lay.setSpacing(6)
        self.b_paineis = {}
        for nome, ic, dica in (("miniaturas", "miniaturas", "Páginas"),
                               ("dados", "dados", "Dados do documento (copiar CPF, CNPJ, valores…)"),
                               ("assinaturas", "escudo", "Assinaturas digitais")):
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
        atalho("Ctrl+P", self.imprimir)
        atalho("Ctrl+F", self.buscar)
        atalho(["Ctrl++", "Ctrl+="], lambda: self._no_visualizador(lambda v: v.aproximar()))
        atalho("Ctrl+-", lambda: self._no_visualizador(lambda v: v.afastar()))
        atalho("Ctrl+0", lambda: self._no_visualizador(lambda v: v.definir_zoom(1.0)))
        atalho("Ctrl+1", lambda: self._no_visualizador(lambda v: v.ajustar("largura")))
        atalho("Ctrl+2", lambda: self._no_visualizador(lambda v: v.ajustar("pagina")))
        atalho("Ctrl+R", lambda: self._no_visualizador(lambda v: v.girar()))
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

    def fechar_aba(self, i: int):
        if not (0 <= i < len(self.abas)):
            return
        aba = self.abas.pop(i)
        self.tabbar.removeTab(i)
        self.pilha.removeWidget(aba)
        aba.doc.fechar()
        aba.deleteLater()
        self._aba_trocada(self.tabbar.currentIndex())

    def _atualizar_estado(self):
        aba = self.aba_atual()
        tem = aba is not None
        for b in (self.b_salvar, self.b_imprimir, self.b_cursor, self.b_mao, self.b_largura, self.b_pagina,
                  self.b_girar, self.b_buscar, self.b_assinar, *self.b_paineis.values()):
            b.setEnabled(tem)
        painel = aba.painel if aba else None
        for nome, b in self.b_paineis.items():
            b.setChecked(nome == painel)
        if aba:
            modo = aba.visualizador.modo
            self.b_cursor.setChecked(modo != "mao")
            self.b_mao.setChecked(modo == "mao")
            self.setWindowTitle(f"{aba.doc.nome} — {NOME_APP} - Versão: {VERSAO}")
        else:
            self.setWindowTitle(f"{NOME_APP} - Versão: {VERSAO}")
            self.inicio.atualizar(self.config.recentes())

    def _alternar_painel(self, nome: str):
        aba = self.aba_atual()
        if aba:
            aba.mostrar_painel(nome)
            self.config.set("painel", aba.painel or "")

    def _modo(self, modo: str):
        aba = self.aba_atual()
        if aba:
            aba.visualizador.definir_modo(modo)
        self._atualizar_estado()

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
                    f"{p.name} está protegido por senha.\n{'Senha incorreta. ' if senha else ''}Digite a senha:",
                    QLineEdit.Password)
                if not ok:
                    return None
            except Exception as e:
                QMessageBox.critical(self, NOME_APP, f"Não foi possível abrir o arquivo:\n{p}\n\n{e}")
                return None

        aba = AbaDocumento(doc)
        aba.painelMudou.connect(lambda _: self._atualizar_estado())
        aba.assinaturas.assinar.connect(self.assinar)
        aba.visualizador.retanguloDesenhado.connect(lambda pg, r, a=aba: self._posicionado(a, pg, r))
        aba.visualizador.posicionamentoCancelado.connect(lambda a=aba: self._posicionamento_cancelado(a))
        self.abas.append(aba)
        self.pilha.addWidget(aba)
        idx = self.tabbar.addTab(icone("arquivo", ui.cores()["texto2"], 14), doc.nome)
        self.tabbar.setTabToolTip(idx, str(doc.caminho))
        fechar = ui.botao("fechar", "Fechar (Ctrl+W)", tamanho=12, obj="abaFechar")
        fechar.clicked.connect(lambda _=False, a=aba: self.fechar_aba(self.abas.index(a)) if a in self.abas else None)
        self.tabbar.setTabButton(idx, QTabBar.RightSide, fechar)
        self.faixa_mais.setFixedHeight(self.tabbar.tabRect(idx).height())
        self.tabbar.setCurrentIndex(idx)
        self._aba_trocada(idx)

        self.config.adicionar_recente(str(resolvido))
        self.config.set("ultima_pasta", str(resolvido.parent))
        painel = painel if painel is not None else (self.config.get("painel", "") or None)
        if painel:
            aba.mostrar_painel(painel)
        aba.visualizador._pag.setFocus()
        return aba

    def salvar_copia(self):
        aba = self.aba_atual()
        if not aba:
            return
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar uma cópia", str(aba.doc.caminho),
                                                 "Documentos PDF (*.pdf)")
        if not destino:
            return
        try:
            Path(destino).write_bytes(aba.doc.dados)
            aba.toast("Cópia salva")
        except OSError as e:
            QMessageBox.critical(self, NOME_APP, f"Não foi possível salvar:\n{e}")

    # ================================================================== busca / impressão
    def buscar(self):
        aba = self.aba_atual()
        if aba:
            aba.buscar()

    def imprimir(self):
        aba = self.aba_atual()
        if not aba:
            return
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        doc = aba.doc
        printer = QPrinter(QPrinter.HighResolution)
        printer.setDocName(doc.nome)
        dlg = QPrintDialog(printer, self)
        dlg.setMinMax(1, doc.n_paginas)
        dlg.setFromTo(1, doc.n_paginas)
        if dlg.exec() != QPrintDialog.Accepted:
            return
        ini, fim = printer.fromPage(), printer.toPage()
        paginas = list(range(ini - 1, fim)) if ini > 0 else list(range(doc.n_paginas))
        dpi = min(printer.resolution(), 300)
        prog = QProgressDialog("Enviando para a impressora…", "Cancelar", 0, len(paginas), self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(300)
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, NOME_APP, "Não foi possível iniciar a impressão.")
            return
        try:
            for k, i in enumerate(paginas):
                if prog.wasCanceled():
                    printer.abort()
                    break
                if k:
                    printer.newPage()
                pm = doc.doc[i].get_pixmap(dpi=dpi, alpha=False)
                img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888)
                alvo = painter.viewport()
                escala = min(alvo.width() / img.width(), alvo.height() / img.height())
                w, h = int(img.width() * escala), int(img.height() * escala)
                painter.drawImage(alvo.x() + (alvo.width() - w) // 2, alvo.y() + (alvo.height() - h) // 2,
                                  img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                prog.setValue(k + 1)
                QApplication.processEvents()
        finally:
            painter.end()
            prog.close()

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
            aba.mostrar_aviso("Clique ou arraste na página para posicionar a assinatura   •   Esc cancela")
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
                self.fechar_aba(self.abas.index(aba))
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
        QApplication.instance().setStyleSheet(tema.qss(self.escuro))
        ui.aplicar_icone(self.b_tema, "sol" if self.escuro else "lua")
        for aba in self.abas:
            aba.atualizar_cores()
        for i in range(self.tabbar.count()):
            self.tabbar.setTabIcon(i, icone("arquivo", ui.cores()["texto2"], 14))

    def verificar_atualizacoes(self):
        from .dialogo_atualizacao import DialogoAtualizacao
        DialogoAtualizacao(self).exec()

    def _checar_atualizacao_em_segundo_plano(self):
        from . import atualizacao

        def verificar():
            rel = atualizacao.ultima_release()
            return rel if atualizacao.eh_mais_nova(rel.versao) else None

        self._tarefa_atualizacao = ui.Tarefa(verificar)
        self._tarefa_atualizacao.concluida.connect(self._atualizacao_disponivel)
        self._tarefa_atualizacao.start()  # falha (sem internet etc.) é ignorada em silêncio

    def _atualizacao_disponivel(self, release):
        if release is None:
            return
        ui.aplicar_icone(self.b_atualizacao, "atualizar", chave_cor="destaque")
        self.b_atualizacao.setToolTip(f"Nova versão {release.versao} disponível — clique para atualizar")

    def _tela_cheia(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _sobre(self):
        QMessageBox.about(
            self, f"Sobre o {NOME_APP}",
            f"<h3>{NOME_APP} {VERSAO}</h3>"
            "<p>Leitor de PDF leve para uso corporativo: leitura, cópia de dados e "
            "assinatura digital PAdES com certificados ICP-Brasil (A1 e A3).</p>"
            "<p>Componentes: PySide6 (Qt), PyMuPDF, pyHanko.</p>")

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
        for aba in self.abas:
            aba.doc.fechar()
        super().closeEvent(e)
