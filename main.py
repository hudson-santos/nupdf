"""NuPDF - leitor de PDF leve com cópia de dados e assinatura ICP-Brasil.

Uso: pythonw main.py [arquivo.pdf ...]

Instância única por usuário: se o NuPDF já estiver aberto, os arquivos
recebidos são enviados para a janela existente (abrem em abas novas) e este
processo termina - é o que acontece ao dar duplo clique em vários PDFs no
Explorer.
"""

import getpass
import json
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
    if _enviar_para_instancia_aberta(arquivos):
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
