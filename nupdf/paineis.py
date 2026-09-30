"""Painéis laterais: miniaturas, propriedades do documento e assinaturas digitais."""

import re

import pymupdf
from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QMenu, QMessageBox,
                               QListWidgetItem, QPushButton, QScrollArea, QToolButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import ui
from .documento import CORES_DESTAQUE, Documento
from .icones import icone


def _cabecalho(titulo: str, maiusculas: bool = True) -> QLabel:
    lb = QLabel(titulo.upper() if maiusculas else titulo)
    lb.setObjectName("tituloPainel")
    return lb


class PainelMiniaturas(QWidget):
    paginaEscolhida = Signal(int)
    girarPagina = Signal(int)  # botões sobre a miniatura / menu do botão direito
    excluirPagina = Signal(int)
    LARGURA = 128
    ALTURA = 182  # caixa fixa (retrato A4): girar não muda o tamanho do item

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
        self.lista.setIconSize(QSize(self.LARGURA, self.ALTURA))
        self.lista.setSpacing(4)
        self.lista.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # só rolagem vertical
        lay.addWidget(self.lista, 1)
        branco = QPixmap(self.LARGURA, self.ALTURA)
        branco.fill(QColor("#ffffff"))
        for i in range(doc.n_paginas):
            it = QListWidgetItem(QIcon(branco), str(i + 1))
            it.setTextAlignment(Qt.AlignHCenter)
            self.lista.addItem(it)
        self.lista.currentRowChanged.connect(self._escolhida)
        self._proxima = 0
        self._timer = QTimer(self, interval=0, timeout=self._renderizar_lote)
        self._bloquear = False
        # rotação da visualização de cada página (a aba liga ao visualizador) e a
        # rotação com que cada miniatura foi desenhada
        self.rotacao_de = lambda i: 0
        self._rot_desenhada: dict[int, int] = {}
        # botão "girar" que aparece sobre a miniatura sob o mouse
        # botões "girar" e "excluir" que aparecem sobre a miniatura sob o mouse
        self._botoes = QWidget(self.lista.viewport())
        bl = QHBoxLayout(self._botoes)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)
        # ícones brancos fixos sobre fundo colorido (fora do ui.botao, que repinta
        # os ícones na cor do tema ao alternar claro/escuro)
        self._bt_excluir = QToolButton()
        self._bt_excluir.setObjectName("miniExcluir")  # vermelho
        self._bt_girar = QToolButton()
        self._bt_girar.setObjectName("miniGirar")  # cinza escuro
        for bt, nome in ((self._bt_excluir, "lixeira"), (self._bt_girar, "girar")):
            bt.setIcon(icone(nome, "#ffffff", 16))
            bt.setIconSize(QSize(16, 16))
            bt.setCursor(Qt.PointingHandCursor)
            bl.addWidget(bt)
        self._botoes.hide()
        self._bt_girar.clicked.connect(lambda: self._pagina_do_botao >= 0 and self.girarPagina.emit(self._pagina_do_botao))
        self._bt_excluir.clicked.connect(self._excluir_sob_mouse)
        self._pagina_do_botao = -1
        self.lista.viewport().setMouseTracking(True)
        self.lista.viewport().installEventFilter(self)
        self.lista.verticalScrollBar().valueChanged.connect(lambda _: self._botoes.hide())
        self.lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu)

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
            self._desenhar(i, dpr)
            self._proxima += 1

    def _desenhar(self, i: int, dpr: float | None = None):
        dpr = dpr or self.devicePixelRatioF()
        rot = self.rotacao_de(i) % 360
        try:
            pg = self.doc.doc[i]
            # tamanho como aparece na tela, encaixado na caixa fixa da miniatura
            larg, alt = (pg.rect.width, pg.rect.height) if rot in (0, 180) else (pg.rect.height, pg.rect.width)
            s = min(self.LARGURA / max(larg, 1), self.ALTURA / max(alt, 1)) * dpr
            pm = pg.get_pixmap(matrix=pymupdf.Matrix(s, s).prerotate(rot), alpha=False)
            img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888).copy()
            # a imagem vai centralizada numa tela transparente sempre do mesmo tamanho: o
            # item nunca muda de tamanho, então a lista não precisa refazer o layout (sem
            # isso, girar deixava o desenho antigo sobreposto ao novo)
            tela = QPixmap(round(self.LARGURA * dpr), round(self.ALTURA * dpr))
            tela.fill(Qt.transparent)
            p = QPainter(tela)
            p.drawImage((tela.width() - img.width()) // 2, (tela.height() - img.height()) // 2, img)
            p.end()
            tela.setDevicePixelRatio(dpr)
            self.lista.item(i).setIcon(QIcon(tela))
            self._rot_desenhada[i] = rot
        except Exception:
            pass

    def rotacao_mudou(self):
        """Redesenha só as miniaturas já desenhadas cuja rotação mudou."""
        for i, rot in list(self._rot_desenhada.items()):
            if self.rotacao_de(i) % 360 != rot:
                self._desenhar(i)
        self.lista.viewport().update()

    # ------------------------------------------------------------------ girar
    def eventFilter(self, obj, e):
        if obj is self.lista.viewport():
            if e.type() == QEvent.MouseMove:
                self._mostrar_botao(e.position().toPoint())
            elif e.type() == QEvent.Leave and not self._botoes.underMouse():
                self._botoes.hide()
        return super().eventFilter(obj, e)

    def _mostrar_botao(self, pos: QPoint):
        it = self.lista.itemAt(pos)
        if it is None:
            self._botoes.hide()
            return
        i = self.lista.row(it)
        r = self.lista.visualItemRect(it)
        bt = self._botoes
        bt.adjustSize()
        bt.move(r.center().x() - bt.width() // 2, r.top() + 6)  # centralizados no topo da miniatura
        self._pagina_do_botao = i
        self._bt_girar.setToolTip(f"Girar Página {i + 1}")
        self._bt_excluir.setToolTip(f"Excluir Página {i + 1}")
        bt.raise_()
        bt.show()

    def _excluir_sob_mouse(self):
        i = self._pagina_do_botao
        self._botoes.hide()
        if i >= 0:
            self.excluirPagina.emit(i)

    def _menu(self, pos: QPoint):
        it = self.lista.itemAt(pos)
        if it is None:
            return
        i = self.lista.row(it)
        m = QMenu(self)
        girar = m.addAction(f"Girar Página {i + 1}")
        excluir = m.addAction(f"Excluir Página {i + 1}")
        esc = m.exec(self.lista.viewport().mapToGlobal(pos))
        if esc is girar:
            self.girarPagina.emit(i)
        elif esc is excluir:
            self.excluirPagina.emit(i)

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
    def __init__(self, r, ao_confiar=None):
        super().__init__()
        self.setObjectName("cartao")
        self.campo = r.campo
        c = ui.cores()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)
        # assinatura válida não ganha selo; ressalvas e erros continuam em destaque
        if r.nivel != "ok":
            topo = QHBoxLayout()
            topo.setSpacing(8)
            nome_ic, cor, status, obj = {
                "aviso": ("escudo_alerta", c["aviso"], "Válida, com ressalvas", "statusAviso"),
                "erro": ("escudo_x", c["erro"], "Assinatura inválida", "statusErro"),
            }[r.nivel]
            ic = QLabel()
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
        if not r.confiavel and r.topo_cadeia_der and ao_confiar:
            # como o "Adicionar a certificados confiáveis" do Adobe
            confiar = QPushButton("Confiar nesta Cadeia")
            confiar.setObjectName("linkCartao")
            confiar.setCursor(Qt.PointingHandCursor)
            confiar.setToolTip(f"Passar a confiar em: {r.topo_cadeia_nome}")
            confiar.clicked.connect(lambda: ao_confiar(r))
            lay.addWidget(confiar, 0, Qt.AlignLeft)


class _ItemDestaque(QFrame):
    """Um campo destacado: texto (até 2 linhas) e página; clicar leva até ele."""

    def __init__(self, d: dict, cor_hex: str, ao_clicar):
        super().__init__()
        self.setObjectName("itemDestaque")
        self.setAttribute(Qt.WA_Hover)  # :hover do QSS
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"#itemDestaque {{ border-left: 4px solid {cor_hex}; }}")
        self._ao_clicar, self._d = ao_clicar, d
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(1)
        texto = d["texto"] if len(d["texto"]) <= 110 else d["texto"][:107].rstrip() + "…"
        rotulo = QLabel(texto)
        rotulo.setWordWrap(True)
        rotulo.setAttribute(Qt.WA_TransparentForMouseEvents)
        pagina = QLabel(f"Página {d['pagina'] + 1}")
        pagina.setObjectName("sub3")
        pagina.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(rotulo)
        lay.addWidget(pagina)
        self.setToolTip(d["texto"])

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._ao_clicar(self._d)
        super().mouseReleaseEvent(e)


