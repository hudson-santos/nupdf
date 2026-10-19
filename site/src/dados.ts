// O download aponta para "releases/latest/download/Instalador.exe": o GitHub
// redireciona sempre para o Instalador.exe da release mais recente (gerado pelo
// workflow .github/workflows/versao.yml), sem precisar republicar o site. A
// página ainda busca a versão/tamanho da última release (ver pages/index.astro).
export const REPO = 'https://github.com/hudson-santos/nupdf';
export const DOWNLOAD = `${REPO}/releases/latest/download/Instalador.exe`;
export const API_RELEASE = 'https://api.github.com/repos/hudson-santos/nupdf/releases/latest';
