"""Impressão pela API do Windows (winspool + GDI), com as configurações do driver.

O QPrinter do Qt não deixa usar a janela de "Propriedades da Impressora" do driver
(cor, frente e verso, papel, bandeja, qualidade...) nem as configurações dela. Aqui:

- DEVMODE: as configurações do trabalho de impressão (estrutura do Windows), lidas
  do driver e alteradas pela janela de propriedades ou pelos atalhos Cor e Frente e
  Verso do diálogo do NuPDF;
- capacidades(): o que a impressora suporta (colorida? frente e verso?);
- imprimir(): cria o trabalho (CreateDC com o DEVMODE) e envia cada página como
  imagem (StretchDIBits), na orientação dela - roda na thread de impressão.

Tudo por ctypes, sem dependências; só no Windows.
"""

import ctypes
from ctypes import wintypes

# DEVMODEW: deslocamentos (bytes) dos campos usados - estrutura documentada do Windows
_DM_FIELDS = 72
_DM_ORIENTATION = 76
_DM_COPIES = 86
_DM_COLOR = 92
_DM_DUPLEX = 94
_DM_COLLATE = 100

DM_ORIENTATION = 0x00000001
DM_COPIES = 0x00000100
DM_COLOR = 0x00000800
DM_DUPLEX = 0x00001000
DM_COLLATE = 0x00008000

DMORIENT_RETRATO, DMORIENT_PAISAGEM = 1, 2
DMCOLOR_PRETO_E_BRANCO, DMCOLOR_COLORIDO = 1, 2
DMDUP_UM_LADO, DMDUP_BORDA_LONGA, DMDUP_BORDA_CURTA = 1, 2, 3

_DM_OUT_BUFFER, _DM_IN_PROMPT, _DM_IN_BUFFER = 2, 4, 8
_DC_DUPLEX, _DC_COPIES, _DC_COLORDEVICE = 7, 18, 32
_HORZRES, _VERTRES, _LOGPIXELSX = 8, 10, 88
_IDOK = 1

try:
    _winspool = ctypes.WinDLL("winspool.drv")
    _gdi32 = ctypes.WinDLL("gdi32")
except (OSError, AttributeError):  # fora do Windows
    _winspool = _gdi32 = None

if _winspool is not None:
    _winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    _winspool.OpenPrinterW.restype = wintypes.BOOL
    _winspool.ClosePrinter.argtypes = [wintypes.HANDLE]
    _winspool.DocumentPropertiesW.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.LPWSTR,
                                              ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    _winspool.DocumentPropertiesW.restype = ctypes.c_long
    _winspool.GetPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD)]
    _winspool.GetPrinterW.restype = wintypes.BOOL
    _winspool.DeviceCapabilitiesW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.WORD,
                                              ctypes.c_void_p, ctypes.c_void_p]
    _winspool.DeviceCapabilitiesW.restype = ctypes.c_int
    _gdi32.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
    _gdi32.CreateDCW.restype = wintypes.HDC
    _gdi32.ResetDCW.argtypes = [wintypes.HDC, ctypes.c_void_p]
    _gdi32.ResetDCW.restype = wintypes.HDC
    _gdi32.DeleteDC.argtypes = [wintypes.HDC]
    _gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    _gdi32.StartDocW.argtypes = [wintypes.HDC, ctypes.c_void_p]
    for _f in ("StartPage", "EndPage", "EndDoc", "AbortDoc"):
        getattr(_gdi32, _f).argtypes = [wintypes.HDC]
    _gdi32.StretchDIBits.argtypes = [wintypes.HDC] + [ctypes.c_int] * 8 + [ctypes.c_void_p, ctypes.c_void_p,
                                                                          wintypes.UINT, wintypes.DWORD]


class _DOCINFOW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wintypes.LPCWSTR), ("lpszOutput", wintypes.LPCWSTR),
                ("lpszDatatype", wintypes.LPCWSTR), ("fwType", wintypes.DWORD)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class _PRINTER_INFO_5(ctypes.Structure):
    _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pPortName", wintypes.LPWSTR), ("Attributes", wintypes.DWORD),
                ("DeviceNotSelectedTimeout", wintypes.DWORD), ("TransmissionRetryTimeout", wintypes.DWORD)]


