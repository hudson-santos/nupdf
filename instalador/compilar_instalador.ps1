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
