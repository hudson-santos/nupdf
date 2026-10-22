<#
    Impressora NuPDF - instala ou remove (executado com administrador, pela
    confirmação do Windows, a partir do NuPDF - nupdf/impressora_virtual.py - ou do
    Instalador.exe na instalação manual - instalador\Setup.cs).

    Mesmo modelo do PDF24: impressora "NuPDF" com o driver "Microsoft Print To PDF"
    do Windows e, como porta, o pipe \\.\pipe\NuPDFPrint - o agente do NuPDF
    (main.py --impressora) recebe por ele o PDF de cada impressão.

    Uso: powershell -ExecutionPolicy Bypass -File impressora.ps1 -Acao instalar|remover
    Log em %TEMP%\nupdf_impressora.log (o do administrador).
#>
param(
    [ValidateSet("instalar", "remover")]
    [string]$Acao = "instalar"
)

$ErrorActionPreference = "Stop"
$NOME = "NuPDF"
$PORTA = "\\.\pipe\NuPDFPrint"
$DRIVER = "Microsoft Print To PDF"
Start-Transcript -Path (Join-Path $env:TEMP "nupdf_impressora.log") -Force | Out-Null

function Garantir-Driver {
    if (Get-PrinterDriver -Name $DRIVER -ErrorAction SilentlyContinue) { return }
    Write-Host "Instalando o driver $DRIVER..."
    try {
        Add-PrinterDriver -Name $DRIVER   # do repositório de drivers do Windows
    } catch {
        # o driver vem com o recurso opcional "Microsoft Print to PDF" do Windows
        Enable-WindowsOptionalFeature -Online -FeatureName "Printing-PrintToPDFServices-Features" -All -NoRestart | Out-Null
        if (-not (Get-PrinterDriver -Name $DRIVER -ErrorAction SilentlyContinue)) {
            Add-PrinterDriver -Name $DRIVER
        }
    }
}

try {
    if ($Acao -eq "instalar") {
        Garantir-Driver
        if (-not (Get-PrinterPort -Name $PORTA -ErrorAction SilentlyContinue)) {
            Write-Host "Criando a porta $PORTA..."
            Add-PrinterPort -Name $PORTA
        }
        if (-not (Get-Printer -Name $NOME -ErrorAction SilentlyContinue)) {
            Write-Host "Criando a impressora $NOME..."
            Add-Printer -Name $NOME -DriverName $DRIVER -PortName $PORTA
        }
        Write-Host "Impressora $NOME instalada."
    } else {
        if (Get-Printer -Name $NOME -ErrorAction SilentlyContinue) {
            Remove-Printer -Name $NOME
        }
        if (Get-PrinterPort -Name $PORTA -ErrorAction SilentlyContinue) {
            try { Remove-PrinterPort -Name $PORTA } catch { Write-Host "Porta em uso; sai na próxima reinicialização." }
        }
        Write-Host "Impressora $NOME removida."
    }
    $codigo = 0
} catch {
    Write-Host "[ERRO] $_"
    $codigo = 1
}
Stop-Transcript | Out-Null
exit $codigo
