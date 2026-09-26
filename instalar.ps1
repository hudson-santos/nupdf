<#
    Instalador/atualizador do NuPDF - sempre em C:\NuPDF, sem pedir
    elevação (mesmo modelo do Zeebs): o Python é instalado por usuário se
    ainda não houver um compatível; C:\NuPDF fica compartilhada entre os
    usuários da máquina (RemoteApp publica o NuPDF.exe a partir dela).

    Também serve para ATUALIZAR: encerra uma instância em execução, copia
    os arquivos novos e reinstala as dependências.

    Uso:
      - Direto (Instalador.bat ou "powershell -File instalar.ps1"): roda
        TODAS as etapas em sequência, com o progresso "[N/7] ...".
      - Com -Etapa N: roda só a etapa N - usado pelo Instalador.exe (Inno
        Setup, ver Instalador.iss), que mostra o progresso na própria janela
        do assistente. A etapa 3 (copiar arquivos) é feita pelo Inno Setup;
        só o pós-processamento roda aqui ("-Etapa 3 -SoPosProcessamento").
#>
param(
    [ValidateSet(0, 1, 2, 3, 4, 5, 6, 7)]
    [int]$Etapa = 0,   # 0 = todas as etapas em sequência (uso direto/manual)
    [switch]$SoPosProcessamento
)

$ErrorActionPreference = "Stop"

$APP_DIR = "C:\NuPDF"
$PYTHON_VERSION = "3.12.10"
$PYTHON_URL = "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-amd64.exe"
# O código usa sintaxe do Python 3.10+; versões muito novas podem ainda não
# ter wheels de todas as dependências.
$PYTHON_MIN = 310
$PYTHON_MAX = 314
# Caminho do python.exe escolhido na etapa 2, lido pela etapa 4 (cada etapa
# roda num processo PowerShell separado quando chamada via -Etapa).
$ESTADO_PYTHON = Join-Path $env:TEMP "nupdf_python_exe.txt"


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


function Testar-Python([string]$exe) {
    # Devolve o caminho real (sys.executable) se a versão for compatível.
    # Nunca executa o alias falso da Microsoft Store (WindowsApps), que
    # pode abrir a Loja e travar o instalador - quem chama já filtra.
    try {
        $saida = & $exe -c "import sys; print(sys.executable); print(sys.version_info[0]*100 + sys.version_info[1])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $saida -or $saida.Count -lt 2) { return $null }
        $versao = [int]$saida[1]
        if ($versao -ge $PYTHON_MIN -and $versao -le $PYTHON_MAX) { return $saida[0] }
        Write-Host "      Ignorando $($saida[0]) (versao $([math]::Floor($versao / 100)).$($versao % 100) incompativel)."
    } catch { }
    return $null
}


