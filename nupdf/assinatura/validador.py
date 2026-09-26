"""Validação das assinaturas digitais existentes em um PDF.

Confiança da cadeia: usa o repositório de certificados do Windows e, além
dele, os certificados raiz/intermediários (.cer/.crt/.pem/.der) colocados em
%APPDATA%\\NuPDF\\cadeias e na pasta 'cadeias' ao lado do programa - é ali que
se instala a cadeia ICP-Brasil (https://www.gov.br/iti/pt-br/assuntos/repositorio).
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from asn1crypto import pem, x509 as asn1x509
from cryptography import x509

from ..config import pasta_dados
from .certificado import info_de_certificado


@dataclass
class ResultadoAssinatura:
    campo: str
    titular: str
    documento: str
    emissor: str
    data: datetime | None
    integra: bool          # o conteúdo assinado não foi alterado e a criptografia confere
    confiavel: bool        # cadeia até uma raiz confiável
    cobre_documento: bool  # nenhuma alteração não permitida depois da assinatura
    carimbo_tempo: bool
    motivo: str
    local: str
    observacao: str

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


def _carregar_cadeias() -> list:
    certs = []
    for pasta in pastas_cadeias():
        if not pasta.is_dir():
            continue
        for arq in pasta.iterdir():
            if arq.suffix.lower() not in (".cer", ".crt", ".pem", ".der"):
                continue
            try:
                dados = arq.read_bytes()
                if pem.detect(dados):
                    for _, _, der in pem.unarmor(dados, multiple=True):
                        certs.append(asn1x509.Certificate.load(der))
                else:
                    certs.append(asn1x509.Certificate.load(dados))
            except Exception:
                continue
    return certs


def validar(dados: bytes) -> list[ResultadoAssinatura]:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    reader = PdfFileReader(BytesIO(dados), strict=False)
    assinaturas = reader.embedded_signatures
    if not assinaturas:
        return []
    extras = _carregar_cadeias()
    resultados = []
    for sig in assinaturas:
        vc = ValidationContext(extra_trust_roots=extras, other_certs=extras, allow_fetching=False)
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
            st = validate_pdf_signature(sig, vc)
            from pyhanko.sign.diff_analysis import ModificationLevel
            integra = bool(st.intact and st.valid)
            confiavel = bool(st.trusted)
            cobre = st.modification_level in (None, ModificationLevel.NONE, ModificationLevel.LTA_UPDATES,
                                              ModificationLevel.FORM_FILLING) and bool(st.docmdp_ok)
            data = st.timestamp_validity.timestamp if st.timestamp_validity else st.signer_reported_dt
            obs = []
            if not confiavel:
                obs.append("Cadeia de certificação não reconhecida neste computador "
                           "(instale a cadeia ICP-Brasil para validar a confiança).")
            if not cobre:
                obs.append("O documento foi modificado depois desta assinatura.")
            resultados.append(ResultadoAssinatura(
                sig.field_name, titular, documento, emissor, data, integra, confiavel, cobre,
                st.timestamp_validity is not None, motivo, local, " ".join(obs)))
        except Exception as e:
            resultados.append(ResultadoAssinatura(
                sig.field_name, titular, documento, emissor, None, False, False, False, False,
                motivo, local, f"Não foi possível validar: {e}"))
    return resultados
