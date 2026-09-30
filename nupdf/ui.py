"""Utilitários de interface: botões com ícone que acompanham o tema, toast e
execução de tarefas em segundo plano."""

from PySide6.QtCore import QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QToolButton, QWidget

from . import tema
from .icones import icone, largura_icone

_cores: dict = tema.ESCURO
_registro: list = []  # (widget, nome_icone, tamanho, chave_cor)


def cores() -> dict:
    return _cores


def definir_cores(c: dict):
    global _cores
    _cores = c
    vivos = []
    for item in _registro:
        w, nome, tam, chave = item
        try:
            w.setIcon(icone(nome, _cores[chave], tam))
            vivos.append(item)
        except RuntimeError:  # widget já destruído
            pass
    _registro[:] = vivos


def aplicar_icone(w, nome: str, tamanho: int = 18, chave_cor: str = "texto2"):
    w.setIcon(icone(nome, _cores[chave_cor], tamanho))
    w.setIconSize(QSize(largura_icone(nome, tamanho), tamanho))
    _registro.append((w, nome, tamanho, chave_cor))


def botao(nome: str, dica: str = "", checavel=False, tamanho=18, obj: str | None = None,
          chave_cor="texto2", pai: QWidget | None = None) -> QToolButton:
    b = QToolButton(pai)
    aplicar_icone(b, nome, tamanho, chave_cor)
    b.setToolTip(dica)
    b.setCheckable(checavel)
    b.setCursor(Qt.PointingHandCursor)
    b.setAutoRaise(True)
    if obj:
        b.setObjectName(obj)
    return b


VERMELHO = ("#c62828", "#b71c1c")  # (cor, cor ao passar o mouse)
CINZA = ("#4b4d53", "#5b5d64")


class BotaoRedondo(QAbstractButton):
    """Botão circular com ícone branco (ações sobre miniaturas e marcadores).

    Desenhado à mão (círculo com antialiasing): o border-radius do QSS com raio igual
    à metade do tamanho corta 1px no topo/base da borda."""

    def __init__(self, nome_icone: str, cores: tuple[str, str], dica: str = "", tamanho: int = 30):
        super().__init__()
        self._cor, self._cor_hover = cores
        self._icone = icone(nome_icone, "#ffffff", 16)
        self.setFixedSize(tamanho, tamanho)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(dica)

    def sizeHint(self) -> QSize:
        return self.size()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._cor_hover if self.underMouse() and self.isEnabled() else self._cor))
        p.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        self._icone.paint(p, self.rect().adjusted((self.width() - 16) // 2, (self.height() - 16) // 2,
                                                  -((self.width() - 16) // 2), -((self.height() - 16) // 2)))
        p.end()


def separador_horizontal() -> QFrame:
    s = QFrame()
    s.setFixedHeight(1)
    s.setObjectName("sep")  # mesma cor do separador vertical
    return s


def separador_vertical(altura=22) -> QFrame:
    s = QFrame()
    s.setFixedSize(1, altura)
    s.setObjectName("sep")
    return s


class Toast(QLabel):
    """Mensagem curta flutuante na parte de baixo do widget pai."""

    def __init__(self, pai: QWidget):
        super().__init__(pai)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._timer = QTimer(self, singleShot=True, timeout=self.hide)

    def mostrar(self, texto: str, ms: int = 1800):
        self.setText(texto)
        self.adjustSize()
        pai = self.parentWidget()
        self.move((pai.width() - self.width()) // 2, pai.height() - self.height() - 90)
        self.raise_()
        self.show()
        self._timer.start(ms)


class Tarefa(QThread):
    """Executa fn(*args) fora da thread da interface."""

    concluida = Signal(object)
    falhou = Signal(str)

    _ativas: set = set()

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs
        Tarefa._ativas.add(self)
        self.finished.connect(lambda: Tarefa._ativas.discard(self))

    def run(self):
        try:
            self.concluida.emit(self._fn(*self._args, **self._kwargs))
        except Exception as e:
            self.falhou.emit(str(e) or e.__class__.__name__)