class PainelDestaques(QWidget):
    """Campos destacados (marca-texto) do documento, agrupados por cor/prioridade."""

    destaqueEscolhido = Signal(int, object)  # página, área (pymupdf.Rect)
    ORDEM = ("vermelho", "amarelo", "azul", "verde")  # alta, média, baixa, resolvido

    def __init__(self, doc: Documento):
        super().__init__()
        self.doc = doc
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(_cabecalho("Campos Destacados", maiusculas=False))
        self.status = QLabel("")
        self.status.setObjectName("sub")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setStyleSheet("QScrollArea { background: transparent; }")
        self.conteudo = QWidget()
        self.conteudo.setStyleSheet("background: transparent;")
        self.lista = QVBoxLayout(self.conteudo)
        self.lista.setContentsMargins(0, 0, 4, 0)
        self.lista.setSpacing(6)
        self.lista.addStretch(1)
        area.setWidget(self.conteudo)
        lay.addWidget(area, 1)

    def carregar(self):
        while self.lista.count() > 1:
            w = self.lista.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        itens = self.doc.listar_destaques()
        n = len(itens)
        self.status.setText("Nenhum Campo Destacado." if not n else
                            f"{n} Campo{'s' if n > 1 else ''} Destacado{'s' if n > 1 else ''}.")
        grupos: dict = {}
        for d in itens:
            grupos.setdefault(d["cor"] if d["cor"] in CORES_DESTAQUE else None, []).append(d)
        for cor in (*self.ORDEM, None):
            if cor not in grupos:
                continue
            if cor:
                rotulo, rgb = CORES_DESTAQUE[cor]
            else:
                rotulo, rgb = "Outras Cores", (0.6, 0.6, 0.6)
            cor_hex = "#%02x%02x%02x" % tuple(round(c * 255) for c in rgb)
            titulo = QLabel(f"{rotulo} ({len(grupos[cor])})")
            titulo.setObjectName("cartaoTitulo")
            titulo.setContentsMargins(0, 6, 0, 0)
            self.lista.insertWidget(self.lista.count() - 1, titulo)
            for d in grupos[cor]:
                rgb_item = d["rgb"] or rgb
                hex_item = cor_hex if cor else "#%02x%02x%02x" % tuple(round(c * 255) for c in rgb_item)
                self.lista.insertWidget(self.lista.count() - 1, _ItemDestaque(
                    d, hex_item, lambda d: self.destaqueEscolhido.emit(d["pagina"], d["area"])))


