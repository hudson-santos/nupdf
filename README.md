# NuPDF

Leitor de PDF leve para uso corporativo interno: **ler**, **copiar dados** e
**assinar digitalmente no padrão ICP-Brasil** — sem o peso do Adobe Reader.

## Funcionalidades

- **Leitura**: abas, miniaturas, zoom (Ctrl + roda), ajuste à largura/página,
  rotação, modo mão, busca (Ctrl+F), impressão, tema claro/escuro, recentes,
  arrastar e soltar. Instância única (PDFs do Explorer abrem em abas).
- **Copiar dados**: seleção de texto em ordem visual (duplo clique = palavra,
  triplo = linha, Alt+arrastar = retângulo). O painel *Dados do documento*
  reconhece "Rótulo: valor", CPF, CNPJ (inclusive alfanumérico), datas,
  valores, e-mails, telefones, CEP, chave de acesso NF-e e linha digitável —
  um clique copia.
- **Assinatura digital**: PAdES (ETSI.CAdES.detached, SHA-256) com certificado
  **A1** (.pfx) ou **A3** (token/cartão via PKCS#11), visível (desenhada na
  página) ou invisível, carimbo de tempo opcional. Assinaturas anteriores são
  preservadas (atualização incremental).
- **Validação**: painel de assinaturas mostra integridade, cobertura e cadeia
  de confiança. Para reconhecer a cadeia ICP-Brasil, coloque os certificados
  das ACs (.cer/.crt) em `C:\NuPDF\cadeias` ou `%APPDATA%\NuPDF\cadeias`
  (além do repositório de certificados do Windows).

## Instalação (usuários)

Execute o `Instalador.exe` (ou `Instalador.bat`). Instala em `C:\NuPDF` sem
pedir administrador, cria atalho na Área de Trabalho e no Menu Iniciar e
registra o NuPDF em "Abrir com" para .pdf. Para torná-lo o leitor padrão:
botão direito num PDF → Abrir com → NuPDF → "Sempre usar este aplicativo".

## Desenvolvimento

```
py -3.14 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe main.py            # ou NuPDF.bat
venv\Scripts\python.exe verificar.py       # verificação de integridade
```

Tecnologias: PySide6 (Qt), PyMuPDF, pyHanko, python-pkcs11, cryptography.
Release: ver `CLAUDE.md` (mesmo fluxo do Zeebs; o GitHub Actions compila o
`Instalador.exe` com Inno Setup a cada commit `release - [X.Y.Z]`).
