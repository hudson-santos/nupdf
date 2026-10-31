# Site do NuPDF

Landing page do NuPDF (https://nupdf.com.br) no mesmo padrão das páginas do
Zeebs, Kippe, QiPonto e Lacsio: cabeçalho, hero com ilustração e rodapé, em
HTML e CSS puros (`src/pages/index.astro` + `public/lp/lp.css`), com a
identidade visual do NuPDF (vermelho `#E5484D`, preto `#0B0D12`; Comfortaa só no
nome "nupdf.", Plus Jakarta Sans nos títulos e Inter no texto - fontes em
`public/fonts`). O Astro só gera a página estática.

O botão **Baixar para Windows** aponta para
`https://arquivos.nukt.com.br/atualizacoes/nupdf/Instalador.exe` (Cloudflare R2),
o instalador da última versão, publicado pelo `instalador\publicar.ps1`.
Não é preciso republicar o site a cada versão.

## Desenvolvimento

```
cd site
npm install
npm run dev        # http://localhost:4321
npm run build      # gera dist/
```

## Cloudflare (Workers Builds)

O projeto do Cloudflare aponta para a **raiz** do repositório
`hudson-santos/nupdf`, com o *Deploy command* padrão `npx wrangler deploy`.
Não é preciso configurar *Root directory* nem *Build command* no painel.

Quem faz o trabalho é o `wrangler.jsonc` da raiz do repositório:

1. `build.command` instala as dependências e roda o build do Astro
   (`npm --prefix site install && npm --prefix site run build`), gerando
   `site/dist`;
2. `assets.directory` publica `site/dist` como arquivos estáticos;
3. `site/worker/index.js` é um Worker mínimo (só devolve o 404 dos assets);
   ele existe porque, com um `main`, o wrangler sempre executa o build
   customizado.

O campo `name` do `wrangler.jsonc` (`pages-nupdf`) precisa ser igual ao nome do projeto no
painel. Os cabeçalhos de `public/_headers` são aplicados pelo Cloudflare. Cada push
na `main` republica o site.