function Etapa2-VerificarPython {
    Write-Host "[2/7] Verificando instalacao do Python..."
    $pythonExe = $null

    $candidatos = @()
    foreach ($v in "312", "313", "311", "310", "314") {
        $candidatos += Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v\python.exe"
    }
    foreach ($cmd in "py", "python") {
        Get-Command $cmd -ErrorAction SilentlyContinue -All |
            Where-Object { $_.Source -and $_.Source -notlike "*WindowsApps*" } |
            ForEach-Object { $candidatos += $_.Source }
    }
    foreach ($c in $candidatos) {
        if (-not (Test-Path $c)) { continue }
        $pythonExe = Testar-Python $c
        if ($pythonExe) { break }
    }

    if ($pythonExe) {
        Write-Host "      Python compativel encontrado: `"$pythonExe`"."
    } else {
        Write-Host "      Python compativel nao encontrado. Baixando Python $PYTHON_VERSION..."
        Write-Host "      (isso pode levar alguns minutos, dependendo da internet)"
        $installer = Join-Path $env:TEMP "nupdf_python_installer.exe"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        try {
            Invoke-WebRequest -Uri $PYTHON_URL -OutFile $installer -TimeoutSec 180 -UseBasicParsing
        } catch {
            Write-Host "[ERRO] Falha ao baixar o instalador do Python."
            Write-Host "       Verifique a conexao com a internet (www.python.org liberado no proxy/firewall)."
            exit 1
        }
        Write-Host "      Instalando Python $PYTHON_VERSION (usuario atual, silencioso)..."
        $proc = Start-Process -FilePath $installer -ArgumentList @(
            "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0"
        ) -Wait -PassThru
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
        if ($proc.ExitCode -ne 0) {
            Write-Host "[ERRO] A instalacao do Python falhou."
            exit 1
        }
        $pythonExe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        if (-not (Test-Path $pythonExe)) {
            Write-Host "[AVISO] Python instalado, mas nao encontrado no caminho esperado."
            Write-Host "        Feche esta janela e execute o instalador novamente."
            exit 1
        }
        Write-Host "      Python instalado com sucesso."
    }

    Set-Content -Path $ESTADO_PYTHON -Value $pythonExe -Encoding ascii -NoNewline
}


function Etapa3-CopiarArquivos {
    # Só no uso direto/manual - no Instalador.exe quem copia é o Inno Setup.
    Write-Host "[3/7] Copiando arquivos para $APP_DIR..."
    Garantir-PastaCompartilhada
    $origem = $PSScriptRoot
    foreach ($arq in "main.py", "NuPDF.cs") {
        Copy-Item -Path (Join-Path $origem $arq) -Destination $APP_DIR -Force
    }
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
        Where-Object { $_.FullName -notlike "$APP_DIR\venv\*" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}


function Etapa4-CriarVenv {
    Write-Host "[4/7] Criando ambiente virtual..."
    $venvPath = Join-Path $APP_DIR "venv"
    if (Test-Path (Join-Path $venvPath "Scripts\python.exe")) {
        Write-Host "      Ambiente virtual ja existe."
        return
    }
    $pythonExe = $null
    if (Test-Path $ESTADO_PYTHON) {
        $pythonExe = Get-Content $ESTADO_PYTHON -ErrorAction SilentlyContinue
    }
    if (-not $pythonExe -or -not (Test-Path $pythonExe)) {
        $padrao = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        $pythonExe = if (Test-Path $padrao) { $padrao } else { "python" }
    }
    & $pythonExe -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Falha ao criar o ambiente virtual."
        exit 1
    }
}


function Etapa5-InstalarDependencias {
    Write-Host "[5/7] Instalando dependencias (pode demorar alguns minutos)..."
    $pythonVenv = Join-Path $APP_DIR "venv\Scripts\python.exe"
    & $pythonVenv -m pip install --upgrade pip -q --disable-pip-version-check

    # Lista embutida aqui (mesma de requirements.txt, usado no desenvolvimento).
    & $pythonVenv -m pip install -q --disable-pip-version-check `
        "PySide6-Essentials>=6.8" `
        "pymupdf>=1.26" `
        "pyHanko>=0.29" `
        "pyhanko-certvalidator>=0.27" `
        "cryptography>=43"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Falha ao instalar as dependencias."
        exit 1
    }

    Write-Host "      Dependencias instaladas."
}


function Etapa6-CompilarLauncher {
    # NuPDF.exe: launcher nativo (C#) - dá ao NuPDF um .exe de verdade, com
    # ícone e nome próprios, usado nos atalhos, no "Abrir com" do Explorer e
    # no RemoteApp. Falha aqui vira só um aviso (os atalhos caem para o
    # pythonw.exe).
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
    $pythonw = Join-Path $APP_DIR "venv\Scripts\pythonw.exe"
    $mainPy = Join-Path $APP_DIR "main.py"
    $criarAtalho = Join-Path $PSScriptRoot "criar_atalho.ps1"
    $definirAppId = Join-Path $PSScriptRoot "criar_atalho_definir_appid.ps1"

    if (Test-Path $launcher) {
        $alvo, $argumentos = $launcher, ""
        $comandoAbrir = "`"$launcher`" `"%1`""
    } else {
        $alvo, $argumentos = $pythonw, $mainPy
        $comandoAbrir = "`"$pythonw`" `"$mainPy`" `"%1`""
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
    2 { Etapa2-VerificarPython }
    3 { if ($SoPosProcessamento) { Etapa3b-PosProcessamento } else { Etapa3-CopiarArquivos } }
    4 { Etapa4-CriarVenv }
    5 { Etapa5-InstalarDependencias }
    6 { Etapa6-CompilarLauncher }
    7 { Etapa7-CriarAtalhos }
    0 {
        Write-Host ""
        Write-Host " =============================================="
        Write-Host "  Instalador NuPDF"
        Write-Host " =============================================="
        Write-Host ""
        Etapa1-EncerrarInstancia
        Etapa2-VerificarPython
        Etapa3-CopiarArquivos
        Etapa4-CriarVenv
        Etapa5-InstalarDependencias
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
