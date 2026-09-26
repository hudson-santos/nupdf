"""Certificados digitais instalados no Windows (repositório Pessoal do usuário).

A chave privada nunca sai do Windows: o NuPDF calcula o hash do conteúdo e
pede ao sistema para assiná-lo (CNG/NCrypt, com fallback para a CryptoAPI
legada). Se o certificado tiver proteção forte ou estiver em token/cartão,
o próprio Windows mostra o pedido de senha/PIN.
"""

import ctypes
import hashlib
import sys
from ctypes import wintypes as wt
from dataclasses import dataclass

from asn1crypto import x509 as asn1x509
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

from .certificado import ErroCertificado, InfoCertificado, info_de_certificado


@dataclass
class CertificadoWindows:
    impressao: str        # SHA-1 do certificado (hex), identifica o certificado no repositório
    der: bytes
    info: InfoCertificado

    def rotulo(self) -> str:
        doc = f" - {self.info.tipo} {self.info.documento}" if self.info.documento else ""
        return f"{self.info.titular}{doc} - Válido Até {self.info.valido_ate:%d/%m/%Y}"


# ---------------------------------------------------------------- API do Windows
if sys.platform == "win32":
    _crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True)
    _ncrypt = ctypes.WinDLL("ncrypt.dll")
    _advapi32 = ctypes.WinDLL("advapi32.dll", use_last_error=True)

    class _CERT_CONTEXT(ctypes.Structure):
        _fields_ = [("dwCertEncodingType", wt.DWORD),
                    ("pbCertEncoded", ctypes.POINTER(ctypes.c_ubyte)),
                    ("cbCertEncoded", wt.DWORD),
                    ("pCertInfo", ctypes.c_void_p),
                    ("hCertStore", ctypes.c_void_p)]

    _PCCERT = ctypes.POINTER(_CERT_CONTEXT)

    class _BCRYPT_PKCS1_PADDING_INFO(ctypes.Structure):
        _fields_ = [("pszAlgId", wt.LPCWSTR)]

    _crypt32.CertOpenSystemStoreW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
    _crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p
    _crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, wt.DWORD]
    _crypt32.CertEnumCertificatesInStore.argtypes = [ctypes.c_void_p, _PCCERT]
    _crypt32.CertEnumCertificatesInStore.restype = _PCCERT
    _crypt32.CertDuplicateCertificateContext.argtypes = [_PCCERT]
    _crypt32.CertDuplicateCertificateContext.restype = _PCCERT
    _crypt32.CertFreeCertificateContext.argtypes = [_PCCERT]
    _crypt32.CertGetCertificateContextProperty.argtypes = [_PCCERT, wt.DWORD, ctypes.c_void_p,
                                                           ctypes.POINTER(wt.DWORD)]
    _crypt32.CertGetCertificateContextProperty.restype = wt.BOOL
    _crypt32.CryptAcquireCertificatePrivateKey.argtypes = [
        _PCCERT, wt.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(wt.DWORD), ctypes.POINTER(wt.BOOL)]
    _crypt32.CryptAcquireCertificatePrivateKey.restype = wt.BOOL

    _ncrypt.NCryptSignHash.argtypes = [ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD,
                                       ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
    _ncrypt.NCryptSignHash.restype = ctypes.c_long
    _ncrypt.NCryptFreeObject.argtypes = [ctypes.c_size_t]

    _advapi32.CryptCreateHash.argtypes = [ctypes.c_size_t, wt.DWORD, ctypes.c_size_t, wt.DWORD,
                                          ctypes.POINTER(ctypes.c_size_t)]
    _advapi32.CryptCreateHash.restype = wt.BOOL
    _advapi32.CryptSetHashParam.argtypes = [ctypes.c_size_t, wt.DWORD, ctypes.c_void_p, wt.DWORD]
    _advapi32.CryptSetHashParam.restype = wt.BOOL
    _advapi32.CryptSignHashW.argtypes = [ctypes.c_size_t, wt.DWORD, wt.LPCWSTR, wt.DWORD,
                                         ctypes.c_void_p, ctypes.POINTER(wt.DWORD)]
    _advapi32.CryptSignHashW.restype = wt.BOOL
    _advapi32.CryptDestroyHash.argtypes = [ctypes.c_size_t]
    _advapi32.CryptReleaseContext.argtypes = [ctypes.c_size_t, wt.DWORD]

_CERT_KEY_PROV_INFO_PROP_ID = 2
_CERT_NCRYPT_KEY_SPEC = 0xFFFFFFFF
_ACQUIRE_COMPARE_KEY = 0x4
_ACQUIRE_PREFER_NCRYPT = 0x00020000
_ACQUIRE_ONLY_NCRYPT = 0x00040000
_BCRYPT_PAD_PKCS1 = 0x2
_HP_HASHVAL = 0x2
_CALG = {"sha256": 0x800C, "sha384": 0x800D, "sha512": 0x800E, "sha1": 0x8004}
_NCRYPT_ALG = {"sha256": "SHA256", "sha384": "SHA384", "sha512": "SHA512", "sha1": "SHA1"}
_CANCELADO = {0x8010006E, 0x800704C7, 0x80090036}  # PIN/senha cancelado pelo usuário


def _certificados_do_repositorio(nome: str):
    """Gera (contexto, der) de um repositório do usuário ("MY", "CA", "ROOT").
    O contexto só vale durante a iteração."""
    loja = _crypt32.CertOpenSystemStoreW(None, nome)
    if not loja:
        return
    try:
        ctx = _crypt32.CertEnumCertificatesInStore(loja, None)
        while ctx:
            c = ctx.contents
            yield ctx, ctypes.string_at(c.pbCertEncoded, c.cbCertEncoded)
            ctx = _crypt32.CertEnumCertificatesInStore(loja, ctx)
    finally:
        _crypt32.CertCloseStore(loja, 0)


def _tem_chave_privada(ctx) -> bool:
    tamanho = wt.DWORD(0)
    return bool(_crypt32.CertGetCertificateContextProperty(
        ctx, _CERT_KEY_PROV_INFO_PROP_ID, None, ctypes.byref(tamanho)))


def _serve_para_assinar(cert: x509.Certificate) -> bool:
    try:
        uso = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        return bool(uso.digital_signature or uso.content_commitment)
    except x509.ExtensionNotFound:
        return True


def listar_certificados() -> list[CertificadoWindows]:
    """Certificados do repositório Pessoal com chave privada e uso de assinatura
    (RSA - o padrão ICP-Brasil). Válidos primeiro, depois por titular."""
    if sys.platform != "win32":
        return []
    saida = []
    for ctx, der in _certificados_do_repositorio("MY"):
        if not _tem_chave_privada(ctx):
            continue
        try:
            cert = x509.load_der_x509_certificate(der)
        except ValueError:
            continue
        if not isinstance(cert.public_key(), rsa.RSAPublicKey) or not _serve_para_assinar(cert):
            continue
        saida.append(CertificadoWindows(hashlib.sha1(der).hexdigest().upper(), der, info_de_certificado(cert)))
    return sorted(saida, key=lambda c: (c.info.expirado, c.info.titular.lower()))


def cadeia_de_certificacao(der: bytes) -> list[bytes]:
    """Certificados intermediários/raiz do emissor, montados a partir dos
    repositórios "Autoridades intermediárias" e "Raiz confiáveis" do Windows
    (vão embutidos na assinatura, como o validador do ITI espera)."""
    por_assunto: dict = {}
    for loja in ("CA", "ROOT"):
        for _, d in _certificados_do_repositorio(loja):
            try:
                c = asn1x509.Certificate.load(d)
                por_assunto.setdefault(c.subject.dump(), c)
            except Exception:
                continue
    cadeia, atual = [], asn1x509.Certificate.load(der)
    for _ in range(10):
        if atual.self_signed != "no" and atual.self_signed:
            break
        emissor = por_assunto.get(atual.issuer.dump())
        if emissor is None or emissor.dump() in cadeia:
            break
        cadeia.append(emissor.dump())
        atual = emissor
    return cadeia


def _erro(codigo: int, contexto: str) -> ErroCertificado:
    codigo &= 0xFFFFFFFF
    if codigo in _CANCELADO:
        return ErroCertificado("Assinatura cancelada: a senha/PIN do certificado não foi informada.")
    return ErroCertificado(f"{contexto} (código 0x{codigo:08X}).")


def assinar_hash(impressao: str, resumo: bytes, algoritmo: str = "sha256") -> bytes:
    """Assina (RSA PKCS#1 v1.5) um hash já calculado com a chave privada do
    certificado identificado pela impressão digital."""
    if sys.platform != "win32":
        raise ErroCertificado("Assinatura com certificado do Windows disponível apenas no Windows.")
    algoritmo = algoritmo.lower()
    if algoritmo not in _CALG:
        raise ErroCertificado(f"Algoritmo de hash não suportado: {algoritmo}")
    for ctx, der in _certificados_do_repositorio("MY"):
        if hashlib.sha1(der).hexdigest().upper() == impressao.upper():
            ctx = _crypt32.CertDuplicateCertificateContext(ctx)
            break
    else:
        raise ErroCertificado("Certificado não encontrado no Windows. Ele pode ter sido removido.")
    try:
        try:
            return _assinar_com_contexto(ctx, resumo, algoritmo, _ACQUIRE_PREFER_NCRYPT)
        except ErroCertificado as e:
            if "cancelada" in str(e):
                raise
            # chaves da CryptoAPI legada em provedor sem SHA-2: tenta via CNG
            return _assinar_com_contexto(ctx, resumo, algoritmo, _ACQUIRE_ONLY_NCRYPT)
    finally:
        _crypt32.CertFreeCertificateContext(ctx)


def _assinar_com_contexto(ctx, resumo: bytes, algoritmo: str, preferencia: int) -> bytes:
    chave = ctypes.c_size_t(0)
    tipo = wt.DWORD(0)
    liberar = wt.BOOL(False)
    if not _crypt32.CryptAcquireCertificatePrivateKey(
            ctx, _ACQUIRE_COMPARE_KEY | preferencia, None, ctypes.byref(chave),
            ctypes.byref(tipo), ctypes.byref(liberar)):
        raise _erro(ctypes.get_last_error() or 0x80090016, "Não foi possível acessar a chave privada do certificado")
    try:
        if tipo.value == _CERT_NCRYPT_KEY_SPEC:
            return _assinar_ncrypt(chave.value, resumo, algoritmo)
        return _assinar_capi(chave.value, tipo.value, resumo, algoritmo)
    finally:
        if liberar.value:
            if tipo.value == _CERT_NCRYPT_KEY_SPEC:
                _ncrypt.NCryptFreeObject(chave.value)
            else:
                _advapi32.CryptReleaseContext(chave.value, 0)


def _assinar_ncrypt(chave: int, resumo: bytes, algoritmo: str) -> bytes:
    pad = _BCRYPT_PKCS1_PADDING_INFO(_NCRYPT_ALG[algoritmo])
    buf_hash = ctypes.create_string_buffer(resumo, len(resumo))
    tamanho = wt.DWORD(0)
    st = _ncrypt.NCryptSignHash(chave, ctypes.byref(pad), buf_hash, len(resumo), None, 0,
                                ctypes.byref(tamanho), _BCRYPT_PAD_PKCS1)
    if st != 0:
        raise _erro(st, "O Windows recusou a assinatura")
    saida = ctypes.create_string_buffer(tamanho.value)
    st = _ncrypt.NCryptSignHash(chave, ctypes.byref(pad), buf_hash, len(resumo), saida, tamanho,
                                ctypes.byref(tamanho), _BCRYPT_PAD_PKCS1)
    if st != 0:
        raise _erro(st, "O Windows recusou a assinatura")
    return saida.raw[:tamanho.value]


def _assinar_capi(prov: int, spec: int, resumo: bytes, algoritmo: str) -> bytes:
    h = ctypes.c_size_t(0)
    if not _advapi32.CryptCreateHash(prov, _CALG[algoritmo], 0, 0, ctypes.byref(h)):
        raise _erro(ctypes.get_last_error(), "O provedor do certificado não suporta este algoritmo")
    try:
        buf_hash = ctypes.create_string_buffer(resumo, len(resumo))
        if not _advapi32.CryptSetHashParam(h.value, _HP_HASHVAL, buf_hash, 0):
            raise _erro(ctypes.get_last_error(), "Falha ao preparar a assinatura")
        tamanho = wt.DWORD(0)
        if not _advapi32.CryptSignHashW(h.value, spec, None, 0, None, ctypes.byref(tamanho)):
            raise _erro(ctypes.get_last_error(), "O Windows recusou a assinatura")
        saida = ctypes.create_string_buffer(tamanho.value)
        if not _advapi32.CryptSignHashW(h.value, spec, None, 0, saida, ctypes.byref(tamanho)):
            raise _erro(ctypes.get_last_error(), "O Windows recusou a assinatura")
        return saida.raw[:tamanho.value][::-1]  # CryptoAPI devolve little-endian
    finally:
        _advapi32.CryptDestroyHash(h.value)


# ---------------------------------------------------------------- pyHanko
def assinante_pyhanko(impressao: str, der: bytes):
    """Signer do pyHanko que delega a operação de chave privada ao Windows."""
    from asn1crypto import algos
    from pyhanko.sign.signers.pdf_cms import Signer
    from pyhanko_certvalidator.registry import SimpleCertificateStore

    cert = asn1x509.Certificate.load(der)
    cadeia = [asn1x509.Certificate.load(c) for c in cadeia_de_certificacao(der)]
    tamanho_assinatura = cert.public_key.bit_size // 8

    class AssinanteWindows(Signer):
        async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run=False) -> bytes:
            if dry_run:
                return bytes(tamanho_assinatura)
            resumo = hashlib.new(digest_algorithm, data).digest()
            return assinar_hash(impressao, resumo, digest_algorithm)

    return AssinanteWindows(
        signing_cert=cert,
        cert_registry=SimpleCertificateStore.from_certs(cadeia),
        signature_mechanism=algos.SignedDigestAlgorithm({"algorithm": "sha256_rsa"}),
    )

