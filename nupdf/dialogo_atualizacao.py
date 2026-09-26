"""Janela "Verificar Atualizações" (no estilo da do JoPDF)."""

import html
import re

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QTextBrowser, QVBoxLayout)

from . import atualizacao as atu
from . import ui
from .icones import pixmap_logo
from .versao import NOME_APP, VERSAO

_SECOES = {"added": "Novidades", "changed": "Alterações", "fixed": "Correções", "removed": "Removido",
           "security": "Segurança", "deprecated": "Descontinuado"}


def _notas_html(md: str, cor_link: str) -> str:
    """Converte as notas da release (seção do CHANGELOG no formato Keep a
    Changelog: "### Added" + itens "- ...", com continuação indentada) em HTML
    com títulos traduzidos e espaçamento controlado."""
    esc = lambda t: html.escape(t, quote=False)

    def inline(t):
        t = esc(t)
        t = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", t)
        return re.sub(r"(https?://[^\s)<]+)",
                      lambda m: f'<a href="{m.group(1)}" style="color:{cor_link}">{m.group(1)}</a>', t)


    partes, itens = [], []

    def fechar_lista():
        if itens:
            partes.append('<ul style="margin-top:0; margin-bottom:10px; -qt-list-indent:1;">'
                          + "".join(f'<li style="margin-bottom:4px;">{inline(i)}</li>' for i in itens) + "</ul>")
            itens.clear()

    for linha in md.splitlines():
        m = re.match(r"^#{2,4}\s*(.+?)\s*$", linha)
        if m:
            fechar_lista()
            nome = _SECOES.get(m.group(1).lower(), m.group(1))
            partes.append(f'<p style="margin-top:4px; margin-bottom:8px;"><b>{esc(nome)}</b></p>')
        elif re.match(r"^\s*[-*]\s+", linha):
            itens.append(re.sub(r"^\s*[-*]\s+", "", linha))
        elif linha.strip() and itens:
            itens[-1] += " " + linha.strip()
        elif linha.strip():
            fechar_lista()
            partes.append(f"<p>{inline(linha.strip())}</p>")
    fechar_lista()
    return "".join(partes) or "<p>Correções e melhorias.</p>"


class _Download(QThread):
    progresso = Signal(int, int)
    concluido = Signal(object)
    falhou = Signal(str)

    def __init__(self, release):
        super().__init__()
        self.release = release
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        try:
            caminho = atu.baixar_instalador(self.release, lambda a, b: self.progresso.emit(a, b),
                                            lambda: self._cancelar)
            self.concluido.emit(caminho)
        except Exception as e:
            self.falhou.emit(str(e))


