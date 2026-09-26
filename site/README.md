# Site do NuPDF

Página de apresentação em [Astro](https://astro.build), com saída 100% estática.

O botão **Baixar para Windows** aponta para
`https://github.com/hudson-santos/nupdf/releases/latest/download/Instalador.exe`,
que o GitHub redireciona sempre para o `Instalador.exe` da release mais recente.
Não é preciso republicar o site a cada versão. A versão, a data e o tamanho
exibidos abaixo do botão são lidos da API do GitHub no navegador.

## Desenvolvimento

```
cd site
npm install
npm run dev        # http://localhost:4321
npm run build      # gera dist/
```

## Cloudflare (Workers Builds)

Ao conectar o repositório `hudson-santos/nupdf` no Cloudflare (*Workers &
Pages → Create → Import a repository*), configure em *Settings → Build*:

| Campo            | Valor               |
|------------------|---------------------|
| Root directory   | `site`              |
| Build command    | `npm run build`     |
| Deploy command   | `npx wrangler deploy` |

O `wrangler.jsonc` desta pasta publica o conteúdo de `dist/` como arquivos
estáticos (sem código de servidor). O campo `name` dele precisa ser igual ao
nome do projeto no painel. A versão do Node vem de `.node-version` (22), e os
cabeçalhos de cache e segurança de `public/_headers` são aplicados pelo
Cloudflare.

Sem o *Root directory* `site`, o Cloudflare trabalha na raiz do repositório:
instala as dependências Python do app e não encontra o site para publicar.
