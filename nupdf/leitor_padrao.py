"""Leitor de PDF padrão do Windows: verifica se é o NuPDF e ajuda a torná-lo padrão.

O Windows 10/11 não deixa um programa se declarar padrão sozinho (a escolha
fica protegida por um hash que só o próprio Windows gera) e bloqueia até a
janela "Abrir com" chamada por um programa ("Para alterar os aplicativos
padrão, vá para Configurações..."). O caminho aceito é a página do NuPDF em
Configurações > Aplicativos > Aplicativos padrão, onde o usuário clica em
"Definir padrão".
"""

import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

PROGID = "NuPDF.Documento"  # ver instalar.ps1
PROGIDS_NUPDF = {PROGID.lower(), "applications\\nupdf.exe"}
_CAPACIDADES = "Software\\NuPDF\\Capabilities"

_ASSOCSTR_EXECUTABLE = 2
_ASSOCSTR_FRIENDLYAPPNAME = 4
_ASSOCSTR_PROGID = 20


def _assoc(tipo: int) -> str:
    """Associação EFETIVA de .pdf para o usuário (considera UserChoice/UserChoiceLatest)."""
    try:
        n = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(n.value)
        if ctypes.windll.shlwapi.AssocQueryStringW(0, tipo, ".pdf", None, buf, ctypes.byref(n)) == 0:
            return buf.value
    except Exception:
        pass
    return ""


def e_padrao() -> bool | None:
    """True/False no Windows; None quando não dá para saber (outro sistema)."""
    if sys.platform != "win32":
        return None
    if _assoc(_ASSOCSTR_PROGID).lower() in PROGIDS_NUPDF:
        return True
    return os.path.basename(_assoc(_ASSOCSTR_EXECUTABLE)).lower() == "nupdf.exe"


def leitor_atual() -> str:
    """Nome amigável do leitor de PDF padrão atual (vazio se nenhum)."""
    return _assoc(_ASSOCSTR_FRIENDLYAPPNAME)


def registrar_nas_configuracoes() -> bool:
    """Garante a página do NuPDF em "Aplicativos padrão" (HKCU, sem admin). O
    instalar.ps1 já faz isso; aqui cobre instalações anteriores a ele."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + PROGID):
            pass  # só registra se o "Abrir com" do NuPDF existir (NuPDF instalado)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CAPACIDADES) as k:
            winreg.SetValueEx(k, "ApplicationName", 0, winreg.REG_SZ, "NuPDF")
            winreg.SetValueEx(k, "ApplicationDescription", 0, winreg.REG_SZ,
                              "Leitor de PDF com assinatura digital ICP-Brasil")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CAPACIDADES + "\\FileAssociations") as k:
            winreg.SetValueEx(k, ".pdf", 0, winreg.REG_SZ, PROGID)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\RegisteredApplications") as k:
            winreg.SetValueEx(k, "NuPDF", 0, winreg.REG_SZ, _CAPACIDADES)
        return True
    except OSError:
        return False


def abrir_configuracoes():
    """Abre a página do NuPDF em Aplicativos padrão (ou a lista geral, se não registrado)."""
    url = ("ms-settings:defaultapps?registeredAppUser=NuPDF" if registrar_nas_configuracoes()
           else "ms-settings:defaultapps")
    QDesktopServices.openUrl(QUrl(url))


class DialogoLeitorPadrao(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Leitor de PDF Padrão")
        self.setMinimumWidth(500)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        titulo = QLabel("Tornar o NuPDF o Leitor de PDF Padrão")
        titulo.setStyleSheet("font-size: 17px; font-weight: 700;")
        lay.addWidget(titulo)

        atual = leitor_atual()
        agora = f"Hoje os arquivos PDF abrem no <b>{atual}</b>. " if atual and atual != "NuPDF" else ""
        texto = QLabel(agora + "Clique em <b>Definir como Padrão</b>: as Configurações do Windows vão "
                       "abrir na página do NuPDF - lá, clique em <b>Definir padrão</b>.")
        texto.setWordWrap(True)
        texto.setTextFormat(Qt.RichText)
        lay.addWidget(texto)

        self.pendente = QLabel("O NuPDF ainda não é o leitor padrão. Nas Configurações do Windows, "
                               "clique em \"Definir padrão\" na página do NuPDF.")
        self.pendente.setObjectName("statusAviso")
        self.pendente.setWordWrap(True)
        self.pendente.hide()
        lay.addWidget(self.pendente)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        agora_nao = QPushButton("Agora Não")
        agora_nao.setObjectName("fechar")  # cinza escuro, mesmo visual do "Fechar"
        agora_nao.setCursor(Qt.PointingHandCursor)
        agora_nao.clicked.connect(self.reject)
        self.ok = QPushButton("Definir como Padrão")
        self.ok.setObjectName("primario")
        self.ok.setCursor(Qt.PointingHandCursor)
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._definir)
        botoes.addWidget(agora_nao)
        botoes.addWidget(self.ok)
        lay.addLayout(botoes)
        self._abriu_configuracoes = False

    def _definir(self):
        self._abriu_configuracoes = True
        abrir_configuracoes()

    def changeEvent(self, e):
        # ao voltar das Configurações: fecha se já virou padrão, senão orienta
        if (e.type() == QEvent.ActivationChange and self.isActiveWindow()
                and self._abriu_configuracoes):
            if e_padrao():
                self.accept()
            else:
                self.pendente.show()
        super().changeEvent(e)
