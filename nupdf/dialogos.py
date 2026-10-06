"""Diálogo de configuração da assinatura digital (certificados instalados no Windows)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QFrame, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QRadioButton, QVBoxLayout)

from . import ui
from .assinatura.assinador import ConfigAssinatura
from .assinatura.certificado import InfoCertificado
from .assinatura.windows import CertificadoWindows, listar_certificados
from .config import Config


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
        # só avisa quando há problema (vencidos já nem aparecem na lista)
        self.status.setObjectName("statusErro")
        self.status.setText("Certificado fora da validade" if info.expirado else "")
        self.status.setVisible(info.expirado)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)


class DialogoAssinatura(QDialog):
    def __init__(self, config: Config, parent=None, certificados: list[CertificadoWindows] | None = None):
        """`certificados`: lista já carregada (a janela carrega em segundo plano, com o
        spinner "Carregando Certificados...", antes de abrir esta tela)."""
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Assinar Documento")
        self.setMinimumWidth(680)  # cabe o rótulo inteiro do certificado

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        titulo = QLabel("Assinatura Digital ICP-Brasil")
        titulo.setStyleSheet("font-size: 17px; font-weight: 700;")
        lay.addWidget(titulo)

        # certificado: lista dos instalados no Windows (repositório Pessoal)
        grupo = QGroupBox("Certificado digital")
        gl = QVBoxLayout(grupo)
        gl.setSpacing(8)
        linha = QHBoxLayout()
        self.lista = QComboBox()
        # seleção só por clique: o campo inteiro abre a lista (sem digitação/busca)
        self.lista.setMaxVisibleItems(15)
        self.lista.setMinimumContentsLength(40)
        self.lista.setCursor(Qt.PointingHandCursor)
        self.lista.currentIndexChanged.connect(self._escolhido)
        atualizar = ui.botao("girar", "Atualizar a lista de certificados", tamanho=16)
        atualizar.clicked.connect(lambda: self._carregar_lista())
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

        # aparência (motivo, local e carimbo de tempo não são pedidos)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        linha_ap = QHBoxLayout()
        linha_ap.setSpacing(18)
        self.rb_visivel = QRadioButton("Visível ( Posicionar na Página )")
        self.rb_invisivel = QRadioButton("Invisível")
        (self.rb_visivel if config.get("assinatura/visivel", True) else self.rb_invisivel).setChecked(True)
        linha_ap.addWidget(self.rb_visivel)
        linha_ap.addWidget(self.rb_invisivel)
        linha_ap.addStretch(1)
        form.addRow("Aparência:", linha_ap)
        lay.addLayout(form)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        cancelar = QPushButton("Cancelar")
        cancelar.setObjectName("fechar")  # cinza escuro, mesmo visual do "Fechar"
        cancelar.setCursor(Qt.PointingHandCursor)
        cancelar.clicked.connect(self.reject)
        self.ok = QPushButton("Continuar")
        self.ok.setObjectName("primario")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._aceitar)
        botoes.addWidget(cancelar)
        botoes.addWidget(self.ok)
        lay.addLayout(botoes)
        self._carregar_lista(certificados)

    # ------------------------------------------------------------------ certificado
    def _carregar_lista(self, todos: list[CertificadoWindows] | None = None):
        if todos is None:
            QGuiApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                todos = listar_certificados()
            finally:
                QGuiApplication.restoreOverrideCursor()
        self._certs = [c for c in todos if not c.info.expirado]
        self.lista.blockSignals(True)
        self.lista.clear()
        for c in self._certs:
            self.lista.addItem(c.rotulo(), c.impressao)
        salvo = self.config.get("assinatura/certificado", "")
        idx = self.lista.findData(salvo) if salvo else -1
        self.lista.setCurrentIndex(idx if idx >= 0 else (0 if self._certs else -1))
        self.lista.blockSignals(False)
        # só orienta quando não há certificado; a contagem não é exibida
        self.aviso.setText("Nenhum certificado digital válido instalado no Windows. Para instalar um "
                           "certificado A1, dê duplo clique no arquivo .pfx e siga o assistente; "
                           "depois clique em atualizar.")
        self.aviso.setVisible(not self._certs)
        self._escolhido(self.lista.currentIndex())

    def _atual(self) -> CertificadoWindows | None:
        i = self.lista.currentIndex()
        if 0 <= i < len(self._certs):
            return self._certs[i]
        return None

    def _escolhido(self, _i: int = -1):
        c = self._atual()
        if c:
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
        self.accept()

    def config_assinatura(self) -> ConfigAssinatura:
        cert = self._atual()
        return ConfigAssinatura(
            cert.info,
            impressao=cert.impressao,
            der=cert.der,
            visivel=self.rb_visivel.isChecked(),
        )
