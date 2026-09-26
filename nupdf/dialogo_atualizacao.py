"""Janela "Verificar Atualizações" (no estilo da do JoPDF)."""

import re

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QTextBrowser, QVBoxLayout)

from . import atualizacao as atu
from . import ui
from .icones import pixmap_logo
from .versao import NOME_APP, VERSAO

_SECOES = {"added": "Novidades", "changed": "Alterações", "fixed": "Correções", "removed": "Removido",
           "security": "Segurança", "deprecated": "Descontinuado"}


def _notas_em_portugues(md: str) -> str:
    """As notas vêm do CHANGELOG (Keep a Changelog, títulos em inglês)."""
    def titulo(m):
        nome = m.group(1).strip()
        return f"**{_SECOES.get(nome.lower(), nome)}**"
    md = re.sub(r"^#{2,4}\s*(.+?)\s*$", titulo, md, flags=re.M)
    return md or "Correções e melhorias."


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
        self.setMinimumWidth(560)
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

        botoes = QHBoxLayout()
        botoes.setSpacing(12)
        self.b_fechar = QPushButton("Fechar")
        self.b_fechar.setMinimumHeight(38)
        self.b_fechar.clicked.connect(self._fechar_ou_cancelar)
        self.b_atualizar = QPushButton("Atualizar")
        self.b_atualizar.setObjectName("primario")
        self.b_atualizar.setMinimumHeight(38)
        self.b_atualizar.setCursor(Qt.PointingHandCursor)
        self.b_atualizar.clicked.connect(self._atualizar)
        botoes.addWidget(self.b_fechar, 1)
        botoes.addWidget(self.b_atualizar, 1)
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
    def _estado(self, titulo, texto="", notas=None, barra=None, status="", atualizar=False):
        self.titulo.setText(titulo)
        self.texto.setText(texto)
        self.texto.setVisible(bool(texto))
        self.notas.setVisible(notas is not None)
        if notas is not None:
            self.notas.setMarkdown(notas)
            self._colorir_links()
        self.barra.setVisible(barra is not None)
        if barra == "indeterminada":
            self.barra.setRange(0, 0)
        elif barra is not None:
            self.barra.setRange(0, 100)
            self.barra.setValue(barra)
        self.status.setText(status)
        self.status.setVisible(bool(status))
        self.b_atualizar.setVisible(atualizar)

    def _colorir_links(self):
        """O import de markdown do Qt grava o azul padrão nos links; troca
        pela cor de destaque do tema (legível no escuro e no claro)."""
        cor = QColor(ui.cores()["destaque"])
        bloco = self.notas.document().begin()
        while bloco.isValid():
            it = bloco.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.charFormat().isAnchor():
                    cur = QTextCursor(self.notas.document())
                    cur.setPosition(frag.position())
                    cur.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                    fmt = QTextCharFormat()
                    fmt.setForeground(cor)
                    cur.mergeCharFormat(fmt)
                it += 1
            bloco = bloco.next()

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
                         notas=_notas_em_portugues(release.notas), atualizar=True)
        else:
            self._estado("Você já está usando a versão mais recente",
                         f"Versão instalada: {VERSAO}")

    # ------------------------------------------------------------------ ações
    def _atualizar(self):
        self.b_atualizar.setEnabled(False)
        self.b_fechar.setText("Cancelar")
        self._estado(f"Baixando a versão {self.release.versao}…", barra=0, status="Iniciando o download…",
                     atualizar=True)
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
        self.b_fechar.setText("Fechar")
        self.b_atualizar.setEnabled(True)
        self.b_atualizar.setText("Tentar novamente")
        self._estado("Não foi possível atualizar", msg, atualizar=True)

    def _baixado(self, caminho):
        self._download = None
        self._estado("Instalando a atualização…",
                     "O NuPDF será fechado e reaberto automaticamente ao final da instalação.",
                     barra=100)
        self.b_fechar.setEnabled(False)
        try:
            atu.executar_instalador(caminho)
        except OSError as e:
            self.b_fechar.setEnabled(True)
            self.b_fechar.setText("Fechar")
            self._estado("Não foi possível iniciar o instalador", f"{e}\n\nArquivo: {caminho}")
            return
        QApplication.instance().quit()

    def _fechar_ou_cancelar(self):
        if self._download is not None:
            self._download.cancelar()
            self._download.wait(3000)
            self._download = None
            self.b_fechar.setText("Fechar")
            self.b_atualizar.setEnabled(True)
            self._recebida(self.release)
            return
        self.reject()

    def reject(self):
        if self._download is not None:
            self._download.cancelar()
            self._download.wait(3000)
        super().reject()
