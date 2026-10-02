# Changelog

## [1.13.3] - 2026-10-02

### Changed
- Tema claro passa a ser o padrão em instalações novas; quem já usava o NuPDF continua no
  tema em que estava.
- Leitor de PDF padrão no Windows 10: "Definir como Padrão" abre a janela do Windows "Como
  você deseja abrir este arquivo?" com o NuPDF e a opção "Sempre usar este aplicativo" -
  sem precisar procurar ".pdf" nas Configurações. Se não resolver, um segundo clique abre
  as Configurações. No Windows 11 o fluxo continua o mesmo.

## [1.13.2] - 2026-10-02

### Changed
- Painel de assinaturas: spinner laranja centralizado no painel enquanto as assinaturas
  digitais são verificadas (também ao atualizar a cadeia ou confiar em um certificado).

## [1.13.1] - 2026-10-02

### Changed
- Painel de assinaturas: o link "Confiar nesta Cadeia" passou a se chamar "Confiar neste
  Certificado" (também no título da confirmação) e não fica mais sublinhado ao passar o mouse.

## [1.13.0] - 2026-10-02

### Added
- Atualização automática silenciosa: ao encontrar uma versão nova (verificação diária), o
  NuPDF baixa o instalador em segundo plano e, no próximo acesso, instala sozinho (só a
  janela de progresso, sem perguntas) e reabre já atualizado - inclusive com o PDF que foi
  aberto naquele acesso. O aviso "Nova Versão Disponível - Atualizar" continua e, com o
  download pronto, instala na hora. Só a cópia instalada em C:\NuPDF se atualiza sozinha.

## [1.12.7] - 2026-10-01

### Changed
- Abertura mais rápida do aplicativo: a fonte do tema é resolvida sem varrer todas as fontes
  instaladas no Windows, e o PyMuPDF e a aba de documento são carregados logo após a janela
  aparecer (PDF aberto pelo Explorer entra depois do primeiro desenho da janela).
- Instalador pré-compila o código do NuPDF: a primeira abertura após instalar/atualizar não
  compila mais tudo na hora.

### Fixed
- Atraso na abertura em máquinas com arquivos recentes em pastas de rede (servidor lento ou
  fora do ar): caminhos de rede da lista de recentes são conferidos em segundo plano.

## [1.12.6] - 2026-10-01

### Changed
- Menu do botão Girar da barra: em documento de uma página só mostra apenas "Girar Página"
  (sem "Girar Todas as Páginas"), como nos menus do botão direito; o menu se ajusta ao
  trocar de aba, excluir ou reordenar páginas.

## [1.12.5] - 2026-10-01

### Changed
- Barras de rolagem mais visíveis em todo o app (documento, miniaturas e painéis): alça com
  cor própria que se destaca do fundo nos temas claro e escuro, mais larga, mais escura ao
  passar o mouse ou arrastar, e com tamanho mínimo maior em documentos com muitas páginas.

## [1.12.4] - 2026-10-01

### Changed
- Documento de uma página só: as opções que não se aplicam somem em vez de aparecer
  desabilitadas - sem os botões Subir, Descer e Excluir na miniatura, sem "Excluir Página" e
  "Girar Todas as Páginas" nos menus do botão direito, e "Girar Página" sem o número.

### Fixed
- Notas das Releases no GitHub com quebras de linha no meio dos itens: o workflow junta as
  linhas de continuação do CHANGELOG antes de publicar.

## [1.12.3] - 2026-09-30

### Fixed
- Botões redondos de ações (Subir, Descer, Girar e Excluir nas miniaturas e a lixeira dos
  Marcadores) com um leve corte no topo da borda: agora são desenhados como círculos
  perfeitos, com antialiasing, mantendo as cores, o realce ao passar o mouse e o estado
  desabilitado.

## [1.12.2] - 2026-09-30

### Changed
- Painel "Páginas": em PDF de uma página só, a miniatura não mostra os botões Subir e Descer
  (nem "Mover Página para Cima/Baixo" no botão direito) - ficam Girar e Excluir.

