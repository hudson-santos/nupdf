"""Juntar PDFs: tela para ordenar os arquivos e unificá-los num só PDF.

Aberta pelo botão "Juntar PDFs" do NuPDF ou pelo menu de contexto do Windows
(NuPDF > Juntar, registrado pelo instalar.ps1): o Explorer chama o
NuPDF uma vez por arquivo selecionado e o main.py reúne as chamadas numa só tela.
"""

import os
import re
from pathlib import Path

import pymupdf
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QVBoxLayout)

from . import ui


def _chave_natural(caminho: str):
    """Ordem "natural" de nome: arquivo2 antes de arquivo10."""
    nome = Path(caminho).name.lower()
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", nome)]


def juntar(arquivos: list[str], destino: str, senhas: dict[str, str] | None = None) -> int:
    """Une os PDFs na ordem dada e grava em `destino`. Cada arquivo de origem vira um
    marcador (índice) no PDF final, apontando para a primeira página dele. Devolve o
    total de páginas."""
    senhas = senhas or {}
    saida = pymupdf.open()
    indice = []
    try:
        for caminho in arquivos:
            origem = pymupdf.open(caminho)
            try:
                if origem.needs_pass and not origem.authenticate(senhas.get(caminho, "")):
                    raise ValueError(f"Senha incorreta: {Path(caminho).name}")
                inicio = saida.page_count
                saida.insert_pdf(origem)
                if saida.page_count > inicio:
                    indice.append([1, Path(caminho).stem, inicio + 1])
            finally:
                origem.close()
        if not saida.page_count:
            raise ValueError("Nenhuma página para juntar.")
        if len(indice) > 1:
            saida.set_toc(indice)
        saida.save(destino, garbage=3, deflate=True)
        return saida.page_count
    finally:
        saida.close()


