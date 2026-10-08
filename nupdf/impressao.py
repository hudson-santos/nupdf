"""Impressão sem travar o NuPDF.

A janela de impressão padrão do sistema (QPrintDialog) e o QPrinter da
impressora padrão abrem a conexão com a impressora *antes* de qualquer
escolha - com uma impressora de rede/WSD fora do ar, o Windows fica
"Aguardando conexão de impressora…" e o app inteiro congela. Aqui:

- a janela é própria e só LISTA as impressoras (instantâneo, sem conectar);
- as configurações do driver (DEVMODE) e o que a impressora suporta (cor, frente e
  verso) são lidos numa thread ao escolher a impressora; "Propriedades" abre a
  janela do próprio driver (papel, bandeja, qualidade...) - ver impressora_win.py;
- a conexão e o envio das páginas acontecem numa thread, com progresso: no Windows
  pela API do Windows com essas configurações; fora dele, pelo QPrinter.
"""

import re

import pymupdf
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPageLayout, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from . import impressora_win as win
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
        linha_imp = QHBoxLayout()
        linha_imp.setSpacing(8)
        linha_imp.addWidget(self.impressora, 1)
        # janela de propriedades do DRIVER (mesma do Word/Adobe): cor, frente e verso,
        # papel, bandeja, qualidade - o que a impressora oferecer
        self.b_propriedades = QPushButton("Propriedades")
        self.b_propriedades.setObjectName("fechar")  # cinza escuro (botão secundário do app)
        self.b_propriedades.setCursor(Qt.PointingHandCursor)
        self.b_propriedades.setToolTip("Abrir as Propriedades da Impressora (configurações do driver)")
        self.b_propriedades.clicked.connect(self._abrir_propriedades)
        self.b_propriedades.setVisible(win.disponivel())
        linha_imp.addWidget(self.b_propriedades)
        form.addRow("Impressora:", linha_imp)

        # atalhos das opções mais usadas - só aparecem se a impressora tiver o recurso
        self.cor = QComboBox()
        self.cor.addItem("Colorido", win.DMCOLOR_COLORIDO)
        self.cor.addItem("Preto e Branco", win.DMCOLOR_PRETO_E_BRANCO)
        self.duplex = QComboBox()
        self.duplex.addItem("Imprimir um Lado", win.DMDUP_UM_LADO)
        self.duplex.addItem("Frente e Verso ( Borda Longa )", win.DMDUP_BORDA_LONGA)
        self.duplex.addItem("Frente e Verso ( Borda Curta )", win.DMDUP_BORDA_CURTA)
        self._rotulo_cor, self._rotulo_duplex = QLabel("Cor:"), QLabel("Frente e Verso:")
        form.addRow(self._rotulo_cor, self.cor)
        form.addRow(self._rotulo_duplex, self.duplex)
        for w in (self._rotulo_cor, self.cor, self._rotulo_duplex, self.duplex):
            w.hide()
        self.devmode: bytearray | None = None  # configurações do driver da impressora escolhida
        self.capacidades = {"cor": False, "duplex": False, "copias": 1}
        self._leitura = None
        self.impressora.currentIndexChanged.connect(lambda _: self._ler_impressora())

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
        if nomes:
            self._ler_impressora()

    # ------------------------------------------------------------------ driver da impressora
    def _ler_impressora(self):
        """Configurações e capacidades do driver numa thread: impressora de rede fora do
        ar não trava a janela (as opções só aparecem quando a resposta chega)."""
        self.devmode = None
        self.capacidades = {"cor": False, "duplex": False, "copias": 1}
        self._mostrar_opcoes()
        if not win.disponivel():
            return
        nome = self.nome_impressora

        def ler():
            dm = win.devmode_padrao(nome)
            return nome, dm, win.capacidades(nome, dm)

        self._leitura = ui.Tarefa(ler)
        self._leitura.concluida.connect(self._impressora_lida)
        self._leitura.start()

    def _impressora_lida(self, resultado):
        nome, dm, caps = resultado
        if nome != self.nome_impressora:
            return  # resposta de uma impressora que já não está escolhida
        self.devmode, self.capacidades = dm, caps
        self._sincronizar_opcoes()
        self._mostrar_opcoes()

    def _sincronizar_opcoes(self):
        """Combos Cor / Frente e Verso refletem o DEVMODE (padrão ou da janela Propriedades)."""
        if self.devmode is None:
            return
        for combo, valor in ((self.cor, win.cor(self.devmode)), (self.duplex, win.duplex(self.devmode))):
            i = combo.findData(valor) if valor is not None else -1
            combo.setCurrentIndex(i if i >= 0 else 0)

    def _mostrar_opcoes(self):
        tem_cor = self.devmode is not None and self.capacidades["cor"]
        tem_duplex = self.devmode is not None and self.capacidades["duplex"]
        for w in (self._rotulo_cor, self.cor):
            w.setVisible(tem_cor)
        for w in (self._rotulo_duplex, self.duplex):
            w.setVisible(tem_duplex)
        self.adjustSize()

    def _abrir_propriedades(self):
        nome = self.nome_impressora
        if not nome:
            return
        try:
            if self.devmode is None:
                self.devmode = win.devmode_padrao(nome)
                self.capacidades = win.capacidades(nome, self.devmode)
            novo = win.propriedades(int(self.winId()), nome, self.devmode_final())
        except OSError as e:
            self.erro.setText(str(e))
            self.erro.show()
            return
        if novo is not None:
            self.devmode = novo
            self._sincronizar_opcoes()
            self._mostrar_opcoes()

    def devmode_final(self) -> bytearray | None:
        """DEVMODE com as escolhas dos atalhos Cor e Frente e Verso aplicadas."""
        if self.devmode is None:
            return None
        dm = bytearray(self.devmode)
        if self.capacidades["cor"]:
            win.definir_cor(dm, self.cor.currentData())
        if self.capacidades["duplex"]:
            win.definir_duplex(dm, self.duplex.currentData())
        return dm

    @property
    def preto_e_branco(self) -> bool:
        if self.devmode is None:
            return False
        if self.capacidades["cor"]:
            return self.cor.currentData() == win.DMCOLOR_PRETO_E_BRANCO
        return win.cor(self.devmode) == win.DMCOLOR_PRETO_E_BRANCO

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
                 copias: int, nome_documento: str, devmode: bytearray | None = None,
                 capacidades: dict | None = None, preto_e_branco: bool = False):
        """`devmode`: configurações do driver (diálogo de impressão); com ele, imprime pela
        API do Windows respeitando cor, frente e verso, papel, bandeja..."""
        super().__init__()
        self.dados, self.senha, self.paginas = dados_pdf, senha, paginas
        self.impressora, self.copias, self.nome = impressora, copias, nome_documento
        self.devmode, self.capacidades = devmode, capacidades or {}
        self.preto_e_branco = preto_e_branco
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        doc = None
        try:
            doc = pymupdf.open(stream=self.dados, filetype="pdf")
            if doc.needs_pass:
                doc.authenticate(self.senha or "")
            if self.devmode is not None and win.disponivel():
                self._imprimir_windows(doc)
                return
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

    def _imprimir_windows(self, doc):
        """Pela API do Windows, com o DEVMODE do diálogo. Cópias: pelo driver quando ele
        suporta (agrupadas); senão, um trabalho por cópia (frente e verso não mistura
        o fim de uma cópia com o começo da outra)."""
        dm = bytearray(self.devmode)
        copias_driver = self.copias <= int(self.capacidades.get("copias", 1))
        if copias_driver:
            win.definir_copias(dm, self.copias)
        rodadas = 1 if copias_driver else self.copias
        total = len(self.paginas) * rodadas
        feitas = 0
        for _ in range(rodadas):
            trabalho = win.Trabalho(self.impressora, dm, self.nome, getattr(self, "arquivo_saida", None))
            try:
                dpi = min(trabalho.dpi, DPI_MAXIMO)
                for i in self.paginas:
                    if self._cancelar:
                        trabalho.fechar(cancelar=True)
                        return
                    pg = doc[i]
                    # preto e branco: a página já vai em tons de cinza (spool menor)
                    cs = pymupdf.csGRAY if self.preto_e_branco else pymupdf.csRGB
                    pm = pg.get_pixmap(dpi=dpi, alpha=False, colorspace=cs)
                    fmt = QImage.Format_Grayscale8 if self.preto_e_branco else QImage.Format_RGB888
                    img = QImage(pm.samples, pm.width, pm.height, pm.stride, fmt).convertToFormat(
                        QImage.Format_RGB32)
                    trabalho.pagina(bytes(img.constBits()), img.width(), img.height(),
                                    paisagem=pg.rect.width > pg.rect.height)
                    feitas += 1
                    self.progresso.emit(feitas, total)
            except Exception:
                trabalho.fechar(cancelar=True)
                raise
            trabalho.fechar()
        self.concluido.emit()
