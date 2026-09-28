"""Verificação de integridade do NuPDF.

Uso:  venv\\Scripts\\python.exe verificar.py

Gera um PDF e um certificado A1 de teste (autoassinado, formato ICP-Brasil),
assina (visível e invisível), valida, extrai dados e abre a interface em modo
offscreen para exercitar o visualizador. Nada é gravado fora de uma pasta
temporária.
"""

import os
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# configurações isoladas: não mexe nos recentes/tema do usuário
_APPDATA_TESTE = tempfile.mkdtemp(prefix="nupdf_cfg_")
os.environ["APPDATA"] = _APPDATA_TESTE
sys.path.insert(0, str(Path(__file__).parent))

falhas: list[str] = []
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import logging
logging.disable(logging.CRITICAL)


def checar(nome: str, cond: bool, detalhe: str = ""):
    print(f"  [{'OK' if cond else 'FALHOU'}] {nome}{(' - ' + detalhe) if detalhe and not cond else ''}")
    if not cond:
        falhas.append(nome)


def gerar_pfx(pasta: Path, senha: str) -> Path:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
        x509.NameAttribute(NameOID.COMMON_NAME, "FULANO DE TESTE:12345678909"),
    ])
    agora = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(nome).issuer_name(nome)
        .public_key(chave.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1)).not_valid_after(agora + timedelta(days=365))
        .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
        .sign(chave, hashes.SHA256())
    )
    caminho = pasta / "teste.pfx"
    caminho.write_bytes(pkcs12.serialize_key_and_certificates(
        b"teste", chave, cert, None, serialization.BestAvailableEncryption(senha.encode())))
    return caminho


def gerar_pdf(pasta: Path) -> Path:
    import pymupdf
    doc = pymupdf.open()
    for n in range(3):
        pg = doc.new_page()
        pg.insert_text((72, 80), "CERTIDÃO NEGATIVA DE DÉBITOS", fontsize=14)
        pg.insert_text((72, 120), "Proprietário:", fontsize=11)
        pg.insert_text((150, 120), "FULANO DE TAL", fontsize=11)
        pg.insert_text((72, 140), "CPF:", fontsize=11)
        pg.insert_text((150, 140), "123.456.789-09", fontsize=11)
        pg.insert_text((72, 160), "CNPJ: 11.222.333/0001-81   Valor: R$ 1.234,56", fontsize=11)
        pg.insert_text((72, 180), f"Data Emissão: 09/09/2026   Página {n + 1}", fontsize=11)
    caminho = pasta / "teste.pdf"
    doc.save(caminho)
    return caminho