class DialogoJuntar(QDialog):
    """Lista dos PDFs (arrastar para reordenar) e o botão Juntar. Depois de aceito,
    `destino` tem o caminho do PDF gerado."""

    def __init__(self, arquivos: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Juntar PDFs")
        self.setMinimumSize(620, 460)
        self.destino = ""
        self._senhas: dict[str, str] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        titulo = QLabel("Juntar PDFs")
        titulo.setStyleSheet("font-size: 17px; font-weight: 700;")
        lay.addWidget(titulo)
        dica = QLabel("Arraste para mudar a ordem. O PDF final segue a ordem da lista, de cima para baixo.")
        dica.setObjectName("sub")
        dica.setWordWrap(True)
        lay.addWidget(dica)

        corpo = QHBoxLayout()
        corpo.setSpacing(12)
        self.lista = QListWidget()
        self.lista.setObjectName("listaJuntar")
        self.lista.setDragDropMode(QAbstractItemView.InternalMove)
        self.lista.setDefaultDropAction(Qt.MoveAction)
        self.lista.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista.setAlternatingRowColors(False)
        self.lista.model().rowsMoved.connect(lambda *_: self._renumerar())
        self.lista.itemSelectionChanged.connect(self._atualizar_botoes)
        corpo.addWidget(self.lista, 1)

        botoes_lado = QVBoxLayout()
        botoes_lado.setSpacing(8)

        def botao(texto, icone, acao, dica_b=""):
            b = QPushButton(f"  {texto}")
            b.setObjectName("ferramenta")
            ui.aplicar_icone(b, icone, 16)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(dica_b)
            b.clicked.connect(acao)
            botoes_lado.addWidget(b)
            return b

        botao("Adicionar PDFs", "mais", self._adicionar, "Incluir mais arquivos PDF na lista")
        self.b_subir = botao("Subir", "acima", lambda: self._mover(-1), "Mover o arquivo selecionado para cima")
        self.b_descer = botao("Descer", "abaixo", lambda: self._mover(1), "Mover o arquivo selecionado para baixo")
        botao("Ordenar por Nome", "texto", self._ordenar, "Ordem alfabética dos nomes dos arquivos")
        self.b_remover = botao("Remover", "lixeira", self._remover, "Tirar o arquivo selecionado da lista")
        botoes_lado.addStretch(1)
        corpo.addLayout(botoes_lado)
        lay.addLayout(corpo, 1)

        self.resumo = QLabel()
        self.resumo.setObjectName("sub3")
        lay.addWidget(self.resumo)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        fechar = QPushButton("Fechar")
        fechar.setObjectName("fechar")
        fechar.setCursor(Qt.PointingHandCursor)
        fechar.clicked.connect(self.reject)
        self.b_juntar = QPushButton("Juntar PDFs")
        self.b_juntar.setObjectName("primario")
        self.b_juntar.setCursor(Qt.PointingHandCursor)
        self.b_juntar.setDefault(True)
        self.b_juntar.clicked.connect(self._juntar)
        rodape.addWidget(fechar)
        rodape.addWidget(self.b_juntar)
        lay.addLayout(rodape)

        self._incluir(sorted(arquivos or [], key=_chave_natural))

    # ------------------------------------------------------------------ lista
    def arquivos(self) -> list[str]:
        return [self.lista.item(i).data(Qt.UserRole) for i in range(self.lista.count())]

    def _incluir(self, caminhos: list[str]):
        ja = {os.path.normcase(c) for c in self.arquivos()}
        for caminho in caminhos:
            caminho = str(Path(caminho).resolve())
            if os.path.normcase(caminho) in ja or not caminho.lower().endswith(".pdf"):
                continue
            paginas = self._paginas(caminho)
            if paginas is None:
                continue
            item = QListWidgetItem()
            item.setData(Qt.UserRole, caminho)
            item.setData(Qt.UserRole + 1, paginas)
            item.setToolTip(caminho)
            self.lista.addItem(item)
            ja.add(os.path.normcase(caminho))
        self._renumerar()

    def _paginas(self, caminho: str) -> int | None:
        """Nº de páginas (pede a senha de PDF protegido); None se não der para usar."""
        try:
            doc = pymupdf.open(caminho)
        except Exception:
            QMessageBox.warning(self, "Juntar PDFs", f"Não foi possível abrir:\n{caminho}")
            return None
        try:
            while doc.needs_pass:
                senha, ok = QInputDialog.getText(self, "PDF protegido", f"{Path(caminho).name} está protegido "
                                                 "por senha. Digite a senha:", QLineEdit.Password)
                if not ok:
                    return None
                if doc.authenticate(senha):
                    self._senhas[caminho] = senha
            return doc.page_count
        finally:
            doc.close()

    def _renumerar(self):
        total = 0
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            paginas = item.data(Qt.UserRole + 1)
            total += paginas
            nome = Path(item.data(Qt.UserRole)).name
            item.setText(f"{i + 1}.  {nome}   ·   {paginas} página{'s' if paginas != 1 else ''}")
        n = self.lista.count()
        self.resumo.setText(f"{n} arquivo{'s' if n != 1 else ''} · {total} página{'s' if total != 1 else ''} no total")
        self.b_juntar.setVisible(n >= 2)
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        sel = bool(self.lista.selectedItems())
        for b in (self.b_subir, self.b_descer, self.b_remover):
            b.setVisible(sel)

    def _adicionar(self):
        pasta = str(Path(self.arquivos()[0]).parent) if self.arquivos() else ""
        caminhos, _ = QFileDialog.getOpenFileNames(self, "Adicionar PDFs", pasta, "Documentos PDF (*.pdf)")
        self._incluir(caminhos)

    def _mover(self, passo: int):
        linhas = sorted(self.lista.row(i) for i in self.lista.selectedItems())
        if not linhas:
            return
        if (passo < 0 and linhas[0] == 0) or (passo > 0 and linhas[-1] == self.lista.count() - 1):
            return
        for linha in (linhas if passo < 0 else reversed(linhas)):
            item = self.lista.takeItem(linha)
            self.lista.insertItem(linha + passo, item)
            item.setSelected(True)
        self._renumerar()

    def _ordenar(self):
        caminhos = sorted(self.arquivos(), key=_chave_natural)
        dados = {self.lista.item(i).data(Qt.UserRole): self.lista.item(i).data(Qt.UserRole + 1)
                 for i in range(self.lista.count())}
        self.lista.clear()
        for c in caminhos:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, c)
            item.setData(Qt.UserRole + 1, dados[c])
            item.setToolTip(c)
            self.lista.addItem(item)
        self._renumerar()

    def _remover(self):
        for item in self.lista.selectedItems():
            self.lista.takeItem(self.lista.row(item))
        self._renumerar()

    # ------------------------------------------------------------------ juntar
    def _juntar(self):
        arquivos = self.arquivos()
        if len(arquivos) < 2:
            return
        sugerido = Path(arquivos[0]).with_name("PDFs Juntados.pdf")
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar o PDF Juntado", str(sugerido),
                                                 "Documentos PDF (*.pdf)")
        if not destino:
            return
        if os.path.normcase(str(Path(destino).resolve())) in {os.path.normcase(a) for a in arquivos}:
            QMessageBox.warning(self, "Juntar PDFs", "Escolha outro nome: o PDF juntado não pode substituir "
                                "um dos arquivos da lista.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            juntar(arquivos, destino, self._senhas)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Juntar PDFs", f"Não foi possível juntar os PDFs:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        self.destino = destino
        self.accept()