## [1.12.1] - 2026-09-30

### Changed
- "Atualizar Cadeia ICP-Brasil": o botão mantém a cor vermelha durante o download (antes
  ficava cinza), mostra "Baixando a Cadeia ICP-Brasil" e ignora cliques repetidos até terminar.

## [1.12.0] - 2026-09-30

### Added
- Reordenar páginas no painel "Páginas": botões Subir e Descer sobre a miniatura (com Girar
  e Excluir), "Mover Página para Cima/Baixo" no botão direito e arrastar a miniatura com o
  mouse (uma linha vermelha mostra onde a página vai entrar). Fica em memória até salvar,
  entra na confirmação ao fechar ("páginas reordenadas"), tem desfazer (Ctrl+Z) e é
  bloqueado em documentos assinados.

### Changed
- Painéis laterais com separador abaixo do título (Páginas, Propriedades, Assinaturas e
  Marcadores) e, em Marcadores, também entre os grupos de cor.
- Marcadores sem o total de marcadores; Assinaturas Digitais sem "Verificando assinaturas…",
  sem a contagem e sem "Documento sem Assinatura Digital.".
- "Atualizar Cadeia ICP-Brasil" só aparece quando o PDF tem assinatura digital, no mesmo
  visual do botão "Assinar com Certificado Digital".
- Botões redondos das miniaturas e da lixeira dos marcadores sem cortes nas bordas.

### Fixed
- PDF com estrutura malformada e sem assinatura mostrava "Não foi possível verificar: Parse
  error..." no painel de assinaturas; agora a verificação só roda quando há campo de assinatura.

## [1.11.5] - 2026-09-30

### Fixed
- Assinatura de PDFs com erro de estrutura (tabela de objetos/xref malformada, comum em PDFs
  gerados por sistemas de prefeituras): falhava com "Parse error on indirect object
  reference". O NuPDF agora reconstrói a estrutura do arquivo (sem mudar o conteúdo das
  páginas) e assina. Se o PDF já tiver assinaturas, não é alterado e a mensagem explica o
  motivo (a reconstrução as invalidaria).

## [1.11.4] - 2026-09-30

### Changed
- Painel "Marcadores": separador abaixo do título e sem o texto "Nenhum Marcador." quando o
  documento não tem marcadores (a contagem só aparece quando há algum).

## [1.11.3] - 2026-09-30

### Changed
- Marcadores: botão de remover com fundo vermelho e ícone branco, igual ao de excluir página
  nas miniaturas.

### Fixed
- Painéis laterais (Marcadores, Propriedades e Assinaturas): o estilo do contêiner da lista
  passava para os itens, apagando o fundo dos botões e deixando as dicas pretas; os cartões
  de marcadores voltam a mostrar o fundo previsto no tema.

## [1.11.2] - 2026-09-30

### Fixed
- Painel "Marcadores": passar o mouse sobre um marcador mostrava um card preto (a dica com o
  texto herdava o estilo do item). A dica foi removida - o item já exibe o texto, agora com
  até 160 caracteres - e a dica da lixeira usa o estilo normal do app.

## [1.11.1] - 2026-09-30

### Changed
- Painel "Campos Destacados" renomeado para "Marcadores" ("N Marcadores." / "Nenhum Marcador.").
- Remover marcador pela barra lateral: lixeira ao passar o mouse sobre o item, para os
  marcadores do NuPDF e também os criados em outros editores de PDF ("Outras Cores"); no
  documento, clicar no marcador continua mostrando "Alterar Cor" e "Remover Destaque".
  Tudo com desfazer (Ctrl+Z). A lista mantém a posição de rolagem ao atualizar.

## [1.11.0] - 2026-09-30

### Added
- Painel "Campos Destacados" no menu lateral (abaixo de Assinaturas Digitais): lista todos os
  destaques do documento agrupados por cor/prioridade (Vermelho - Alta, Amarelo - Média,
  Azul - Baixa, Verde - Resolvido e Outras Cores), com o texto destacado e a página. Clicar
  num item leva até ele na página, com um realce momentâneo. A lista acompanha as alterações
  (destacar, remover, mudar a cor e desfazer) e inclui os destaques que já vinham no PDF.