def disponivel() -> bool:
    return _winspool is not None


# ---------------------------------------------------------------- DEVMODE
def _ler(dm: bytearray, pos: int) -> int:
    return int.from_bytes(dm[pos:pos + 2], "little", signed=True)


def _gravar(dm: bytearray, pos: int, valor: int, flag: int):
    dm[pos:pos + 2] = int(valor).to_bytes(2, "little", signed=True)
    campos = int.from_bytes(dm[_DM_FIELDS:_DM_FIELDS + 4], "little") | flag
    dm[_DM_FIELDS:_DM_FIELDS + 4] = campos.to_bytes(4, "little")


def _tem(dm: bytearray, flag: int) -> bool:
    return bool(int.from_bytes(dm[_DM_FIELDS:_DM_FIELDS + 4], "little") & flag)


def cor(dm: bytearray) -> int | None:
    return _ler(dm, _DM_COLOR) if _tem(dm, DM_COLOR) else None


def duplex(dm: bytearray) -> int | None:
    return _ler(dm, _DM_DUPLEX) if _tem(dm, DM_DUPLEX) else None


def definir_cor(dm: bytearray, valor: int):
    _gravar(dm, _DM_COLOR, valor, DM_COLOR)


def definir_duplex(dm: bytearray, valor: int):
    _gravar(dm, _DM_DUPLEX, valor, DM_DUPLEX)


def definir_orientacao(dm: bytearray, valor: int):
    _gravar(dm, _DM_ORIENTATION, valor, DM_ORIENTATION)


def definir_copias(dm: bytearray, copias: int):
    _gravar(dm, _DM_COPIES, copias, DM_COPIES)
    _gravar(dm, _DM_COLLATE, 1, DM_COLLATE)  # cópias agrupadas (1,2,3, 1,2,3)


class _Impressora:
    def __init__(self, nome: str):
        self.nome = nome
        self.h = wintypes.HANDLE()
        if not _winspool.OpenPrinterW(nome, ctypes.byref(self.h), None):
            raise OSError(f"Não foi possível acessar a impressora \"{nome}\".")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        _winspool.ClosePrinter(self.h)


def devmode_padrao(nome: str) -> bytearray:
    """Configurações padrão do driver para a impressora (cópia própria do DEVMODE)."""
    with _Impressora(nome) as imp:
        tamanho = _winspool.DocumentPropertiesW(None, imp.h, nome, None, None, 0)
        if tamanho <= 0:
            raise OSError("O driver da impressora não informou as configurações.")
        buf = ctypes.create_string_buffer(tamanho)
        if _winspool.DocumentPropertiesW(None, imp.h, nome, buf, None, _DM_OUT_BUFFER) < 0:
            raise OSError("O driver da impressora não informou as configurações.")
        return bytearray(buf.raw)


def propriedades(hwnd: int, nome: str, dm: bytearray) -> bytearray | None:
    """Abre a janela de propriedades do DRIVER (a mesma do Word/Adobe) partindo de `dm`.
    Devolve o DEVMODE alterado, ou None se o usuário cancelou."""
    with _Impressora(nome) as imp:
        tamanho = _winspool.DocumentPropertiesW(None, imp.h, nome, None, None, 0)
        saida = ctypes.create_string_buffer(max(tamanho, len(dm)))
        entrada = ctypes.create_string_buffer(bytes(dm), len(dm))
        r = _winspool.DocumentPropertiesW(hwnd, imp.h, nome, saida, entrada,
                                          _DM_IN_BUFFER | _DM_OUT_BUFFER | _DM_IN_PROMPT)
        if r != _IDOK:
            return None
        return bytearray(saida.raw)


