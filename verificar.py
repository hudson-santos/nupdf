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
    campos = doc_d.listar_destaques()
    checar("listar campos destacados (cor e texto)", len(campos) == 1 and campos[0]["cor"] == "amarelo"
           and campos[0]["pagina"] == 0 and linha[0][4] in campos[0]["texto"], str(campos))
    salvo = _pm.open(stream=doc_d.bytes_editados({}), filetype="pdf")
    pg_salva = salvo[0]  # a página precisa continuar referenciada enquanto as anotações são lidas
    anots = [a.rect for a in pg_salva.annots() if a.type[1] == "Highlight"]
    checar("salvar com texto destacado", len(anots) == 1 and
           " ".join(w[4] for w in linha) in pg_salva.get_textbox(anots[0]).replace("\n", " "), str(anots))
    meio = _pm.Point((linha[0][0] + linha[0][2]) / 2, (linha[0][1] + linha[0][3]) / 2)
    xref = doc_d.destaque_em(0, meio)
    doc_d.remover_destaque(0, xref)
    checar("remover destaque da sessão", xref is not None and doc_d.destaque_em(0, meio) is None
           and not doc_d.destaques_pendentes and doc_d.bytes_editados({}) is doc_d.dados)
    doc_d.fechar()
    # destaque que já vinha no arquivo: reabre o PDF salvo e remove
    com_destaque = pasta / "com_destaque.pdf"
    com_destaque.write_bytes(salvo.tobytes())
    from nupdf.documento import CORES_DESTAQUE
    doc_c = Documento(str(com_destaque))
    xref_c = doc_c.destaque_em(0, meio)
    cor_antes = doc_c.cor_do_destaque(0, xref_c)
    doc_c.mudar_cor_destaque(0, xref_c, "vermelho")
    recolorido = _pm.open(stream=doc_c.bytes_editados({}), filetype="pdf")
    pg_rec = recolorido[0]
    an = pg_rec.load_annot(xref_c)
    checar("alterar cor de destaque salvo (Prioridade Alta)", cor_antes == "amarelo" and doc_c.destaques_pendentes
           and all(abs(a - b) < 0.01 for a, b in zip(an.colors["stroke"], CORES_DESTAQUE["vermelho"][1]))
           and an.info["content"] == "Prioridade Alta", f"{cor_antes} {an.colors} {an.info.get('content')}")
    doc_c.mudar_cor_destaque(0, xref_c, "amarelo")
    doc_c.destacar(0, [_pm.Rect(linha[0][:4])], "verde")
    novo = max(doc_c._destaques_novos)
    checar("destacar em verde (Resolvido)", doc_c.cor_do_destaque(0, novo) == "verde")
    doc_c.fechar()
    # Ctrl+Z: remover um destaque que já vinha no arquivo e desfazer
    doc_u = Documento(str(com_destaque))
    antes = doc_u.estado_edicao()
    doc_u.remover_destaque(0, doc_u.destaque_em(0, meio))
    removido = doc_u.destaque_em(0, meio) is None and doc_u.destaques_pendentes
    doc_u.restaurar_edicao(antes)
    checar("desfazer remoção de destaque do arquivo", removido and doc_u.destaque_em(0, meio) is not None
           and not doc_u.destaques_pendentes and doc_u.bytes_editados({}) is doc_u.dados)
    doc_u.fechar()
    doc_r = Documento(str(com_destaque))
    xref = doc_r.destaque_em(0, meio)
    doc_r.remover_destaque(0, xref)
    sem = _pm.open(stream=doc_r.bytes_editados({}), filetype="pdf")
    pg_sem = sem[0]
    checar("remover destaque salvo no arquivo", xref is not None and doc_r.destaques_pendentes
           and not list(pg_sem.annots(types=[_pm.PDF_ANNOT_HIGHLIGHT])))
    doc_r.fechar()

    movido = _pm.open(stream=doc.com_pagina_movida(0, 2, {}), filetype="pdf")
    textos = [doc.doc[i].get_text()[:30] for i in range(3)]
    checar("reordenar página (1ª vai para o fim)", movido.page_count == 3
           and [movido[i].get_text()[:30] for i in range(3)] == [textos[1], textos[2], textos[0]])
    sem2 = _pm.open(stream=doc.sem_pagina(1, {2: 90}), filetype="pdf")
    doc_sem = Documento(str(pdf), dados=sem2.tobytes(), pendencias=["páginas excluídas"])
    checar("excluir página (em memória)", sem2.page_count == 2 and sem2[1].rotation == 90
           and doc_sem.n_paginas == 2 and doc_sem.pendencias_herdadas == ["páginas excluídas"]
           and _pm.open(str(pdf)).page_count == 3)  # o arquivo em disco não muda
    doc_sem.marcar_salvo()
    checar("excluir página: salvar limpa a pendência", doc_sem.pendencias_herdadas == [])
    doc_sem.fechar()

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
    checar("pasta de desenvolvimento não se atualiza sozinha",
           atualizacao.instalado() == (Path(atualizacao.__file__).resolve().parents[1]
                                       == atualizacao.PASTA_INSTALACAO.resolve()))
    # atualização automática: instalador baixado em segundo plano -> instalado no próximo acesso
    orig = (atualizacao.PASTA_INSTALACAO, atualizacao.PASTA_PENDENTE, atualizacao.instalado,
            atualizacao.executar_instalador, atualizacao.baixar_instalador)
    executados, baixados = [], []
    try:
        base = Path(tempfile.mkdtemp())
        atualizacao.PASTA_INSTALACAO, atualizacao.PASTA_PENDENTE = base, base / "atualizacao"
        atualizacao.instalado = lambda: True
        atualizacao.executar_instalador = executados.append

        def falso_download(rel, destino=None, **_):
            baixados.append(rel.versao)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(b"MZ" + b"0" * 8)
            return destino

        atualizacao.baixar_instalador = falso_download
        nova = atualizacao.Release("999.0.0", "", "https://github.com/x", 10, "")
        (base / "atualizacao").mkdir()
        (base / "atualizacao" / "Instalador-0.0.1.exe").write_bytes(b"MZ")  # sobra de versão já instalada
        atualizacao.baixar_pendente(nova)
        atualizacao.baixar_pendente(nova)  # já baixado e íntegro: não baixa de novo
        checar("baixa a versão nova uma vez só", baixados == ["999.0.0"])
        pendente = atualizacao.atualizacao_pendente()
        checar("encontra a atualização pendente (e apaga sobras)",
               pendente is not None and pendente.name == "Instalador-999.0.0.exe"
               and not (base / "atualizacao" / "Instalador-0.0.1.exe").exists())
        checar("instala a pendente uma vez só (sai da fila)",
               atualizacao.instalar_pendente(pendente) and executados == [base / "Instalador.exe"]
               and atualizacao.atualizacao_pendente() is None)
    finally:
        (atualizacao.PASTA_INSTALACAO, atualizacao.PASTA_PENDENTE, atualizacao.instalado,
         atualizacao.executar_instalador, atualizacao.baixar_instalador) = orig

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
        res = validar(duas, buscar_na_internet=False)
        checar("2 assinaturas encontradas", len(res) == 2, str(len(res)))
        checar("assinaturas íntegras", all(r.integra for r in res), str([r.observacao for r in res]))
        checar("titular na validação", res[0].titular == "FULANO DE TESTE")
        checar("1ª assinatura continua cobrindo (incremental)", res[0].cobre_documento, res[0].observacao)
        checar("autoassinado não confiável", not res[0].confiavel)
        # PDF com a tabela xref quebrada (objetos deslocados): o pyHanko recusa, o NuPDF
        # reconstrói a estrutura e assina (o conteúdo das páginas não muda)
        k = doc.dados.find(b" 0 obj", len(doc.dados) // 3)
        quebrado = doc.dados[:k] + b"\n%" + b"x" * 60 + b"\n" + doc.dados[k:]
        try:
            checar("PDF quebrado sem assinatura: validação sem erro", validar(quebrado, buscar_na_internet=False) == [])
        except Exception as e:
            checar("PDF quebrado sem assinatura: validação sem erro", False, str(e))
        try:
            ok_quebrado = assinar_pdf(quebrado, ConfigAssinatura(info, impressao="TESTE", der=b"x",
                                                                 visivel=False))
            res_q = validar(ok_quebrado, buscar_na_internet=False)
            checar("assinar PDF com estrutura quebrada (reconstruída)", len(res_q) == 1 and res_q[0].integra)
        except Exception as e:
            checar("assinar PDF com estrutura quebrada (reconstruída)", False, str(e))
        # PDF com metadados XMP malformados: o pyHanko falha ao atualizar o XMP; o
        # NuPDF troca o XMP por um novo na própria revisão da assinatura
        import pymupdf as _pm
        _d = _pm.open(stream=doc.dados, filetype="pdf")
        _d.set_xml_metadata('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><quebrado')
        xmp_quebrado = _d.tobytes()
        _d.close()
        try:
            ok_xmp = assinar_pdf(xmp_quebrado, ConfigAssinatura(info, impressao="TESTE", der=b"x", visivel=False))
            res_x = validar(ok_xmp, buscar_na_internet=False)
            checar("assinar PDF com metadados XMP malformados", len(res_x) == 1 and res_x[0].integra)
        except Exception as e:
            checar("assinar PDF com metadados XMP malformados", False, str(e))
        # "Confiar neste Certificado": grava o topo da cadeia e a assinatura passa a ser confiável
        from nupdf.assinatura import validador as _val
        checar("oferece 'Confiar neste Certificado'", res[0].topo_cadeia_der is not None, res[0].topo_cadeia_nome)
        _val.confiar(res[0].topo_cadeia_der)
        res_t = validar(duas, buscar_na_internet=False)
        checar("confiar na cadeia torna a assinatura confiável", all(r.confiavel for r in res_t),
               str([r.observacao for r in res_t]))
        # pacote ICP-Brasil: raiz (autoassinada) vira âncora, AC intermediária não
        import datetime as _dt
        from cryptography.hazmat.primitives import hashes as _h
        from cryptography.hazmat.primitives.asymmetric import ec as _ec
        from cryptography.hazmat.primitives.serialization import Encoding as _Enc

        def _cert(cn, emissor_cn, chave_emissor, chave):
            agora = _dt.datetime.now(_dt.timezone.utc)
            nome = lambda n: x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, n)])
            return (x509.CertificateBuilder().subject_name(nome(cn)).issuer_name(nome(emissor_cn))
                    .public_key(chave.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(agora).not_valid_after(agora + _dt.timedelta(days=30))
                    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                    .sign(chave_emissor, _h.SHA256()))
        from cryptography import x509
        k_raiz, k_ac = _ec.generate_private_key(_ec.SECP256R1()), _ec.generate_private_key(_ec.SECP256R1())
        pasta_icp = _val.pastas_cadeias()[0] / "icp-brasil"
        pasta_icp.mkdir(parents=True, exist_ok=True)
        (pasta_icp / "raiz.crt").write_bytes(_cert("Raiz Teste", "Raiz Teste", k_raiz, k_raiz).public_bytes(_Enc.DER))
        (pasta_icp / "ac.crt").write_bytes(_cert("AC Teste", "Raiz Teste", k_raiz, k_ac).public_bytes(_Enc.PEM))
        raizes, inter = _val._carregar_cadeias()
        nomes = lambda cs: {c.subject.native.get("common_name") for c in cs}
        checar("cadeia ICP: raiz é âncora e AC é intermediária",
               "Raiz Teste" in nomes(raizes) and "AC Teste" in nomes(inter) and "AC Teste" not in nomes(raizes))
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
            res_c = validar(bytes(corrompido), buscar_na_internet=False)
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
