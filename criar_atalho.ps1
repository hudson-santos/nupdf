<#
    Cria um atalho (.lnk) numa pasta especial do Windows.

    Existe à parte (em vez de mais um bloco `powershell -Command` inline
    no instalar.ps1) porque
    `.Arguments` aqui precisa ficar entre aspas (para o caminho do
    main.py sempre chegar como um único argumento pro pythonw.exe, seja
    lá o que tiver dentro de `$Arguments`) - e uma aspas literal dentro
    de um token já delimitado por aspas do cmd.exe (o jeito que os outros
    blocos inline são escritos, com continuação de linha via "^") quebra
    o parser do cmd.exe bem no meio (mesma causa raiz já documentada em
    outros comentários do Instalador.bat, para o download do Python e para
    o config.json). Como conteúdo de .ps1 não passa pelo parser do
    cmd.exe, aspas aqui dentro são só aspas normais do PowerShell.

    Uso:
        powershell -File criar_atalho.ps1 -Pasta "Desktop" -TargetPath "C:\NuPDF\NuPDF.exe" -WorkingDirectory "C:\NuPDF" -IconLocation "C:\NuPDF\assets\nupdf.ico"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Pasta,

    [Parameter(Mandatory = $true)]
    [string]$TargetPath,

    [string]$Arguments,

    [Parameter(Mandatory = $true)]
    [string]$WorkingDirectory,

    [Parameter(Mandatory = $true)]
    [string]$IconLocation
)

$caminhoAtalho = Join-Path ([Environment]::GetFolderPath($Pasta)) "NuPDF.lnk"

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($caminhoAtalho)
$sc.TargetPath = $TargetPath
if ($Arguments) {
    $sc.Arguments = '"' + $Arguments + '"'
}
$sc.WorkingDirectory = $WorkingDirectory
$sc.IconLocation = $IconLocation
$sc.Save()

Write-Host "      Atalho criado em $caminhoAtalho"
