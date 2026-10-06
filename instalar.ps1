<#
    Instalador/atualizador do NuPDF - sempre em C:\NuPDF, sem pedir
    elevação (mesmo modelo do Zeebs). O Python vem EMBUTIDO no próprio
    NuPDF (C:\NuPDF\python: pacote "embeddable" oficial do python.org com as
    dependências já instaladas no build - ver instalador\compilar_instalador.ps1):
    a máquina não precisa de Python, pip nem internet. C:\NuPDF fica
    compartilhada entre os usuários da máquina (RemoteApp publica o NuPDF.exe
    a partir dela).

    Também serve para ATUALIZAR: encerra uma instância em execução e copia os
    arquivos novos (o Python embutido inclusive).

    Uso:
      - Direto (Instalador.bat ou "powershell -File instalar.ps1"): roda
        TODAS as etapas em sequência, com o progresso "[N/7] ...". Precisa do
        Python embutido já montado em build\python (rode antes
        instalador\compilar_instalador.ps1).
      - Com -Etapa N: roda só a etapa N - usado pelo Instalador.exe (Inno
        Setup, ver Instalador.iss). A etapa 3 (copiar arquivos) é feita pelo
        Inno Setup; só o pós-processamento roda aqui ("-Etapa 3 -SoPosProcessamento").
#>
param(
    [ValidateSet(0, 1, 2, 3, 4, 5, 6, 7)]
    [int]$Etapa = 0,   # 0 = todas as etapas em sequência (uso direto/manual)
    [switch]$SoPosProcessamento
)

$ErrorActionPreference = "Stop"

$APP_DIR = "C:\NuPDF"
$PYTHON_DIR = Join-Path $APP_DIR "python"          # Python embutido
$PYTHON_EXE = Join-Path $PYTHON_DIR "python.exe"
$PYTHONW_EXE = Join-Path $PYTHON_DIR "pythonw.exe"


function Garantir-PastaCompartilhada {
    New-Item -ItemType Directory -Force -Path $APP_DIR | Out-Null
    icacls $APP_DIR /grant "*S-1-5-32-545:(OI)(CI)M" 2>$null | Out-Null
}


function Etapa1-EncerrarInstancia {
    Write-Host "[1/7] Verificando se o NuPDF ja esta em execucao..."
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe' or Name='NuPDF.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "NuPDF.exe" -or ($_.CommandLine -and $_.CommandLine -like "*NuPDF*main.py*") }
    if ($procs) {
        $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Write-Host "      Instancia anterior encerrada."
        Start-Sleep -Seconds 2
    } else {
        Write-Host "      Nenhuma instancia em execucao."
    }
}


function Etapa2-VerificarSistema {
    # Antes o NuPDF instalava o Python na máquina aqui; agora ele vem embutido.
    Write-Host "[2/7] Verificando o sistema..."
    if (-not [Environment]::Is64BitOperatingSystem) {
        Write-Host "[ERRO] O NuPDF precisa do Windows 64 bits."
        exit 1
    }
    Write-Host "      Windows 64 bits - Python embutido no NuPDF (nao precisa instalar)."
}


