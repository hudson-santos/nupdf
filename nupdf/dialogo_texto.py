"""Diálogo do Editor de PDF para digitar texto (Inserir Texto / Substituir Texto)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QSpinBox, QVBoxLayout)

from .edicao import CORES_TEXTO


class DialogoTexto(QDialog):
    """`com_estilo=True` (Inserir Texto): também tamanho, cor e negrito. Na substituição o
    estilo vem do texto original."""

    def __init__(self, parent, titulo: str, explicacao: str, texto: str = "", com_estilo: bool = False,
                 rotulo_ok: str = "Aplicar", fontes_doc: list[str] | None = None, fonte_padrao: str | None = None):
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
        # Fonte: as do documento (uma por família, sem negrito/itálico) + Helvetica
        from .fontes import familia_e_estilo, nome_familia
        self.fonte = QComboBox()
        vistas = set()
        padrao_fam = familia_e_estilo(fonte_padrao)[0] if fonte_padrao else None
        for nome in fontes_doc or []:
            fam = familia_e_estilo(nome)[0]
            if fam in vistas:
                continue
            vistas.add(fam)
            self.fonte.addItem(nome_familia(nome), nome)
            if fam == padrao_fam:
                self.fonte.setCurrentIndex(self.fonte.count() - 1)
        self.fonte.addItem("Helvetica (Padrão do PDF)", None)
        self.fonte.setToolTip("Mesma fonte do documento; se não estiver instalada, o NuPDF tenta baixá-la")
        if com_estilo:
            linha_fonte = QHBoxLayout()
            r = QLabel("Fonte")
            r.setObjectName("sub")
            linha_fonte.addWidget(r)
            linha_fonte.addWidget(self.fonte, 1)
            lay.addLayout(linha_fonte)
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
                "negrito": self.negrito.isChecked(), "fonte": self.fonte.currentData()}