## [1.10.2] - 2026-09-30

### Added
- Pasta ms/ com as imagens da listagem na Microsoft Store: 6 capturas de tela (1920x1080)
  e os logotipos 1:1 (2160x2160), 2:3 (1440x2160) e 16:9 (3840x2160), gerados a partir do
  próprio NuPDF com documentos e certificado fictícios (ms/gerar_imagens.py refaz tudo;
  ms/README.md indica onde cada arquivo vai no Partner Center).

## [1.10.1] - 2026-09-29

### Changed
- Botão "Desfazer" na barra de ações do documento (ao lado de Girar), além do Ctrl+Z;
  fica desabilitado quando não há nada para desfazer.

## [1.10.0] - 2026-09-29

### Added
- Desfazer (Ctrl+Z): volta, passo a passo, destaques (incluir, remover - inclusive os que já
  vinham no PDF - e mudar a cor), giros de página (uma ou todas) e exclusão de página, que
  volta ao lugar com os destaques e giros que tinha. Histórico por aba (até 50 passos),
  mantendo página, zoom e painel; desfazer tudo zera as alterações pendentes. Sem nada a
  desfazer, aparece "Nada para Desfazer".

### Changed
- Instalador sem a pergunta inicial "Isto instalará... Deseja continuar?" (equivale ao
  /SP-). Instalação silenciosa na Microsoft Store: /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-.
  A atualização pelo botão do app também passa /SP-.

## [1.9.1] - 2026-09-29

### Changed
- Instalador pronto para instalação/desinstalação silenciosa (ex.: Microsoft Store):
  com /VERYSILENT /SUPPRESSMSGBOXES /NORESTART instala em segundo plano sem abrir o NuPDF
  no fim (o /SILENT da atualização pelo botão do app continua reabrindo o programa), e a
  desinstalação com /VERYSILENT remove tudo sem perguntas. O instalador passa a gravar um
  log em %TEMP% (Setup Log) para diagnóstico.

## [1.9.0] - 2026-09-29

### Added
- Cadeia oficial ICP-Brasil: o instalador baixa o pacote do ITI (raízes v5, v6, v10, v11 e
  v12 e todas as ACs credenciadas) para C:\NuPDF\cadeias\icp-brasil, e o painel de
  assinaturas ganhou "Atualizar Cadeia ICP-Brasil" para baixar de novo quando surgirem ACs
  novas. Sem internet na instalação, ela continua normalmente.
- AC intermediária que ainda faltar é buscada automaticamente pelo endereço indicado no
  próprio certificado (só para as assinaturas não reconhecidas).
