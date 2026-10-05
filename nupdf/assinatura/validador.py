"""Validação das assinaturas digitais existentes em um PDF.

Confiança da cadeia, além do repositório de certificados do Windows:
- cadeia ICP-Brasil oficial (pasta 'icp-brasil', baixada do ITI pelo instalador ou
  pelo botão "Atualizar Cadeia ICP-Brasil" - ver cadeia_icp.py): as raízes viram
  âncoras de confiança e as ACs intermediárias só ajudam a montar o caminho;
- certificados em que o usuário mandou confiar ("Confiar neste Certificado"), na pasta
  'confiaveis' de %APPDATA%\\NuPDF\\cadeias;
- certificados colocados à mão em %APPDATA%\\NuPDF\\cadeias ou na pasta 'cadeias'
  ao lado do programa (todos tratados como confiáveis, como antes).
Se mesmo assim faltar alguma AC intermediária, uma segunda tentativa busca o
certificado no endereço indicado nele próprio (AIA), pela internet.
"""

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from asn1crypto import pem, x509 as asn1x509
from cryptography import x509

from ..config import pasta_dados
from .cadeia_icp import NOME_PASTA as PASTA_ICP
from .certificado import info_de_certificado

PASTA_CONFIAVEIS = "confiaveis"
TEMPO_BUSCA = 8  # segundos por requisição ao buscar ACs intermediárias pela internet


@dataclass
class ResultadoAssinatura:
    campo: str
    titular: str
    documento: str
    emissor: str
    data: datetime | None
    integra: bool          # o conteúdo assinado não foi alterado e a criptografia confere
    confiavel: bool        # cadeia até uma raiz confiável
    cobre_documento: bool  # nenhuma alteração NÃO permitida depois da assinatura
    carimbo_tempo: bool
    motivo: str
    local: str
    observacao: str
    # topo da cadeia que acompanha a assinatura: o que "Confiar neste Certificado" grava
    topo_cadeia_der: bytes | None = None
    topo_cadeia_nome: str = ""

    @property
    def nivel(self) -> str:
        if not self.integra:
            return "erro"
        if not self.confiavel or not self.cobre_documento:
            return "aviso"
        return "ok"


def pastas_cadeias() -> list[Path]:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    pastas = [pasta_dados() / "cadeias", base / "cadeias"]
    pastas[0].mkdir(parents=True, exist_ok=True)
    return pastas


def _ler(arq: Path) -> list:
    try:
        dados = arq.read_bytes()
        if pem.detect(dados):
            return [asn1x509.Certificate.load(der) for _, _, der in pem.unarmor(dados, multiple=True)]
        return [asn1x509.Certificate.load(dados)]
    except Exception:
        return []


def _carregar_cadeias() -> tuple[list, list]:
    """(âncoras de confiança, intermediárias), sem repetidos."""
    raizes, intermediarias, vistos = [], [], set()
    for pasta in pastas_cadeias():
        if not pasta.is_dir():
            continue
        for arq in pasta.rglob("*"):
            if arq.suffix.lower() not in (".cer", ".crt", ".pem", ".der") or not arq.is_file():
                continue
            icp = PASTA_ICP in arq.relative_to(pasta).parts
            for cert in _ler(arq):
                chave = cert.sha256
                if chave in vistos:
                    continue
                vistos.add(chave)
                # do pacote ICP-Brasil só as raízes (autoassinadas) são âncoras; o
                # resto (confiáveis do usuário e colocados à mão) é confiável
                if icp and cert.self_signed == "no":
                    intermediarias.append(cert)
                else:
                    raizes.append(cert)
    return raizes, intermediarias


def confiar(der: bytes) -> Path:
    """Passa a confiar no certificado (topo de uma cadeia) - "Confiar neste Certificado"."""
    pasta = pasta_dados() / "cadeias" / PASTA_CONFIAVEIS
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"{hashlib.sha1(der).hexdigest()}.cer"
    arq.write_bytes(der)
    return arq


def _topo_da_cadeia(sig, conhecidos: list):
    """Sobe de emissor em emissor a partir do certificado do assinante, usando os
    certificados que vêm na assinatura e os conhecidos; devolve o último achado."""
    try:
        embutidos = [c.chosen for c in sig.signed_data["certificates"]
                     if isinstance(c.chosen, asn1x509.Certificate)]
    except Exception:
        embutidos = []
    por_nome = {}
    for c in embutidos + conhecidos:
        por_nome.setdefault(c.subject.dump(), c)
    atual, passos = sig.signer_cert, 0
    while atual.self_signed == "no" and passos < 10:
        emissor = por_nome.get(atual.issuer.dump())
        if emissor is None or emissor.dump() == atual.dump():
            break
        atual, passos = emissor, passos + 1
    return atual


