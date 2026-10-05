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
from pathlib import Path

from pyhanko import stamp
from pyhanko.pdf_utils import generic
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


_LOGO_ICP = Path(__file__).resolve().parents[2] / "assets" / "icp_brasil.png"
_LOGO_PROPORCAO = 297 / 360  # largura / altura do PNG
_DOMINIO_VALIDAR = "validar.iti.gov.br"
URL_VALIDAR = "https://validar.iti.gov.br"


def _gerar_carimbo(info: InfoCertificado, largura: float, altura: float,
                   rotacao: int = 0) -> tuple[str, tuple[float, float, float, float] | None]:
    """Desenha a aparência da assinatura visível num PDF de uma página (PyMuPDF)
    e devolve o caminho do arquivo temporário e a área do texto
    "validar.iti.gov.br" (coordenadas do carimbo, origem no canto superior
    esquerdo, já considerando a rotação) para o link. Usar o PyMuPDF garante boa
    renderização de texto (acentos, métricas) em qualquer visualizador."""
    import pymupdf

    agora = datetime.now().astimezone()
    linhas = [
        ("helv", "Assinado Digitalmente por :", 0.42),
        ("hebo", info.titular, 0.10),
    ]
    if info.documento:
        linhas.append(("helv", f"{'CPF' if info.tipo == 'e-CPF' else 'CNPJ'}: {info.documento}", 0.10))
    linhas.append(("helv", f"Data/Hora: {agora:%d/%m/%Y %H:%M:%S} {agora:%z}", 0.10))
    linhas.append(("helv", f"Verifique em {_DOMINIO_VALIDAR}", 0.42))

    rotacao %= 360
    if rotacao in (90, 270):  # desenha na orientação que o usuário vê
        largura, altura = altura, largura
    doc = pymupdf.open()
    pg = doc.new_page(width=largura, height=altura)
    pg.draw_rect(pymupdf.Rect(0.5, 0.5, largura - 0.5, altura - 0.5), color=(0.72, 0.74, 0.78),
                 fill=(1, 1, 1), width=0.8, radius=0.06)
    pg.draw_rect(pymupdf.Rect(0.5, 0.5, 4, altura - 0.5), color=None, fill=(0.898, 0.282, 0.302))

    # logo ICP-Brasil (preta) entre a barra e o texto, na altura útil do carimbo
    margem_y = 5
    # (em caixas estreitas a logo encolhe para não tomar o lugar do texto)
    logo_w = min((altura - 2 * margem_y) * _LOGO_PROPORCAO, largura * 0.25)
    logo_h = logo_w / _LOGO_PROPORCAO
    margem_logo = (altura - logo_h) / 2
    pg.insert_image(pymupdf.Rect(9, margem_logo, 9 + logo_w, margem_logo + logo_h), filename=str(_LOGO_ICP))
    margem_x = 9 + logo_w + 7
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

    achados = doc[0].search_for(_DOMINIO_VALIDAR)
    area_link = tuple(achados[0]) if achados else None
    arq = tempfile.NamedTemporaryFile(prefix="nupdf_carimbo_", suffix=".pdf", delete=False)
    arq.close()
    doc.save(arq.name)
    doc.close()
    return arq.name, area_link


def _adicionar_link(w: IncrementalPdfFileWriter, pagina: int, rect: tuple[float, float, float, float],
                    url: str):
    """Anotação de link (URI) na página, gravada na mesma revisão da assinatura
    (antes de assinar, então fica coberta por ela)."""
    page_ref, _ = w.find_page_for_modification(pagina)
    page = page_ref.get_object()
    link = generic.DictionaryObject({
        generic.NameObject("/Type"): generic.NameObject("/Annot"),
        generic.NameObject("/Subtype"): generic.NameObject("/Link"),
        generic.NameObject("/Rect"): generic.ArrayObject(generic.FloatObject(v) for v in rect),
        generic.NameObject("/Border"): generic.ArrayObject([generic.NumberObject(0)] * 3),
        generic.NameObject("/F"): generic.NumberObject(4),  # imprimível
        generic.NameObject("/P"): page_ref,
        generic.NameObject("/A"): generic.DictionaryObject({
            generic.NameObject("/S"): generic.NameObject("/URI"),
            generic.NameObject("/URI"): generic.TextStringObject(url),
        }),
    })
    ref = w.add_object(link)
    existentes = page.get("/Annots")
    anots = generic.ArrayObject(list(existentes) if existentes is not None else [])
    anots.append(ref)
    page[generic.NameObject("/Annots")] = anots
    w.update_container(page)


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


def _reparar(dados: bytes, senha_pdf: str | None) -> bytes:
    """Reescreve a estrutura do PDF (tabela xref e objetos) com o MuPDF, que tolera e
    corrige arquivos malformados. O conteúdo das páginas não muda."""
    import pymupdf
    doc = pymupdf.open(stream=dados, filetype="pdf")
    try:
        if doc.needs_pass:
            doc.authenticate(senha_pdf or "")
        return doc.tobytes(garbage=3, deflate=True)
    finally:
        doc.close()