class PainelAssinaturas(QWidget):
    # sem botão "Assinar" aqui: a ação fica na barra de ferramentas

    def __init__(self, doc: Documento):
        super().__init__()
        self.doc = doc
        self._carregado = False
        self._resultados = None
        self._destaque = None  # campo da assinatura clicada na página
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(_cabecalho("Assinaturas Digitais", maiusculas=False))
        self.status = QLabel("")
        self.status.setObjectName("sub")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        area = self._area = QScrollArea()
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
        # cadeia oficial do ITI (o instalador já baixa; aqui atualiza quando surgem ACs novas)
        self.b_cadeia = QPushButton("Atualizar Cadeia ICP-Brasil")
        self.b_cadeia.setObjectName("linkPequeno")
        self.b_cadeia.setCursor(Qt.PointingHandCursor)
        self.b_cadeia.setToolTip("Baixar novamente a cadeia de certificados oficial da ICP-Brasil (ITI)")
        self.b_cadeia.clicked.connect(self._atualizar_cadeia)
        lay.addWidget(self.b_cadeia, 0, Qt.AlignHCenter)

    def _atualizar_cadeia(self):
        from .assinatura import cadeia_icp
        self.b_cadeia.setEnabled(False)
        self.b_cadeia.setText("Baixando a Cadeia ICP-Brasil…")
        self._tarefa_cadeia = ui.Tarefa(cadeia_icp.atualizar)

        def fim(texto: str):
            self.b_cadeia.setEnabled(True)
            self.b_cadeia.setText("Atualizar Cadeia ICP-Brasil")
            self.status.setText(texto)

        def ok(n):
            fim(f"Cadeia ICP-Brasil atualizada ({n} certificados).")
            QTimer.singleShot(1500, lambda: self.carregar(forcar=True))

        self._tarefa_cadeia.concluida.connect(ok)
        self._tarefa_cadeia.falhou.connect(lambda e: fim(f"Não foi possível atualizar a cadeia: {e}"))
        self._tarefa_cadeia.start()

    def _confiar(self, r):
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Confiar nesta Cadeia")
        caixa.setIcon(QMessageBox.NoIcon)
        caixa.setText(f"Passar a confiar nas assinaturas cuja cadeia chega a:<br><br><b>{r.topo_cadeia_nome}</b>"
                      "<br><br>Vale para todos os documentos, neste computador. Só confirme se você "
                      "conhece e confia nessa autoridade certificadora.")
        sim = caixa.addButton("Confiar", QMessageBox.AcceptRole)
        nao = caixa.addButton("Cancelar", QMessageBox.RejectRole)
        for botao, nome in ((sim, "primario"), (nao, "fechar")):
            botao.setObjectName(nome)
            botao.setCursor(Qt.PointingHandCursor)
            botao.style().unpolish(botao)
            botao.style().polish(botao)
        caixa.setDefaultButton(nao)
        caixa.setEscapeButton(nao)
        caixa.exec()
        if caixa.clickedButton() is sim:
            from .assinatura.validador import confiar
            confiar(r.topo_cadeia_der)
            self.carregar(forcar=True)

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
            self.status.setText("Documento sem Assinatura Digital.")
            return
        n = len(resultados)
        self.status.setText(f"{n} Assinatura{'s' if n > 1 else ''} Encontrada{'s' if n > 1 else ''}.")
        for r in resultados:
            self.lista.insertWidget(self.lista.count() - 1, _CartaoAssinatura(r, self._confiar))
        self._aplicar_destaque()

    def destacar(self, campo: str):
        """Realça o cartão da assinatura clicada (aplicado quando a validação terminar)."""
        self._destaque = campo
        self._aplicar_destaque()

    def _aplicar_destaque(self):
        for k in range(self.lista.count() - 1):
            w = self.lista.itemAt(k).widget()
            if not isinstance(w, _CartaoAssinatura):
                continue
            ativo = bool(self._destaque) and w.campo == self._destaque
            w.setProperty("destaque", ativo)
            w.style().unpolish(w)
            w.style().polish(w)
            if ativo:
                QTimer.singleShot(0, lambda w=w: self._area.ensureWidgetVisible(w))
