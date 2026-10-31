"""Verificação e download de atualizações (Cloudflare R2, arquivos.nukt.com.br).

Cada versão é publicada pelo instalador\\publicar.ps1 (compilado localmente) em
https://arquivos.nukt.com.br/atualizacoes/nupdf/: Instalador-X.Y.Z.exe,
Instalador.exe (link fixo da última versão) e versao.json com versão, URL,
SHA-256, tamanho, data e novidades (do CHANGELOG.md). Só a biblioteca padrão é
usada: urllib respeita o proxy configurado no Windows e o ssl usa o repositório
de certificados do sistema (inclusive certificados de inspeção SSL corporativos).

Atualização automática: a verificação diária (janela.py) baixa o instalador da
versão nova em segundo plano para PASTA_PENDENTE; no próximo acesso, o main.py
roda esse instalador em modo silencioso antes de montar a janela (o instalador
reabre o NuPDF ao final). O urllib só é importado ao consultar/baixar - a
checagem de pendência roda em toda abertura e precisa ser instantânea.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .versao import VERSAO

URL_VERSAO = "https://arquivos.nukt.com.br/atualizacoes/nupdf/versao.json"
PAGINA_DOWNLOAD = "https://nupdf.com.br"
PASTA_INSTALACAO = Path(r"C:\NuPDF")
NOME_INSTALADOR = "Instalador.exe"
HOSTS_PERMITIDOS = ("arquivos.nukt.com.br",)
PASTA_PENDENTE = PASTA_INSTALACAO / "atualizacao"
TIMEOUT = 15


class ErroAtualizacao(Exception):
    pass


@dataclass
class Release:
    versao: str
    notas: str          # markdown: itens "- ..." (novidades do versao.json)
    url_instalador: str
    tamanho: int
    pagina: str
    sha256: str = ""    # conferido depois do download
    minima: str = ""    # versão mínima suportada (informativo: o NuPDF já se atualiza sozinho)
    data: str = ""


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
    req = urllib.request.Request(url, headers={"User-Agent": f"NuPDF/{VERSAO}", "Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def ultima_release() -> Release:
    import urllib.error
    try:
        # ?t=...: nunca uma cópia antiga do versao.json guardada por cache/proxy
        with _abrir(f"{URL_VERSAO}?t={int(time.time())}") as r:
            dados = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ErroAtualizacao("Nenhuma versão publicada ainda.") from e
        raise ErroAtualizacao(f"O servidor de atualizações respondeu com erro {e.code}.") from e
    except ValueError as e:
        raise ErroAtualizacao("Resposta inválida do servidor de atualizações.") from e
    except OSError as e:
        raise ErroAtualizacao("Não foi possível conectar ao servidor de atualizações. "
                              "Verifique a conexão com a internet.") from e
    try:
        versao, url = str(dados["versao"]).strip(), str(dados["url"]).strip()
    except (KeyError, TypeError) as e:
        raise ErroAtualizacao("Resposta inválida do servidor de atualizações.") from e
    novidades = dados.get("novidades") or []
    return Release(
        versao=versao,
        notas="\n".join(f"- {n}" for n in novidades if isinstance(n, str) and n.strip()),
        url_instalador=url,
        tamanho=int(dados.get("tamanho") or 0),
        pagina=PAGINA_DOWNLOAD,
        sha256=str(dados.get("sha256") or "").strip().lower(),
        minima=str(dados.get("minima") or ""),
        data=str(dados.get("data") or ""),
    )


def baixar_instalador(release: Release, progresso=None, cancelado=lambda: False,
                      destino: Path | None = None) -> Path:
    """Baixa o Instalador.exe para C:\\NuPDF (arquivo .part renomeado no fim)."""
    import urllib.parse
    host = urllib.parse.urlparse(release.url_instalador).hostname or ""
    if urllib.parse.urlparse(release.url_instalador).scheme != "https" or \
            not any(host == h or host.endswith("." + h) for h in HOSTS_PERMITIDOS):
        raise ErroAtualizacao(f"Endereço de download inesperado: {host}")
    destino = destino or PASTA_INSTALACAO / NOME_INSTALADOR
    destino.parent.mkdir(parents=True, exist_ok=True)
    # .part por processo: em servidor RemoteApp vários usuários podem baixar ao mesmo tempo
    parcial = destino.with_name(f"{destino.name}.{os.getpid()}.part")
    try:
        resumo = hashlib.sha256()
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
                resumo.update(bloco)
                lido += len(bloco)
                if progresso:
                    progresso(lido, total)
        if release.tamanho and parcial.stat().st_size != release.tamanho:
            raise ErroAtualizacao("O download ficou incompleto. Tente novamente.")
        if release.sha256 and resumo.hexdigest() != release.sha256:
            raise ErroAtualizacao("O instalador baixado não confere com o publicado (SHA-256). Tente novamente.")
        with open(parcial, "rb") as f:
            if f.read(2) != b"MZ":
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
