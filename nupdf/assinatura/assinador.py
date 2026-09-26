"""Assinatura digital PAdES (ETSI.CAdES.detached, SHA-256) com pyHanko.

Gera assinaturas PAdES-B-B (ou B-T quando há carimbo de tempo) com um
certificado ICP-Brasil instalado no Windows (a chave privada não sai do
sistema - ver windows.py), no formato aceito pelo Verificador de
Conformidade do ITI (validar.iti.gov.br).
"""

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

from pyhanko import stamp
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers, timestamps

from .certificado import InfoCertificado


class ErroAssinatura(Exception):
    pass


@dataclass
class ConfigAssinatura:
    info: InfoCertificado
    # certificado do repositório do Windows
    impressao: str = ""             # SHA-1 (hex) do certificado
    der: bytes = b""
    # aparência / metadados
    motivo: str = ""
    local: str = ""
    tsa_url: str = ""
    visivel: bool = True
    pagina: int = 0
    caixa: tuple | None = None      # (x0, y0, x1, y1) em coordenadas PDF (origem embaixo)
    rotacao: int = 0                # /Rotate da página (o carimbo é contra-rotacionado)
    extras: dict = field(default_factory=dict)


def _gerar_carimbo(info: InfoCertificado, largura: float, altura: float, rotacao: int = 0) -> str:
    """Desenha a aparência da assinatura visível num PDF de uma página (PyMuPDF)
    e devolve o caminho do arquivo temporário. Usar o PyMuPDF garante boa
    renderização de texto (acentos, métricas) em qualquer visualizador."""
    import pymupdf

    agora = datetime.now().astimezone()
    linhas = [
        ("helv", "Assinado digitalmente por", 0.42),
        ("hebo", info.titular, 0.10),
    ]
    if info.documento:
        linhas.append(("helv", f"{'CPF' if info.tipo == 'e-CPF' else 'CNPJ'}: {info.documento_mascarado}", 0.10))
    linhas.append(("helv", f"Data: {agora:%d/%m/%Y %H:%M:%S} {agora:%z}", 0.10))
    linhas.append(("helv", "Verifique em validar.iti.gov.br", 0.42))

    rotacao %= 360
    if rotacao in (90, 270):  # desenha na orientação que o usuário vê
        largura, altura = altura, largura
    doc = pymupdf.open()
    pg = doc.new_page(width=largura, height=altura)
    pg.draw_rect(pymupdf.Rect(0.5, 0.5, largura - 0.5, altura - 0.5), color=(0.72, 0.74, 0.78),
                 fill=(1, 1, 1), width=0.8, radius=0.06)
    pg.draw_rect(pymupdf.Rect(0.5, 0.5, 4, altura - 0.5), color=None, fill=(0.898, 0.282, 0.302))

    margem_x, margem_y = 10, 5
    util_w = largura - margem_x - 6
    fs = min(10.5, (altura - 2 * margem_y) / (len(linhas) * 1.22))
    for fonte, texto, _ in linhas:  # reduz a fonte até a linha mais larga caber
        while fs > 4 and pymupdf.get_text_length(texto, fontname=fonte, fontsize=fs) > util_w:
            fs -= 0.25
    altura_texto = len(linhas) * fs * 1.22
    y = (altura - altura_texto) / 2 + fs
    for fonte, texto, cinza in linhas:
        pg.insert_text((margem_x, y), texto, fontname=fonte, fontsize=fs, color=(cinza, cinza, cinza + 0.02))
        y += fs * 1.22

    if rotacao:
        # a página é exibida girada; gira o carimbo no sentido oposto para ele aparecer "em pé"
        final = pymupdf.open()
        fw, fh = (altura, largura) if rotacao in (90, 270) else (largura, altura)
        final.new_page(width=fw, height=fh).show_pdf_page(pymupdf.Rect(0, 0, fw, fh), doc, 0, rotate=rotacao)
        doc.close()
        doc = final

    arq = tempfile.NamedTemporaryFile(prefix="nupdf_carimbo_", suffix=".pdf", delete=False)
    arq.close()
    doc.save(arq.name)
    doc.close()
    return arq.name


def _nome_campo(reader: PdfFileReader) -> str:
    existentes = {nome for nome, _, _ in fields.enumerate_sig_fields(reader)}
    n = 1
    while f"Assinatura{n}" in existentes:
        n += 1
    return f"Assinatura{n}"


def _assinante(cfg: ConfigAssinatura):
    from .windows import assinante_pyhanko
    if not cfg.impressao or not cfg.der:
        raise ErroAssinatura("Nenhum certificado digital selecionado.")
    return assinante_pyhanko(cfg.impressao, cfg.der)


def assinar_pdf(dados: bytes, cfg: ConfigAssinatura, senha_pdf: str | None = None,
                assinante=None) -> bytes:
    """Assina os bytes de um PDF e devolve os bytes do PDF assinado (atualização incremental).
    `assinante` permite injetar outro Signer do pyHanko (usado nos testes)."""
    signer = assinante or _assinante(cfg)
    carimbo = None
    try:
        entrada = BytesIO(dados)
        w = IncrementalPdfFileWriter(entrada, strict=False)
        if senha_pdf and w.prev.encrypted:
            w.encrypt(senha_pdf.encode("utf-8"))
        nome = _nome_campo(w.prev)

        if cfg.visivel and cfg.caixa:
            x0, y0, x1, y1 = (int(round(v)) for v in cfg.caixa)
            spec = fields.SigFieldSpec(sig_field_name=nome, on_page=cfg.pagina, box=(x0, y0, x1, y1))
            carimbo = _gerar_carimbo(cfg.info, x1 - x0, y1 - y0, cfg.rotacao)
            estilo = stamp.StaticStampStyle.from_pdf_file(carimbo, border_width=0)
        else:
            spec = fields.SigFieldSpec(sig_field_name=nome)
            estilo = None

        meta = signers.PdfSignatureMetadata(
            field_name=nome,
            md_algorithm="sha256",
            reason=cfg.motivo or None,
            location=cfg.local or None,
            name=cfg.info.titular,
            subfilter=fields.SigSeedSubFilter.PADES,
            signer_key_usage={"digital_signature"},
        )
        tsa = timestamps.HTTPTimeStamper(cfg.tsa_url, timeout=15) if cfg.tsa_url else None
        pdf_signer = signers.PdfSigner(meta, signer=signer, timestamper=tsa,
                                       stamp_style=estilo, new_field_spec=spec)
        saida = BytesIO()
        pdf_signer.sign_pdf(w, output=saida)
        return saida.getvalue()
    except ErroAssinatura:
        raise
    except Exception as e:
        raise ErroAssinatura(f"Falha ao assinar o documento:\n{e}") from e
    finally:
        if carimbo:
            try:
                os.remove(carimbo)
            except OSError:
                pass
