"""Gera as imagens da listagem do NuPDF na Microsoft Store (pasta ms/).

Uso (na raiz do projeto):  venv\\Scripts\\python.exe ms\\gerar_imagens.py

- Capturas de tela 1920x1080 (.png) tiradas do próprio NuPDF, renderizado fora da
  tela, com documentos e certificado FICTÍCIOS gerados aqui (nada do computador do
  usuário aparece: nem certificados instalados, nem impressoras, nem arquivos).
- Logotipos da Store a partir do logo vetorial do app (nupdf/icones.py):
  1:1 (2160x2160, obrigatório), 2:3 pôster (1440x2160) e 16:9 hero (3840x2160).
"""

import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

TMP = Path(tempfile.mkdtemp(prefix="nupdf_ms_"))
os.environ["APPDATA"] = str(TMP / "appdata")  # preferências isoladas (não usa as do usuário)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pymupdf  # noqa: E402
from PySide6.QtCore import QByteArray, QPoint, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

LARGURA, ALTURA = 1920, 1080
VERMELHO = QColor("#e5484d")
TEXTO = QColor("#1f2328")
TEXTO2 = QColor("#5b616b")

app = QApplication([])
app.setStyle("Fusion")


def esperar(seg: float = 0.6):
    fim = time.time() + seg
    while time.time() < fim:
        app.processEvents()


# ====================================================================== documentos fictícios
CSS = """
body { font-family: sans-serif; color: #202124; font-size: 10.5pt; line-height: 1.45; }
h1 { font-size: 15pt; text-align: center; margin: 0 0 4px 0; }
h2 { font-size: 11pt; margin: 14px 0 4px 0; }
p { text-align: justify; margin: 0 0 7px 0; }
.sub { text-align: center; color: #5b616b; margin-bottom: 14px; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; }
th { background: #5b9bd5; color: #ffffff; text-align: left; padding: 5px 6px; }
td { padding: 4px 6px; border-bottom: 1px solid #e3e6ea; }
.num { text-align: right; }
"""

CLAUSULAS = [
    ("CLÁUSULA PRIMEIRA - DO OBJETO",
     "O presente contrato tem por objeto a prestação de serviços de consultoria em gestão documental, "
     "digitalização e organização do acervo da CONTRATANTE, conforme o plano de trabalho anexo, que "
     "passa a fazer parte integrante deste instrumento."),
    ("CLÁUSULA SEGUNDA - DO PRAZO",
     "O contrato vigorará por 12 (doze) meses a partir da data de assinatura, podendo ser prorrogado por "
     "iguais períodos mediante termo aditivo assinado pelas partes."),
    ("CLÁUSULA TERCEIRA - DO VALOR E DO PAGAMENTO",
     "Pelos serviços prestados a CONTRATANTE pagará à CONTRATADA o valor mensal de R$ 4.850,00 (quatro mil, "
     "oitocentos e cinquenta reais), até o 5º (quinto) dia útil de cada mês, mediante a emissão de nota fiscal."),
    ("CLÁUSULA QUARTA - DAS OBRIGAÇÕES DA CONTRATADA",
     "Executar os serviços com zelo e qualidade, manter sigilo sobre as informações a que tiver acesso e "
     "apresentar relatório mensal das atividades realizadas, com os indicadores acordados."),
    ("CLÁUSULA QUINTA - DAS OBRIGAÇÕES DA CONTRATANTE",
     "Fornecer as informações e o acesso necessários à execução dos serviços e efetuar os pagamentos nas "
     "datas previstas neste contrato."),
    ("CLÁUSULA SEXTA - DA ASSINATURA ELETRÔNICA",
     "As partes reconhecem a validade da assinatura digital com certificado ICP-Brasil, nos termos da "
     "Medida Provisória nº 2.200-2/2001, para todos os fins de direito."),
]