def capacidades(nome: str, dm: bytearray | None = None) -> dict:
    """{"cor": bool, "duplex": bool, "copias": int} - o que o driver diz suportar.
    Sem resposta do driver, cai no que o DEVMODE padrão anuncia."""
    porta = None
    try:
        with _Impressora(nome) as imp:
            precisa = wintypes.DWORD(0)
            _winspool.GetPrinterW(imp.h, 5, None, 0, ctypes.byref(precisa))
            if precisa.value:
                buf = ctypes.create_string_buffer(precisa.value)
                if _winspool.GetPrinterW(imp.h, 5, buf, precisa.value, ctypes.byref(precisa)):
                    porta = ctypes.cast(buf, ctypes.POINTER(_PRINTER_INFO_5)).contents.pPortName
    except OSError:
        pass

    def cap(codigo: int) -> int:
        try:
            return _winspool.DeviceCapabilitiesW(nome, porta, codigo, None, None)
        except Exception:
            return -1

    tem_cor, tem_duplex, copias = cap(_DC_COLORDEVICE), cap(_DC_DUPLEX), cap(_DC_COPIES)
    if dm is not None:
        if tem_cor < 0:
            tem_cor = 1 if _tem(dm, DM_COLOR) else 0
        if tem_duplex < 0:
            tem_duplex = 1 if _tem(dm, DM_DUPLEX) else 0
    return {"cor": tem_cor == 1, "duplex": tem_duplex == 1, "copias": max(copias, 1)}


# ---------------------------------------------------------------- impressão
class Trabalho:
    """Trabalho de impressão GDI: abrir(), pagina(imagem RGB32, paisagem) e fechar()."""

    def __init__(self, nome_impressora: str, dm: bytearray, nome_documento: str, arquivo: str | None = None):
        """`arquivo`: grava o que iria para a impressora num arquivo (testes)."""
        self.nome, self.dm = nome_impressora, bytearray(dm)
        self.hdc = _gdi32.CreateDCW("WINSPOOL", nome_impressora, None, bytes(self.dm))
        if not self.hdc:
            raise OSError(f"Não foi possível conectar na impressora \"{nome_impressora}\".")
        info = _DOCINFOW(ctypes.sizeof(_DOCINFOW), nome_documento, arquivo, None, 0)
        if _gdi32.StartDocW(self.hdc, ctypes.byref(info)) <= 0:
            _gdi32.DeleteDC(self.hdc)
            raise OSError("A impressora recusou o trabalho de impressão.")
        self._paginas = 0
        self._paisagem = None

    @property
    def dpi(self) -> int:
        return _gdi32.GetDeviceCaps(self.hdc, _LOGPIXELSX) or 300

    def pagina(self, bits: bytes, largura: int, altura: int, paisagem: bool):
        """Uma página: imagem 32 bits (BGRA, linhas de cima para baixo), centralizada
        e ajustada à área imprimível, na orientação da página do PDF."""
        if paisagem != self._paisagem:
            # ResetDC entre páginas: cada página sai na orientação dela (retrato/paisagem)
            definir_orientacao(self.dm, DMORIENT_PAISAGEM if paisagem else DMORIENT_RETRATO)
            _gdi32.ResetDCW(self.hdc, bytes(self.dm))
            self._paisagem = paisagem
        if _gdi32.StartPage(self.hdc) <= 0:
            raise OSError("Falha ao iniciar a página na impressora.")
        area_l, area_a = _gdi32.GetDeviceCaps(self.hdc, _HORZRES), _gdi32.GetDeviceCaps(self.hdc, _VERTRES)
        escala = min(area_l / largura, area_a / altura)
        w, h = int(largura * escala), int(altura * escala)
        bmi = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), largura, -altura, 1, 32, 0, 0, 0, 0, 0, 0)
        _gdi32.StretchDIBits(self.hdc, (area_l - w) // 2, (area_a - h) // 2, w, h, 0, 0, largura, altura,
                             bits, ctypes.byref(bmi), 0, 0x00CC0020)
        if _gdi32.EndPage(self.hdc) <= 0:
            raise OSError("Falha ao enviar a página para a impressora.")
        self._paginas += 1

    def fechar(self, cancelar: bool = False):
        if self.hdc:
            if cancelar:
                _gdi32.AbortDoc(self.hdc)
            else:
                _gdi32.EndDoc(self.hdc)
            _gdi32.DeleteDC(self.hdc)
            self.hdc = None
