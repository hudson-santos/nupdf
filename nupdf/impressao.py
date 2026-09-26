"""Impressão sem travar o NuPDF.

A janela de impressão padrão do sistema (QPrintDialog) e o QPrinter da
impressora padrão abrem a conexão com a impressora *antes* de qualquer
escolha - com uma impressora de rede/WSD fora do ar, o Windows fica
"Aguardando conexão de impressora…" e o app inteiro congela. Aqui:

- a janela é própria e só LISTA as impressoras (instantâneo, sem conectar);
- a conexão e o envio das páginas acontecem numa thread (QPainter pode
  desenhar num QPrinter fora da thread da interface), com progresso.
"""

import re

import pymupdf
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPageLayout, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from . import ui

DPI_MAXIMO = 300


def interpretar_intervalo(texto: str, total: int) -> list[int]:
    """'1-3, 5' -> [0, 1, 2, 4] (índices). Levanta ValueError se inválido."""
    paginas: list[int] = []
    for parte in re.split(r"[;,]", texto):
        parte = parte.strip()
        if not parte:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", parte)
        if m:
            ini, fim = int(m.group(1)), int(m.group(2))
        elif parte.isdigit():
            ini = fim = int(parte)
        else:
            ini = fim = 0
        if not (1 <= ini <= fim <= total):
            raise ValueError(f"Intervalo inválido: “{parte}” (o documento tem {total} página(s)).")
        paginas.extend(range(ini - 1, fim))
    if not paginas:
        raise ValueError("Informe as páginas a imprimir, por exemplo: 1-3, 5")
    return paginas


class _Contador(QWidget):
    """Campo numérico com botões − e + no visual do app (no lugar das setinhas do QSpinBox)."""

    def __init__(self, minimo: int = 1, maximo: int = 99):
        super().__init__()
        self._min, self._max = minimo, maximo
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._menos = ui.botao("menos", "Menos uma cópia", tamanho=16)
        self._campo = QLineEdit(str(minimo))
        self._campo.setAlignment(Qt.AlignCenter)
        self._campo.setFixedWidth(52)
        self._campo.setValidator(QIntValidator(minimo, maximo, self))
        self._mais = ui.botao("mais", "Mais uma cópia", tamanho=16)
        for w in (self._menos, self._campo, self._mais):
            lay.addWidget(w)
        lay.addStretch(1)
        self._menos.clicked.connect(lambda: self.setValue(self.value() - 1))
        self._mais.clicked.connect(lambda: self.setValue(self.value() + 1))
        self._campo.editingFinished.connect(lambda: self.setValue(self.value()))
        self._atualizar_botoes()

    def value(self) -> int:
        try:
            return int(self._campo.text())
        except ValueError:
            return self._min

    def setValue(self, n: int):
        n = max(self._min, min(self._max, n))
        self._campo.setText(str(n))
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        self._menos.setEnabled(self.value() > self._min)
        self._mais.setEnabled(self.value() < self._max)


