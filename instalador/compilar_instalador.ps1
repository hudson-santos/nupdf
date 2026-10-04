# Gera o Instalador.exe distribuído (raiz do projeto), em duas partes:
#   1. Inno Setup: Instalador.iss -> InstaladorInno.exe (o motor da instalação)
#   2. csc.exe do .NET Framework do Windows: instalador\Setup.cs -> Instalador.exe,
#      a janela de instalação, com o InstaladorInno.exe embutido como recurso.
# Usado no GitHub Actions (.github/workflows/versao.yml) e para compilar localmente:
#   powershell -ExecutionPolicy Bypass -File instalador\compilar_instalador.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "ISCC.exe (Inno Setup 6) nao encontrado." }

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe" }
if (-not (Test-Path $csc)) { throw "csc.exe do .NET Framework nao encontrado." }

# Instaladores oficiais do Python embutidos no motor (Instalador.iss). Ficam em
# instalador\python\ (fora do git); se faltarem, baixa do python.org. O SHA-256
# fixado garante que é exatamente o arquivo oficial (assinado pela PSF).
$pythonVersao = "3.14.8"
$pythonHashes = @{
    "python-$pythonVersao-amd64.exe" = "759BE887B96E736A3CA886DAF8D575F18FCAE1A09EFAB6902F42D59E8999F8EF"
    "python-$pythonVersao.exe"       = "963DEF30C7EBC6381A1EE9056D251DDC4520B18391DA2CF0602CFB58F5B80568"
}
$pastaPython = Join-Path $PSScriptRoot "python"
New-Item -ItemType Directory -Force -Path $pastaPython | Out-Null
foreach ($nome in $pythonHashes.Keys) {
    $arq = Join-Path $pastaPython $nome
    if (-not (Test-Path $arq)) {
        Write-Host "Baixando $nome (python.org)..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$pythonVersao/$nome" -OutFile $arq -UseBasicParsing
    }
    if ((Get-FileHash $arq -Algorithm SHA256).Hash -ne $pythonHashes[$nome]) {
        Remove-Item $arq -Force
        throw "SHA-256 de $nome nao confere com o oficial do python.org."
    }
}

Write-Host "[1/2] Compilando o motor (Inno Setup)..."
& $iscc /Q (Join-Path $raiz "Instalador.iss")
if ($LASTEXITCODE -ne 0) { throw "Falha no Inno Setup (codigo $LASTEXITCODE)." }
$motor = Join-Path $raiz "InstaladorInno.exe"

$versao = ((Select-String -Path (Join-Path $raiz "nupdf\versao.py") -Pattern '^VERSAO = "' |
    Select-Object -First 1).Line -split '"')[1]
$assemblyInfo = Join-Path $env:TEMP "nupdf_instalador_versao.cs"
@"
using System.Reflection;
[assembly: AssemblyVersion("$versao")]
[assembly: AssemblyFileVersion("$versao")]
[assembly: AssemblyInformationalVersion("$versao")]
"@ | Set-Content -Path $assemblyInfo -Encoding ascii

Write-Host "[2/2] Compilando a janela de instalacao ($versao)..."
& $csc /nologo /target:winexe /optimize+ /out:"$raiz\Instalador.exe" `
    /win32icon:"$raiz\assets\nupdf.ico" /win32manifest:"$PSScriptRoot\instalador.manifest" `
    /resource:"$motor,NuPDF.Motor.exe" /resource:"$PSScriptRoot\logo.png,NuPDF.Logo.png" `
    /r:System.dll /r:System.Core.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll `
    "$PSScriptRoot\Setup.cs" $assemblyInfo
$codigo = $LASTEXITCODE
Remove-Item $assemblyInfo -Force -ErrorAction SilentlyContinue
if ($codigo -ne 0) { throw "Falha ao compilar Setup.cs (codigo $codigo)." }
Write-Host "Instalador.exe gerado em $raiz"
