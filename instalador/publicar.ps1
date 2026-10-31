<#
    Publica uma versão do NuPDF no Cloudflare R2 (bucket "nds", domínio público
    https://arquivos.nukt.com.br) - o Instalador.exe é compilado só aqui, localmente
    (o GitHub Actions não compila mais nada):

      1. compila o Instalador.exe (instalador\compilar_instalador.ps1);
      2. monta build\publicacao\ com Instalador-X.Y.Z.exe e versao.json (versão, URL,
         SHA-256, tamanho, data e as novidades da seção da versão no CHANGELOG.md);
      3. envia para atualizacoes/nupdf/ no R2: Instalador-X.Y.Z.exe, Instalador.exe
         (link fixo da última versão, usado pelo site) e, por último, versao.json - só
         então os NuPDF instalados enxergam a versão nova (nupdf/atualizacao.py);
      4. confere o versao.json e o instalador publicados pela URL pública.

    Uso (depois de atualizar nupdf/versao.py e o CHANGELOG.md):
      powershell -ExecutionPolicy Bypass -File instalador\publicar.ps1 [-SemCompilar] [-Minima X.Y.Z] [-SemEnviar]

    Envio com o wrangler (npx), usando o login do Cloudflare desta máquina - se
    expirar, rode uma vez num terminal: npx wrangler login
#>
param(
    [switch]$SemCompilar,   # usa o Instalador.exe já compilado (precisa ser da versão atual)
    [string]$Minima = "",   # versão mínima suportada no versao.json (padrão: a própria versão)
    [switch]$SemEnviar      # só monta build\publicacao (conferência), sem enviar ao R2
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$BUCKET = "nds"
$PASTA_R2 = "atualizacoes/nupdf"
$URL_BASE = "https://arquivos.nukt.com.br/$PASTA_R2"

$versao = ((Select-String -Path (Join-Path $raiz "nupdf\versao.py") -Pattern '^VERSAO = "' |
    Select-Object -First 1).Line -split '"')[1]
if (-not $versao) { throw "VERSAO nao encontrada em nupdf\versao.py." }
if (-not $Minima) { $Minima = $versao }
Write-Host "Publicando o NuPDF $versao em $URL_BASE"

# ---------------------------------------------------------------- 1) Instalador.exe
if (-not $SemCompilar) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "compilar_instalador.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o Instalador.exe." }
}
$exe = Join-Path $raiz "Instalador.exe"
if (-not (Test-Path $exe)) { throw "Instalador.exe nao encontrado em $raiz." }
$versaoExe = (Get-Item $exe).VersionInfo.FileVersion
if ($versaoExe -ne $versao) { throw "O Instalador.exe e da versao $versaoExe, nao da ${versao} - compile de novo." }

# ---------------------------------------------------------------- 2) versao.json
# novidades = itens "- ..." da seção "## [X.Y.Z] - " do CHANGELOG (continuações indentadas juntas)
$novidades = New-Object System.Collections.Generic.List[string]
$dentro = $false
foreach ($linha in (Get-Content (Join-Path $raiz "CHANGELOG.md") -Encoding UTF8)) {
    if ($linha.StartsWith("## [")) {
        if ($dentro) { break }
        $dentro = $linha.StartsWith("## [$versao] - ")
        continue
    }
    if (-not $dentro) { continue }
    if ($linha -match '^\s*[-*]\s+(.+)$') { $novidades.Add($Matches[1].Trim()) }
    elseif ($linha -match '^\s+\S' -and $novidades.Count -gt 0) {
        $novidades[$novidades.Count - 1] += " " + $linha.Trim()
    }
}
if ($novidades.Count -eq 0) { throw "Secao '## [$versao] - ' sem itens no CHANGELOG.md." }

$saida = Join-Path $raiz "build\publicacao"
if (Test-Path $saida) { Remove-Item $saida -Recurse -Force }
New-Item -ItemType Directory -Force -Path $saida | Out-Null
$nomeVersionado = "Instalador-$versao.exe"
$exeVersionado = Join-Path $saida $nomeVersionado
Copy-Item $exe $exeVersionado
$sha256 = (Get-FileHash $exeVersionado -Algorithm SHA256).Hash.ToLower()
$tamanho = (Get-Item $exeVersionado).Length

$info = [ordered]@{
    versao    = $versao
    minima    = $Minima
    url       = "$URL_BASE/$nomeVersionado"
    sha256    = $sha256
    tamanho   = $tamanho
    data      = (Get-Date -Format "yyyy-MM-dd")
    novidades = [string[]]$novidades.ToArray()
}
$json = Join-Path $saida "versao.json"
# UTF-8 sem BOM (o Set-Content -Encoding UTF8 do PowerShell 5.1 grava com BOM)
[IO.File]::WriteAllText($json, ($info | ConvertTo-Json -Depth 3), (New-Object Text.UTF8Encoding $false))
Write-Host "      versao.json: $versao, $([math]::Round($tamanho / 1MB, 1)) MB, sha256 $sha256"
if ($SemEnviar) {
    Write-Host "      -SemEnviar: nada enviado. Arquivos em $saida"
    exit 0
}

# ---------------------------------------------------------------- 3) envio ao R2
function Enviar([string]$arquivo, [string]$nome, [string]$tipo, [string]$cache) {
    Write-Host "      enviando $nome..."
    Push-Location $env:TEMP  # fora do repositório: o wrangler.jsonc da raiz é do site
    try {
        & npx.cmd --yes wrangler@4 r2 object put "$BUCKET/$PASTA_R2/$nome" --file $arquivo --remote `
            --content-type $tipo --cache-control $cache
        $codigo = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($codigo -ne 0) {
        throw "Falha ao enviar $nome ao R2. Se o login expirou, rode num terminal: npx wrangler login"
    }
}
Enviar $exeVersionado $nomeVersionado "application/vnd.microsoft.portable-executable" "public, max-age=31536000, immutable"
Enviar $exeVersionado "Instalador.exe" "application/vnd.microsoft.portable-executable" "no-cache"
Enviar $json "versao.json" "application/json; charset=utf-8" "no-cache"

# ---------------------------------------------------------------- 4) conferência pública
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$publicado = Invoke-RestMethod -Uri "$URL_BASE/versao.json?t=$([DateTimeOffset]::Now.ToUnixTimeSeconds())" -UseBasicParsing
if ($publicado.versao -ne $versao -or $publicado.sha256 -ne $sha256) {
    throw "O versao.json publicado nao confere (versao $($publicado.versao))."
}
$baixado = Join-Path $saida "conferencia.exe"
Invoke-WebRequest -Uri $publicado.url -OutFile $baixado -UseBasicParsing
if ((Get-FileHash $baixado -Algorithm SHA256).Hash.ToLower() -ne $sha256) {
    throw "O $nomeVersionado publicado nao confere com o SHA-256 do versao.json."
}
Remove-Item $baixado -Force
Write-Host ""
Write-Host "NuPDF $versao publicado:"
Write-Host "  $URL_BASE/versao.json"
Write-Host "  $URL_BASE/$nomeVersionado"
Write-Host "  $URL_BASE/Instalador.exe"