- "Confiar nesta Cadeia" no cartão de uma assinatura não reconhecida (como o "Adicionar a
  certificados confiáveis" do Adobe), com confirmação.

### Changed
- Assinatura seguida de alterações permitidas pelo documento (outra assinatura, carimbo)
  continua válida, com a observação "Houve alterações permitidas depois desta assinatura",
  como no Adobe; só alterações não permitidas geram ressalva.
- Só as raízes do pacote ICP-Brasil são âncoras de confiança (as ACs servem apenas para
  montar o caminho).

## [1.8.0] - 2026-09-29

### Added
- Excluir página: pelo botão direito na página ("Excluir Página N") ou pela miniatura
  (botão vermelho de lixeira ao passar o mouse, ou botão direito), sempre com confirmação
  ("Excluir" / "Cancelar"). A exclusão fica só em memória até o "Salvar" (o arquivo não
  muda antes disso) e mantém giros e destaques já feitos. Bloqueada em documentos assinados
  e na última página.
- Girar página pela miniatura: botão cinza de girar ao passar o mouse (centralizado ao lado
  do de excluir) ou botão direito ("Girar Página N"). As miniaturas passam a mostrar a
  página girada como na tela.
- Confirmação ao fechar também quando há páginas giradas ou excluídas não salvas: a janela
  "Alterações Não Salvas" lista o que mudou (ex.: "páginas giradas e texto destacado").

### Changed
- Janela de alterações não salvas: "Não Salvar" em cinza escuro e "Cancelar" virou
  "Fechar" (vermelho), que fecha só a janela e mantém a aba aberta.

### Fixed
- Miniatura de página girada aparecia duplicada (desenho antigo sobreposto ao novo).

## [1.7.1] - 2026-09-28

### Changed
- Menu do botão direito: removidos "Selecionar tudo" (o Ctrl+A continua) e "Copiar texto
  da página N"; "Destacar" só aparece quando há texto selecionado; "Copiar" mostra o
  aviso "Texto Copiado", como o botão flutuante; "Girar página N" passou a "Girar Página N".

## [1.7.0] - 2026-09-28

### Added
- Cores do destaque por prioridade: Azul - Prioridade Baixa, Amarelo - Prioridade Média,
  Vermelho - Prioridade Alta e Verde - Resolvido. O "Destacar" usa a última cor escolhida
  (lembrada entre as sessões) e a seta ao lado abre as quatro cores; no botão direito,
  "Destacar" virou um submenu com as cores. A prioridade também fica gravada no PDF e
  aparece ao passar o mouse sobre o destaque em outros leitores (Adobe etc.).
- Clicar sobre um texto destacado mostra "Alterar Cor" e "Remover Destaque" (também no
  botão direito: "Alterar Cor do Destaque" e "Remover Destaque"). Vale para os destaques
  feitos no NuPDF e para os que já vinham no PDF; o "Salvar" grava a mudança.
- Confirmação ao fechar uma aba (ou o NuPDF) com destaques não salvos: "Salvar", "Não
  Salvar" ou "Cancelar". Em documentos assinados, onde os destaques não podem ser salvos,
  a escolha é "Fechar sem Salvar" ou "Cancelar".

## [1.6.0] - 2026-09-28

### Added
- Botão "Destacar" ao lado do "Copiar" quando há texto selecionado (e também no menu do
  botão direito, abaixo de "Copiar"): pinta o texto selecionado de amarelo, uma faixa por
  linha, inclusive em seleções de várias páginas, e mostra "Texto Destacado". O "Salvar"
  grava os destaques no PDF (anotações de marca-texto padrão, visíveis em qualquer leitor)
  e a impressão os inclui. Em documentos assinados dá para destacar, mas o "Salvar" fica
  desabilitado (salvar invalidaria as assinaturas).

### Changed
- Script do instalador renomeado para `criar_atalho_appid.ps1`.

## [1.5.0] - 2026-09-26

### Added
- Verificação automática de nova versão no máximo 1x por dia (conferida de hora em hora,
  inclusive com o NuPDF aberto por vários dias). Quando há versão nova, aparece no topo o
  aviso "Nova Versão X.Y.Z Disponível - Atualizar", no mesmo visual do aviso de leitor
  padrão; um clique já baixa e instala a atualização. O aviso continua visível ao reabrir o
  NuPDF e some quando a versão é instalada.

## [1.4.1] - 2026-09-26

### Fixed
- Instalação/atualização: o NuPDF só é aberto depois de o instalador concluir todas as
  etapas (ambiente, dependências, NuPDF.exe e atalhos); antes ele abria logo após a cópia
  dos arquivos, no meio da atualização.

## [1.4.0] - 2026-09-26

### Added
- Aviso "O NuPDF não é o Leitor de PDF Padrão" no topo da janela (ao lado de Verificar
  Atualizações) quando os PDFs abrem em outro programa. Ao clicar, a janela "Tornar o NuPDF
  o Leitor de PDF Padrão" mostra o leitor atual e o botão "Definir como Padrão", que abre a
  página do NuPDF em Configurações > Aplicativos > Aplicativos padrão do Windows (onde se
  clica em "Definir padrão" - o Windows não permite que um programa se torne padrão
  sozinho). O aviso some assim que o NuPDF passa a ser o padrão.
- Instalador registra o NuPDF em "Aplicativos padrão" das Configurações do Windows
  (removido na desinstalação).

## [1.3.0] - 2026-09-26

### Added
- Impressão própria, que não trava o NuPDF com impressoras de rede fora do ar: janela
  "Imprimir Documento" com impressora (a padrão indicada com "( Padrão )"), Todas / Página
  Atual / Intervalo (ex.: 1-3, 5) e número de cópias; o envio acontece em segundo plano,
  com progresso e opção de cancelar.
- Girar com duas opções (seta ao lado do botão Girar): "Girar Página Atual" (Ctrl+Shift+R)
  e "Girar Todas as Páginas" (Ctrl+R), também no menu de contexto. O "Salvar" grava a
  rotação no PDF; em documentos assinados a rotação é só de visualização e o "Salvar" fica
  desabilitado (salvar invalidaria as assinaturas).
- Assinatura visível com a logo ICP-Brasil entre a barra lateral e o texto, e o endereço
  "validar.iti.gov.br" clicável (link para https://validar.iti.gov.br - adicionado só na
  primeira assinatura do documento, para não afetar a validade das anteriores).
- Clicar numa assinatura visível na página abre o painel "Assinaturas Digitais" e destaca
  a assinatura correspondente, como no Adobe Reader.

### Changed
- Carimbo da assinatura: "Assinado Digitalmente por :", "Data/Hora:" e CPF exibido completo.
- Painel "Assinaturas Digitais": "N Assinatura(s) Encontrada(s)", sem o selo "Assinatura
  válida" (ressalvas e erros continuam destacados) e sem Motivo/Local.
- Diálogo "Assinar Documento": certificado escolhido só por clique na lista, com
  "Válido Até" no rótulo e separador " - "; status só aparece quando há problema;
  aparência "Visível ( Posicionar na Página )"; botão Cancelar em cinza escuro.
- Aviso ao posicionar a assinatura: "Clique ou Arraste na Página para Posicionar a
  Assinatura • ESC - Cancela".
- Confirmação de link externo: "Abrir Link Externo", "O Documento está Tentando Acessar :",
  "Deseja Continuar ?", botões "Sim" (laranja) e "Não" (cinza), sem ícone.
- Botões Cancelar/Fechar dos diálogos padronizados em cinza escuro; seleção em cinza nas
  listas e caixas de seleção; botões de opção e caixas de marcação no visual do app.
- Dicas dos botões com iniciais maiúsculas (ex.: "Página Anterior", "Aumentar Zoom") e
  seta do menu de zoom no mesmo padrão do Girar.
- "Limpar Tudo" dos arquivos recentes com a dica "Limpar a Lista de Arquivos Recentes
  ( os Arquivos não são Apagados )"; aviso "Texto Copiado".
- Instalação e atualização: ao terminar, o instalador fecha sozinho (sem a página final) e
  abre o NuPDF automaticamente.
- Removidos os botões "Mover página" e "Selecionar texto" da barra de ferramentas.

## [1.2.2] - 2026-09-26

### Changed
- Janela "Verificar Atualizações": sem o botão "Cancelar" durante o download (fechar a
  janela pelo X ou Esc continua cancelando).

## [1.2.1] - 2026-09-26

### Changed
- Programas e Recursos / Aplicativos instalados: nome exibido com a versão
  ("NuPDF 1.2.1"), no mesmo padrão dos demais programas, atualizado a cada instalação.

## [1.2.0] - 2026-09-26

### Added
- Desinstalador: o NuPDF aparece em "Aplicativos instalados" / "Programas e Recursos" do
  Windows, com nome, ícone, versão e editora. A desinstalação fecha o NuPDF aberto,
  remove os atalhos, o registro em "Abrir com" para .pdf e a pasta C:\NuPDF (inclusive o
  ambiente Python); as preferências do usuário em %APPDATA%\NuPDF são mantidas.

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
