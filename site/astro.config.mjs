// Site de apresentação do NuPDF (https://nupdf.com.br) - saída 100%
// estática, publicada no Cloudflare pelo wrangler.jsonc da raiz do repositório.
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://nupdf.com.br",
  output: "static",
  build: { format: "directory" },
});