function Etapa3-CopiarArquivos {
    # Só no uso direto/manual - no Instalador.exe quem copia é o Inno Setup.
    Write-Host "[3/7] Copiando arquivos para $APP_DIR..."
    Garantir-PastaCompartilhada
    $origem = $PSScriptRoot
    $pythonBuild = Join-Path $origem "build\python"
    if (-not (Test-Path (Join-Path $pythonBuild "python.exe"))) {
        Write-Host "[ERRO] Python embutido nao encontrado em $pythonBuild."
        Write-Host "       Rode antes: powershell -ExecutionPolicy Bypass -File instalador\compilar_instalador.ps1"
        exit 1
    }
    foreach ($arq in "main.py", "NuPDF.cs") {
        Copy-Item -Path (Join-Path $origem $arq) -Destination $APP_DIR -Force
    }
    if (Test-Path $PYTHON_DIR) { Remove-Item $PYTHON_DIR -Recurse -Force }  # sem sobras da versão anterior
    Copy-Item -Path $pythonBuild -Destination $PYTHON_DIR -Recurse -Force
    foreach ($pasta in "nupdf", "assets") {
        $origemPasta = Join-Path $origem $pasta
        $destPasta = Join-Path $APP_DIR $pasta
        New-Item -ItemType Directory -Force -Path $destPasta | Out-Null
        Get-ChildItem -Path $origemPasta -Recurse -File |
            Where-Object { $_.FullName -notmatch '\\__pycache__\\' -and $_.FullName -notmatch '\\\.claude\\' } |
            ForEach-Object {
                $relativo = $_.FullName.Substring($origemPasta.Length).TrimStart('\')
                $destino = Join-Path $destPasta $relativo
                New-Item -ItemType Directory -Force -Path (Split-Path $destino -Parent) | Out-Null
                Copy-Item -Path $_.FullName -Destination $destino -Force
            }
    }
    Write-Host "      Arquivos copiados em $APP_DIR."
    Etapa3b-PosProcessamento
}


function Etapa3b-PosProcessamento {
    Garantir-PastaCompartilhada
    # Cadeias de certificados confiáveis (ex.: ICP-Brasil) para validar
    # assinaturas - ver nupdf/assinatura/validador.py.
    New-Item -ItemType Directory -Force -Path (Join-Path $APP_DIR "cadeias") | Out-Null
    Get-ChildItem -Path $APP_DIR -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notlike "$PYTHON_DIR\*" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    # Instalações antigas: o ambiente virtual (venv) do Python do sistema não é mais usado
    $venvAntigo = Join-Path $APP_DIR "venv"
    if (Test-Path $venvAntigo) {
        Remove-Item $venvAntigo -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "      Ambiente antigo (venv) removido."
    }
}


function Etapa4-PrepararPython {
    # Pré-compila o bytecode (dependências e o próprio NuPDF): sem isso a primeira
    # abertura depois de instalar/atualizar compila tudo na hora.
    Write-Host "[4/7] Preparando o Python embutido..."
    if (-not (Test-Path $PYTHON_EXE)) {
        Write-Host "[ERRO] Python embutido nao encontrado em $PYTHON_DIR."
        exit 1
    }
    & $PYTHON_EXE -m compileall -q -j 0 (Join-Path $PYTHON_DIR "Lib\site-packages") (Join-Path $APP_DIR "nupdf") | Out-Null
    $global:LASTEXITCODE = 0  # um arquivo que não compila não impede o NuPDF de rodar
    Write-Host "      Python embutido pronto."
}


function Etapa5-CadeiaICP {
    # Cadeia oficial ICP-Brasil (raízes + ACs, pacote do ITI) para validar assinaturas.
    # Falha aqui (sem internet) não interrompe a instalação: dá para baixar depois no
    # painel de assinaturas ("Atualizar Cadeia ICP-Brasil").
    Write-Host "[5/7] Baixando a cadeia ICP-Brasil..."
    Push-Location $APP_DIR
    & $PYTHON_EXE -m nupdf.assinatura.cadeia_icp (Join-Path $APP_DIR "cadeias\icp-brasil")
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[AVISO] Cadeia ICP-Brasil nao baixada - atualize depois pelo painel de assinaturas."
    }
    $global:LASTEXITCODE = 0
}


