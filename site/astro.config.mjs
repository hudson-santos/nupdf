// Site de apresentação do NuPDF - saída 100% estática (Cloudflare Pages
// serve a pasta dist/ direto, sem adapter nem Functions).
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://nupdf.pages.dev",
  output: "static",
  build: { format: "directory" },
});