class DialogoImpressao(QDialog):
    def __init__(self, n_paginas: int, pagina_atual: int, impressora_salva: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Imprimir")
        self.setMinimumWidth(460)
        self.n_paginas, self.pagina_atual = n_paginas, pagina_atual
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        titulo = QLabel("Imprimir Documento")
        titulo.setStyleSheet("font-size: 17px; font-weight: 700;")
        lay.addWidget(titulo)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        # só lista (EnumPrinters): não conecta em nenhuma impressora
        self.impressora = QComboBox()
        padrao = QPrinterInfo.defaultPrinterName()
        nomes = QPrinterInfo.availablePrinterNames()
        for nome in nomes:
            self.impressora.addItem(f"{nome} ( Padrão )" if nome == padrao else nome, nome)
        escolha = impressora_salva if impressora_salva in nomes else padrao
        if escolha in nomes:
            self.impressora.setCurrentIndex(nomes.index(escolha))
        form.addRow("Impressora:", self.impressora)

        grupo = QButtonGroup(self)
        self.rb_todas = QRadioButton(f"Todas ({n_paginas})")
        self.rb_atual = QRadioButton(f"Página Atual ({pagina_atual + 1})")
        self.rb_intervalo = QRadioButton("Intervalo:")
        for rb in (self.rb_todas, self.rb_atual, self.rb_intervalo):
            grupo.addButton(rb)
        self.rb_todas.setChecked(True)
        self.intervalo = QLineEdit()
        self.intervalo.setPlaceholderText("ex.: 1-3, 5")
        self.intervalo.textEdited.connect(lambda _: self.rb_intervalo.setChecked(True))
        linha_int = QHBoxLayout()
        linha_int.setSpacing(10)
        linha_int.addWidget(self.rb_intervalo)
        linha_int.addWidget(self.intervalo, 1)
        caixa = QVBoxLayout()
        caixa.setContentsMargins(0, 6, 0, 0)  # alinha "Todas" com o rótulo "Páginas:"
        caixa.setSpacing(12)
        caixa.addWidget(self.rb_todas)
        caixa.addWidget(self.rb_atual)
        caixa.addLayout(linha_int)
        form.addRow("Páginas:", caixa)

        self.copias = _Contador(1, 99)
        form.addRow("Cópias:", self.copias)
        lay.addLayout(form)

        self.erro = QLabel()
        self.erro.setObjectName("statusErro")
        self.erro.setWordWrap(True)
        self.erro.hide()
        lay.addWidget(self.erro)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        cancelar = QPushButton("Fechar")
        cancelar.setObjectName("fechar")  # cinza escuro
        cancelar.setCursor(Qt.PointingHandCursor)
        cancelar.clicked.connect(self.reject)
        self.ok = QPushButton("Imprimir")
        self.ok.setObjectName("primario")
        self.ok.setDefault(True)
        self.ok.setEnabled(bool(nomes))
        self.ok.clicked.connect(self._aceitar)
        botoes.addWidget(cancelar)
        botoes.addWidget(self.ok)
        lay.addLayout(botoes)
        if not nomes:
            self.erro.setText("Nenhuma impressora instalada no Windows.")
            self.erro.show()
        self.paginas: list[int] = []

    def _aceitar(self):
        try:
            if self.rb_atual.isChecked():
                self.paginas = [self.pagina_atual]
            elif self.rb_intervalo.isChecked():
                self.paginas = interpretar_intervalo(self.intervalo.text(), self.n_paginas)
            else:
                self.paginas = list(range(self.n_paginas))
        except ValueError as e:
            self.erro.setText(str(e))
            self.erro.show()
            return
        self.accept()

    @property
    def nome_impressora(self) -> str:
        return self.impressora.currentData() or ""


class TrabalhoImpressao(QThread):
    """Conecta na impressora e envia as páginas fora da thread da interface."""

    progresso = Signal(int, int)
    concluido = Signal()
    falhou = Signal(str)

    def __init__(self, dados_pdf: bytes, senha: str | None, paginas: list[int], impressora: str,
                 copias: int, nome_documento: str):
        super().__init__()
        self.dados, self.senha, self.paginas = dados_pdf, senha, paginas
        self.impressora, self.copias, self.nome = impressora, copias, nome_documento
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        doc = None
        try:
            doc = pymupdf.open(stream=self.dados, filetype="pdf")
            if doc.needs_pass:
                doc.authenticate(self.senha or "")
            printer = QPrinter(QPrinterInfo.printerInfo(self.impressora), QPrinter.HighResolution)
            printer.setDocName(self.nome)
            printer.setCopyCount(self.copias)
            primeira = doc[self.paginas[0]].rect
            printer.setPageOrientation(QPageLayout.Landscape if primeira.width > primeira.height
                                       else QPageLayout.Portrait)
            dpi = min(printer.resolution(), DPI_MAXIMO)
            painter = QPainter()
            if not painter.begin(printer):
                raise RuntimeError("Não foi possível iniciar a impressão nesta impressora.")
            try:
                total = len(self.paginas)
                for k, i in enumerate(self.paginas):
                    if self._cancelar:
                        printer.abort()
                        return
                    pg = doc[i]
                    if k:
                        # orientação de cada página (retrato/paisagem) acompanha o PDF
                        printer.setPageOrientation(QPageLayout.Landscape if pg.rect.width > pg.rect.height
                                                   else QPageLayout.Portrait)
                        printer.newPage()
                    pm = pg.get_pixmap(dpi=dpi, alpha=False)
                    img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888)
                    alvo = painter.viewport()
                    escala = min(alvo.width() / img.width(), alvo.height() / img.height())
                    w, h = int(img.width() * escala), int(img.height() * escala)
                    painter.drawImage(alvo.x() + (alvo.width() - w) // 2, alvo.y() + (alvo.height() - h) // 2,
                                      img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.progresso.emit(k + 1, total)
            finally:
                painter.end()
            self.concluido.emit()
        except Exception as e:
            self.falhou.emit(str(e) or e.__class__.__name__)
        finally:
            if doc is not None:
                doc.close()