class DialogoAtualizacao(QDialog):
    def __init__(self, parent=None, release=None):
        super().__init__(parent)
        self.setWindowTitle("Verificar Atualizações")
        self.setMinimumWidth(600)
        self.release = release
        self._download = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(14)

        cab = QHBoxLayout()
        cab.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(pixmap_logo(48))
        cab.addWidget(logo)
        nome = QLabel(f"{NOME_APP} para Windows")
        nome.setStyleSheet("font-size: 18px; font-weight: 700;")
        cab.addWidget(nome, 1)
        lay.addLayout(cab)

        self.cartao = QFrame()
        self.cartao.setObjectName("cartao")
        self.cartao.setMinimumHeight(190)
        cl = QVBoxLayout(self.cartao)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(8)
        self.titulo = QLabel()
        self.titulo.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.titulo.setWordWrap(True)
        cl.addWidget(self.titulo)
        self.texto = QLabel()
        self.texto.setObjectName("sub")
        self.texto.setWordWrap(True)
        cl.addWidget(self.texto)
        self.notas = QTextBrowser()
        self.notas.setOpenExternalLinks(True)
        self.notas.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.notas.setFrameShape(QFrame.NoFrame)
        self.notas.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        cl.addWidget(self.notas, 1)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(8)
        cl.addWidget(self.barra)
        self.status = QLabel()
        self.status.setObjectName("sub3")
        cl.addWidget(self.status)
        cl.addStretch()  # mantém o texto no topo quando não há notas (as notas têm prioridade)
        lay.addWidget(self.cartao, 1)

        cor_link = ui.cores()["destaque"]
        self.nota = QLabel(f'Nota: Você também pode visitar <a href="{atu.PAGINA_DOWNLOAD}" '
                           f'style="color:{cor_link}">aqui</a> para baixar a versão mais recente')
        self.nota.setObjectName("sub")
        self.nota.setAlignment(Qt.AlignCenter)
        self.nota.setOpenExternalLinks(True)
        lay.addWidget(self.nota)

        # Um único botão centralizado: "Atualizar" (ou "Tentar novamente") e,
        # durante o download, "Cancelar" no lugar dele. A janela fecha pelo X/Esc.
        botoes = QHBoxLayout()
        self.b_cancelar = QPushButton("Cancelar")
        self.b_cancelar.setMinimumHeight(38)
        self.b_cancelar.setFixedWidth(260)
        self.b_cancelar.clicked.connect(self._cancelar_download)
        self.b_atualizar = QPushButton("Atualizar")
        self.b_atualizar.setObjectName("primario")
        self.b_atualizar.setMinimumHeight(38)
        self.b_atualizar.setCursor(Qt.PointingHandCursor)
        self.b_atualizar.clicked.connect(self._atualizar)
        self.b_atualizar.setFixedWidth(260)
        botoes.addStretch(1)
        botoes.addWidget(self.b_atualizar)
        botoes.addWidget(self.b_cancelar)
        botoes.addStretch(1)
        lay.addLayout(botoes)

        if release is None:
            self._verificando()
            self._tarefa = ui.Tarefa(atu.ultima_release)
            self._tarefa.concluida.connect(self._recebida)
            self._tarefa.falhou.connect(self._erro)
            self._tarefa.start()
        else:
            self._recebida(release)

    # ------------------------------------------------------------------ estados
    def _estado(self, titulo, texto="", notas=None, barra=None, status="", atualizar=False, cancelar=False):
        self.titulo.setText(titulo)
        self.texto.setText(texto)
        self.texto.setVisible(bool(texto))
        self.notas.setVisible(notas is not None)
        if notas is not None:
            self.notas.setHtml(notas)
            QTimer.singleShot(0, self._ajustar_altura)
        self.barra.setVisible(barra is not None)
        if barra == "indeterminada":
            self.barra.setRange(0, 0)
        elif barra is not None:
            self.barra.setRange(0, 100)
            self.barra.setValue(barra)
        self.status.setText(status)
        self.status.setVisible(bool(status))
        self.b_atualizar.setVisible(atualizar)
        self.b_cancelar.setVisible(cancelar)

    def _ajustar_altura(self):
        """Área de novidades do tamanho do texto (sem rolagem), até um limite -
        acima dele, aparece a barra de rolagem. A janela é redimensionada no
        ciclo de eventos seguinte, quando o Qt já recalculou o layout."""
        limite = int(self.screen().availableGeometry().height() * 0.55) if self.screen() else 520
        doc = self.notas.document()
        doc.setTextWidth(self.notas.viewport().width())
        self.notas.setFixedHeight(min(int(doc.size().height()) + 8, limite))
        QTimer.singleShot(0, lambda: self.resize(self.width(), self.sizeHint().height()))

    def _verificando(self):
        self._estado("Verificando atualizações…", f"Versão instalada: {VERSAO}", barra="indeterminada")

    def _erro(self, msg):
        self._estado("Não foi possível verificar", msg)

    def _recebida(self, release):
        self.release = release
        if atu.eh_mais_nova(release.versao):
            mb = f" · {release.tamanho / 1048576:.1f} MB".replace(".", ",") if release.tamanho else ""
            self._estado(f"Versão: {release.versao}",
                         f"Você está usando a versão {VERSAO}{mb}\n\nO que há de novo:",
                         notas=_notas_html(release.notas, ui.cores()["destaque"]), atualizar=True)
        else:
            self._estado("Você já está usando a versão mais recente",
                         f"Versão instalada: {VERSAO}")

    # ------------------------------------------------------------------ ações
    def _atualizar(self):
        self._estado(f"Baixando a versão {self.release.versao}…", barra=0, status="Iniciando o download…",
                     cancelar=True)
        self._download = _Download(self.release)
        self._download.progresso.connect(self._progresso)
        self._download.concluido.connect(self._baixado)
        self._download.falhou.connect(self._falha_download)
        self._download.start()

    def _progresso(self, lido, total):
        mb = lambda n: f"{n / 1048576:.1f}".replace(".", ",")
        if total:
            self.barra.setValue(int(lido * 100 / total))
            self.status.setText(f"{mb(lido)} de {mb(total)} MB")
        else:
            self.status.setText(f"{mb(lido)} MB")

    def _falha_download(self, msg):
        self._download = None
        self.b_atualizar.setText("Tentar novamente")
        self._estado("Não foi possível atualizar", msg, atualizar=True)

    def _baixado(self, caminho):
        self._download = None
        self._estado("Instalando a atualização…",
                     "O NuPDF será fechado e reaberto automaticamente ao final da instalação.",
                     barra=100)
        try:
            atu.executar_instalador(caminho)
        except OSError as e:
            self._estado("Não foi possível iniciar o instalador", f"{e}\n\nArquivo: {caminho}")
            return
        QApplication.instance().quit()

    def _cancelar_download(self):
        if self._download is not None:
            self._download.cancelar()
            self._download.wait(3000)
            self._download = None
        self._recebida(self.release)

    def reject(self):
        if self._download is not None:
            self._download.cancelar()
            self._download.wait(3000)
        super().reject()
