"""Impressora NuPDF: imprimir de qualquer programa gera um PDF que abre no NuPDF.

Mesmo modelo do PDF24:
- a impressora "NuPDF" usa o driver "Microsoft Print To PDF" do Windows e, como
  porta, o pipe nomeado PORTA - o Windows manda o PDF de cada impressão por ele;
- o AGENTE (main.py --impressora, iniciado com o Windows - chave Run do usuário)
  escuta o pipe, grava o PDF em Documentos\\NuPDF Impressões e o abre no NuPDF.

Instalar/remover a impressora exige administrador: impressora.ps1 roda com a
confirmação do Windows (UAC). O agente roda sem privilégios, só para o usuário.
"""

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

NOME_IMPRESSORA = "NuPDF"
PORTA = r"\\.\pipe\NuPDFPrint"
_MUTEX_AGENTE = "Local\\NuPDF-Impressora"
_PARAR = b"NUPDF-AGENTE-PARAR"  # mensagem que encerra o agente (remover a impressora)
_CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALOR_RUN = "NuPDF Impressora"
APP_DIR = Path(__file__).resolve().parents[1]

_k32 = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None
if _k32 is not None:
    _k32.CreateMutexW.restype = wintypes.HANDLE
    _k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    _k32.OpenMutexW.restype = wintypes.HANDLE
    _k32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]


def pasta_impressoes() -> Path:
    """Documentos\\NuPDF Impressões (a pasta Documentos real, mesmo redirecionada)."""
    try:
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL
        documentos = Path(buf.value) if buf.value else Path.home() / "Documents"
    except Exception:
        documentos = Path.home() / "Documents"
    return documentos / "NuPDF Impressões"


# ---------------------------------------------------------------- situação
def instalada() -> bool:
    """A impressora NuPDF existe no Windows (registro do spooler, sem conectar em nada)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            rf"SYSTEM\CurrentControlSet\Control\Print\Printers\{NOME_IMPRESSORA}"):
            return True
    except OSError:
        return False


def agente_rodando() -> bool:
    if _k32 is None:
        return False
    h = _k32.OpenMutexW(0x00100000, False, _MUTEX_AGENTE)  # SYNCHRONIZE
    if h:
        _k32.CloseHandle(h)
        return True
    return False


def _comando_agente() -> list[str]:
    pythonw = APP_DIR / "python" / "pythonw.exe"
    if not pythonw.exists():  # desenvolvimento / instalações antigas
        pythonw = Path(sys.executable).with_name("pythonw.exe")
    return [str(pythonw), str(APP_DIR / "main.py"), "--impressora"]


def registrar_inicio():
    """Agente iniciado junto com o Windows (só para este usuário)."""
    import winreg
    cmd = " ".join(f'"{p}"' for p in _comando_agente())
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _CHAVE_RUN) as k:
        winreg.SetValueEx(k, _VALOR_RUN, 0, winreg.REG_SZ, cmd)


def remover_inicio():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CHAVE_RUN, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, _VALOR_RUN)
    except OSError:
        pass


def iniciar_agente():
    """Garante o agente rodando (chamado ao abrir o NuPDF e depois de instalar)."""
    if not instalada() or agente_rodando():
        return
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(_comando_agente(), cwd=str(APP_DIR), creationflags=flags, close_fds=True)


def parar_agente():
    try:
        with open(PORTA, "wb") as p:
            p.write(_PARAR)
    except OSError:
        pass


# ---------------------------------------------------------------- instalar (administrador)
def _executar_como_admin(acao: str) -> int:
    """impressora.ps1 -Acao <acao> com a confirmação do Windows (UAC); espera terminar.
    Devolve o código de saída (-1: o usuário recusou a confirmação)."""
    script = APP_DIR / "impressora.ps1"

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), r"System32\WindowsPowerShell\v1.0\powershell.exe")
    info.lpParameters = f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}" -Acao {acao}'
    info.nShow = 0
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        return -1  # cancelado na confirmação do Windows
    _k32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    codigo = wintypes.DWORD()
    _k32.GetExitCodeProcess(info.hProcess, ctypes.byref(codigo))
    _k32.CloseHandle(info.hProcess)
    return codigo.value


def instalar() -> int:
    codigo = _executar_como_admin("instalar")
    if codigo == 0 and instalada():
        registrar_inicio()
        iniciar_agente()
    return codigo


def remover() -> int:
    parar_agente()
    remover_inicio()
    return _executar_como_admin("remover")


# ---------------------------------------------------------------- agente
def _abrir_no_nupdf(arquivo: Path):
    exe = APP_DIR / "NuPDF.exe"
    if exe.exists():
        cmd = [str(exe), str(arquivo)]
    else:
        cmd = [_comando_agente()[0], str(APP_DIR / "main.py"), str(arquivo)]
    subprocess.Popen(cmd, cwd=str(APP_DIR), close_fds=True)


def _gravar_impressao(dados: bytes) -> Path:
    pasta = pasta_impressoes()
    pasta.mkdir(parents=True, exist_ok=True)
    base = "Impressão " + datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    destino, n = pasta / f"{base}.pdf", 2
    while destino.exists():
        destino, n = pasta / f"{base} ({n}).pdf", n + 1
    destino.write_bytes(dados)
    return destino


def agente():
    """Escuta o pipe da impressora: cada conexão do Windows é uma impressão (o PDF
    inteiro); grava e abre no NuPDF. Uma instância por usuário."""
    mutex = _k32.CreateMutexW(None, False, _MUTEX_AGENTE)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: já está rodando
        return
    PIPE_ACCESS_INBOUND, PIPE_TYPE_BYTE, PIPE_WAIT, ILIMITADO = 0x1, 0x0, 0x0, 255
    _k32.CreateNamedPipeW.restype = wintypes.HANDLE
    _k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    _k32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    _k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                              ctypes.c_void_p]
    _k32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
    INVALIDO = wintypes.HANDLE(-1).value
    buf = ctypes.create_string_buffer(1 << 20)
    try:
        while True:
            h = _k32.CreateNamedPipeW(PORTA, PIPE_ACCESS_INBOUND, PIPE_TYPE_BYTE | PIPE_WAIT, ILIMITADO,
                                      0, 1 << 20, 0, None)
            if not h or h == INVALIDO:
                time.sleep(2)
                continue
            try:
                ok = _k32.ConnectNamedPipe(h, None) or ctypes.get_last_error() == 535  # PIPE_CONNECTED
                if not ok:
                    continue
                partes, lido = [], wintypes.DWORD()
                while True:  # até o Windows fechar o pipe (fim da impressão)
                    ok = _k32.ReadFile(h, buf, len(buf), ctypes.byref(lido), None)
                    if lido.value:
                        partes.append(buf.raw[:lido.value])
                    if not ok or not lido.value:
                        break
                dados = b"".join(partes)
            finally:
                _k32.DisconnectNamedPipe(h)
                _k32.CloseHandle(h)
            if dados == _PARAR:
                return
            if dados.lstrip()[:5] == b"%PDF-":
                try:
                    _abrir_no_nupdf(_gravar_impressao(dados))
                except Exception:
                    pass
    finally:
        _k32.CloseHandle(mutex)
