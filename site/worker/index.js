// Worker mínimo do site do NuPDF. Os arquivos estáticos de site/dist são
// servidos direto pelo Cloudflare (assets) antes de chegar aqui; este código
// só recebe o que não existe em dist/ e devolve a resposta padrão dos assets
// (404). Existe porque, com um "main", o wrangler sempre executa o build
// customizado definido em wrangler.jsonc (npm run build do Astro).
//
// /versao.json: repassa o versao.json publicado no R2 (arquivos.nukt.com.br) pelo
// próprio domínio do site - a página lê versão, data e tamanho sem depender de CORS
// no bucket.
const VERSAO_JSON = 'https://arquivos.nukt.com.br/atualizacoes/nupdf/versao.json';

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname === '/versao.json') {
      const r = await fetch(`${VERSAO_JSON}?t=${Date.now()}`, { cf: { cacheTtl: 0 } });
      return new Response(r.body, {
        status: r.status,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=300' },
      });
    }
    return env.ASSETS.fetch(request);
  },
};
