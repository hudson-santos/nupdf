"""Preferências do usuário (arquivo INI em %APPDATA%\\NuPDF)."""

import json
import os
from pathlib import Path

from PySide6.QtCore import QSettings

MAX_RECENTES = 12


def pasta_dados() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "NuPDF"
    base.mkdir(parents=True, exist_ok=True)
    return base


class Config:
    def __init__(self):
        self._s = QSettings(str(pasta_dados() / "nupdf.ini"), QSettings.IniFormat)

    def get(self, chave: str, padrao=None):
        valor = self._s.value(chave, padrao)
        if isinstance(padrao, bool) and isinstance(valor, str):
            return valor.lower() in ("true", "1", "sim")
        return valor

    def set(self, chave: str, valor):
        self._s.setValue(chave, valor)

    def tema_escuro(self) -> bool:
        """Tema claro é o padrão de instalações novas. Quem já usava o NuPDF (já há
        preferências gravadas) sem nunca ter trocado o tema estava no escuro - o
        padrão antigo - e continua nele."""
        if not self._s.contains("tema_escuro"):
            self._s.setValue("tema_escuro", bool(self._s.allKeys()))
        return bool(self.get("tema_escuro", False))

    # --- arquivos recentes -------------------------------------------------
    def recentes(self) -> list[str]:
        try:
            lista = json.loads(self._s.value("recentes", "[]"))
        except (TypeError, ValueError):
            lista = []
        return [c for c in lista if isinstance(c, str)]

    def adicionar_recente(self, caminho: str):
        caminho = str(Path(caminho).resolve())
        lista = [c for c in self.recentes() if c.lower() != caminho.lower()]
        lista.insert(0, caminho)
        self._s.setValue("recentes", json.dumps(lista[:MAX_RECENTES]))

    def limpar_recentes(self):
        self._s.setValue("recentes", "[]")

    def remover_recente(self, caminho: str):
        lista = [c for c in self.recentes() if c.lower() != caminho.lower()]
        self._s.setValue("recentes", json.dumps(lista))
