#define FindVersaoLinha(int Handle) \
  Local[1] = FileRead(Handle), \
  Local[2] = Pos('VERSAO = "', Local[1]), \
  Local[2] > 0 ? ( \
    Local[3] = Copy(Local[1], Local[2] + 10, Len(Local[1])), \
    Local[4] = Pos('"', Local[3]), \
    Copy(Local[3], 1, Local[4] - 1) \
  ) : FindVersaoLinha(Handle)

#define FileHandle FileOpen(SourcePath + "nupdf\versao.py")
#define MyAppVersion FindVersaoLinha(FileHandle)
#expr FileClose(FileHandle)

#define MyAppName "NuPDF"
#define MyAppPublisher "Nukt Ltda"

[Setup]
AppId={{E26FD3D4-6B38-4EF0-B6A2-2F5EA33A3B7B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoDescription={#MyAppName}
VersionInfoCopyright=Nukt Ltda
AppVerName={#MyAppName} - Versão: {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=C:\NuPDF
DisableDirPage=yes
DisableProgramGroupPage=yes
; Desinstalador em "Aplicativos instalados" / "Programas e Recursos" do
; usuário (instalação sem admin -> entrada em HKCU). Remove também o que os
; scripts criam fora do controle do Inno (venv, NuPDF.exe, atalhos, "Abrir
; com") - ver [UninstallRun] (desinstalar.ps1) e [UninstallDelete].
; As preferências do usuário (%APPDATA%\NuPDF) são mantidas.
Uninstallable=yes
; nome com a versão, como os demais programas da lista (ex.: "NuPDF 1.2.0");
; atualizado a cada instalação/atualização
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\assets\nupdf.ico
AppPublisherURL=https://nupdf.com.br
AppSupportURL=https://github.com/hudson-santos/nupdf
AppUpdatesURL=https://nupdf.com.br
; Por usuário, sem UAC/administrador (também o recomendado para a Microsoft Store).
; Sem PrivilegesRequiredOverridesAllowed: o modo "todos os usuários" gravaria a
; desinstalação em HKLM, enquanto o "Abrir com" e os atalhos (instalar.ps1) são por usuário.
PrivilegesRequired=lowest
; Log em %TEMP%\Setup Log *.txt - diagnóstico de instalações silenciosas (Store)
SetupLogging=yes
; Sem a pergunta "Isto instalará... Deseja continuar?" ao abrir (o mesmo que /SP-).
; Instalação silenciosa na Microsoft Store (Partner Center):
;   /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
DisableStartupPrompt=yes
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=.
; Motor da instalação: vai embutido no Instalador.exe distribuído (a janela de
; instalação própria, instalador\Setup.cs - ver instalador\compilar_instalador.ps1),
; que o executa em /VERYSILENT e mostra o progresso gravado por Progresso() abaixo.
OutputBaseFilename=InstaladorInno
SetupIconFile=assets\nupdf.ico
WizardStyle=modern
; sem a página "Completando o Assistente": ao terminar, o instalador fecha
; sozinho e o NuPDF é aberto (AbrirNuPDF, no fim da etapa 7 em [Code])
DisableFinishedPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "NuPDF.cs"; DestDir: "{app}"; Flags: ignoreversion
Source: "nupdf\*"; DestDir: "{app}\nupdf"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,.claude"
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
; Limpeza executada pelo desinstalador (ver [UninstallRun])
Source: "desinstalar.ps1"; DestDir: "{app}"; Flags: ignoreversion

; Scripts auxiliares: não vão para {app}, só são extraídos sob demanda
; (ExtractTemporaryFile em [Code]) e executados de uma pasta temporária.
Source: "instalar.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "criar_atalho.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "criar_atalho_appid.ps1"; DestDir: "{tmp}"; Flags: dontcopy

[Dirs]
; Cadeias de certificados confiáveis (ICP-Brasil) para validar assinaturas.
Name: "{app}\cadeias"

[UninstallRun]
; Fecha o NuPDF e remove atalhos e o "Abrir com" antes de apagar os arquivos
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\desinstalar.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "LimpezaNuPDF"

[UninstallDelete]
; Tudo o que ficou em C:\NuPDF e não foi copiado pelo Inno (venv, NuPDF.exe,
; Instalador.exe baixado pela atualização, cadeias, __pycache__...)
Type: filesandordirs; Name: "{app}"

[Code]
var
  PaginaProgresso: TOutputProgressWizardPage;
  CaminhoInstalarPs1: String;

// Progresso para a janela de instalação (instalador\Setup.cs): arquivo indicado na
// variável de ambiente NUPDF_PROGRESSO, com "inicio|fim|texto" (faixa da barra em %)
// ou "erro|mensagem". Sem a variável (Inno executado direto), não grava nada.
procedure Progresso(Inicio, Fim: Integer; const Texto: String);
var
  Arquivo: String;
begin
  Arquivo := GetEnv('NUPDF_PROGRESSO');
  if Arquivo <> '' then
    SaveStringToFile(Arquivo, IntToStr(Inicio) + '|' + IntToStr(Fim) + '|' + Texto, False);
end;

procedure ProgressoErro(const Mensagem: String);
var
  Arquivo: String;
begin
  Arquivo := GetEnv('NUPDF_PROGRESSO');
  if Arquivo <> '' then
    SaveStringToFile(Arquivo, 'erro|' + Mensagem, False);
end;

// Abre o NuPDF ao final, sem pedir confirmação (instalação, atualização pelo
// botão do app com /SILENT e atualização manual). Fica aqui e não em [Run]:
// entradas de [Run] sem "postinstall" rodam logo depois da cópia dos arquivos,
// ANTES das etapas 4 a 7 (CurStepChanged) - o NuPDF abria no meio da atualização.
// /VERYSILENT (Microsoft Store e implantações automatizadas): instalação em segundo
// plano, sem abrir o NuPDF no fim. O /SILENT da atualização pelo botão do app continua
// reabrindo o programa.
function MuitoSilencioso: Boolean;
var
  i: Integer;
begin
  Result := False;
  for i := 1 to ParamCount do
    if CompareText(ParamStr(i), '/VERYSILENT') = 0 then
      Result := True;
end;

procedure AbrirNuPDF;
var
  ResultCode: Integer;
begin
  if MuitoSilencioso then
    Exit;
  if FileExists(ExpandConstant('{app}\NuPDF.exe')) then
    Exec(ExpandConstant('{app}\NuPDF.exe'), '', ExpandConstant('{app}'), SW_SHOW, ewNoWait, ResultCode)
  else
    Exec(ExpandConstant('{app}\venv\Scripts\pythonw.exe'), '"' + ExpandConstant('{app}\main.py') + '"',
      ExpandConstant('{app}'), SW_SHOW, ewNoWait, ResultCode);
end;

// Roda uma etapa de instalar.ps1 (1-7) com a janela ESCONDIDA e espera terminar.
function RodarEtapaInstalador(Etapa: Integer; const ArgumentosExtras: String): Boolean;
var
  ResultCode: Integer;
  Parametros: String;
begin
  Parametros := '-NoProfile -ExecutionPolicy Bypass -File "' + CaminhoInstalarPs1 +
    '" -Etapa ' + IntToStr(Etapa) + ' ' + ArgumentosExtras;
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Parametros, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

// Etapas 1 (encerrar instância aberta) e 2 (Python) antes da cópia dos arquivos.
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  ExtractTemporaryFile('instalar.ps1');
  ExtractTemporaryFile('criar_atalho.ps1');
  ExtractTemporaryFile('criar_atalho_appid.ps1');
  CaminhoInstalarPs1 := ExpandConstant('{tmp}\instalar.ps1');

  PaginaProgresso := CreateOutputProgressPage('Instalando o NuPDF',
    'Aguarde enquanto o NuPDF é instalado - isso pode levar alguns minutos.');
  PaginaProgresso.Show;
  try
    PaginaProgresso.SetText('[1/7] Verificando se o NuPDF já está em execução...', '');
    PaginaProgresso.SetProgress(1, 7);
    Progresso(0, 4, 'Fechando o NuPDF aberto');
    if not RodarEtapaInstalador(1, '') then begin
      Result := 'Falha ao verificar/encerrar uma instância do NuPDF em execução.';
      ProgressoErro(Result);
      Exit;
    end;

    PaginaProgresso.SetText('[2/7] Verificando instalação do Python...',
      'Se precisar baixar o Python, isso pode demorar alguns minutos.');
    PaginaProgresso.SetProgress(2, 7);
    Progresso(4, 24, 'Preparando o Python');
    if not RodarEtapaInstalador(2, '') then begin
      Result := 'Falha ao verificar/instalar o Python. Verifique sua conexão com a internet e tente novamente.';
      ProgressoErro(Result);
      Exit;
    end;
  finally
    PaginaProgresso.Hide;
  end;
end;

// Etapas 4 a 7 depois da cópia dos arquivos (etapa 3, feita pelo Inno Setup).
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    Progresso(24, 32, 'Copiando os arquivos');
  if CurStep <> ssPostInstall then
    Exit;

  RodarEtapaInstalador(3, '-SoPosProcessamento');

  PaginaProgresso.Show;
  try
    PaginaProgresso.SetText('[4/7] Criando ambiente virtual...', '');
    PaginaProgresso.SetProgress(4, 7);
    Progresso(32, 40, 'Criando o ambiente do NuPDF');
    if not RodarEtapaInstalador(4, '') then begin
      ProgressoErro('Falha ao criar o ambiente virtual do NuPDF.');
      SuppressibleMsgBox('Falha ao criar o ambiente virtual do NuPDF.', mbCriticalError, MB_OK, IDOK);
      Abort;
    end;

    PaginaProgresso.SetText('[5/7] Instalando dependências...', 'Isso pode demorar alguns minutos.');
    PaginaProgresso.SetProgress(5, 7);
    Progresso(40, 88, 'Instalando os componentes, isso pode levar alguns minutos');
    if not RodarEtapaInstalador(5, '') then begin
      ProgressoErro('Falha ao instalar os componentes do NuPDF. Verifique a conexão com a internet e tente novamente.');
      SuppressibleMsgBox('Falha ao instalar as dependências do NuPDF.', mbCriticalError, MB_OK, IDOK);
      Abort;
    end;

    // Falha aqui é só aviso: os atalhos caem para o pythonw.exe.
    PaginaProgresso.SetText('[6/7] Compilando NuPDF.exe...', '');
    PaginaProgresso.SetProgress(6, 7);
    Progresso(88, 94, 'Finalizando');
    RodarEtapaInstalador(6, '');

    PaginaProgresso.SetText('[7/7] Criando atalhos...', '');
    PaginaProgresso.SetProgress(7, 7);
    Progresso(94, 99, 'Criando os atalhos');
    if not RodarEtapaInstalador(7, '') then
      SuppressibleMsgBox('Falha ao criar os atalhos do NuPDF.', mbError, MB_OK, IDOK);
  finally
    PaginaProgresso.Hide;
  end;
  // só agora, com ambiente, dependências, NuPDF.exe e atalhos prontos
  AbrirNuPDF;
end;