def _ja_assinado(dados: bytes) -> bool:
    import pymupdf
    try:
        doc = pymupdf.open(stream=dados, filetype="pdf")
        try:
            return doc.get_sigflags() > 0
        finally:
            doc.close()
    except Exception:
        return False


def assinar_pdf(dados: bytes, cfg: ConfigAssinatura, senha_pdf: str | None = None,
                assinante=None) -> bytes:
    """Assina os bytes de um PDF e devolve os bytes do PDF assinado (atualização incremental).
    `assinante` permite injetar outro Signer do pyHanko (usado nos testes).

    PDF com erro de estrutura (xref/objetos malformados - comum em PDFs gerados por
    sistemas de prefeituras etc.): os leitores abrem, mas o pyHanko recusa. Nesse caso,
    se o documento ainda não tem assinaturas, a estrutura é reconstruída e a assinatura
    é refeita sobre ela (só nesse erro de leitura - um PIN cancelado não repete).

    PDF com metadados XMP malformados (ex.: editados por outro programa): ao assinar, o
    pyHanko atualiza o XMP e falha ao ler o XML. Nesse caso o XMP quebrado é trocado por
    um novo, válido, na própria atualização incremental - funciona também em PDF já
    assinado, sem invalidar as assinaturas existentes."""
    from pyhanko.pdf_utils.misc import PdfReadError
    signer = assinante or _assinante(cfg)
    try:
        return _assinar(dados, cfg, senha_pdf, signer)
    except _XmpInvalido:
        return _assinar(dados, cfg, senha_pdf, signer, novo_xmp=True)
    except PdfReadError as e:
        if _ja_assinado(dados):
            raise ErroAssinatura(
                "O PDF tem erros de estrutura e já possui assinaturas digitais: não é possível "
                f"corrigi-lo sem invalidar as assinaturas existentes.\n\n{e}") from e
        try:
            reparado = _reparar(dados, senha_pdf)
        except Exception:
            raise ErroAssinatura(f"Falha ao assinar o documento (PDF com erro de estrutura):\n{e}") from e
        try:
            return _assinar(reparado, cfg, senha_pdf, signer)
        except PdfReadError as e2:
            raise ErroAssinatura(f"Falha ao assinar o documento (PDF com erro de estrutura):\n{e2}") from e2


class _XmpInvalido(Exception):
    """Metadados XMP do PDF malformados (assinar_pdf tenta de novo com um XMP novo)."""


def _trocar_xmp(w):
    """Substitui o XMP do catálogo por um novo, vazio e válido (o pyHanko o preenche
    ao assinar). Só a referência no catálogo muda, numa revisão nova do arquivo."""
    from pyhanko.pdf_utils.metadata import model, xmp_xml
    stm = xmp_xml.MetadataStream.from_xmp(xmp_xml.update_xmp_with_meta(model.DocumentMetadata()))
    w.root["/Metadata"] = w.add_object(stm)
    w.update_root()


def _assinar(dados: bytes, cfg: ConfigAssinatura, senha_pdf: str | None, signer,
             novo_xmp: bool = False) -> bytes:
    from pyhanko.pdf_utils.metadata.xmp_xml import XmpXmlProcessingError
    from pyhanko.pdf_utils.misc import PdfReadError
    carimbo = None
    try:
        entrada = BytesIO(dados)
        w = IncrementalPdfFileWriter(entrada, strict=False)
        if senha_pdf and w.prev.encrypted:
            w.encrypt(senha_pdf.encode("utf-8"))
        if novo_xmp:
            _trocar_xmp(w)
        nome = _nome_campo(w.prev)

        if cfg.visivel and cfg.caixa:
            x0, y0, x1, y1 = (int(round(v)) for v in cfg.caixa)
            spec = fields.SigFieldSpec(sig_field_name=nome, on_page=cfg.pagina, box=(x0, y0, x1, y1))
            carimbo, area = _gerar_carimbo(cfg.info, x1 - x0, y1 - y0, cfg.rotacao)
            # link só na 1ª assinatura: anotação nova numa revisão posterior faz os
            # validadores (Adobe, pyHanko) acusarem as assinaturas anteriores como modificadas
            ja_assinado = any(True for _ in fields.enumerate_sig_fields(w.prev, filled_status=True))
            if area and not ja_assinado:  # carimbo (origem em cima) -> página (origem embaixo)
                _adicionar_link(w, cfg.pagina, (x0 + area[0], y1 - area[3], x0 + area[2], y1 - area[1]),
                                URL_VALIDAR)
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
    except (ErroAssinatura, PdfReadError):
        raise  # PdfReadError: assinar_pdf tenta de novo com a estrutura reconstruída
    except XmpXmlProcessingError as e:
        if novo_xmp:
            raise ErroAssinatura(f"Falha ao assinar o documento (metadados XMP inválidos):\n{e}") from e
        raise _XmpInvalido() from e
    except Exception as e:
        raise ErroAssinatura(f"Falha ao assinar o documento:\n{e}") from e
    finally:
        if carimbo:
            try:
                os.remove(carimbo)
            except OSError:
                pass
