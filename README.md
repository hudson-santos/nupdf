# NuPDF

Leitor de PDF leve para uso corporativo interno: **ler**, **copiar dados** e
**assinar digitalmente no padrão ICP-Brasil** - sem o peso do Adobe Reader.

## Funcionalidades

- **Leitura**: abas, miniaturas, zoom (Ctrl + roda), ajuste à largura/página,
  rotação, modo mão, busca (Ctrl+F), impressão, tema claro/escuro, recentes,
  arrastar e soltar. Instância única (PDFs do Explorer abrem em abas).
- **Copiar dados**: seleção de texto em ordem visual (duplo clique = palavra,
  triplo = linha, Alt+arrastar = retângulo), Ctrl+C e menu de contexto.
- **Propriedades do documento**: painel com os metadados do PDF (título,
  autor, assunto, palavras-chave, aplicativo de criação, datas, versão,
  tamanho da página e proteção).
- **Assinatura digital**: PAdES (ETSI.CAdES.detached, SHA-256) com um dos
  **certificados ICP-Brasil instalados no Windows** (escolhido numa lista com
  busca; a chave privada não sai do Windows, que pede a senha/PIN quando o
  certificado é protegido), visível (desenhada na página) ou invisível,
  carimbo de tempo opcional. Assinaturas anteriores são preservadas
  (atualização incremental).
- **Validação**: painel de assinaturas mostra integridade, cobertura e cadeia
  de confiança. A cadeia oficial ICP-Brasil (pacote do ITI) é baixada na
  instalação e pode ser atualizada no painel ("Atualizar Cadeia ICP-Brasil");
  ACs intermediárias que faltarem são buscadas pela internet. Para outras
  cadeias, "Confiar nesta Cadeia" no cartão da assinatura (como no Adobe), ou
  coloque os certificados (.cer/.crt) em `%APPDATA%\NuPDF\cadeias`.

## Instalação (usuários)

Execute o `Instalador.exe` (ou `Instalador.bat`). Instala em `C:\NuPDF` sem
pedir administrador, cria atalho na Área de Trabalho e no Menu Iniciar e
registra o NuPDF em "Abrir com" para .pdf. Usa o Python de `C:\Python64`; se a
máquina não tiver `C:\Python64` e `C:\Python32`, instala o Python 3.14.8 (64 e
32 bits) nessas pastas. Para torná-lo o leitor padrão:
botão direito num PDF → Abrir com → NuPDF → "Sempre usar este aplicativo".

Para desinstalar: Configurações → Aplicativos → Aplicativos instalados (ou
Painel de Controle → Programas e Recursos) → **NuPDF** → Desinstalar. Remove
a pasta `C:\NuPDF`, os atalhos e o registro em "Abrir com"; as preferências
do usuário (`%APPDATA%\NuPDF`) são mantidas.

## Desenvolvimento

```
py -3.14 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe main.py            # ou NuPDF.bat
venv\Scripts\python.exe verificar.py       # verificação de integridade
```

Tecnologias: PySide6 (Qt), PyMuPDF, pyHanko, cryptography.
Release: ver `CLAUDE.md` (o GitHub Actions compila o `Instalador.exe` a cada
commit `release - [X.Y.Z]`). O `Instalador.exe` é a janela de instalação própria
(`instalador/Setup.cs`) com o motor do Inno Setup (`Instalador.iss`) embutido;
para gerar localmente: `powershell -ExecutionPolicy Bypass -File instalador\compilar_instalador.ps1`.