def main() -> int:
    import compileall
    print("Compilação:")
    checar("compileall nupdf/", compileall.compile_dir(str(Path(__file__).parent / "nupdf"), quiet=1))

    pasta = Path(tempfile.mkdtemp(prefix="nupdf_"))
    pdf = gerar_pdf(pasta)
    pfx = gerar_pfx(pasta, "1234")

    print("Documento / propriedades:")
    from nupdf.documento import Documento
    from nupdf import paineis
    doc = Documento(str(pdf))
    checar("3 páginas", doc.n_paginas == 3)
    checar("texto em ordem visual", "Proprietário: FULANO DE TAL" in doc.texto_pagina(0), doc.texto_pagina(0))
    checar("nome sem extensão", doc.nome == "teste")
    checar("data do PDF formatada", paineis._data_pdf("D:20260928103000-03'00'") == "28/09/2026 10:30")
    checar("tamanho da página A4", paineis._formato_pagina(595, 842).startswith("A4 (retrato)"))
    import pymupdf as _pm
    girado = _pm.open(stream=doc.bytes_editados({1: 90, 2: 270}), filetype="pdf")
    checar("salvar com páginas giradas", [pg.rotation for pg in girado] == [0, 90, 270]
           and doc.bytes_editados({}) is doc.dados)
    doc_d = Documento(str(pdf))
    linha = doc_d.linhas(0)[0]
    doc_d.destacar(0, [_pm.Rect(linha[0][:4]) | _pm.Rect(linha[-1][:4])])
    salvo = _pm.open(stream=doc_d.bytes_editados({}), filetype="pdf")
    pg_salva = salvo[0]  # a página precisa continuar referenciada enquanto as anotações são lidas
    anots = [a.rect for a in pg_salva.annots() if a.type[1] == "Highlight"]
    checar("salvar com texto destacado", len(anots) == 1 and
           " ".join(w[4] for w in linha) in pg_salva.get_textbox(anots[0]).replace("\n", " "), str(anots))
    doc_d.fechar()

    print("Impressão:")
    from nupdf import impressao
    checar("intervalo de páginas", impressao.interpretar_intervalo("1-3, 5", 5) == [0, 1, 2, 4])
    try:
        impressao.interpretar_intervalo("2-9", 5)
        checar("intervalo inválido rejeitado", False)
    except ValueError:
        checar("intervalo inválido rejeitado", True)

    print("Atualização:")
    from nupdf import atualizacao
    checar("compara versões (semver)", atualizacao.eh_mais_nova("0.10.0", "0.9.9")
           and not atualizacao.eh_mais_nova("0.2.1", "0.2.1") and not atualizacao.eh_mais_nova("0.2.0", "0.2.1"))

    print("Leitor de PDF padrão:")
    from nupdf import leitor_padrao
    padrao = leitor_padrao.e_padrao()
    checar("consulta a associação efetiva de .pdf", padrao in (True, False) if sys.platform == "win32" else padrao is None,
           f"{padrao} ({leitor_padrao.leitor_atual() or 'nenhum'})")

    print("Certificado / assinatura:")
    from nupdf.assinatura.certificado import ErroCertificado, carregar_pfx
    from nupdf.assinatura.assinador import ConfigAssinatura, assinar_pdf
    from nupdf.assinatura.validador import validar
    try:
        carregar_pfx(str(pfx), "errada")
        checar("senha errada rejeitada", False)
    except ErroCertificado:
        checar("senha errada rejeitada", True)
    info = carregar_pfx(str(pfx), "1234")
    checar("titular/CPF lidos do CN ICP", info.titular == "FULANO DE TESTE" and info.documento == "123.456.789-09",
           info.resumo())

    try:
        # o app assina com certificados do Windows; aqui o certificado de teste é
        # passado direto ao pyHanko para não mexer no repositório do usuário
        from pyhanko.sign import signers as hk_signers
        teste = hk_signers.SimpleSigner.load_pkcs12(str(pfx), passphrase=b"1234")
        from nupdf.assinatura import windows as win
        win.assinante_pyhanko = lambda impressao, der: teste
        certs_win = win.listar_certificados()
        checar("leitura dos certificados do Windows", isinstance(certs_win, list))
        cfg = ConfigAssinatura(info, impressao="TESTE", der=b"x", motivo="Teste", local="Rio Verde - GO",
                               visivel=True, pagina=0, caixa=(350, 650, 560, 720))
        assinado = assinar_pdf(doc.dados, cfg)
        cfg2 = ConfigAssinatura(info, impressao="TESTE", der=b"x", visivel=False)
        duas = assinar_pdf(assinado, cfg2)
        (pasta / "assinado.pdf").write_bytes(duas)
        res = validar(duas)
        checar("2 assinaturas encontradas", len(res) == 2, str(len(res)))
        checar("assinaturas íntegras", all(r.integra for r in res), str([r.observacao for r in res]))
        checar("titular na validação", res[0].titular == "FULANO DE TESTE")
        checar("1ª assinatura continua cobrindo (incremental)", res[0].cobre_documento, res[0].observacao)
        checar("autoassinado não confiável", not res[0].confiavel)
        import pymupdf
        d2 = pymupdf.open(stream=duas, filetype="pdf")
        widgets = [w for w in d2[0].widgets() if w.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE]
        checar("campo visível na página 1", len(widgets) >= 1)
        links = [l for l in d2[0].get_links() if l.get("uri") == "https://validar.iti.gov.br"]
        from nupdf.documento import Documento as _Doc
        vis = _Doc(str(pasta / "assinado.pdf")).assinaturas_visiveis(0)
        checar("assinatura visível clicável (abre o painel)", len(vis) == 1 and vis[0][1] == res[0].campo, str(vis))
        checar("link validar.iti.gov.br dentro do carimbo", len(links) == 1
               and widgets[0].rect.contains(links[0]["from"]), str(links))
        # adulteração: troca um byte dentro do conteúdo assinado
        corrompido = bytearray(duas)
        k = duas.find(b"stream") + 20
        corrompido[k] = (corrompido[k] + 1) % 256
        try:
            res_c = validar(bytes(corrompido))
            detectou = not res_c or not all(r.integra for r in res_c)
        except Exception:
            detectou = True
        checar("adulteração detectada", detectou)
    except Exception:
        traceback.print_exc()
        checar("assinatura", False)

    print("Interface (offscreen):")
    try:
        from PySide6.QtCore import QPointF
        from PySide6.QtWidgets import QApplication
        from nupdf.janela import JanelaPrincipal
        app = QApplication.instance() or QApplication([])
        jan = JanelaPrincipal()
        jan.resize(1280, 800)
        jan.show()
        jan.abrir_arquivo(str(pasta / "assinado.pdf"))
        app.processEvents()
        aba = jan.aba_atual()
        checar("aba aberta", aba is not None)
        v = aba.visualizador
        v.definir_zoom(1.5)
        v.girar()
        v.girar()
        v.girar()
        v.girar()
        app.processEvents()
        v._pag.grab()  # força pintura
        checar("busca (texto + carimbo)", v.buscar("CPF") == 4)
        v.selecionar_tudo()
        checar("selecionar tudo + copiar", "123.456.789-09" in v.texto_selecionado())
        ini = v._ponto_tela(0, __import__("pymupdf").Point(73, 116))
        fim = v._ponto_tela(0, __import__("pymupdf").Point(300, 136))
        v.sel_ini, v.sel_fim = v._palavra_em(ini), v._palavra_em(fim)
        checar("seleção por arraste", v.texto_selecionado().startswith("Proprietário:"), v.texto_selecionado())
        v.ir_para_pagina(2)
        checar("navegação", v.pagina_atual == 2)
        aba.mostrar_painel("dados")
        aba.mostrar_painel("assinaturas")
        aba.mostrar_painel("miniaturas")
        for _ in range(50):
            app.processEvents()
        jan.alternar_tema()
        jan.fechar_aba(0)
        # recentes: remover um e limpar todos (só a lista - os arquivos continuam lá)
        ini = jan.inicio
        antes = len(jan.config.recentes())
        ini.remover(jan.config.recentes()[0])
        checar("remover um recente", len(jan.config.recentes()) == antes - 1 and (pasta / "assinado.pdf").exists())
        jan.abrir_arquivo(str(pdf)); jan.fechar_aba(0)
        ini.limpar_tudo()
        checar("limpar todos os recentes", jan.config.recentes() == [] and not ini.cab_recentes.isVisibleTo(ini))
        checar("fechar aba", jan.aba_atual() is None)

        # fluxo completo: posicionar o retângulo na tela -> assinar -> reabrir (inclui página com /Rotate)
        import pymupdf
        from PySide6.QtWidgets import QFileDialog
        drot = pymupdf.open(str(pdf))
        drot[1].set_rotation(90)
        drot.save(str(pasta / "rot.pdf"))
        for nome_pdf, pagina in (("teste.pdf", 0), ("rot.pdf", 1)):
            aba = jan.abrir_arquivo(str(pasta / nome_pdf))
            app.processEvents()
            # retângulo como o usuário vê na tela (espaço visual) -> espaço não rotacionado
            visual = pymupdf.Rect(320, 100, 530, 160)
            alvo = (visual * aba.doc.doc[pagina].derotation_matrix).normalize()
            destino = pasta / f"gui_{nome_pdf}"
            QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(destino), ""))
            cfg = ConfigAssinatura(info, impressao="TESTE", der=b"x", visivel=True)
            aba.cfg_pendente = cfg
            aba.visualizador.iniciar_posicionamento()
            aba.visualizador.retanguloDesenhado.emit(pagina, alvo)
            import time
            t0 = time.time()
            while not destino.exists() and time.time() - t0 < 20:
                app.processEvents()
            for _ in range(20):
                app.processEvents()
            ok = destino.exists()
            if ok:
                dd = pymupdf.open(str(destino))
                ws = [w for w in dd[pagina].widgets() if w.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE]
                r = pymupdf.Rect(ws[0].rect) if ws else None
                ok = r is not None and abs(r.x0 - alvo.x0) < 2 and abs(r.y0 - alvo.y0) < 2 and abs(r.x1 - alvo.x1) < 2
            checar(f"assinatura via interface na posição certa ({nome_pdf})", ok, str(r if destino.exists() else "sem arquivo"))
            if destino.exists():
                dd[pagina].get_pixmap(dpi=110).save(str(pasta / f"gui_{nome_pdf}.png"))
            checar(f"aba reaberta com painel de assinaturas ({nome_pdf})",
                   jan.aba_atual() is not None and jan.aba_atual().painel == "assinaturas")
        jan.close()
    except Exception:
        traceback.print_exc()
        checar("interface", False)

    import shutil
    shutil.rmtree(_APPDATA_TESTE, ignore_errors=True)
    if not falhas:
        shutil.rmtree(pasta, ignore_errors=True)
    print()
    if falhas:
        print(f"FALHAS: {len(falhas)} -> {', '.join(falhas)}")
        return 1
    print("Tudo certo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
