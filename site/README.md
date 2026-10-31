# Site do NuPDF

Página de apresentação em [Astro](https://astro.build), com saída 100% estática.

O botão **Baixar para Windows** aponta para
`https://arquivos.nukt.com.br/atualizacoes/nupdf/Instalador.exe` (Cloudflare R2),
o instalador da última versão, publicado pelo `instalador\publicar.ps1`.
Não é preciso republicar o site a cada versão. A versão, a data e o tamanho
exibidos abaixo do botão vêm do `versao.json` do R2, repassado pelo worker do
site em `/versao.json` (`worker/index.js`).

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
painel. Os cabeçalhos de `public/_headers` são aplicados pelo Cloudflare.
