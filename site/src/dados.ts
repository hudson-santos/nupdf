// O download aponta para o Instalador.exe da última versão no Cloudflare R2
// (publicado pelo instalador\publicar.ps1 a cada versão), sem precisar republicar
// o site. A página ainda busca versão/data/tamanho no versao.json, repassado pelo
// worker do site em /versao.json (ver worker/index.js e pages/index.astro).
export const REPO = 'https://github.com/hudson-santos/nupdf';
export const DOWNLOAD = 'https://arquivos.nukt.com.br/atualizacoes/nupdf/Instalador.exe';
export const VERSAO_JSON = '/versao.json';
