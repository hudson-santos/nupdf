# Gera o Instalador.exe distribuído (raiz do projeto), em três partes:
#   1. Python embutido (build\python): embeddable oficial + dependências já instaladas
#   2. Inno Setup: Instalador.iss -> InstaladorInno.exe (o motor da instalação)
#   3. csc.exe do .NET Framework do Windows: instalador\Setup.cs -> Instalador.exe,
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

# Python EMBUTIDO no NuPDF (build\python -> C:\NuPDF\python): o pacote "embeddable"
# oficial do python.org + as dependências (requirements.txt) já instaladas aqui no
# build. A máquina do usuário não precisa de Python, pip nem internet para instalar.
$pythonVersao = "3.14.8"
$pythonZip = "python-$pythonVersao-embed-amd64.zip"
$pythonZipHash = "A93ABE456AB01BD96D7A085B3CDB6566B3063F4241360D114142FBDB07F0A310"  # SHA-256 oficial
$cache = Join-Path $PSScriptRoot "python"   # fora do git
$destPython = Join-Path $raiz "build\python"  # fora do git; o Instalador.iss copia para {app}\python

Write-Host "[1/3] Montando o Python embutido ($pythonVersao)..."
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$zip = Join-Path $cache $pythonZip
if (-not (Test-Path $zip)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$pythonVersao/$pythonZip" -OutFile $zip -UseBasicParsing
}
if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $pythonZipHash) {
    Remove-Item $zip -Force
    throw "SHA-256 de $pythonZip nao confere com o oficial do python.org."
}
if (Test-Path $destPython) { Remove-Item $destPython -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $destPython -Force
# sys.path fixo e isolado: biblioteca padrão, site-packages e a pasta do app (..) para
# importar nupdf/. Sem "import site": nada de pacotes do usuário (%APPDATA%\Python)
# se misturando com os do NuPDF (nenhuma dependência usa arquivos .pth).
$pth = Get-ChildItem $destPython -Filter "python*._pth" | Select-Object -First 1
$zipStd = (Get-ChildItem $destPython -Filter "python3*.zip" | Select-Object -First 1).Name
Set-Content -Path $pth.FullName -Encoding ascii -Value @($zipStd, ".", "Lib\site-packages", "..")

# Dependências: pip do Python do build (qualquer versão) baixando os wheels prontos
# para CPython 3.14 / Windows 64 bits direto na pasta do Python embutido.
$hostPy = @((Join-Path $raiz "venv\Scripts\python.exe")) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $hostPy) { $hostPy = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $hostPy) { throw "Python do build (para o pip) nao encontrado." }
$sitePackages = Join-Path $destPython "Lib\site-packages"
& $hostPy -m pip install -q --disable-pip-version-check --no-compile --target $sitePackages `
    --platform win_amd64 --python-version 3.14 --implementation cp --abi cp314 --only-binary=:all: `
    -r (Join-Path $raiz "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependencias no Python embutido." }

# Enxuga o PySide6: o NuPDF usa só QtCore, QtGui, QtWidgets, QtNetwork, QtPrintSupport e
# QtSvg. Fora: QML/Quick, Designer, ferramentas (.exe), traduções do Qt, OpenGL por
# software, stubs (.pyi) e afins (~150 MB a menos).
$pyside = Join-Path $sitePackages "PySide6"
$modulos = "QtCore", "QtGui", "QtWidgets", "QtNetwork", "QtPrintSupport", "QtSvg"
Get-ChildItem $pyside -File | Where-Object {
    ($_.Extension -eq ".pyd" -and $_.BaseName -like "Qt*" -and $modulos -notcontains $_.BaseName) -or
    ($_.Extension -eq ".dll" -and $_.BaseName -like "Qt6*" -and $modulos -notcontains ("Qt" + $_.BaseName.Substring(3))) -or
    $_.Extension -in ".exe", ".pyi" -or $_.Name -eq "opengl32sw.dll"
} | Remove-Item -Force
foreach ($d in "qml", "translations", "resources", "metatypes", "include", "typesystems", "glue", "scripts",
               "doc", "examples", "plugins\designer", "plugins\qmllint", "plugins\qmltooling", "plugins\sqldrivers") {
    $alvo = Join-Path $pyside $d
    if (Test-Path $alvo) { Remove-Item $alvo -Recurse -Force }
}
Get-ChildItem $sitePackages -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
$mb = [math]::Round(((Get-ChildItem $destPython -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB)
Write-Host "      Python embutido pronto: $mb MB em $destPython"

Write-Host "[2/3] Compilando o motor (Inno Setup)..."
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

Write-Host "[3/3] Compilando a janela de instalacao ($versao)..."
& $csc /nologo /target:winexe /optimize+ /out:"$raiz\Instalador.exe" `
    /win32icon:"$raiz\assets\nupdf.ico" /win32manifest:"$PSScriptRoot\instalador.manifest" `
    /resource:"$motor,NuPDF.Motor.exe" /resource:"$PSScriptRoot\logo.png,NuPDF.Logo.png" `
    /r:System.dll /r:System.Core.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll `
    "$PSScriptRoot\Setup.cs" $assemblyInfo
$codigo = $LASTEXITCODE
Remove-Item $assemblyInfo -Force -ErrorAction SilentlyContinue
if ($codigo -ne 0) { throw "Falha ao compilar Setup.cs (codigo $codigo)." }
Write-Host "Instalador.exe gerado em $raiz"
