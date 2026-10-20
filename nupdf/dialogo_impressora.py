"""Janela "Impressora NuPDF": instala/remove a impressora virtual (ver impressora_virtual.py)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import impressora_virtual as iv


class DialogoImpressora(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Impressora NuPDF")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        titulo = QLabel("Impressora NuPDF")
        titulo.setStyleSheet("font-size: 17px; font-weight: 700;")
        lay.addWidget(titulo)
        texto = QLabel(
            "Imprima de qualquer programa na impressora <b>NuPDF</b> para gerar um PDF: ele é salvo em "
            f"<b>Documentos\\{iv.pasta_impressoes().name}</b> e abre no NuPDF.")
        texto.setWordWrap(True)
        texto.setTextFormat(Qt.RichText)
        lay.addWidget(texto)
        self.situacao = QLabel()
        self.situacao.setWordWrap(True)
        lay.addWidget(self.situacao)
        nota = QLabel("Instalar ou remover a impressora pede a permissão de administrador do Windows.")
        nota.setObjectName("sub3")
        nota.setWordWrap(True)
        lay.addWidget(nota)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        fechar = QPushButton("Fechar")
        fechar.setObjectName("fechar")
        fechar.setCursor(Qt.PointingHandCursor)
        fechar.clicked.connect(self.accept)
        self.b_remover = QPushButton("Remover Impressora")
        self.b_remover.setObjectName("perigo")
        self.b_remover.setCursor(Qt.PointingHandCursor)
        self.b_remover.clicked.connect(self._remover)
        self.b_instalar = QPushButton("Instalar Impressora")
        self.b_instalar.setObjectName("primario")
        self.b_instalar.setCursor(Qt.PointingHandCursor)
        self.b_instalar.clicked.connect(self._instalar)
        for b in (fechar, self.b_remover, self.b_instalar):
            botoes.addWidget(b)
        lay.addLayout(botoes)
        self._atualizar()

    def _atualizar(self, aviso: str = ""):
        instalada = iv.instalada()
        if instalada:
            iv.iniciar_agente()
            self.situacao.setText(aviso or "✓  A impressora <b>NuPDF</b> está instalada e pronta para uso.")
            self.situacao.setObjectName("statusOk")
        else:
            self.situacao.setText(aviso or "A impressora NuPDF ainda não está instalada.")
            self.situacao.setObjectName("statusAviso" if not aviso else "statusErro")
        self.situacao.style().unpolish(self.situacao)
        self.situacao.style().polish(self.situacao)
        # instalar ou remover: só o botão que faz sentido aparece
        self.b_instalar.setVisible(not instalada)
        self.b_remover.setVisible(instalada)

    def _executar(self, acao):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return acao()
        finally:
            QApplication.restoreOverrideCursor()

    def _instalar(self):
        codigo = self._executar(iv.instalar)
        if codigo == -1:
            self._atualizar("A instalação foi cancelada na confirmação do Windows.")
        elif codigo != 0 or not iv.instalada():
            self._atualizar("Não foi possível instalar a impressora. Detalhes no log %TEMP%\\nupdf_impressora.log "
                            "do administrador.")
        else:
            self._atualizar()

    def _remover(self):
        codigo = self._executar(iv.remover)
        if codigo == -1:
            iv.registrar_inicio()  # cancelou: a impressora continua - o agente também
            iv.iniciar_agente()
            self._atualizar()
        else:
            self._atualizar()