FUNCIONARIOS = [
    ("1024", "ANA CLARA MENDES", "Financeiro", "4.215,30"),
    ("1031", "BRUNO HENRIQUE COSTA", "Operações", "3.180,00"),
    ("1047", "CARLA REGINA DUARTE", "Comercial", "5.640,75"),
    ("1052", "DANIEL AUGUSTO PIRES", "TI", "6.920,10"),
    ("1068", "EDUARDA LIMA SANTOS", "Recursos Humanos", "3.875,45"),
    ("1073", "FELIPE MARTINS ROCHA", "Logística", "2.990,00"),
    ("1089", "GABRIELA NUNES FARIAS", "Jurídico", "7.310,60"),
    ("1094", "HENRIQUE SOUZA ALVES", "Operações", "3.180,00"),
    ("1102", "ISABELA TEIXEIRA GOMES", "Comercial", "4.905,20"),
    ("1115", "JOÃO PEDRO CARVALHO", "TI", "5.480,00"),
    ("1128", "LARISSA MOURA BATISTA", "Financeiro", "4.215,30"),
    ("1136", "MARCOS VINÍCIUS REIS", "Logística", "2.990,00"),
    ("1149", "NATÁLIA FERREIRA LOPES", "Marketing", "4.460,90"),
    ("1157", "OTÁVIO RIBEIRO DIAS", "Operações", "3.325,15"),
    ("1163", "PAULA CRISTINA VIANA", "Recursos Humanos", "3.875,45"),
    ("1178", "RAFAEL ANTUNES MELO", "Comercial", "5.120,00"),
    ("1184", "SABRINA OLIVEIRA CRUZ", "Jurídico", "6.745,80"),
    ("1191", "THIAGO BARBOSA PINTO", "TI", "5.480,00"),
]


def gerar_contrato(destino: Path):
    doc = pymupdf.open()
    corpo = ["<h1>CONTRATO DE PRESTAÇÃO DE SERVIÇOS</h1>",
             "<p class='sub'>Empresa Exemplo Ltda &nbsp;•&nbsp; Consultoria Modelo S/A</p>",
             "<p><b>CONTRATANTE:</b> EMPRESA EXEMPLO LTDA, inscrita no CNPJ sob o nº 12.345.678/0001-95, com "
             "sede na Avenida Central, 1000, Centro, Cidade Exemplo - UF.</p>",
             "<p><b>CONTRATADA:</b> CONSULTORIA MODELO S/A, inscrita no CNPJ sob o nº 98.765.432/0001-10, "
             "neste ato representada por MARIA APARECIDA SOUZA.</p>",
             "<p>As partes acima identificadas têm, entre si, justo e acertado o presente contrato, que se "
             "regerá pelas cláusulas seguintes e pelas condições descritas no presente.</p>"]
    for titulo, texto in CLAUSULAS:
        corpo.append(f"<h2>{titulo}</h2><p>{texto}</p>")
    corpo.append("<p style='margin-top:18px'>Cidade Exemplo, 29 de setembro de 2026.</p>")
    for k in range(3):
        pg = doc.new_page(width=595, height=842)
        html = "".join(corpo) if k == 0 else (
            f"<h2>ANEXO {k} - PLANO DE TRABALHO</h2>" + "".join(f"<p>{t}</p>" for _, t in CLAUSULAS))
        pg.insert_htmlbox(pymupdf.Rect(60, 60, 535, 700 if k == 0 else 780), html, css=CSS)
        pg.insert_text((490, 815), f"Página {k + 1} de 3", fontsize=8, color=(0.45, 0.45, 0.45))
    doc.save(destino)


def gerar_relatorio(destino: Path):
    doc = pymupdf.open()
    linhas = "".join(f"<tr><td>{m}</td><td>{n}</td><td>{s}</td><td class='num'>{v}</td></tr>"
                     for m, n, s, v in FUNCIONARIOS)
    html = ("<h1>RELAÇÃO DE PAGAMENTOS - SETEMBRO/2026</h1>"
            "<p class='sub'>Empresa Exemplo Ltda &nbsp;•&nbsp; CNPJ 12.345.678/0001-95</p>"
            "<table><tr><th>Matrícula</th><th>Nome</th><th>Setor</th><th class='num'>Líquido (R$)</th></tr>"
            f"{linhas}</table>")
    for k in range(2):
        pg = doc.new_page(width=595, height=842)
        pg.insert_htmlbox(pymupdf.Rect(50, 55, 545, 800), html, css=CSS)
    doc.save(destino)


