"""Certificados A3 (token USB / cartão) via PKCS#11."""

import os
from dataclasses import dataclass
from pathlib import Path

from .certificado import ErroCertificado, InfoCertificado, info_de_der

_SYS32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
_PF = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
_PF86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))

# Middlewares mais comuns nos tokens/cartões ICP-Brasil
BIBLIOTECAS_CONHECIDAS = [
    ("SafeNet / Thales eToken", _SYS32 / "eTPKCS11.dll"),
    ("SafeSign (GD / Valid)", _SYS32 / "aetpkss1.dll"),
    ("Watchdata (Certisign)", _SYS32 / "WDPKCS.dll"),
    ("Thales IDPrime", _SYS32 / "IDPrimePKCS11.dll"),
    ("Thales IDPrime (x64)", _PF / "Gemalto" / "IDGo 800 PKCS#11" / "IDPrimePKCS1164.dll"),
    ("ePass2003", _SYS32 / "eps2003csp11.dll"),
    ("Oberthur / IDEMIA", _SYS32 / "OcsCryptoki.dll"),
    ("GD StarSign", _PF / "Giesecke+Devrient" / "StarSign" / "StarSign CUT" / "aetpkss1.dll"),
    ("Kryptus / Soluti", _SYS32 / "libkryptus.dll"),
    ("OpenSC", _PF / "OpenSC Project" / "OpenSC" / "pkcs11" / "opensc-pkcs11.dll"),
    ("OpenSC (x86)", _PF86 / "OpenSC Project" / "OpenSC" / "pkcs11" / "opensc-pkcs11.dll"),
]


def bibliotecas_encontradas() -> list[tuple[str, str]]:
    return [(nome, str(c)) for nome, c in BIBLIOTECAS_CONHECIDAS if c.is_file()]


@dataclass
class CertificadoToken:
    token: str       # rótulo do token
    rotulo: str      # rótulo do certificado
    id: bytes        # CKA_ID (o mesmo da chave privada)
    der: bytes
    info: InfoCertificado


def listar_certificados(biblioteca: str, pin: str) -> list[CertificadoToken]:
    try:
        import pkcs11
        from pkcs11 import Attribute, ObjectClass
    except ImportError as e:
        raise ErroCertificado("Suporte a PKCS#11 não instalado (python-pkcs11).") from e
    try:
        lib = pkcs11.lib(biblioteca)
    except Exception as e:
        raise ErroCertificado(f"Não foi possível carregar a biblioteca do token:\n{e}") from e

    saida: list[CertificadoToken] = []
    slots = lib.get_slots(token_present=True)
    if not slots:
        raise ErroCertificado("Nenhum token/cartão encontrado. Verifique se está conectado.")
    for slot in slots:
        token = slot.get_token()
        try:
            sessao = token.open(user_pin=pin) if pin else token.open()
        except pkcs11.exceptions.PinIncorrect as e:
            raise ErroCertificado("PIN incorreto.") from e
        except pkcs11.exceptions.PinLocked as e:
            raise ErroCertificado("PIN bloqueado. Use o software do token para desbloquear.") from e
        except Exception as e:
            raise ErroCertificado(f"Erro ao abrir o token '{token.label}':\n{e}") from e
        with sessao:
            chaves = {bytes(k[Attribute.ID]) for k in sessao.get_objects({Attribute.CLASS: ObjectClass.PRIVATE_KEY})}
            for obj in sessao.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                try:
                    der = bytes(obj[Attribute.VALUE])
                    cid = bytes(obj[Attribute.ID])
                    rotulo = str(obj[Attribute.LABEL])
                except Exception:
                    continue
                # Só certificados que têm chave privada correspondente (descarta cadeia AC)
                if chaves and cid not in chaves:
                    continue
                saida.append(CertificadoToken(token.label.strip(), rotulo, cid, der, info_de_der(der)))
    return saida
