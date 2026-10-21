"""NuPDF - leitor de PDF leve com cópia de dados e assinatura ICP-Brasil.

Uso: pythonw main.py [arquivo.pdf ...]
     pythonw main.py --juntar arquivo.pdf ...   (menu de contexto NuPDF > Juntar)
     pythonw main.py --impressora               (agente da Impressora NuPDF, sem janela)

Instância única por usuário: se o NuPDF já estiver aberto, os arquivos
recebidos são enviados para a janela existente (abrem em abas novas) e este
processo termina - é o que acontece ao dar duplo clique em vários PDFs no
Explorer.
"""

import sys

if __name__ == "__main__" and "--impressora" in sys.argv:
    # agente da Impressora NuPDF: só escuta o pipe da impressora - sem Qt (leve)
    from nupdf.impressora_virtual import agente
    agente()
    sys.exit(0)

import getpass
import json
import logging
import os
import time
import traceback

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from nupdf.versao import NOME_APP, VERSAO

APP_ID = "NuPDF.App"
SERVIDOR = f"NuPDF-{getpass.getuser()}"


def _definir_app_id():
    """Mesmo AppUserModelID gravado nos atalhos pelo instalador
    (criar_atalho_appid.ps1) - sem ele, "Fixar na barra de tarefas"
    a partir da janela aberta mostraria o ícone do pythonw.exe."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _arquivos_da_linha_de_comando() -> list[str]:
    return [os.path.abspath(a) for a in sys.argv[1:] if a.lower().endswith(".pdf")]


def _pediu_juntar() -> bool:
    # o NuPDF.exe até a 1.22.1 transformava "--juntar" em caminho (C:\NuPDF\--juntar)
    return any(os.path.basename(a) == "--juntar" for a in sys.argv[1:])


def _aguardar_primeira_instancia(arquivos: list[str], juntar: bool) -> bool:
    """Vários NuPDFs iniciados juntos (o Explorer abre um por PDF selecionado): o primeiro
    pega o mutex e o segura até fechar; os outros esperam a janela dele ficar pronta e
    entregam os arquivos a ela (True). False: este processo é o primeiro e abre a janela."""
    import ctypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k32.WaitForSingleObject.restype = ctypes.c_uint32
    global _MUTEX_INICIO  # fica aberto (e nosso) enquanto este processo viver
    _MUTEX_INICIO = k32.CreateMutexW(None, True, f"Local\\NuPDF-Inicio-{getpass.getuser()}")
    if not _MUTEX_INICIO or ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
        return False
    inicio = time.monotonic()
    while time.monotonic() - inicio < 20:
        if _enviar_para_instancia_aberta(arquivos, juntar):
            return True
        if k32.WaitForSingleObject(_MUTEX_INICIO, 200) in (0, 0x80):
            break  # o primeiro terminou sem abrir a janela (ex.: foi instalar atualização)
    return False


_MUTEX_INICIO = None


MARCA_JUNTAR = "#JUNTAR"  # 1ª linha da mensagem para a instância aberta: abrir a tela de juntar
_FILA_JUNTAR = os.path.join(os.environ.get("TEMP", "."), f"nupdf_juntar_{getpass.getuser()}.txt")


def _reunir_para_juntar(arquivos: list[str]) -> list[str] | None:
    """Menu de contexto "Juntar PDFs com o NuPDF": o Explorer abre um NuPDF POR ARQUIVO
    selecionado, quase ao mesmo tempo. Cada um anota o seu arquivo numa fila; o primeiro
    (que pega o mutex) espera a fila parar de crescer e devolve todos - os outros
    terminam (None)."""
    import ctypes
    for _ in range(50):  # anota na fila (outro processo pode estar gravando)
        try:
            with open(_FILA_JUNTAR, "a", encoding="utf-8") as f:
                f.write("".join(a + "\n" for a in arquivos))
            break
        except OSError:
            time.sleep(0.02)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = k32.CreateMutexW(None, False, "Local\\NuPDF-Juntar")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: outro processo reúne a lista
        k32.CloseHandle(mutex)
        return None
    try:
        tamanho, parado_desde, inicio = -1, time.monotonic(), time.monotonic()
        while time.monotonic() - inicio < 6:
            atual = os.path.getsize(_FILA_JUNTAR) if os.path.exists(_FILA_JUNTAR) else 0
            if atual != tamanho:
                tamanho, parado_desde = atual, time.monotonic()
            elif time.monotonic() - parado_desde > 0.8:
                break
            time.sleep(0.1)
        try:
            with open(_FILA_JUNTAR, encoding="utf-8") as f:
                linhas = [l.strip() for l in f if l.strip()]
            os.remove(_FILA_JUNTAR)
        except OSError:
            linhas = list(arquivos)
    finally:
        k32.CloseHandle(mutex)
    vistos, saida = set(), []
    for c in linhas:
        if os.path.normcase(c) not in vistos:
            vistos.add(os.path.normcase(c))
            saida.append(c)
    return saida


def _enviar_para_instancia_aberta(arquivos: list[str], juntar: bool = False) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SERVIDOR)
    if not sock.waitForConnected(400):
        return False
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # deixa a janela existente vir para a frente
    except Exception:
        pass
    linhas = ([MARCA_JUNTAR] if juntar else []) + arquivos
    sock.write(QByteArray(("\n".join(linhas) + "\n").encode("utf-8")))
    sock.waitForBytesWritten(1500)
    sock.disconnectFromServer()
    return True


def _iniciar_servidor(janela) -> QLocalServer:
    QLocalServer.removeServer(SERVIDOR)  # limpa sobra de uma execução que caiu
    servidor = QLocalServer(janela)
    servidor.setSocketOptions(QLocalServer.UserAccessOption)

    def nova_conexao():
        sock = servidor.nextPendingConnection()
        buffer = bytearray()

        def ler():
            buffer.extend(bytes(sock.readAll()))

        def fim():
            ler()
            if janela.isMinimized():
                janela.showNormal()
            janela.raise_()
            janela.activateWindow()
            linhas = [l.strip() for l in buffer.decode("utf-8", "ignore").splitlines() if l.strip()]
            if linhas and linhas[0] == MARCA_JUNTAR:
                QTimer.singleShot(0, lambda: janela.juntar_pdfs(linhas[1:]))
            else:
                for caminho in linhas:
                    janela.abrir_arquivo(caminho)
            sock.deleteLater()

        sock.readyRead.connect(ler)
        sock.disconnected.connect(fim)

    servidor.newConnection.connect(nova_conexao)
    servidor.listen(SERVIDOR)
    return servidor


def _arquivo_abrir_depois():
    from nupdf.config import pasta_dados
    return pasta_dados() / "abrir_apos_atualizar.json"


def _instalar_atualizacao_pendente(arquivos: list[str]) -> bool:
    """Atualização automática: se a verificação diária já baixou o instalador de
    uma versão nova, instala agora em modo silencioso (só a janelinha de progresso)
    e o próprio instalador reabre o NuPDF ao final. Os PDFs pedidos nesta abertura
    ficam anotados e são abertos pelo NuPDF já atualizado."""
    from nupdf import atualizacao
    pendente = atualizacao.atualizacao_pendente()
    if pendente is None:
        return False
    anotacao = _arquivo_abrir_depois()
    try:
        if arquivos:
            anotacao.write_text(json.dumps(arquivos), encoding="utf-8")
    except OSError:
        pass
    if atualizacao.instalar_pendente(pendente):
        return True
    anotacao.unlink(missing_ok=True)
    return False


def _arquivos_apos_atualizacao() -> list[str]:
    anotacao = _arquivo_abrir_depois()
    if not anotacao.is_file():
        return []
    try:
        lista = json.loads(anotacao.read_text(encoding="utf-8"))
        anotacao.unlink(missing_ok=True)
    except (OSError, ValueError):
        return []
    return [c for c in lista if isinstance(c, str)]


def _erro_nao_tratado(tipo, valor, tb):
    texto = "".join(traceback.format_exception(tipo, valor, tb))
    if sys.__stderr__:
        sys.__stderr__.write(texto)
    QMessageBox.critical(None, NOME_APP, f"Ocorreu um erro inesperado:\n\n{valor}\n\n{texto[-1500:]}")


def main() -> int:
    logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
    logging.getLogger("pyhanko_certvalidator").setLevel(logging.CRITICAL)
    _definir_app_id()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    arquivos = _arquivos_da_linha_de_comando()
    juntar = _pediu_juntar()
    if juntar:
        arquivos = _reunir_para_juntar(arquivos)
        if arquivos is None:
            return 0  # outro processo do mesmo clique reúne os arquivos
    if _enviar_para_instancia_aberta(arquivos, juntar):
        return 0
    if _aguardar_primeira_instancia(arquivos, juntar):
        return 0
    if _instalar_atualizacao_pendente(arquivos):
        return 0
    arquivos = _arquivos_apos_atualizacao() + arquivos

    from nupdf.icones import icone_app
    from nupdf.janela import JanelaPrincipal

    app.setApplicationName(NOME_APP)
    app.setApplicationVersion(VERSAO)
    app.setOrganizationName(NOME_APP)
    app.setWindowIcon(icone_app())
    app.setStyle("Fusion")
    sys.excepthook = _erro_nao_tratado

    janela = JanelaPrincipal(verificar_atualizacao=True)
    _iniciar_servidor(janela)
    janela.showMaximized()
    if juntar:
        QTimer.singleShot(0, lambda: janela.juntar_pdfs(arquivos))
    elif arquivos:
        # abre depois do primeiro desenho: a janela aparece na hora e o PDF entra em seguida
        QTimer.singleShot(0, lambda: [janela.abrir_arquivo(arq) for arq in arquivos])
    else:
        # pré-carga da aba de documento (PyMuPDF etc.) logo após a janela aparecer -
        # o primeiro "Abrir PDF" não paga essa importação
        from nupdf.janela import preparar_documentos
        QTimer.singleShot(150, preparar_documentos)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
