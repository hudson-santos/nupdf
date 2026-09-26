// Worker mínimo do site do NuPDF. Os arquivos estáticos de site/dist são
// servidos direto pelo Cloudflare (assets) antes de chegar aqui; este código
// só recebe o que não existe em dist/ e devolve a resposta padrão dos assets
// (404). Existe porque, com um "main", o wrangler sempre executa o build
// customizado definido em wrangler.jsonc (npm run build do Astro).
export default {
  async fetch(request, env) {
    return env.ASSETS.fetch(request);
  },
};