def _status(sig, raizes, intermediarias, buscar: bool):
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    extras = {}
    if buscar:
        from pyhanko_certvalidator.fetchers.aiohttp_fetchers import AIOHttpFetcherBackend
        extras = dict(allow_fetching=True, revocation_mode="soft-fail",
                      fetcher_backend=AIOHttpFetcherBackend(per_request_timeout=TEMPO_BUSCA))
    vc = ValidationContext(extra_trust_roots=raizes, other_certs=intermediarias, **extras)
    return validate_pdf_signature(sig, vc)


def _tem_campo_de_assinatura(dados: bytes) -> bool:
    """Checagem prévia com o MuPDF, que tolera PDFs com estrutura malformada: há algum
    campo de assinatura? Na dúvida (não abriu), responde que sim e deixa o pyHanko decidir."""
    import pymupdf
    try:
        doc = pymupdf.open(stream=dados, filetype="pdf")
    except Exception:
        return True
    try:
        if doc.get_sigflags() > 0:
            return True
        for pg in doc:
            if any(True for _ in pg.widgets(types=[pymupdf.PDF_WIDGET_TYPE_SIGNATURE])):
                return True
        return False
    except Exception:
        return True
    finally:
        doc.close()


def validar(dados: bytes, buscar_na_internet: bool = True) -> list[ResultadoAssinatura]:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.diff_analysis import ModificationLevel

    # sem campo de assinatura não há o que validar - e o pyHanko nem é chamado, o que
    # evita erro de leitura ("Parse error...") em PDF malformado que não é assinado
    if not _tem_campo_de_assinatura(dados):
        return []
    reader = PdfFileReader(BytesIO(dados), strict=False)
    assinaturas = reader.embedded_signatures
    if not assinaturas:
        return []
    raizes, intermediarias = _carregar_cadeias()
    resultados = []
    for sig in assinaturas:
        cert = sig.signer_cert
        try:
            info = info_de_certificado(x509.load_der_x509_certificate(cert.dump()))
            titular, documento, emissor = info.titular, info.documento, info.emissor
        except Exception:
            titular, documento, emissor = cert.subject.human_friendly, "", cert.issuer.human_friendly
        sd = sig.sig_object
        motivo = str(sd.get("/Reason", "") or "")
        local = str(sd.get("/Location", "") or "")
        try:
            st = _status(sig, raizes, intermediarias, buscar=False)
            if not st.trusted and buscar_na_internet:
                # falta alguma AC intermediária? busca pelo endereço do próprio certificado
                try:
                    st2 = _status(sig, raizes, intermediarias, buscar=True)
                    if st2.trusted:
                        st = st2
                except Exception:
                    pass
            integra = bool(st.intact and st.valid)
            confiavel = bool(st.trusted)
            # como no Adobe: alterações permitidas depois da assinatura (outras
            # assinaturas, carimbos, preenchimento) não a invalidam
            nivel_mod = st.modification_level
            cobre = bool(st.docmdp_ok) or nivel_mod is None
            data = st.timestamp_validity.timestamp if st.timestamp_validity else st.signer_reported_dt
            obs = []
            if not confiavel:
                obs.append("Cadeia de Certificação Não Reconhecida.")
            if not cobre:
                obs.append("Documento Modificado Após Assinatura.")
            elif nivel_mod not in (None, ModificationLevel.NONE):
                obs.append("Alterações Permitidas Após Assinatura.")
            topo = _topo_da_cadeia(sig, intermediarias + raizes) if not confiavel else None
            resultados.append(ResultadoAssinatura(
                sig.field_name, titular, documento, emissor, data, integra, confiavel, cobre,
                st.timestamp_validity is not None, motivo, local, " ".join(obs),
                topo.dump() if topo is not None else None,
                topo.subject.human_friendly if topo is not None else ""))
        except Exception as e:
            resultados.append(ResultadoAssinatura(
                sig.field_name, titular, documento, emissor, None, False, False, False, False,
                motivo, local, f"Não foi possível validar: {e}"))
    return resultados
