# Instruções para o Claude Code neste repositório

## Fluxo de release do NuPDF

Uma única etapa, disparada só por pedido explícito do usuário. **Nunca**
execute por conta própria, mesmo que a mudança pareça pronta para liberar.

### Usuário pede: "Atualizar Changelog - NuPDF"

1. Leia `nupdf/versao.py` (`VERSAO`) para saber a versão atual.
2. Escolha o bump (semver `MAJOR.MINOR.PATCH`, ver docstring de
   `nupdf/versao.py`) olhando as mudanças desde a última entrada do
   `CHANGELOG.md`:
   - **PATCH**: correção de bug, ajuste cosmético/UX, sem funcionalidade nova.
   - **MINOR**: funcionalidade nova, compatível com o que já existia.
   - **MAJOR**: mudança que quebra compatibilidade.
3. Atualize `VERSAO` em `nupdf/versao.py`.
4. Adicione uma entrada nova no topo de `CHANGELOG.md`, no formato exato:

   ```
   ## [X.Y.Z] - AAAA-MM-DD

   ### Added|Changed|Fixed
   - ...
   ```

   O título precisa bater exatamente com `## [X.Y.Z] - ` — o workflow
   `.github/workflows/versao.yml` procura por ele para montar a Release.
   Cubra TODAS as mudanças feitas desde a última entrada.
5. Rode a verificação de integridade:
   `/c/App/NuPDF/venv/Scripts/python.exe verificar.py`
   Se falhar, **pare** e informe o usuário - sem commit nem push.
6. `git status` e `git add` só nos arquivos relevantes (`CHANGELOG.md`,
   `nupdf/versao.py` e os arquivos alterados desde a última release) -
   nunca `git add -A`/`git add .`. Confira que nada sensível (certificados,
   configurações locais, dados pessoais reais) vai junto: o repositório é
   público.
7. Commit com mensagem no formato exato:

   ```
   release - [X.Y.Z]

   <resumo curto do que mudou nesta versão>

   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   ```

   A primeira linha precisa começar com `release - [` - é o gatilho do
   workflow que cria a tag/Release e compila o `Instalador.exe`.
8. `git push origin main`.
9. Confirme para o usuário a nova versão com o link do commit
   (`https://github.com/hudson-santos/nupdf/commit/<hash>`) e o da página
   de Actions (`https://github.com/hudson-santos/nupdf/actions`).

### Regra geral

Sem o pedido "Atualizar Changelog - NuPDF" (ou equivalente inequívoco),
não faça bump de versão, commit ou push - só implemente e verifique a
mudança, e avise que está pronta para o changelog.

## Estrutura

- `main.py` - entrada (instância única via QLocalServer, AppUserModelID `NuPDF.App`).
- `nupdf/` - aplicação (visualizador, painéis, diálogo e módulo `assinatura/`).
- `verificar.py` - verificação de integridade (gera PDF/certificado de teste,
  assina, valida e exercita a interface em modo offscreen).
- `Instalador.iss` + `instalar.ps1` + `criar_atalho*.ps1` + `NuPDF.cs` -
  instalador (C:\NuPDF, sem admin, atalho na Área de Trabalho), mesmo modelo do Zeebs.
