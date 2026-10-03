"""Verificação e download de atualizações (releases do GitHub).

A release é criada pelo workflow .github/workflows/versao.yml a cada commit
"release - [X.Y.Z]", com o Instalador.exe anexado e as notas copiadas do
CHANGELOG.md. Só a biblioteca padrão é usada: urllib respeita o proxy
configurado no Windows e o ssl usa o repositório de certificados do sistema
(inclusive certificados de inspeção SSL corporativos).

Atualização automática: a verificação diária (janela.py) baixa o instalador da
versão nova em segundo plano para PASTA_PENDENTE; no próximo acesso, o main.py
roda esse instalador em modo silencioso antes de montar a janela (o instalador
reabre o NuPDF ao final). O urllib só é importado ao consultar/baixar - a
checagem de pendência roda em toda abertura e precisa ser instantânea.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .versao import VERSAO

REPO = "hudson-santos/nupdf"
API_ULTIMA = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA_DOWNLOAD = "https://nupdf.com.br"
PASTA_INSTALACAO = Path(r"C:\NuPDF")
NOME_INSTALADOR = "Instalador.exe"
HOSTS_PERMITIDOS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
PASTA_PENDENTE = PASTA_INSTALACAO / "atualizacao"
TIMEOUT = 15


class ErroAtualizacao(Exception):
    pass


@dataclass
class Release:
    versao: str
    notas: str          # markdown (seção do CHANGELOG)
    url_instalador: str
    tamanho: int
    pagina: str


def _tupla(versao: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", versao)[:3]) or (0,)


def eh_mais_nova(remota: str, local: str = VERSAO) -> bool:
    return _tupla(remota) > _tupla(local)


def instalado() -> bool:
    """Só a cópia instalada em C:\\NuPDF se atualiza sozinha (nunca a pasta de desenvolvimento)."""
    try:
        return Path(__file__).resolve().parents[1] == PASTA_INSTALACAO.resolve()
    except OSError:
        return False


def _abrir(url: str):
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": f"NuPDF/{VERSAO}",
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def ultima_release() -> Release:
    import urllib.error
    try:
        with _abrir(API_ULTIMA) as r:
            dados = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ErroAtualizacao("Nenhuma versão publicada ainda.") from e
        if e.code == 403:
            raise ErroAtualizacao("O GitHub limitou as consultas por agora. Tente novamente mais tarde.") from e
        raise ErroAtualizacao(f"O GitHub respondeu com erro {e.code}.") from e
    except OSError as e:
        raise ErroAtualizacao("Não foi possível conectar ao GitHub. Verifique a conexão com a internet.") from e
    exe = next((a for a in dados.get("assets", []) if a.get("name") == NOME_INSTALADOR), None)
    if not exe:
        raise ErroAtualizacao("A versão mais recente ainda não tem o instalador disponível.")
    return Release(
        versao=str(dados.get("tag_name", "")).lstrip("vV"),
        notas=str(dados.get("body") or "").strip(),
        url_instalador=exe["browser_download_url"],
        tamanho=int(exe.get("size") or 0),
        pagina=dados.get("html_url") or PAGINA_DOWNLOAD,
    )


def baixar_instalador(release: Release, progresso=None, cancelado=lambda: False,
                      destino: Path | None = None) -> Path:
    """Baixa o Instalador.exe para C:\\NuPDF (arquivo .part renomeado no fim)."""
    import urllib.parse
    host = urllib.parse.urlparse(release.url_instalador).hostname or ""
    if not any(host == h or host.endswith("." + h) for h in HOSTS_PERMITIDOS):
        raise ErroAtualizacao(f"Endereço de download inesperado: {host}")
    destino = destino or PASTA_INSTALACAO / NOME_INSTALADOR
    destino.parent.mkdir(parents=True, exist_ok=True)
    # .part por processo: em servidor RemoteApp vários usuários podem baixar ao mesmo tempo
    parcial = destino.with_name(f"{destino.name}.{os.getpid()}.part")
    try:
        with _abrir(release.url_instalador) as r, open(parcial, "wb") as f:
            total = int(r.headers.get("Content-Length") or release.tamanho or 0)
            lido = 0
            while True:
                if cancelado():
                    raise ErroAtualizacao("Download cancelado.")
                bloco = r.read(64 * 1024)
                if not bloco:
                    break
                f.write(bloco)
                lido += len(bloco)
                if progresso:
                    progresso(lido, total)
        if release.tamanho and parcial.stat().st_size != release.tamanho:
            raise ErroAtualizacao("O download ficou incompleto. Tente novamente.")
        if parcial.read_bytes()[:2] != b"MZ":
            raise ErroAtualizacao("O arquivo baixado não é um instalador válido.")
        os.replace(parcial, destino)
        return destino
    except ErroAtualizacao:
        parcial.unlink(missing_ok=True)
        raise
    except OSError as e:
        parcial.unlink(missing_ok=True)
        raise ErroAtualizacao(f"Falha no download do instalador:\n{e}") from e


def executar_instalador(caminho: Path):
    """Roda o instalador com /SILENT: só a janela de instalação do NuPDF
    (instalador/Setup.cs), sem perguntas. O instalador encerra o NuPDF aberto
    (etapa 1) e o reabre ao final. Instaladores antigos (só o Inno) entendem o
    mesmo /SILENT: janelinha de progresso do Inno e AbrirNuPDF no fim."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(caminho), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
                     cwd=str(caminho.parent), creationflags=flags, close_fds=True)


# ---------------------------------------------------------------- atualização automática
def _pendentes() -> list[tuple[tuple, Path]]:
    try:
        arquivos = list(PASTA_PENDENTE.glob("Instalador-*.exe"))
    except OSError:
        return []
    return sorted(((_tupla(a.stem.split("-", 1)[1]), a) for a in arquivos), reverse=True)


def baixar_pendente(release: Release) -> Path:
    """Baixa (em segundo plano) o instalador da versão nova para PASTA_PENDENTE,
    a ser instalado no próximo acesso. Já baixado e íntegro: não baixa de novo."""
    destino = PASTA_PENDENTE / f"Instalador-{release.versao}.exe"
    if not (destino.is_file() and (not release.tamanho or destino.stat().st_size == release.tamanho)):
        baixar_instalador(release, destino=destino)
    for _, antigo in _pendentes():
        if antigo != destino:
            antigo.unlink(missing_ok=True)
    return destino


def atualizacao_pendente() -> Path | None:
    """Instalador já baixado de uma versão mais nova que a atual (o mais novo).
    Sobras de versões já instaladas são apagadas."""
    if not instalado():
        return None
    atual = _tupla(VERSAO)
    escolhido = None
    for versao, arq in _pendentes():
        if versao > atual and escolhido is None:
            escolhido = arq
        elif versao <= atual:
            try:
                arq.unlink(missing_ok=True)
            except OSError:
                pass
    return escolhido


def instalar_pendente(caminho: Path) -> bool:
    """Tira o instalador da pasta de pendentes (se a instalação falhar, não tenta
    de novo a cada abertura - a verificação diária baixa outra vez) e o executa
    em modo silencioso. False se não deu (ex.: outro usuário já está instalando)."""
    executar = PASTA_INSTALACAO / NOME_INSTALADOR
    try:
        os.replace(caminho, executar)
        executar_instalador(executar)
        return True
    except OSError:
        return False
