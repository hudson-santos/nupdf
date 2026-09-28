"""Visualizador de páginas: renderização sob demanda, zoom, rotação, seleção de
texto, busca, links e desenho do retângulo da assinatura visível.

Coordenadas:
- "página": espaço NÃO rotacionado do PyMuPDF (o mesmo de get_text/search_for).
- "tela": pixels lógicos do widget interno (_Paginas).
Para cada página guardamos a matriz página->tela (rotação da página * zoom *
rotação de visualização) e o deslocamento que normaliza a origem em (0, 0).
"""

import bisect
import time
from collections import OrderedDict

import pymupdf
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QMessageBox, QPushButton, QScrollArea, QWidget

from .documento import COR_PADRAO, CORES_DESTAQUE, Documento
from .icones import icone

MARGEM = 24
ESPACO = 14
ZOOM_MIN, ZOOM_MAX = 0.25, 5.0
PX_POR_PT = 96 / 72
CACHE_MAX_BYTES = 48 * 1024 * 1024  # páginas renderizadas mantidas em memória


class Visualizador(QScrollArea):
    paginaMudou = Signal(int)
    zoomMudou = Signal(float)
    selecaoMudou = Signal(bool)
    retanguloDesenhado = Signal(int, object)  # página, pymupdf.Rect (espaço da página)
    posicionamentoCancelado = Signal()
    copiadoPeloBotao = Signal(str)
    rotacaoMudou = Signal()
    destaqueFeito = Signal()
    destaqueRemovido = Signal()
    corDestaqueAlterada = Signal()
    corDestaqueEscolhida = Signal(str)  # nova cor padrão do "Destacar" (a janela salva)
    assinaturaClicada = Signal(str)  # nome do campo da assinatura visível clicada

    def __init__(self, documento: Documento, cores: dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(False)
        self.doc = documento
        self.cores = cores
        self.zoom = 1.0
        self.rotacao = 0                 # rotação de todas as páginas
        self.rotacao_pagina: dict = {}   # rotação extra de páginas específicas
        self.modo = "texto"          # texto | mao | posicionar
        self.ajuste = ("largura", 1.5)  # (modo, zoom máximo) ou None
        self._cache: OrderedDict = OrderedDict()
        self._cache_bytes = 0
        self._base = []
        for pg in documento.doc:
            self._base.append(((pg.rect * pg.derotation_matrix).normalize(), pg.rotation_matrix))
        self._geo: list = []
        self._topos: list[int] = []
        self._pagina_atual = 0
        self._primeiro_show = True
        # busca
        self.resultados: list[tuple[int, pymupdf.Rect]] = []
        self.resultado_atual = -1
        # seleção: âncora/foco = (pagina, indice_palavra); ou retângulo (pagina, Rect)
        self.sel_ini = None
        self.sel_fim = None
        self.sel_ret = None
        self.destaque_temp = None  # (pagina, Rect) realce momentâneo

        self._pag = _Paginas(self)
        self.setWidget(self._pag)
        # botões "Copiar" e "Destacar" que aparecem junto do texto selecionado
        # (rolam com as páginas)
        self._acoes_sel = QWidget(self._pag)
        acoes = QHBoxLayout(self._acoes_sel)
        acoes.setContentsMargins(0, 0, 0, 0)
        acoes.setSpacing(6)
        self._bt_copiar = QPushButton("  Copiar")
        self._bt_copiar.setObjectName("botaoCopiar")
        self._bt_copiar.setIcon(icone("copiar", "#ffffff", 15))
        self._bt_copiar.setCursor(Qt.PointingHandCursor)
        self._bt_copiar.clicked.connect(self._copiar_pelo_botao)
        # "Destacar" usa a última cor escolhida; a seta ao lado abre as cores
        self.cor_destaque = COR_PADRAO  # a janela restaura a escolha salva nas preferências
        self._bt_destacar = QPushButton("  Destacar")
        self._bt_destacar.setObjectName("botaoCopiar")  # mesmo visual do "Copiar"
        self._bt_destacar.setCursor(Qt.PointingHandCursor)
        self._bt_destacar.clicked.connect(lambda: self._destacar_selecao())
        self._bt_cor = QPushButton()
        self._bt_cor.setObjectName("botaoCopiar")
        self._bt_cor.setIcon(icone("seta_menu", "#ffffff", 14))
        self._bt_cor.setToolTip("Escolher a Cor do Destaque")
        self._bt_cor.setCursor(Qt.PointingHandCursor)
        self._bt_cor.clicked.connect(self._escolher_cor_e_destacar)
        acoes.addWidget(self._bt_copiar)
        acoes.addWidget(self._bt_destacar)
        acoes.addSpacing(-4)  # seta colada ao "Destacar"
        acoes.addWidget(self._bt_cor)
        self._acoes_sel.hide()
        self._atualizar_icone_destacar()
        # "Alterar Cor" e "Remover Destaque": aparecem ao clicar sobre um texto destacado
        self._acoes_destaque = QWidget(self._pag)
        acoes_d = QHBoxLayout(self._acoes_destaque)
        acoes_d.setContentsMargins(0, 0, 0, 0)
        acoes_d.setSpacing(6)
        self._bt_alterar_cor = QPushButton("  Alterar Cor")
        self._bt_alterar_cor.setObjectName("botaoCopiar")
        self._bt_alterar_cor.setCursor(Qt.PointingHandCursor)
        self._bt_alterar_cor.clicked.connect(self._escolher_nova_cor)
        self._bt_remover = QPushButton("  Remover Destaque")
        self._bt_remover.setObjectName("botaoCopiar")
        self._bt_remover.setIcon(icone("lixeira", "#ffffff", 15))
        self._bt_remover.setCursor(Qt.PointingHandCursor)
        self._bt_remover.clicked.connect(lambda: self.remover_destaque())
        acoes_d.addWidget(self._bt_alterar_cor)
        acoes_d.addWidget(self._bt_remover)
        self._acoes_destaque.hide()
        self._destaque_alvo = None
        self._sem_botao_copiar = False
        self.selecaoMudou.connect(self._posicionar_botao_copiar)
        self.verticalScrollBar().valueChanged.connect(self._ao_rolar)
        self._recalcular()

    # ------------------------------------------------------------------ geometria
    def _recalcular(self):
        s = self.zoom * PX_POR_PT
        geos, topos = [], []
        y, larg_max = MARGEM, 0
        for i, (r0, rotm) in enumerate(self._base):
            m = rotm * pymupdf.Matrix(s, s).prerotate(self._rot(i))
            bb = (r0 * m).normalize()
            w, h = max(1, round(bb.width)), max(1, round(bb.height))
            geos.append([QRect(0, y, w, h), m, pymupdf.Point(bb.x0, bb.y0)])
            topos.append(y)
            y += h + ESPACO
            larg_max = max(larg_max, w)
        alt = y - ESPACO + MARGEM
        larg = max(larg_max + 2 * MARGEM, self.viewport().width())
        for g in geos:
            g[0].moveLeft((larg - g[0].width()) // 2)
        self._geo, self._topos = geos, topos
        self._pag.resize(larg, alt)
        self._pag.update()
        self._acoes_destaque.hide()  # zoom/rotação: a posição do clique deixa de valer
        if self._acoes_sel.isVisible():  # zoom/rotação: acompanha o texto selecionado
            self._posicionar_botao_copiar(True)

    def _pagina_em(self, pos: QPointF) -> int:
        if not self._geo:
            return -1
        i = bisect.bisect_right(self._topos, pos.y()) - 1
        i = max(0, min(i, len(self._geo) - 1))
        # no espaço entre páginas escolhe a mais próxima
        if i + 1 < len(self._geo) and pos.y() > self._geo[i][0].bottom():
            meio = (self._geo[i][0].bottom() + self._geo[i + 1][0].top()) / 2
            if pos.y() > meio:
                i += 1
        return i

    def _para_pagina(self, i: int, pos: QPointF) -> pymupdf.Point:
        rect, m, off = self._geo[i]
        return pymupdf.Point(pos.x() - rect.x() + off.x, pos.y() - rect.y() + off.y) * ~m

    def _ponto_tela(self, i: int, pt: pymupdf.Point) -> QPointF:
        rect, m, off = self._geo[i]
        q = pt * m
        return QPointF(q.x - off.x + rect.x(), q.y - off.y + rect.y())

    def _ret_tela(self, i: int, r) -> QRectF:
        rect, m, off = self._geo[i]
        b = (pymupdf.Rect(r) * m).normalize()
        return QRectF(b.x0 - off.x + rect.x(), b.y0 - off.y + rect.y(), b.width, b.height)

    def _visiveis(self, area: QRect) -> range:
        if not self._geo:
            return range(0)
        ini = max(0, bisect.bisect_right(self._topos, area.top()) - 1)
        fim = bisect.bisect_right(self._topos, area.bottom())
        return range(ini, min(fim, len(self._geo)))

    # ------------------------------------------------------------------ render
    def _pixmap(self, i: int) -> QPixmap:
        dpr = self.devicePixelRatioF()
        chave = (i, self.zoom, self._rot(i), dpr)
        pix = self._cache.get(chave)
        if pix is not None:
            self._cache.move_to_end(chave)
            return pix
        s = self.zoom * PX_POR_PT * dpr
        try:
            pm = self.doc.doc[i].get_pixmap(matrix=pymupdf.Matrix(s, s).prerotate(self._rot(i)), alpha=False)
            img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888).copy()
            pix = QPixmap.fromImage(img)
        except Exception:
            r = self._geo[i][0]
            pix = QPixmap(int(r.width() * dpr), int(r.height() * dpr))
            pix.fill(Qt.white)
        pix.setDevicePixelRatio(dpr)
        self._cache[chave] = pix
        self._cache_bytes += pix.width() * pix.height() * 4
        while self._cache_bytes > CACHE_MAX_BYTES and len(self._cache) > 3:
            _, velho = self._cache.popitem(last=False)
            self._cache_bytes -= velho.width() * velho.height() * 4
        return pix

    def _limpar_cache(self):
        self._cache.clear()
        self._cache_bytes = 0

    def atualizar_cores(self, cores: dict):
        self.cores = cores
        self._pag.update()

    # ------------------------------------------------------------------ navegação
    @property
    def pagina_atual(self) -> int:
        return self._pagina_atual

    def _ao_rolar(self):
        if not self._geo:
            return
        y = self.verticalScrollBar().value() + self.viewport().height() * 0.35
        i = max(0, min(bisect.bisect_right(self._topos, y) - 1, len(self._geo) - 1))
        if self.verticalScrollBar().value() >= self.verticalScrollBar().maximum() - 2:
            # no fim do documento a última página pode nunca chegar ao topo
            ultima_visivel = self._visiveis(self._area_visivel())
            if ultima_visivel:
                i = max(i, ultima_visivel[-1]) if self.verticalScrollBar().maximum() > 0 else i
        if i != self._pagina_atual:
            self._pagina_atual = i
            self.paginaMudou.emit(i)

    def _area_visivel(self) -> QRect:
        return QRect(self.horizontalScrollBar().value(), self.verticalScrollBar().value(),
                     self.viewport().width(), self.viewport().height())

    def ir_para_pagina(self, i: int):
        if not self._geo:
            return
        i = max(0, min(i, len(self._geo) - 1))
        self.verticalScrollBar().setValue(self._geo[i][0].top() - ESPACO)
        if i != self._pagina_atual:
            self._pagina_atual = i
            self.paginaMudou.emit(i)

    def mostrar_retangulo(self, i: int, r, realcar=False):
        q = self._ret_tela(i, r)
        c = q.center()
        self.ensureVisible(int(c.x()), int(c.y()), int(q.width() / 2 + 60), int(q.height() / 2 + 120))
        if realcar:
            self.destaque_temp = (i, pymupdf.Rect(r))
            self._pag.update()
            QTimer.singleShot(1600, self._limpar_destaque)

    def _limpar_destaque(self):
        self.destaque_temp = None
        self._pag.update()

    # ------------------------------------------------------------------ zoom / rotação
    def definir_zoom(self, z: float, ancora: QPoint | None = None, manual=True):
        z = max(ZOOM_MIN, min(ZOOM_MAX, z))
        if manual:
            self.ajuste = None
        if abs(z - self.zoom) < 1e-4 or not self._geo:
            return
        if ancora is None:
            ancora = QPoint(self.viewport().width() // 2, self.viewport().height() // 3)
        conteudo = QPointF(ancora) + QPointF(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        i = self._pagina_em(conteudo)
        pt = self._para_pagina(i, conteudo)
        self.zoom = z
        self._limpar_cache()
        self._recalcular()
        novo = self._ponto_tela(i, pt)
        self.horizontalScrollBar().setValue(int(novo.x() - ancora.x()))
        self.verticalScrollBar().setValue(int(novo.y() - ancora.y()))
        self.zoomMudou.emit(z)

    def aproximar(self):
        self.definir_zoom(self.zoom * 1.2)

    def afastar(self):
        self.definir_zoom(self.zoom / 1.2)

    def _zoom_de_ajuste(self, modo: str) -> float:
        i = self._pagina_atual
        rect = self._geo[i][0]
        w1, h1 = rect.width() / self.zoom, rect.height() / self.zoom
        largura = (self.viewport().width() - 2 * MARGEM) / w1
        if modo == "largura":
            return largura
        return min(largura, (self.viewport().height() - 2 * ESPACO) / h1)

    def ajustar(self, modo: str, maximo: float = ZOOM_MAX):
        if not self._geo:
            return
        self.ajuste = (modo, maximo)
        i = self._pagina_atual
        self.definir_zoom(min(self._zoom_de_ajuste(modo), maximo), manual=False)
        self.ir_para_pagina(i)

    def _rot(self, i: int) -> int:
        return (self.rotacao + self.rotacao_pagina.get(i, 0)) % 360

    def girar(self):
        """Gira a visualização de todas as páginas em 90° (sentido horário)."""
        i = self._pagina_atual
        self.rotacao = (self.rotacao + 90) % 360
        self._limpar_cache()
        self._recalcular()
        if self.ajuste:
            self.ajustar(*self.ajuste)
        self.ir_para_pagina(i)
        self.rotacaoMudou.emit()

    def rotacoes(self) -> dict[int, int]:
        """Rotação efetiva (geral + da página) de cada página girada na tela."""
        return {i: self._rot(i) for i in range(len(self._base)) if self._rot(i)}

    def girar_pagina(self, i: int | None = None):
        """Gira só a visualização de uma página (a atual, por padrão) em 90°."""
        i = self._pagina_atual if i is None else i
        if not (0 <= i < len(self._base)):
            return
        self.rotacao_pagina[i] = (self.rotacao_pagina.get(i, 0) + 90) % 360
        self._recalcular()
        self.ir_para_pagina(i)
        self.rotacaoMudou.emit()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            passo = e.angleDelta().y() / 120
            if passo:
                self.definir_zoom(self.zoom * (1.1 ** passo), e.position().toPoint())
            e.accept()
            return
        super().wheelEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._primeiro_show:
            return
        if self.ajuste:
            modo, maximo = self.ajuste
            z = min(self._zoom_de_ajuste(modo), maximo)
            if abs(z - self.zoom) > 0.01:
                self.definir_zoom(z, manual=False)
                return
        self._recalcular()

    def showEvent(self, e):
        super().showEvent(e)
        if self._primeiro_show:
            self._primeiro_show = False
            QTimer.singleShot(0, lambda: self.ajustar(*self.ajuste) if self.ajuste else None)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape and self.modo == "posicionar":
            self.cancelar_posicionamento()
            return
        if e.key() == Qt.Key_Home and not e.modifiers():
            self.ir_para_pagina(0)
            return
        if e.key() == Qt.Key_End and not e.modifiers():
            self.ir_para_pagina(len(self._geo) - 1)
            return
        super().keyPressEvent(e)

    # ------------------------------------------------------------------ modos
    def definir_modo(self, modo: str):
        self.modo = modo
        self._pag.atualizar_cursor()

    def iniciar_posicionamento(self):
        self._modo_retorno = self.modo if self.modo != "posicionar" else "texto"
        self.modo = "posicionar"
        self._pag.ret_assinatura = None
        self._pag.atualizar_cursor()
        self._pag.setFocus()

    def cancelar_posicionamento(self):
        if self.modo == "posicionar":
            self.modo = getattr(self, "_modo_retorno", "texto")
            self._pag.ret_assinatura = None
            self._pag.atualizar_cursor()
            self._pag.update()
            self.posicionamentoCancelado.emit()

    def _concluir_posicionamento(self, i: int, ret_tela: QRectF):
        a = self._para_pagina(i, ret_tela.topLeft())
        b = self._para_pagina(i, ret_tela.bottomRight())
        r = pymupdf.Rect(a, b).normalize()
        self.modo = getattr(self, "_modo_retorno", "texto")
        self._pag.ret_assinatura = None
        self._pag.atualizar_cursor()
        self._pag.update()
        self.retanguloDesenhado.emit(i, r)

    # ------------------------------------------------------------------ busca
    def buscar(self, termo: str) -> int:
        self.resultados, self.resultado_atual = [], -1
        termo = termo.strip()
        if termo:
            for i in range(self.doc.n_paginas):
                for r in self.doc.doc[i].search_for(termo):
                    self.resultados.append((i, r))
            if self.resultados:
                # começa no primeiro resultado a partir da página atual
                self.resultado_atual = next(
                    (k for k, (i, _) in enumerate(self.resultados) if i >= self._pagina_atual), 0)
                self._mostrar_resultado()
        self._pag.update()
        return len(self.resultados)

    def proximo_resultado(self, passo: int = 1):
        if not self.resultados:
            return
        self.resultado_atual = (self.resultado_atual + passo) % len(self.resultados)
        self._mostrar_resultado()
        self._pag.update()

    def _mostrar_resultado(self):
        i, r = self.resultados[self.resultado_atual]
        self.mostrar_retangulo(i, r)

    def limpar_busca(self):
        self.resultados, self.resultado_atual = [], -1
        self._pag.update()

    # ------------------------------------------------------------------ seleção
    def _palavra_em(self, pos: QPointF, estrito=False):
        i = self._pagina_em(pos)
        if i < 0:
            return None
        ws = self.doc.palavras(i)
        if not ws:
            return None
        p = self._para_pagina(i, pos)
        melhor, melhor_d = None, None
        for k, w in enumerate(ws):
            dx = 0 if w[0] <= p.x <= w[2] else min(abs(p.x - w[0]), abs(p.x - w[2]))
            dy = 0 if w[1] <= p.y <= w[3] else min(abs(p.y - w[1]), abs(p.y - w[3]))
            if estrito and (dx or dy):
                continue
            d = dy * 4 + dx
            if melhor_d is None or d < melhor_d:
                melhor, melhor_d = k, d
        return None if melhor is None else (i, melhor)

    def tem_selecao(self) -> bool:
        return bool(self.sel_ret or (self.sel_ini and self.sel_fim))

    def limpar_selecao(self):
        tinha = self.tem_selecao()
        self.sel_ini = self.sel_fim = self.sel_ret = None
        self._pag.update()
        if tinha:
            self.selecaoMudou.emit(False)

    def _selecao_na_pagina(self, i: int):
        ws = self.doc.palavras(i)
        if self.sel_ret:
            pg, r = self.sel_ret
            if pg != i:
                return []
            return [k for k, w in enumerate(ws)
                    if r.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))]
        if not (self.sel_ini and self.sel_fim):
            return []
        a, b = sorted([self.sel_ini, self.sel_fim])
        if i < a[0] or i > b[0] or not ws:
            return []
        ini = a[1] if i == a[0] else 0
        fim = b[1] if i == b[0] else len(ws) - 1
        return range(ini, fim + 1)

    def _paginas_selecionadas(self) -> range:
        if self.sel_ret:
            return range(self.sel_ret[0], self.sel_ret[0] + 1)
        if not (self.sel_ini and self.sel_fim):
            return range(0)
        a, b = sorted([self.sel_ini, self.sel_fim])
        return range(a[0], b[0] + 1)

    def texto_selecionado(self) -> str:
        partes, ant = [], None
        for i in self._paginas_selecionadas():
            ws = self.doc.palavras(i)
            for k in self._selecao_na_pagina(i):
                w = ws[k]
                if ant is None:
                    partes.append(w[4])
                elif ant[0] == i and ant[1][5] == w[5]:
                    partes.append(" " + w[4])
                else:
                    partes.append("\n" + w[4])
                ant = (i, w)
        return "".join(partes)

    def selecionar_tudo(self):
        n = self.doc.n_paginas
        ultima = next((i for i in range(n - 1, -1, -1) if self.doc.palavras(i)), None)
        primeira = next((i for i in range(n) if self.doc.palavras(i)), None)
        if primeira is None:
            return
        self.sel_ret = None
        self.sel_ini = (primeira, 0)
        self.sel_fim = (ultima, len(self.doc.palavras(ultima)) - 1)
        self._pag.update()
        self._sem_botao_copiar = True  # documento inteiro: Ctrl+C basta
        self.selecaoMudou.emit(True)
        self._sem_botao_copiar = False

    def copiar(self) -> str:
        texto = self.texto_selecionado()
        if texto:
            QGuiApplication.clipboard().setText(texto)
        return texto

    def _copiar_pelo_botao(self):
        texto = self.copiar()
        self._acoes_sel.hide()
        self._pag.setFocus()
        if texto:
            self.copiadoPeloBotao.emit(texto)

    def linhas_selecionadas(self) -> dict[int, list[pymupdf.Rect]]:
        """Seleção atual como retângulos, um por linha visual, agrupados por página."""
        saida: dict[int, list[pymupdf.Rect]] = {}
        for i in self._paginas_selecionadas():
            ws = self.doc.palavras(i)
            por_linha: dict[int, pymupdf.Rect] = {}
            for k in self._selecao_na_pagina(i):
                w = ws[k]
                r = pymupdf.Rect(w[:4])
                por_linha[w[5]] = por_linha[w[5]] | r if w[5] in por_linha else r
            if por_linha:
                saida[i] = [por_linha[n] for n in sorted(por_linha)]
        return saida

    def _redesenhar_pagina(self, i: int):
        for chave in [c for c in self._cache if c[0] == i]:
            pix = self._cache.pop(chave)
            self._cache_bytes -= pix.width() * pix.height() * 4
        self._pag.update()

    # ------------------------------------------------------------------ cores do destaque
    @staticmethod
    def _hex(rgb) -> str:
        return "#%02x%02x%02x" % tuple(round(c * 255) for c in rgb)

    @staticmethod
    def icone_cor(rgb) -> QIcon:
        """Bolinha na cor do destaque (menus de cores)."""
        pm = QPixmap(14, 14)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor.fromRgbF(*rgb))
        p.setPen(QPen(QColor(0, 0, 0, 70)))
        p.drawEllipse(1, 1, 12, 12)
        p.end()
        return QIcon(pm)

    def preencher_menu_cores(self, m: QMenu, acao: str, atual: str | None = None):
        """Uma opção por cor ("Azul - Prioridade Baixa"...); data = (acao, chave da cor)."""
        for chave, (rotulo, rgb) in CORES_DESTAQUE.items():
            a = m.addAction(self.icone_cor(rgb), rotulo)
            a.setData((acao, chave))
            if chave == atual:
                a.setCheckable(True)
                a.setChecked(True)

    def _escolher_cor(self, botao: QPushButton, acao: str, atual: str | None) -> str | None:
        m = QMenu(self)
        self.preencher_menu_cores(m, acao, atual)
        esc = m.exec(botao.mapToGlobal(QPoint(0, botao.height() + 2)))
        return esc.data()[1] if esc is not None and esc.data() else None

    def _atualizar_icone_destacar(self):
        self._bt_destacar.setIcon(icone("destacar", self._hex(CORES_DESTAQUE[self.cor_destaque][1]), 15))
        self._bt_destacar.setToolTip(f"Destacar em {CORES_DESTAQUE[self.cor_destaque][0]}")

    def definir_cor_destaque(self, cor: str):
        if cor in CORES_DESTAQUE:
            self.cor_destaque = cor
            self._atualizar_icone_destacar()

    # ------------------------------------------------------------------ destacar
    def _destacar_selecao(self, cor: str | None = None):
        if cor and cor != self.cor_destaque:  # a cor escolhida vira a padrão do "Destacar"
            self.definir_cor_destaque(cor)
            self.corDestaqueEscolhida.emit(cor)
        linhas = self.linhas_selecionadas()
        for i, rets in linhas.items():
            self.doc.destacar(i, rets, self.cor_destaque)
            self._redesenhar_pagina(i)
        self._acoes_sel.hide()
        self.limpar_selecao()
        self._pag.setFocus()
        if linhas:
            self.destaqueFeito.emit()

    def _escolher_cor_e_destacar(self):
        cor = self._escolher_cor(self._bt_cor, "destacar", self.cor_destaque)
        if cor:
            self._destacar_selecao(cor)

    # ------------------------------------------------------------------ destaque existente
    def _destaque_em(self, pos: QPointF) -> tuple[int, int] | None:
        """(página, xref) do destaque sob o ponto da tela, se houver."""
        i = self._pagina_em(pos)
        if i < 0 or not self._geo[i][0].contains(pos.toPoint()):
            return None
        xref = self.doc.destaque_em(i, self._para_pagina(i, pos))
        return None if xref is None else (i, xref)

    def _mostrar_acoes_destaque(self, alvo: tuple[int, int], pos: QPointF):
        """ "Alterar Cor" e "Remover Destaque" logo abaixo do ponto clicado sobre o destaque."""
        self._destaque_alvo = alvo
        cor = self.doc.cor_do_destaque(*alvo)
        rgb = CORES_DESTAQUE[cor][1] if cor else (1, 1, 1)
        self._bt_alterar_cor.setIcon(icone("destacar", self._hex(rgb), 15))
        bt = self._acoes_destaque
        bt.adjustSize()
        pag = self._geo[alvo[0]][0]
        x = int(min(max(pos.x() - bt.width() / 2, pag.left() + 4), pag.right() - bt.width() - 4))
        y = int(pos.y() + 14)
        if y + bt.height() > pag.bottom():
            y = int(pos.y() - bt.height() - 14)
        bt.move(x, y)
        bt.raise_()
        bt.show()

    def _escolher_nova_cor(self):
        alvo = self._destaque_alvo
        if alvo:
            cor = self._escolher_cor(self._bt_alterar_cor, "cor", self.doc.cor_do_destaque(*alvo))
            if cor:
                self.mudar_cor_destaque(cor, alvo)

    def mudar_cor_destaque(self, cor: str, alvo: tuple[int, int] | None = None):
        alvo = alvo or self._destaque_alvo
        self._acoes_destaque.hide()
        self._destaque_alvo = None
        if not alvo or cor == self.doc.cor_do_destaque(*alvo):
            return
        self.doc.mudar_cor_destaque(*alvo, cor)
        self._redesenhar_pagina(alvo[0])
        self._pag.setFocus()
        self.corDestaqueAlterada.emit()

    def remover_destaque(self, alvo: tuple[int, int] | None = None):
        alvo = alvo or self._destaque_alvo
        self._acoes_destaque.hide()
        self._destaque_alvo = None
        if not alvo:
            return
        self.doc.remover_destaque(*alvo)
        self._redesenhar_pagina(alvo[0])
        self._pag.setFocus()
        self.destaqueRemovido.emit()

    def _posicionar_botao_copiar(self, tem: bool):
        """Mostra "Copiar" e "Destacar" logo abaixo da última palavra selecionada
        (ou acima, se não couber na página)."""
        bt = self._acoes_sel
        if not tem or self._sem_botao_copiar or self.modo != "texto":
            bt.hide()
            return
        alvo = None
        for i in reversed(self._paginas_selecionadas()):
            ks = list(self._selecao_na_pagina(i))
            if ks:
                alvo = (i, self.doc.palavras(i)[ks[-1]])
                break
        if alvo is None:
            bt.hide()
            return
        i, w = alvo
        q = self._ret_tela(i, w[:4])
        pag = self._geo[i][0]
        bt.adjustSize()
        x = int(min(max(q.left(), pag.left() + 4), pag.right() - bt.width() - 4))
        y = int(q.bottom() + 6)
        if y + bt.height() > pag.bottom():
            y = int(q.top() - bt.height() - 6)
        bt.move(x, y)
        bt.raise_()
        bt.show()

    # ------------------------------------------------------------------ links
    def _link_em(self, pos: QPointF):
        i = self._pagina_em(pos)
        if i < 0 or not self._geo[i][0].contains(pos.toPoint()):
            return None
        p = self._para_pagina(i, pos)
        for ln in self.doc.links(i):
            if pymupdf.Rect(ln["from"]).contains(p):
                return ln
        return None

    def _assinatura_em(self, pos: QPointF) -> str | None:
        """Nome do campo da assinatura visível sob o ponto (None se não houver)."""
        i = self._pagina_em(pos)
        if i < 0 or not self._geo[i][0].contains(pos.toPoint()):
            return None
        p = self._para_pagina(i, pos)
        for r, nome in self.doc.assinaturas_visiveis(i):
            if r.contains(p):
                return nome
        return None

    def _abrir_link(self, ln):
        if ln.get("kind") == pymupdf.LINK_GOTO and ln.get("page", -1) >= 0:
            self.ir_para_pagina(ln["page"])
        elif ln.get("kind") == pymupdf.LINK_URI and ln.get("uri"):
            uri = ln["uri"]
            caixa = QMessageBox(QMessageBox.NoIcon, "Abrir Link Externo",
                                f"O Documento está Tentando Acessar :\n\n{uri}\n\nDeseja Continuar ?", parent=self)
            sim = caixa.addButton("Sim", QMessageBox.YesRole)
            nao = caixa.addButton("Não", QMessageBox.NoRole)
            for botao, nome in ((sim, "primario"), (nao, "fechar")):  # laranja / cinza do "Fechar"
                botao.setObjectName(nome)
                botao.setCursor(Qt.PointingHandCursor)
                botao.style().unpolish(botao)  # reaplica o QSS com o novo objectName
                botao.style().polish(botao)
            caixa.setDefaultButton(sim)
            caixa.setEscapeButton(nao)
            caixa.exec()
            if caixa.clickedButton() is sim:
                QDesktopServices.openUrl(QUrl(uri))


