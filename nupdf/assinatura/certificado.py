"""Leitura de certificados ICP-Brasil (A1 em arquivo .pfx/.p12)."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from asn1crypto import core
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

OID_PF_DADOS = "2.16.76.1.3.1"   # data de nascimento + CPF do titular (e-CPF)
OID_PJ_CNPJ = "2.16.76.1.3.3"    # CNPJ (e-CNPJ)


class ErroCertificado(Exception):
    pass


@dataclass
class InfoCertificado:
    titular: str
    documento: str        # CPF/CNPJ formatado (vazio se não identificado)
    tipo: str             # "e-CPF", "e-CNPJ" ou ""
    emissor: str
    valido_de: datetime
    valido_ate: datetime
    serie: str

    @property
    def expirado(self) -> bool:
        agora = datetime.now(timezone.utc)
        return not (self.valido_de <= agora <= self.valido_ate)

    @property
    def documento_mascarado(self) -> str:
        d = self.documento
        if self.tipo == "e-CPF" and len(d) == 14:
            return f"***.{d[4:7]}.{d[8:11]}-**"
        return d

    def resumo(self) -> str:
        doc = f" ({self.tipo} {self.documento})" if self.documento else ""
        return f"{self.titular}{doc}"


def formatar_cpf(d: str) -> str:
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def formatar_cnpj(d: str) -> str:
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def _nome(nome: x509.Name, oid) -> str:
    attrs = nome.get_attributes_for_oid(oid)
    return str(attrs[0].value) if attrs else ""


def _outros_nomes(cert: x509.Certificate) -> dict[str, str]:
    """Lê os OtherName ICP-Brasil do SubjectAltName."""
    saida = {}
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return saida
    for on in san.get_values_for_type(x509.OtherName):
        try:
            valor = core.load(on.value).native
            if isinstance(valor, bytes):
                valor = valor.decode("latin-1", "ignore")
            saida[on.type_id.dotted_string] = str(valor)
        except Exception:
            continue
    return saida


def info_de_certificado(cert: x509.Certificate) -> InfoCertificado:
    cn = _nome(cert.subject, NameOID.COMMON_NAME)
    titular, documento, tipo = cn, "", ""
    # Padrão ICP-Brasil: "NOME DO TITULAR:12345678900" / "RAZAO SOCIAL:12345678000199"
    m = re.match(r"^(.*?):\s*([0-9A-Z]{11}|[0-9A-Z]{14})$", cn)
    if m:
        titular, doc = m.group(1).strip(), m.group(2)
        if len(doc) == 11:
            documento, tipo = formatar_cpf(doc), "e-CPF"
        else:
            documento, tipo = formatar_cnpj(doc), "e-CNPJ"
    else:
        outros = _outros_nomes(cert)
        if OID_PJ_CNPJ in outros and re.fullmatch(r"[0-9A-Z]{14}", outros[OID_PJ_CNPJ].strip()):
            documento, tipo = formatar_cnpj(outros[OID_PJ_CNPJ].strip()), "e-CNPJ"
        elif OID_PF_DADOS in outros and len(outros[OID_PF_DADOS]) >= 19:
            cpf = outros[OID_PF_DADOS][8:19]
            if cpf.isdigit():
                documento, tipo = formatar_cpf(cpf), "e-CPF"
    return InfoCertificado(
        titular=titular or "(sem nome)",
        documento=documento,
        tipo=tipo,
        emissor=_nome(cert.issuer, NameOID.COMMON_NAME) or cert.issuer.rfc4514_string(),
        valido_de=cert.not_valid_before_utc,
        valido_ate=cert.not_valid_after_utc,
        serie=format(cert.serial_number, "X"),
    )


def info_de_der(der: bytes) -> InfoCertificado:
    return info_de_certificado(x509.load_der_x509_certificate(der))


def carregar_pfx(caminho: str, senha: str) -> InfoCertificado:
    try:
        dados = Path(caminho).read_bytes()
    except OSError as e:
        raise ErroCertificado(f"Não foi possível ler o arquivo:\n{e}") from e
    try:
        chave, cert, _ = pkcs12.load_key_and_certificates(dados, senha.encode("utf-8") if senha else None)
    except ValueError as e:
        raise ErroCertificado("Senha incorreta ou arquivo de certificado inválido.") from e
    if chave is None or cert is None:
        raise ErroCertificado("O arquivo não contém chave privada e certificado.")
    return info_de_certificado(cert)
