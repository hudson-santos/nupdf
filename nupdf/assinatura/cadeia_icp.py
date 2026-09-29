"""Cadeia de certificados da ICP-Brasil (raízes e ACs intermediárias).

O ITI publica todas as ACs da ICP-Brasil num pacote único (ACcompactado.zip).
O instalador baixa esse pacote para C:\\NuPDF\\cadeias\\icp-brasil e o botão
"Atualizar Cadeia ICP-Brasil" do painel de assinaturas baixa de novo para a
pasta do usuário (%APPDATA%\\NuPDF\\cadeias\\icp-brasil) - útil quando o ITI
credencia ACs novas. O validador (validador.py) usa as raízes deste pacote como
âncoras de confiança e as demais como intermediárias.

Uso pelo instalador:  python -m nupdf.assinatura.cadeia_icp <pasta destino>
"""

import io
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

URL_CADEIA_ICP = "https://acraiz.icpbrasil.gov.br/credenciadas/CertificadosAC-ICP-Brasil/ACcompactado.zip"
NOME_PASTA = "icp-brasil"
EXTENSOES = (".crt", ".cer", ".pem", ".der")
TAMANHO_MAXIMO = 20 * 1024 * 1024  # o pacote tem ~350 KB; limite contra respostas inesperadas


class ErroCadeia(Exception):
    pass


def pasta_programa() -> Path:
    """C:\\NuPDF\\cadeias\\icp-brasil (gravada pelo instalador)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "cadeias" / NOME_PASTA


def pasta_usuario() -> Path:
    """%APPDATA%\\NuPDF\\cadeias\\icp-brasil (gravada pelo botão de atualizar)."""
    from ..config import pasta_dados
    return pasta_dados() / "cadeias" / NOME_PASTA


def _baixar(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "NuPDF"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dados = resp.read(TAMANHO_MAXIMO + 1)
    if len(dados) > TAMANHO_MAXIMO:
        raise ErroCadeia("O pacote da cadeia ICP-Brasil é maior que o esperado.")
    return dados


def _certificados(pacote: bytes) -> dict[str, bytes]:
    """Arquivos do .zip que são certificados X.509 válidos (nome -> conteúdo)."""
    from asn1crypto import pem, x509
    saida = {}
    try:
        z = zipfile.ZipFile(io.BytesIO(pacote))
    except zipfile.BadZipFile as e:
        raise ErroCadeia("O pacote baixado não é um arquivo .zip válido.") from e
    for info in z.infolist():
        nome = Path(info.filename).name
        if info.is_dir() or not nome.lower().endswith(EXTENSOES):
            continue
        dados = z.read(info)
        try:
            der = pem.unarmor(dados)[2] if pem.detect(dados) else dados
            x509.Certificate.load(der).native  # confere que é um certificado legível
        except Exception:
            continue
        saida[nome] = dados
    if not saida:
        raise ErroCadeia("O pacote baixado não contém certificados.")
    return saida


def atualizar(destino: Path | None = None, timeout: float = 30) -> int:
    """Baixa o pacote do ITI e substitui a pasta `destino` (padrão: a do usuário).
    Devolve quantos certificados foram gravados. Em caso de erro a pasta anterior
    fica intacta."""
    destino = Path(destino) if destino else pasta_usuario()
    try:
        certs = _certificados(_baixar(URL_CADEIA_ICP, timeout))
    except ErroCadeia:
        raise
    except Exception as e:
        raise ErroCadeia(f"Não foi possível baixar a cadeia ICP-Brasil: {e}") from e
    destino.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="icp-brasil-", dir=destino.parent))
    try:
        for nome, dados in certs.items():
            (temp / nome).write_bytes(dados)
        antiga = destino.with_name(destino.name + ".antiga")
        shutil.rmtree(antiga, ignore_errors=True)
        if destino.exists():
            destino.rename(antiga)
        temp.rename(destino)
        shutil.rmtree(antiga, ignore_errors=True)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return len(certs)


if __name__ == "__main__":  # instalador: python -m nupdf.assinatura.cadeia_icp <destino>
    try:
        n = atualizar(Path(sys.argv[1]) if len(sys.argv) > 1 else pasta_programa())
        print(f"Cadeia ICP-Brasil instalada: {n} certificados.")
    except ErroCadeia as e:
        print(f"[AVISO] {e}")
        sys.exit(1)
