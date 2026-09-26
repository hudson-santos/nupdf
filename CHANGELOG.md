# Changelog

## [0.1.0] - 2026-09-25

### Added
- Leitor de PDF com abas, renderização sob demanda (PyMuPDF), zoom (Ctrl+roda, 25%–500%),
  ajuste à largura/página, rotação da visualização, modo mão e navegação por página.
- Seleção de texto em ordem visual (arrastar, duplo clique = palavra, triplo = linha,
  Alt+arrastar = seleção retangular), Ctrl+C/Ctrl+A e menu de contexto.
- Busca no documento (Ctrl+F) com destaque de todas as ocorrências.
- Painel "Dados do documento": detecta pares "Rótulo: valor", CPF, CNPJ (inclusive
  alfanumérico), datas, valores, e-mails, telefones, CEP, chave de acesso NF-e e linha
  digitável — um clique copia.
- Assinatura digital PAdES (SHA-256) com certificado ICP-Brasil A1 (.pfx) ou A3
  (token/cartão via PKCS#11), visível (posicionada na página) ou invisível, com carimbo
  de tempo opcional. Atualização incremental preserva assinaturas anteriores.
- Painel de assinaturas com validação de integridade, cobertura e cadeia de confiança.
- Miniaturas, arquivos recentes, arrastar e soltar, impressão, tema claro/escuro.
- Instância única: PDFs abertos pelo Explorer com o NuPDF já aberto viram abas novas.
- Instalador (Inno Setup + instalar.ps1, mesmo modelo do Zeebs): instala em C:\NuPDF
  sem pedir administrador, cria atalhos na Área de Trabalho e no Menu Iniciar, compila o
  launcher NuPDF.exe e registra o NuPDF em "Abrir com" para arquivos .pdf.
