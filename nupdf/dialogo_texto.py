"""Diálogo do Editor de PDF para digitar texto (Inserir Texto / Substituir Texto)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QSpinBox, QVBoxLayout)

from .edicao import CORES_TEXTO


class DialogoTexto(QDialog):
    """`com_estilo=True` (Inserir Texto): também tamanho, cor e negrito. Na substituição o
    estilo vem do texto original."""

    def __init__(self, parent, titulo: str, explicacao: str, texto: str = "", com_estilo: bool = False,
                 rotulo_ok: str = "Aplicar"):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        info = QLabel(explicacao)
        info.setWordWrap(True)
        lay.addWidget(info)
        self.campo = QPlainTextEdit(texto)
        self.campo.setMinimumHeight(110)
        self.campo.setTabChangesFocus(True)
        lay.addWidget(self.campo)

        self.tamanho = QSpinBox()
        self.tamanho.setRange(4, 96)
        self.tamanho.setValue(11)
        self.tamanho.setSuffix(" pt")
        self.cor = QComboBox()
        for chave, (rotulo, _) in CORES_TEXTO.items():
            self.cor.addItem(rotulo, chave)
        self.negrito = QCheckBox("Negrito")
        if com_estilo:
            estilo = QHBoxLayout()
            estilo.setSpacing(8)
            for rotulo, w in (("Tamanho", self.tamanho), ("Cor", self.cor)):
                r = QLabel(rotulo)
                r.setObjectName("sub")
                estilo.addWidget(r)
                estilo.addWidget(w)
            estilo.addSpacing(6)
            estilo.addWidget(self.negrito)
            estilo.addStretch(1)
            lay.addLayout(estilo)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        cancelar = QPushButton("Cancelar")
        cancelar.setObjectName("fechar")
        cancelar.setCursor(Qt.PointingHandCursor)
        cancelar.clicked.connect(self.reject)
        self.ok = QPushButton(rotulo_ok)
        self.ok.setObjectName("primario")
        self.ok.setCursor(Qt.PointingHandCursor)
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._confirmar)
        botoes.addWidget(cancelar)
        botoes.addWidget(self.ok)
        lay.addLayout(botoes)
        self.campo.setFocus()
        self.campo.selectAll()

    def _confirmar(self):
        if self.texto():
            self.accept()
        else:
            self.campo.setFocus()

    def texto(self) -> str:
        return self.campo.toPlainText().rstrip()

    def estilo(self) -> dict:
        return {"tamanho": float(self.tamanho.value()), "cor": CORES_TEXTO[self.cor.currentData()][1],
                "negrito": self.negrito.isChecked()}