def gerar_certificado(pasta: Path):
    """AC fictícia -> certificado e-CPF fictício (CPF de exemplo 123.456.789-09)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    agora = datetime.now(timezone.utc)
    k_ac, k_titular = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))
    nome_ac = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
                         x509.NameAttribute(NameOID.COMMON_NAME, "AC EXEMPLO v5")])
    ac = (x509.CertificateBuilder().subject_name(nome_ac).issuer_name(nome_ac)
          .public_key(k_ac.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(agora - timedelta(days=30)).not_valid_after(agora + timedelta(days=3650))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
          .sign(k_ac, hashes.SHA256()))
    nome = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
                      x509.NameAttribute(NameOID.COMMON_NAME, "MARIA APARECIDA SOUZA:12345678909")])
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome_ac)
            .public_key(k_titular.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(agora - timedelta(days=10)).not_valid_after(agora + timedelta(days=365))
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
            .sign(k_ac, hashes.SHA256()))
    pfx = pasta / "exemplo.pfx"
    pfx.write_bytes(pkcs12.serialize_key_and_certificates(
        b"exemplo", k_titular, cert, [ac], serialization.BestAvailableEncryption(b"1234")))
    return pfx, cert, ac


# ====================================================================== capturas
def salvar(img, nome: str):
    img.save(str(SAIDA / nome))
    print("  ", nome, f"{img.width()}x{img.height()}")


def selecionar_linha(v, pagina: int, primeira_palavra: str):
    ws = v.doc.palavras(pagina)
    k = next(i for i, w in enumerate(ws) if w[4] == primeira_palavra)
    linha = [i for i, w in enumerate(ws) if w[5] == ws[k][5]]
    v.sel_ret = None
    v.sel_ini, v.sel_fim = (pagina, linha[0]), (pagina, linha[-1])


def main():
    from nupdf import tema
    from nupdf.assinatura.assinador import ConfigAssinatura, assinar_pdf
    from nupdf.assinatura.certificado import info_de_certificado
    from nupdf.assinatura.validador import confiar
    from nupdf.assinatura.windows import CertificadoWindows
    from nupdf import dialogos, leitor_padrao
    from nupdf.janela import JanelaPrincipal
    from pyhanko.sign import signers

    print("Documentos e certificado fictícios...")
    docs = TMP / "Documentos"
    docs.mkdir(parents=True)
    contrato, relatorio = docs / "Contrato de Prestação de Serviços.pdf", docs / "Relação de Pagamentos.pdf"
    gerar_contrato(contrato)
    gerar_relatorio(relatorio)
    pfx, cert, ac = gerar_certificado(TMP)
    info = info_de_certificado(cert)
    assinante = signers.SimpleSigner.load_pkcs12(str(pfx), passphrase=b"1234")
    cfg = ConfigAssinatura(info, impressao="EXEMPLO", der=b"x", visivel=True, pagina=0,
                           caixa=(300, 52, 545, 128))
    assinado = docs / "Contrato de Prestação de Serviços_assinado.pdf"
    assinado.write_bytes(assinar_pdf(contrato.read_bytes(), cfg, assinante=assinante))
    from cryptography.hazmat.primitives.serialization import Encoding
    confiar(ac.public_bytes(Encoding.DER))  # a AC fictícia vale só nesta pasta temporária

    # nada do computador do usuário: leitor padrão "ok" e lista de certificados fictícia
    leitor_padrao.e_padrao = lambda: True
    dialogos.listar_certificados = lambda: [CertificadoWindows("EXEMPLO", cert.public_bytes(Encoding.DER), info)]

    print("Capturas de tela...")
    j = JanelaPrincipal()
    j.resize(LARGURA, ALTURA)
    j.show()
    if j.escuro:
        j.alternar_tema()
    for p in (relatorio, assinado, contrato):
        j.config.adicionar_recente(str(p))
    j.inicio.atualizar(j.config.recentes())
    esperar(1.0)
    salvar(j.grab().toImage(), "captura-01-inicio.png")

    # 2) leitura com miniaturas
    aba = j.abrir_arquivo(str(contrato), painel="miniaturas")
    esperar(1.5)
    aba.visualizador.ajustar("largura", 1.25)
    esperar(0.8)
    salvar(j.grab().toImage(), "captura-02-leitura-e-miniaturas.png")

    # 3) destaques por prioridade + botões Copiar / Destacar
    aba = j.abrir_arquivo(str(relatorio), painel="")
    aba.mostrar_painel(None)
    esperar(1.0)
    v = aba.visualizador
    v.ajustar("largura", 1.6)
    esperar(0.5)
    for nome, cor in (("CARLA", "vermelho"), ("DANIEL", "amarelo"), ("GABRIELA", "azul"), ("JOÃO", "verde"),
                      ("NATÁLIA", "vermelho")):
        selecionar_linha(v, 0, nome)
        v._destacar_selecao(cor)
    v.definir_cor_destaque("amarelo")
    esperar(2.6)  # some o aviso "Texto Destacado"
    selecionar_linha(v, 0, "EDUARDA")  # linha visível, com os botões Copiar / Destacar
    v._pag.update()
    v.selecaoMudou.emit(True)
    esperar(0.8)
    salvar(j.grab().toImage(), "captura-03-destaques-por-prioridade.png")

    # 4) documento assinado + validação
    aba = j.abrir_arquivo(str(assinado), painel="assinaturas")
    esperar(1.0)
    v = aba.visualizador
    v.ajustar("largura", 1.25)
    esperar(0.5)
    v.verticalScrollBar().setValue(int(v._geo[0][0].bottom() - v.viewport().height() + 40))
    fim = time.time() + 20
    while time.time() < fim and aba.assinaturas._resultados is None:
        app.processEvents()
    esperar(0.8)
    salvar(j.grab().toImage(), "captura-04-assinatura-validada.png")

    # 5) janela "Assinar Documento" sobre o contrato
    aba = j.abrir_arquivo(str(contrato), painel="")
    aba.mostrar_painel(None)
    esperar(0.8)
    fundo = j.grab().toImage()
    dlg = dialogos.DialogoAssinatura(j.config, j)
    dlg.show()
    dlg.adjustSize()
    esperar(0.6)
    salvar(compor_dialogo(fundo, dlg.grab().toImage(), "Assinar Documento"), "captura-05-assinar-com-certificado.png")
    dlg.close()

    # 6) tema escuro
    j.alternar_tema()
    aba = j.abrir_arquivo(str(relatorio))  # já aberto: só troca de aba
    aba.visualizador.limpar_selecao()
    if aba.painel != "miniaturas":
        aba.mostrar_painel("miniaturas")
    esperar(1.5)
    salvar(j.grab().toImage(), "captura-06-tema-escuro.png")
    j.alternar_tema()
    return j


def compor_dialogo(fundo: QImage, dlg: QImage, titulo: str) -> QImage:
    """Janela modal desenhada sobre a captura: fundo escurecido, sombra e barra de título."""
    img = QImage(fundo)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.fillRect(img.rect(), QColor(0, 0, 0, 70))
    barra = 36
    w, h = dlg.width(), dlg.height() + barra
    x, y = (img.width() - w) // 2, (img.height() - h) // 2
    for k in range(18, 0, -2):  # sombra suave
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 6))
        p.drawRoundedRect(QRectF(x - k, y - k + 8, w + 2 * k, h + 2 * k), 12 + k, 12 + k)
    caminho = QPainterPath()
    caminho.addRoundedRect(QRectF(x, y, w, h), 8, 8)
    p.setClipPath(caminho)
    p.fillRect(QRect(x, y, w, barra), QColor("#f3f3f3"))
    p.drawImage(QPoint(x, y + barra), dlg)
    p.setClipping(False)
    p.setPen(TEXTO2)
    f = QFont("Google Sans", 10)
    p.setFont(f)
    p.drawText(QRect(x + 16, y, w - 32, barra), Qt.AlignVCenter | Qt.AlignLeft, titulo)
    p.drawText(QRect(x + w - 40, y, 30, barra), Qt.AlignCenter, "✕")
    p.end()
    return img


# ====================================================================== logotipos
def logo(tamanho: int) -> QImage:
    from nupdf.icones import _LOGO
    img = QImage(tamanho, tamanho, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(_LOGO.encode())).render(p, QRectF(0, 0, tamanho, tamanho))
    p.end()
    return img


def fundo_suave(p: QPainter, w: int, h: int):
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#ffffff"))
    g.setColorAt(1, QColor("#fdecec"))
    p.fillRect(0, 0, w, h, g)


def nome_app(p: QPainter, rect: QRect, px: int, alinhamento=Qt.AlignHCenter):
    """ "Nu" escuro + "PDF" vermelho, como no topo do app."""
    f = QFont("Google Sans", 10, QFont.Bold)
    f.setPixelSize(px)
    p.setFont(f)
    fm = p.fontMetrics()
    w = fm.horizontalAdvance("Nu") + fm.horizontalAdvance("PDF")
    x = rect.x() + (rect.width() - w) // 2 if alinhamento == Qt.AlignHCenter else rect.x()
    y = rect.y() + (rect.height() + fm.ascent() - fm.descent()) // 2
    p.setPen(TEXTO)
    p.drawText(x, y, "Nu")
    p.setPen(VERMELHO)
    p.drawText(x + fm.horizontalAdvance("Nu"), y, "PDF")


def texto(p: QPainter, rect: QRect, conteudo: str, px: int, cor=TEXTO2, peso=QFont.Normal,
          alinhamento=Qt.AlignHCenter | Qt.AlignTop):
    f = QFont("Google Sans", 10, peso)
    f.setPixelSize(px)
    p.setFont(f)
    p.setPen(cor)
    p.drawText(rect, alinhamento | Qt.TextWordWrap, conteudo)


def logotipos(captura: Path):
    print("Logotipos...")
    # quebras de linha fixas: sem isso "ICP-Brasil" quebra no hífen
    frase = "Leia PDFs, Copie Dados e\nAssine Digitalmente com\nCertificado ICP-Brasil"

    # 1:1 (arte de caixa, obrigatória): 2160 x 2160
    t = 2160
    img = QImage(t, t, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    fundo_suave(p, t, t)
    m = int(t * 0.46)
    p.drawImage((t - m) // 2, int(t * 0.18), logo(m))
    nome_app(p, QRect(0, int(t * 0.68), t, int(t * 0.16)), int(t * 0.115))
    p.end()
    salvar(img, "logo-1x1-2160.png")

    # 2:3 (pôster, recomendada): 1440 x 2160
    w, h = 1440, 2160
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    fundo_suave(p, w, h)
    m = int(w * 0.5)
    p.drawImage((w - m) // 2, int(h * 0.2), logo(m))
    nome_app(p, QRect(0, int(h * 0.56), w, int(h * 0.1)), int(w * 0.15))
    texto(p, QRect(int(w * 0.12), int(h * 0.7), int(w * 0.76), int(h * 0.2)), frase, int(w * 0.045))
    p.end()
    salvar(img, "poster-2x3-1440x2160.png")

    # 16:9 (hero, opcional): 3840 x 2160, com uma captura do app
    w, h = 3840, 2160
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    fundo_suave(p, w, h)
    m = 420
    p.drawImage(260, 560, logo(m))
    nome_app(p, QRect(260, 1010, 1300, 240), 210, alinhamento=Qt.AlignLeft)
    texto(p, QRect(260, 1290, 1250, 400), frase, 82, alinhamento=Qt.AlignLeft | Qt.AlignTop)
    tela = QImage(str(captura)).scaledToWidth(2050, Qt.SmoothTransformation)
    x, y = w - tela.width() - 180, (h - tela.height()) // 2
    for k in range(40, 0, -4):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 5))
        p.drawRoundedRect(QRectF(x - k, y - k + 20, tela.width() + 2 * k, tela.height() + 2 * k), 30 + k, 30 + k)
    caminho = QPainterPath()
    caminho.addRoundedRect(QRectF(x, y, tela.width(), tela.height()), 24, 24)
    p.setClipPath(caminho)
    p.drawImage(x, y, tela)
    p.end()
    salvar(img, "hero-16x9-3840x2160.png")


if __name__ == "__main__":
    janela = main()
    logotipos(SAIDA / "captura-03-destaques-por-prioridade.png")
    print("Pronto:", SAIDA)
    os._exit(0)  # encerra sem esperar tarefas de validação em segundo plano