class _Paginas(QWidget):
    """Widget interno que desenha as páginas e trata o mouse."""

    def __init__(self, v: Visualizador):
        super().__init__()
        self.v = v
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._press = None
        self._arrastou = False
        self._ancora = None
        self._ret_ini = None
        self._pan = None
        self._t_duplo = 0.0
        self.ret_assinatura = None  # (pagina, QRectF)
        self.atualizar_cursor()

    def atualizar_cursor(self):
        modo = self.v.modo
        self.setCursor({"mao": Qt.OpenHandCursor, "posicionar": Qt.CrossCursor}.get(modo, Qt.IBeamCursor))

    # ---------------------------------------------------------------- pintura
    def paintEvent(self, ev):
        v, c = self.v, self.v.cores
        p = QPainter(self)
        p.fillRect(ev.rect(), QColor(c["canvas"]))
        cor_sel = QColor(c["selecao"])
        cor_sel.setAlpha(80)
        cor_busca = QColor(255, 200, 0, 90)
        cor_busca_atual = QColor(255, 120, 0, 150)
        sombra = QColor(c["sombra"])
        sombra.setAlpha(45)

        for i in v._visiveis(ev.rect()):
            rect = v._geo[i][0]
            p.fillRect(rect.adjusted(1, 2, 2, 3), sombra)
            p.drawPixmap(rect.topLeft(), v._pixmap(i))

            # resultados da busca
            for k, (pg, r) in enumerate(v.resultados):
                if pg == i:
                    p.fillRect(v._ret_tela(i, r), cor_busca_atual if k == v.resultado_atual else cor_busca)

            # seleção (retângulos unidos por linha)
            ks = v._selecao_na_pagina(i)
            if ks:
                ws = v.doc.palavras(i)
                por_linha: dict = {}
                for k in ks:
                    w = ws[k]
                    r = pymupdf.Rect(w[:4])
                    por_linha[w[5]] = por_linha[w[5]] | r if w[5] in por_linha else r
                for r in por_linha.values():
                    p.fillRect(v._ret_tela(i, r), cor_sel)
            if v.sel_ret and v.sel_ret[0] == i:
                pen = QPen(QColor(c["selecao"]), 1, Qt.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawRect(v._ret_tela(i, v.sel_ret[1]))

            if v.destaque_temp and v.destaque_temp[0] == i:
                p.fillRect(v._ret_tela(i, v.destaque_temp[1]).adjusted(-3, -2, 3, 2), QColor(229, 72, 77, 90))

        if self.ret_assinatura:
            _, q = self.ret_assinatura
            cor = QColor(c["destaque"])
            p.setPen(QPen(cor, 1.5, Qt.DashLine))
            cor.setAlpha(40)
            p.setBrush(cor)
            p.drawRoundedRect(q, 4, 4)
        p.end()

    # ---------------------------------------------------------------- mouse
    def mousePressEvent(self, e):
        self.setFocus()
        v = self.v
        v._acoes_sel.hide()
        v._acoes_destaque.hide()
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and v.modo == "mao"):
            self._pan = (e.globalPosition(), v.horizontalScrollBar().value(), v.verticalScrollBar().value())
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        pos = e.position()
        self._press, self._arrastou = pos, False

        if v.modo == "posicionar":
            i = v._pagina_em(pos)
            if i >= 0 and v._geo[i][0].contains(pos.toPoint()):
                self.ret_assinatura = (i, QRectF(pos, pos))
            return

        # clique triplo -> linha inteira
        if time.monotonic() - self._t_duplo < QGuiApplication.styleHints().mouseDoubleClickInterval() / 1000:
            alvo = v._palavra_em(pos, estrito=True)
            if alvo:
                i, k = alvo
                ws = v.doc.palavras(i)
                linha = ws[k][5]
                ks = [j for j, w in enumerate(ws) if w[5] == linha]
                v.sel_ret, v.sel_ini, v.sel_fim = None, (i, ks[0]), (i, ks[-1])
                self.update()
                v.selecaoMudou.emit(True)
                self._press = None
                return

        if e.modifiers() & Qt.AltModifier:
            i = v._pagina_em(pos)
            self._ret_ini = (i, pos) if i >= 0 else None
            self._ancora = None
        else:
            self._ret_ini = None
            self._ancora = v._palavra_em(pos)

    def mouseMoveEvent(self, e):
        v = self.v
        pos = e.position()
        if self._pan:
            ini, h, vv = self._pan
            d = e.globalPosition() - ini
            v.horizontalScrollBar().setValue(int(h - d.x()))
            v.verticalScrollBar().setValue(int(vv - d.y()))
            return

        if not (e.buttons() & Qt.LeftButton) or self._press is None:
            if v.modo == "texto":
                ln = v._link_em(pos)
                i = v._pagina_em(pos)
                dentro = i >= 0 and v._geo[i][0].contains(pos.toPoint())
                clicavel = ln or v._assinatura_em(pos) is not None
                self.setCursor(Qt.PointingHandCursor if clicavel else (Qt.IBeamCursor if dentro else Qt.ArrowCursor))
            return

        if not self._arrastou and (pos - self._press).manhattanLength() < 4:
            return
        self._arrastou = True
        v.ensureVisible(int(pos.x()), int(pos.y()), 10, 10)

        if v.modo == "posicionar" and self.ret_assinatura:
            i, _ = self.ret_assinatura
            pag = QRectF(v._geo[i][0])
            fim = QPointF(min(max(pos.x(), pag.left()), pag.right()), min(max(pos.y(), pag.top()), pag.bottom()))
            self.ret_assinatura = (i, QRectF(self._press, fim).normalized())
            self.update()
            return

        if self._ret_ini:
            i, ini = self._ret_ini
            a, b = v._para_pagina(i, ini), v._para_pagina(i, pos)
            v.sel_ini = v.sel_fim = None
            v.sel_ret = (i, pymupdf.Rect(a, b).normalize())
            self.update()
            return

        if self._ancora:
            foco = v._palavra_em(pos)
            if foco:
                v.sel_ret = None
                v.sel_ini, v.sel_fim = self._ancora, foco
                self.update()

    def mouseReleaseEvent(self, e):
        v = self.v
        if self._pan:
            self._pan = None
            self.atualizar_cursor()
            return
        if e.button() != Qt.LeftButton or self._press is None:
            return
        pos = e.position()

        if v.modo == "posicionar":
            if self.ret_assinatura:
                i, q = self.ret_assinatura
                if not self._arrastou or q.width() < 20 or q.height() < 10:
                    # clique simples: caixa padrão (≈ 190 x 60 pt) centrada no clique
                    w = 190 * v.zoom * PX_POR_PT
                    h = 60 * v.zoom * PX_POR_PT
                    pag = QRectF(v._geo[i][0])
                    x = min(max(self._press.x() - w / 2, pag.left()), pag.right() - w)
                    y = min(max(self._press.y() - h / 2, pag.top()), pag.bottom() - h)
                    q = QRectF(x, y, w, h)
                v._concluir_posicionamento(i, q)
            self._press = None
            return

        if not self._arrastou:
            ln = v._link_em(pos)
            v.limpar_selecao()
            if ln:
                v._abrir_link(ln)
            else:
                # como no Adobe Reader: clicar numa assinatura visível abre o painel de assinaturas
                campo = v._assinatura_em(pos)
                if campo is not None:
                    v.assinaturaClicada.emit(campo)
                elif v.modo == "texto" and (alvo := v._destaque_em(pos)):
                    v._mostrar_acoes_destaque(alvo, pos)
        else:
            v.selecaoMudou.emit(v.tem_selecao())
        self._press = None

    def mouseDoubleClickEvent(self, e):
        v = self.v
        if v.modo != "texto" or e.button() != Qt.LeftButton:
            return
        alvo = v._palavra_em(e.position(), estrito=True)
        self._t_duplo = time.monotonic()
        if alvo:
            v.sel_ret, v.sel_ini, v.sel_fim = None, alvo, alvo
            self.update()
            v.selecaoMudou.emit(True)

    def keyPressEvent(self, e):
        v = self.v
        if e.modifiers() & Qt.ControlModifier and e.key() == Qt.Key_C:
            v.copiar()
            return
        if e.modifiers() & Qt.ControlModifier and e.key() == Qt.Key_A:
            v.selecionar_tudo()
            return
        if e.key() == Qt.Key_Escape and v.tem_selecao() and v.modo != "posicionar":
            v.limpar_selecao()
            return
        e.ignore()  # sobe para o QScrollArea (setas, PageUp/Down, Home/End, Esc)

    def contextMenuEvent(self, e):
        v = self.v
        if v.modo == "posicionar":
            return
        i = v._pagina_em(QPointF(e.pos()))
        m = QMenu(self)
        a_copiar = m.addAction("Copiar")
        a_copiar.setEnabled(v.tem_selecao())
        m_destacar = m.addMenu("Destacar")
        v.preencher_menu_cores(m_destacar, "destacar", v.cor_destaque)
        m_destacar.setEnabled(v.tem_selecao())
        alvo = v._destaque_em(QPointF(e.pos()))  # clicou sobre um texto destacado?
        a_remover = None
        if alvo:
            m_cor = m.addMenu("Alterar Cor do Destaque")
            v.preencher_menu_cores(m_cor, "cor", v.doc.cor_do_destaque(*alvo))
            a_remover = m.addAction("Remover Destaque")
        a_tudo = m.addAction("Selecionar tudo")
        a_pag = m.addAction(f"Copiar texto da página {i + 1}") if i >= 0 else None
        m.addSeparator()
        a_girar_pag = m.addAction(f"Girar página {i + 1}") if i >= 0 else None
        a_girar = m.addAction("Girar Todas as Páginas")
        a_larg = m.addAction("Ajustar à Largura")
        a_pagina = m.addAction("Página Inteira")
        esc = m.exec(e.globalPos())
        if esc is a_copiar:
            v.copiar()
        elif esc is not None and isinstance(esc.data(), (tuple, list)):  # cores dos submenus
            acao, cor = esc.data()
            if acao == "destacar":
                v._destacar_selecao(cor)
            else:
                v.mudar_cor_destaque(cor, alvo)
        elif a_remover is not None and esc is a_remover:
            v.remover_destaque(alvo)
        elif esc is a_tudo:
            v.selecionar_tudo()
        elif a_pag is not None and esc is a_pag:
            QGuiApplication.clipboard().setText(v.doc.texto_pagina(i))
        elif a_girar_pag is not None and esc is a_girar_pag:
            v.girar_pagina(i)
        elif esc is a_girar:
            v.girar()
        elif esc is a_larg:
            v.ajustar("largura")
        elif esc is a_pagina:
            v.ajustar("pagina")
