"""Diálogo de configuração da assinatura digital."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QRadioButton, QTabWidget, QVBoxLayout, QWidget)

from .assinatura import token as mod_token
from .assinatura.assinador import ConfigAssinatura
from .assinatura.certificado import ErroCertificado, InfoCertificado, carregar_pfx
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
        self.setMinimumWidth(520)
        self._info_a1: InfoCertificado | None = None
        self._certs_a3: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        titulo = QLabel("Assinatura digital ICP-Brasil")
        titulo.setStyleSheet("font-size: 17px; font-weight: 700;")
        lay.addWidget(titulo)
        sub = QLabel("Padrão PAdES (PDF Advanced Electronic Signature), SHA-256.")
        sub.setObjectName("sub")
        lay.addWidget(sub)

        self.abas = QTabWidget()
        self.abas.addTab(self._aba_a1(), "Certificado A1 (arquivo)")
        self.abas.addTab(self._aba_a3(), "Token / Cartão A3")
        self.abas.setCurrentIndex(1 if config.get("assinatura/origem", "a1") == "a3" else 0)
        self.abas.currentChanged.connect(self._validar)
        lay.addWidget(self.abas)

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
        self._validar()

    # ------------------------------------------------------------------ A1
    def _aba_a1(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        linha = QHBoxLayout()
        self.pfx = QLineEdit(self.config.get("assinatura/pfx", ""))
        self.pfx.setPlaceholderText("Arquivo .pfx ou .p12")
        self.pfx.textChanged.connect(self._a1_alterado)
        procurar = QPushButton("Procurar…")
        procurar.clicked.connect(self._procurar_pfx)
        linha.addWidget(self.pfx, 1)
        linha.addWidget(procurar)
        lay.addLayout(linha)
        linha2 = QHBoxLayout()
        self.senha = QLineEdit()
        self.senha.setEchoMode(QLineEdit.Password)
        self.senha.setPlaceholderText("Senha do certificado")
        self.senha.textChanged.connect(self._a1_alterado)
        self.senha.returnPressed.connect(self._carregar_a1)
        carregar = QPushButton("Carregar")
        carregar.clicked.connect(self._carregar_a1)
        linha2.addWidget(self.senha, 1)
        linha2.addWidget(carregar)
        lay.addLayout(linha2)
        self.cartao_a1 = _CartaoCertificado()
        lay.addWidget(self.cartao_a1)
        lay.addStretch(1)
        return w

    def _procurar_pfx(self):
        inicial = self.pfx.text() or str(Path.home())
        arq, _ = QFileDialog.getOpenFileName(self, "Selecionar certificado A1", inicial,
                                             "Certificado digital (*.pfx *.p12);;Todos os arquivos (*)")
        if arq:
            self.pfx.setText(arq)
            self.senha.setFocus()

    def _a1_alterado(self):
        self._info_a1 = None
        self.cartao_a1.hide()
        self._validar()

    def _carregar_a1(self):
        try:
            self._info_a1 = carregar_pfx(self.pfx.text().strip(), self.senha.text())
            self.cartao_a1.mostrar(self._info_a1)
        except ErroCertificado as e:
            self._info_a1 = None
            self.cartao_a1.mostrar(None, str(e))
        self._validar()

    # ------------------------------------------------------------------ A3
    def _aba_a3(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        linha = QHBoxLayout()
        self.lib = QComboBox()
        self.lib.setEditable(True)
        self.lib.lineEdit().setPlaceholderText("Biblioteca PKCS#11 do token (.dll)")
        for nome, caminho in mod_token.bibliotecas_encontradas():
            self.lib.addItem(f"{nome}", caminho)
        salvo = self.config.get("assinatura/pkcs11", "")
        if salvo:
            idx = self.lib.findData(salvo)
            if idx >= 0:
                self.lib.setCurrentIndex(idx)
            else:
                self.lib.insertItem(0, salvo, salvo)
                self.lib.setCurrentIndex(0)
        procurar = QPushButton("Procurar…")
        procurar.clicked.connect(self._procurar_lib)
        linha.addWidget(self.lib, 1)
        linha.addWidget(procurar)
        lay.addLayout(linha)
        if self.lib.count() == 0:
            aviso = QLabel("Nenhum driver de token conhecido foi encontrado. Instale o software do "
                           "fabricante do token ou aponte a DLL PKCS#11 manualmente.")
            aviso.setObjectName("sub3")
            aviso.setWordWrap(True)
            lay.addWidget(aviso)
        linha2 = QHBoxLayout()
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setPlaceholderText("PIN do token")
        self.pin.returnPressed.connect(self._ler_token)
        ler = QPushButton("Ler token")
        ler.clicked.connect(self._ler_token)
        linha2.addWidget(self.pin, 1)
        linha2.addWidget(ler)
        lay.addLayout(linha2)
        self.lista_a3 = QListWidget()
        self.lista_a3.setMinimumHeight(90)
        self.lista_a3.currentRowChanged.connect(self._a3_escolhido)
        lay.addWidget(self.lista_a3)
        self.cartao_a3 = _CartaoCertificado()
        lay.addWidget(self.cartao_a3)
        return w

    def _caminho_lib(self) -> str:
        texto = self.lib.currentText().strip()
        dado = self.lib.currentData()
        return dado if dado and self.lib.itemText(self.lib.currentIndex()) == texto else texto

    def _procurar_lib(self):
        arq, _ = QFileDialog.getOpenFileName(self, "Biblioteca PKCS#11", r"C:\Windows\System32",
                                             "Biblioteca (*.dll);;Todos os arquivos (*)")
        if arq:
            self.lib.insertItem(0, arq, arq)
            self.lib.setCurrentIndex(0)

    def _ler_token(self):
        self.lista_a3.clear()
        self._certs_a3 = []
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._certs_a3 = mod_token.listar_certificados(self._caminho_lib(), self.pin.text())
        except ErroCertificado as e:
            self.cartao_a3.mostrar(None, str(e))
        finally:
            QGuiApplication.restoreOverrideCursor()
        for c in self._certs_a3:
            QListWidgetItem(f"{c.info.resumo()}  —  válido até {c.info.valido_ate:%d/%m/%Y}", self.lista_a3)
        if self._certs_a3:
            self.lista_a3.setCurrentRow(0)
        elif not self.cartao_a3.isVisible():
            self.cartao_a3.mostrar(None, "Nenhum certificado com chave privada encontrado no token.")
        self._validar()

    def _a3_escolhido(self, i: int):
        if 0 <= i < len(self._certs_a3):
            self.cartao_a3.mostrar(self._certs_a3[i].info)
        self._validar()

    # ------------------------------------------------------------------ resultado
    def _info_atual(self) -> InfoCertificado | None:
        if self.abas.currentIndex() == 0:
            return self._info_a1
        i = self.lista_a3.currentRow()
        return self._certs_a3[i].info if 0 <= i < len(self._certs_a3) else None

    def _validar(self):
        info = self._info_atual()
        self.ok.setEnabled(info is not None and not info.expirado)

    def _aceitar(self):
        c = self.config
        c.set("assinatura/origem", "a1" if self.abas.currentIndex() == 0 else "a3")
        c.set("assinatura/pfx", self.pfx.text().strip())
        c.set("assinatura/pkcs11", self._caminho_lib())
        c.set("assinatura/visivel", self.rb_visivel.isChecked())
        c.set("assinatura/motivo", self.motivo.text().strip())
        c.set("assinatura/local", self.local.text().strip())
        c.set("assinatura/usar_tsa", self.cb_tsa.isChecked())
        c.set("assinatura/tsa", self.tsa.text().strip())
        self.accept()

    def config_assinatura(self) -> ConfigAssinatura:
        comum = dict(
            motivo=self.motivo.text().strip(),
            local=self.local.text().strip(),
            tsa_url=self.tsa.text().strip() if self.cb_tsa.isChecked() else "",
            visivel=self.rb_visivel.isChecked(),
        )
        if self.abas.currentIndex() == 0:
            return ConfigAssinatura("a1", self._info_a1, pfx=self.pfx.text().strip(),
                                    senha=self.senha.text(), **comum)
        cert = self._certs_a3[self.lista_a3.currentRow()]
        return ConfigAssinatura("a3", cert.info, biblioteca=self._caminho_lib(), token=cert.token,
                                cert_id=cert.id, pin=self.pin.text(), **comum)
