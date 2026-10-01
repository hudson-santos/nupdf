"""NuPDF - leitor de PDF leve com cópia de dados e assinatura ICP-Brasil.

Uso: pythonw main.py [arquivo.pdf ...]

Instância única por usuário: se o NuPDF já estiver aberto, os arquivos
recebidos são enviados para a janela existente (abrem em abas novas) e este
processo termina - é o que acontece ao dar duplo clique em vários PDFs no
Explorer.
"""

import getpass
import logging
import os
import sys
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


def _enviar_para_instancia_aberta(arquivos: list[str]) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SERVIDOR)
    if not sock.waitForConnected(400):
        return False
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # deixa a janela existente vir para a frente
    except Exception:
        pass
    sock.write(QByteArray(("\n".join(arquivos) + "\n").encode("utf-8")))
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
            for caminho in buffer.decode("utf-8", "ignore").splitlines():
                if caminho.strip():
                    janela.abrir_arquivo(caminho.strip())
            sock.deleteLater()

        sock.readyRead.connect(ler)
        sock.disconnected.connect(fim)

    servidor.newConnection.connect(nova_conexao)
    servidor.listen(SERVIDOR)
    return servidor


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
    if _enviar_para_instancia_aberta(arquivos):
        return 0

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
    if arquivos:
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
