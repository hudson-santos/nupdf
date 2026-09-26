# Changelog

## [1.1.1] - 2026-09-26

### Changed
- Site de apresentação: card "Copie com um clique" descreve o botão "Copiar" que aparece ao
  selecionar texto no PDF.

## [1.1.0] - 2026-09-26

### Added
- Botão "Copiar" que aparece junto do texto ao selecioná-lo no PDF (arrastar, duplo ou
  triplo clique, seleção retangular): um clique copia o texto e mostra "Texto copiado".
  Some ao clicar fora, iniciar outra seleção ou pressionar Esc; não aparece no Ctrl+A.
- Site de apresentação: alternância de tema claro/escuro no topo, com o claro como padrão
  (a escolha fica salva no navegador).

### Changed
- Site de apresentação: todo o conteúdo visível em uma tela de computador, sem rolagem
  (1366×768 e 1280×720).

## [1.0.1] - 2026-09-26

### Changed
- Janela "Sobre": descrição "Leia PDFs, Copie Dados e Assine Digitalmente com Certificado
  ICP-Brasil." em uma única linha (janela mais larga).
- Painel "Assinaturas Digitais": texto "Documento sem Assinatura Digital." e sem o botão
  "Assinar documento" no rodapé (a ação fica no botão "Assinar com Certificado Digital" da
  barra de ferramentas).

## [1.0.0] - 2026-09-26

### Added
- Assinatura com os certificados digitais instalados no Windows (repositório Pessoal): o
  formulário mostra uma lista com busca por nome ou CPF/CNPJ (vencidos ocultos) e lembra o
  último certificado usado. A chave privada não sai do Windows, que pede a senha/PIN quando
  o certificado é protegido; a cadeia de certificação é embutida na assinatura.
- Painel "Propriedades do Documento": metadados do PDF (nome, tamanho, páginas, tamanho da
  página, versão, título, autor, assunto, palavras-chave, aplicativo de criação, gerador,
  datas de criação e modificação e proteção).

### Changed
- Menu lateral (Páginas, Propriedades e Assinaturas) só aparece com documento aberto.
- Nome do documento sem a extensão ".pdf" no título da janela, na aba, nos recentes, no
  pedido de senha e na fila de impressão; título da janela no formato
  "NuPDF - Versão: X.Y.Z - nome do documento".
- Painel de páginas: título "Páginas" sem caixa-alta e centralizado sobre as miniaturas,
  painel mais estreito e sem barra de rolagem horizontal.
- Títulos e dicas "Propriedades do Documento" e "Assinaturas Digitais" no mesmo padrão.
- "Limpar tudo" passa a "Limpar Tudo"; botão OK da janela "Sobre" na cor de destaque.
- Site de apresentação com os textos atualizados (cópia de texto e assinatura com
  certificado do Windows).

### Removed
- Assinatura por arquivo de certificado (.pfx/.p12) com senha, substituída pela lista de
  certificados do Windows.
- Assinatura com token/cartão A3 via PKCS#11 (biblioteca `python-pkcs11`).
- Detecção automática de dados para copiar (CPF, CNPJ, datas, valores e campos
  "Rótulo: valor"), substituída pelo painel de propriedades.

### Fixed
- Janela "Verificar Atualizações" recentralizada sobre o NuPDF ao crescer.
- Botão de fechar da aba afastado da borda direita.

## [0.3.2] - 2026-09-26

### Changed
- Janela "Verificar Atualizações": um único botão centralizado ("Atualizar", trocado por
  "Cancelar" durante o download), sem o "Fechar" no rodapé.
- Novidades da atualização com espaçamento após os títulos (Novidades, Alterações,
  Correções) e entre os itens.

### Fixed
- A área de novidades da janela de atualização cresce conforme o conteúdo, sem ocultar
  itens (barra de rolagem só em notas muito longas).
- Endereços e trechos de código nas novidades apareciam vazios.

## [0.3.1] - 2026-09-26

### Changed
- Barra de ferramentas (salvar, imprimir, seleção, mão, ajustes de zoom, girar, buscar e
  "Assinar com Certificado Digital") só aparece com documento aberto; sem documento a
  tela inicial ocupa a janela inteira.
- Botão "Abrir" removido da barra de ferramentas: a abertura é feita pelo botão central
  "Abrir PDF", pelo "+" das abas, por Ctrl+O ou arrastando o arquivo.
- Botão "+" das abas só aparece quando há um ou mais documentos abertos.
- Arquivos recentes mostram só o nome do arquivo (nomes longos são abreviados); ao passar
  o mouse aparece, ao lado da lixeira, um botão de pasta que abre o Explorer com o arquivo
  selecionado (também no menu do botão direito).
- Janela "Verificar Atualizações": sem o botão "Fechar" no rodapé quando ele seria o único
  botão (a janela fecha pelo X ou Esc).
- Site de apresentação: tag do Google Analytics adicionada.

## [0.3.0] - 2026-09-26

### Added
- Botão "Verificar atualizações" na barra do topo (à esquerda do botão de tema): consulta
  a última release no GitHub e, se houver versão mais nova, mostra a versão, o tamanho e
  as novidades. "Atualizar" baixa o `Instalador.exe` para `C:\NuPDF` com barra de
  progresso (cancelável), confere o arquivo, executa a instalação em modo silencioso e
  fecha o NuPDF, que é reaberto automaticamente ao final.
- Verificação discreta ao abrir o NuPDF: se existir versão nova, o ícone do botão fica
  destacado, sem abrir janela.

### Changed
- Site de apresentação: removida a seção com a captura de tela do aplicativo.

## [0.2.1] - 2026-09-26

### Changed
- Site de apresentação publicado em https://nupdf.com.br (Cloudflare Workers com
  arquivos estáticos, configurado pelo `wrangler.jsonc` da raiz), com o título "NuPDF -
  Leitor de PDF Leve com Assinatura Digital ICP-Brasil" e sem barra de rolagem visível.

### Fixed
- Tela inicial: espaçamento entre "ou" e "Arraste um Arquivo para esta Janela" igual ao
  espaçamento entre o botão "Abrir PDF" e o "ou".

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
