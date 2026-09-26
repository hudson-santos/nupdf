# Changelog

## [0.2.0] - 2026-09-25

### Added
- Arquivos recentes da tela inicial podem ser removidos individualmente (ícone de lixeira
  ao passar o mouse ou botão direito → "Remover da lista") ou todos de uma vez
  ("Limpar tudo"). Só a lista é limpa; os arquivos não são apagados.
- Página de apresentação do NuPDF em Astro (pasta `site/`), estática e compatível com o
  Cloudflare Pages, com botão de download do `Instalador.exe` da última release e link
  para o repositório no GitHub.

### Changed
- A janela abre maximizada por padrão.
- Novo ícone do aplicativo, sem a letra "N": folha com traço de assinatura, em várias
  resoluções (16 a 256 px) no `nupdf.ico`.
- Fonte da interface trocada para Google Sans, embutida em `assets/fonts` (com Segoe UI
  como alternativa).
- Botão "Assinar" renomeado para "Assinar com Certificado Digital".
- Textos da tela inicial: subtítulo "Leia PDFs, Copie Dados e Assine Digitalmente com
  Certificado ICP-Brasil" e instrução de arrastar em duas linhas ("ou" / "Arraste um
  Arquivo para esta Janela").

### Fixed
- Botão de fechar da aba e botão "+" alinhados verticalmente com o nome do documento.
- Itens removidos da lista de recentes e do painel de assinaturas não ficam mais
  desenhados por cima do cartão até serem descartados.
- Dados pessoais reais nos testes (`verificar.py`) e em um comentário de `nupdf/dados.py`
  substituídos por dados fictícios.

## [0.1.0] - 2026-09-25

### Added
- Leitor de PDF com abas, renderização sob demanda (PyMuPDF), zoom (Ctrl+roda, 25%–500%),
  ajuste à largura/página, rotação da visualização, modo mão e navegação por página.
- Seleção de texto em ordem visual (arrastar, duplo clique = palavra, triplo = linha,
  Alt+arrastar = seleção retangular), Ctrl+C/Ctrl+A e menu de contexto.
- Busca no documento (Ctrl+F) com destaque de todas as ocorrências.
- Painel "Dados do documento": detecta pares "Rótulo: valor", CPF, CNPJ (inclusive
  alfanumérico), datas, valores, e-mails, telefones, CEP, chave de acesso NF-e e linha
  digitável — um clique copia.
- Assinatura digital PAdES (SHA-256) com certificado ICP-Brasil A1 (.pfx) ou A3
  (token/cartão via PKCS#11), visível (posicionada na página) ou invisível, com carimbo
  de tempo opcional. Atualização incremental preserva assinaturas anteriores.
- Painel de assinaturas com validação de integridade, cobertura e cadeia de confiança.
- Miniaturas, arquivos recentes, arrastar e soltar, impressão, tema claro/escuro.
- Instância única: PDFs abertos pelo Explorer com o NuPDF já aberto viram abas novas.
- Instalador (Inno Setup + instalar.ps1, mesmo modelo do Zeebs): instala em C:\NuPDF
  sem pedir administrador, cria atalhos na Área de Trabalho e no Menu Iniciar, compila o
  launcher NuPDF.exe e registra o NuPDF em "Abrir com" para arquivos .pdf.
