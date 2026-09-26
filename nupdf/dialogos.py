"""Diálogo de configuração da assinatura digital (certificados instalados no Windows)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QCompleter, QDialog, QFormLayout, QFrame, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout)

from . import ui
from .assinatura.assinador import ConfigAssinatura
from .assinatura.certificado import InfoCertificado
from .assinatura.windows import CertificadoWindows, listar_certificados
from .config import Config

TSA_PADRAO = "http://timestamp.digicert.com"


class _CartaoCertificado(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("cartao")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        self.titulo = QLabel()
        self.titulo.setObjectName("cartaoTitulo")
        self.titulo.setWordWrap(True)
        self.detalhe = QLabel()
        self.detalhe.setObjectName("sub")
        self.detalhe.setWordWrap(True)
        self.status = QLabel()
        lay.addWidget(self.titulo)
        lay.addWidget(self.detalhe)
        lay.addWidget(self.status)
        self.hide()

    def mostrar(self, info: InfoCertificado | None, erro: str = ""):
        self.show()
        if info is None:
            self.titulo.setText("Certificado não carregado")
            self.detalhe.setText(erro)
            self.status.setText("")
            return
        self.titulo.setText(info.titular)
        linhas = []
        if info.documento:
            linhas.append(f"{info.tipo}: {info.documento}")
        linhas.append(f"Emissor: {info.emissor}")
        linhas.append(f"Validade: {info.valido_de:%d/%m/%Y} a {info.valido_ate:%d/%m/%Y}")
        self.detalhe.setText("\n".join(linhas))
        if info.expirado:
            self.status.setObjectName("statusErro")
            self.status.setText("Certificado fora da validade")
        else:
            self.status.setObjectName("statusOk")
            self.status.setText("Certificado pronto para assinar")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)


class DialogoAssinatura(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Assinar documento")
        self.setMinimumWidth(600)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        titulo = QLabel("Assinatura digital ICP-Brasil")
        titulo.setStyleSheet("font-size: 17px; font-weight: 700;")
        lay.addWidget(titulo)
        sub = QLabel("Padrão PAdES (PDF Advanced Electronic Signature), SHA-256.")
        sub.setObjectName("sub")
        lay.addWidget(sub)

        # certificado: lista dos instalados no Windows (repositório Pessoal)
        grupo = QGroupBox("Certificado digital")
        gl = QVBoxLayout(grupo)
        gl.setSpacing(8)
        linha = QHBoxLayout()
        self.lista = QComboBox()
        self.lista.setEditable(True)  # digitar filtra por nome ou CPF/CNPJ
        self.lista.setInsertPolicy(QComboBox.NoInsert)
        self.lista.lineEdit().setPlaceholderText("Selecione ou digite para buscar…")
        self.lista.setMinimumContentsLength(40)
        self.lista.currentIndexChanged.connect(self._escolhido)
        atualizar = ui.botao("girar", "Atualizar a lista de certificados", tamanho=16)
        atualizar.clicked.connect(self._carregar_lista)
        linha.addWidget(self.lista, 1)
        linha.addWidget(atualizar)
        gl.addLayout(linha)
        self.aviso = QLabel()
        self.aviso.setObjectName("sub3")
        self.aviso.setWordWrap(True)
        gl.addWidget(self.aviso)
        self.cartao = _CartaoCertificado()
        gl.addWidget(self.cartao)
        lay.addWidget(grupo)
        self._certs: list[CertificadoWindows] = []

        # aparência e metadados
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        linha_ap = QHBoxLayout()
        linha_ap.setSpacing(18)
        self.rb_visivel = QRadioButton("Visível (posicionar na página)")
        self.rb_invisivel = QRadioButton("Invisível")
        (self.rb_visivel if config.get("assinatura/visivel", True) else self.rb_invisivel).setChecked(True)
        linha_ap.addWidget(self.rb_visivel)
        linha_ap.addWidget(self.rb_invisivel)
        linha_ap.addStretch(1)
        form.addRow("Aparência:", linha_ap)
        self.motivo = QLineEdit(config.get("assinatura/motivo", "Assinatura digital"))
        form.addRow("Motivo:", self.motivo)
        self.local = QLineEdit(config.get("assinatura/local", ""))
        self.local.setPlaceholderText("Ex.: Rio Verde - GO")
        form.addRow("Local:", self.local)
        linha_tsa = QHBoxLayout()
        linha_tsa.setSpacing(12)
        self.cb_tsa = QCheckBox("Carimbo de tempo")
        self.cb_tsa.setChecked(config.get("assinatura/usar_tsa", False))
        self.tsa = QLineEdit(config.get("assinatura/tsa", TSA_PADRAO))
        self.tsa.setEnabled(self.cb_tsa.isChecked())
        self.cb_tsa.toggled.connect(self.tsa.setEnabled)
        linha_tsa.addWidget(self.cb_tsa)
        linha_tsa.addWidget(self.tsa, 1)
        form.addRow("", linha_tsa)
        lay.addLayout(form)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.ok = QPushButton("Continuar")
        self.ok.setObjectName("primario")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._aceitar)
        botoes.addWidget(cancelar)
        botoes.addWidget(self.ok)
        lay.addLayout(botoes)
        self._carregar_lista()

    # ------------------------------------------------------------------ certificado
    def _carregar_lista(self):
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            todos = listar_certificados()
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._certs = [c for c in todos if not c.info.expirado]
        vencidos = len(todos) - len(self._certs)
        self.lista.blockSignals(True)
        self.lista.clear()
        for c in self._certs:
            self.lista.addItem(c.rotulo(), c.impressao)
        completar = QCompleter([c.rotulo() for c in self._certs], self.lista)
        completar.setFilterMode(Qt.MatchContains)
        completar.setCaseSensitivity(Qt.CaseInsensitive)
        self.lista.setCompleter(completar)
        salvo = self.config.get("assinatura/certificado", "")
        idx = self.lista.findData(salvo) if salvo else -1
        self.lista.setCurrentIndex(idx if idx >= 0 else (0 if self._certs else -1))
        self.lista.blockSignals(False)
        if not self._certs:
            self.aviso.setText("Nenhum certificado digital válido instalado no Windows. Para instalar um "
                               "certificado A1, dê duplo clique no arquivo .pfx e siga o assistente; "
                               "depois clique em atualizar.")
        elif vencidos:
            self.aviso.setText(f"{len(self._certs)} certificado(s) disponível(is) · {vencidos} vencido(s) "
                               "não exibido(s).")
        else:
            self.aviso.setText(f"{len(self._certs)} certificado(s) disponível(is).")
        self._escolhido(self.lista.currentIndex())

    def _atual(self) -> CertificadoWindows | None:
        i = self.lista.currentIndex()
        if 0 <= i < len(self._certs) and self.lista.currentText() == self.lista.itemText(i):
            return self._certs[i]
        return None

    def _escolhido(self, _i: int = -1):
        c = self._atual()
        if c:
            self.lista.lineEdit().setCursorPosition(0)  # mostra o início (nome), não o fim
            self.cartao.mostrar(c.info)
        else:
            self.cartao.hide()
        self._validar()

    # ------------------------------------------------------------------ resultado
    def _validar(self):
        c = self._atual()
        self.ok.setEnabled(c is not None and not c.info.expirado)

    def _aceitar(self):
        c = self.config
        c.set("assinatura/certificado", self._atual().impressao)
        c.set("assinatura/visivel", self.rb_visivel.isChecked())
        c.set("assinatura/motivo", self.motivo.text().strip())
        c.set("assinatura/local", self.local.text().strip())
        c.set("assinatura/usar_tsa", self.cb_tsa.isChecked())
        c.set("assinatura/tsa", self.tsa.text().strip())
        self.accept()

    def config_assinatura(self) -> ConfigAssinatura:
        cert = self._atual()
        return ConfigAssinatura(
            cert.info,
            impressao=cert.impressao,
            der=cert.der,
            motivo=self.motivo.text().strip(),
            local=self.local.text().strip(),
            tsa_url=self.tsa.text().strip() if self.cb_tsa.isChecked() else "",
            visivel=self.rb_visivel.isChecked(),
        )