function Etapa6-CompilarLauncher {
    # NuPDF.exe: launcher nativo (C#) - dá ao NuPDF um .exe de verdade, com
    # ícone e nome próprios, usado nos atalhos, no "Abrir com" do Explorer e
    # no RemoteApp. Falha aqui vira só um aviso (os atalhos caem para o
    # pythonw.exe embutido).
    Write-Host "[6/7] Compilando NuPDF.exe..."
    $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if (-not (Test-Path $csc)) {
        $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
    }
    if (-not (Test-Path $csc)) {
        Write-Host "[AVISO] csc.exe do .NET Framework nao encontrado - NuPDF.exe nao foi compilado."
        return
    }
    $versao = "0.0.0"
    $versaoLinha = Select-String -Path (Join-Path $APP_DIR "nupdf\versao.py") -Pattern '^VERSAO = "' -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($versaoLinha) { $versao = ($versaoLinha.Line -split '"')[1] }

    $assemblyInfo = Join-Path $env:TEMP "nupdf_assemblyinfo.cs"
    @"
using System.Reflection;
[assembly: AssemblyVersion("$versao")]
[assembly: AssemblyFileVersion("$versao")]
"@ | Set-Content -Path $assemblyInfo -Encoding ascii

    # Compila num arquivo temporário e troca depois: o NuPDF.exe antigo pode
    # estar travado por um Explorer que acabou de ler o ícone dele.
    $novo = Join-Path $APP_DIR "NuPDF.new.exe"
    & $csc /nologo /target:winexe /out:"$novo" /win32icon:"$APP_DIR\assets\nupdf.ico" `
        /r:System.Windows.Forms.dll "$APP_DIR\NuPDF.cs" $assemblyInfo | Out-Null
    $codigoSaida = $LASTEXITCODE
    Remove-Item $assemblyInfo -Force -ErrorAction SilentlyContinue
    if ($codigoSaida -ne 0) {
        Write-Host "[AVISO] Falha ao compilar NuPDF.exe - os atalhos usarao o pythonw.exe."
        return
    }
    Move-Item -Path $novo -Destination (Join-Path $APP_DIR "NuPDF.exe") -Force
    Write-Host "      NuPDF.exe compilado (versao $versao)."
}


function Registrar-AbrirCom([string]$exe, [string]$icone) {
    # Associação por usuário (HKCU, sem admin): o NuPDF aparece em
    # "Abrir com" para .pdf. O Windows 10/11 não deixa um programa se
    # declarar padrão sozinho - o usuário escolhe "Sempre usar este
    # aplicativo" na primeira vez que abrir um PDF pelo "Abrir com".
    $classes = "HKCU:\Software\Classes"
    $progId = "NuPDF.Documento"
    New-Item -Path "$classes\$progId\DefaultIcon" -Force | Out-Null
    New-Item -Path "$classes\$progId\shell\open\command" -Force | Out-Null
    Set-ItemProperty -Path "$classes\$progId" -Name "(default)" -Value "Documento PDF"
    Set-ItemProperty -Path "$classes\$progId" -Name "FriendlyTypeName" -Value "Documento PDF"
    Set-ItemProperty -Path "$classes\$progId\DefaultIcon" -Name "(default)" -Value $icone
    Set-ItemProperty -Path "$classes\$progId\shell\open\command" -Name "(default)" -Value $exe
    New-Item -Path "$classes\.pdf\OpenWithProgids" -Force | Out-Null
    New-ItemProperty -Path "$classes\.pdf\OpenWithProgids" -Name $progId -Value ([byte[]]@()) -PropertyType None -Force | Out-Null

    $app = "$classes\Applications\NuPDF.exe"
    New-Item -Path "$app\shell\open\command" -Force | Out-Null
    New-Item -Path "$app\SupportedTypes" -Force | Out-Null
    Set-ItemProperty -Path "$app" -Name "FriendlyAppName" -Value "NuPDF"
    Set-ItemProperty -Path "$app\shell\open\command" -Name "(default)" -Value $exe
    New-ItemProperty -Path "$app\SupportedTypes" -Name ".pdf" -Value "" -PropertyType String -Force | Out-Null

    # "Aplicativos padrão" das Configurações: o NuPDF ganha página própria
    # (ms-settings:defaultapps?registeredAppUser=NuPDF), usada pelo app para
    # ajudar o usuário a torná-lo o leitor de PDF padrão.
    $cap = "HKCU:\Software\NuPDF\Capabilities"
    New-Item -Path "$cap\FileAssociations" -Force | Out-Null
    Set-ItemProperty -Path $cap -Name "ApplicationName" -Value "NuPDF"
    Set-ItemProperty -Path $cap -Name "ApplicationDescription" -Value "Leitor de PDF com assinatura digital ICP-Brasil"
    Set-ItemProperty -Path "$cap\FileAssociations" -Name ".pdf" -Value $progId
    New-Item -Path "HKCU:\Software\RegisteredApplications" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\RegisteredApplications" -Name "NuPDF" -Value "Software\NuPDF\Capabilities"

    # avisa o Explorer que as associações mudaram
    Add-Type -Namespace NuPDF -Name Shell -MemberDefinition '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int e, int f, IntPtr a, IntPtr b);' -ErrorAction SilentlyContinue
    try { [NuPDF.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero) } catch { }
}


function Etapa7-CriarAtalhos {
    Write-Host "[7/7] Criando atalhos..."
    $iconPath = Join-Path $APP_DIR "assets\nupdf.ico"
    $launcher = Join-Path $APP_DIR "NuPDF.exe"
    $mainPy = Join-Path $APP_DIR "main.py"
    $criarAtalho = Join-Path $PSScriptRoot "criar_atalho.ps1"
    $definirAppId = Join-Path $PSScriptRoot "criar_atalho_appid.ps1"

    if (Test-Path $launcher) {
        $alvo, $argumentos = $launcher, ""
        $comandoAbrir = "`"$launcher`" `"%1`""
    } else {
        $alvo, $argumentos = $PYTHONW_EXE, $mainPy
        $comandoAbrir = "`"$PYTHONW_EXE`" `"$mainPy`" `"%1`""
    }

    # Área de Trabalho e Menu Iniciar do usuário atual - o atalho do Menu
    # Iniciar é o que o Windows usa para o ícone ao "Fixar na barra de tarefas".
    foreach ($pasta in "Desktop", "Programs") {
        $params = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $criarAtalho,
            "-Pasta", $pasta, "-TargetPath", $alvo, "-WorkingDirectory", $APP_DIR, "-IconLocation", $iconPath)
        if ($argumentos) { $params += @("-Arguments", $argumentos) }
        & powershell @params
        & powershell -NoProfile -ExecutionPolicy Bypass -File $definirAppId `
            -AppId "NuPDF.App" -Pasta $pasta
    }

    try {
        Registrar-AbrirCom $comandoAbrir $iconPath
        Write-Host "      NuPDF registrado em `"Abrir com`" para arquivos .pdf."
    } catch {
        Write-Host "      [AVISO] Nao foi possivel registrar o NuPDF em `"Abrir com`": $_"
    }
    Write-Host "      Atalhos criados."
}


switch ($Etapa) {
    1 { Etapa1-EncerrarInstancia }
    2 { Etapa2-VerificarSistema }
    3 { if ($SoPosProcessamento) { Etapa3b-PosProcessamento } else { Etapa3-CopiarArquivos } }
    4 { Etapa4-PrepararPython }
    5 { Etapa5-CadeiaICP }
    6 { Etapa6-CompilarLauncher }
    7 { Etapa7-CriarAtalhos }
    0 {
        Write-Host ""
        Write-Host " =============================================="
        Write-Host "  Instalador NuPDF"
        Write-Host " =============================================="
        Write-Host ""
        Etapa1-EncerrarInstancia
        Etapa2-VerificarSistema
        Etapa3-CopiarArquivos
        Etapa4-PrepararPython
        Etapa5-CadeiaICP
        Etapa6-CompilarLauncher
        Etapa7-CriarAtalhos

        $versaoInstalada = "desconhecida"
        $vLinha = Select-String -Path (Join-Path $APP_DIR "nupdf\versao.py") -Pattern '^VERSAO = "' -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($vLinha) { $versaoInstalada = ($vLinha.Line -split '"')[1] }

        Write-Host ""
        Write-Host " =============================================="
        Write-Host "  Instalacao concluida - NuPDF $versaoInstalada"
        Write-Host " =============================================="
        Write-Host ""
        Write-Host "  - Aplicacao instalada em:  $APP_DIR"
        Write-Host "  - Nao precisou de privilegios de administrador"
        Write-Host "  - Atalho criado na Area de Trabalho"
        Write-Host ""
    }
}
