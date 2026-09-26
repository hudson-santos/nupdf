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

## Cloudflare Pages

Em *Workers & Pages → Create → Pages → Connect to Git*, escolha o repositório
`hudson-santos/nupdf` e configure:

| Campo                  | Valor           |
|------------------------|-----------------|
| Framework preset       | Astro           |
| Root directory         | `site`          |
| Build command          | `npm run build` |
| Build output directory | `dist`          |

A versão do Node vem do arquivo `.node-version` (22). Os cabeçalhos de cache e
segurança ficam em `public/_headers`.
