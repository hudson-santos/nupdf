<#
    Limpeza da desinstalação do NuPDF - executado pelo desinstalador do Inno
    Setup ([UninstallRun] em Instalador.iss) ANTES de os arquivos serem
    removidos. Desfaz o que o instalar.ps1 cria fora do controle do Inno:

      1. encerra o NuPDF aberto (só processos do NuPDF, nunca outros pythonw);
      2. remove os atalhos da Área de Trabalho e do Menu Iniciar;
      3. remove o registro em "Abrir com" para .pdf (HKCU).

    A pasta C:\NuPDF (venv, NuPDF.exe etc.) é apagada pelo próprio Inno
    ([UninstallDelete]). As preferências do usuário em %APPDATA%\NuPDF são
    mantidas.
#>
$ErrorActionPreference = "SilentlyContinue"

# 1) NuPDF aberto
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe' or Name='NuPDF.exe'" |
    Where-Object { $_.Name -eq "NuPDF.exe" -or ($_.CommandLine -and $_.CommandLine -like "*NuPDF*main.py*") }
if ($procs) {
    $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep -Seconds 2  # libera os arquivos em uso (dlls do venv)
}

# 2) Atalhos
foreach ($pasta in "Desktop", "Programs") {
    Remove-Item (Join-Path ([Environment]::GetFolderPath($pasta)) "NuPDF.lnk") -Force
}

# 3) "Abrir com" (.pdf)
$classes = "HKCU:\Software\Classes"
Remove-Item "$classes\NuPDF.Documento" -Recurse -Force
Remove-Item "$classes\Applications\NuPDF.exe" -Recurse -Force
Remove-ItemProperty -Path "$classes\.pdf\OpenWithProgids" -Name "NuPDF.Documento" -Force
exit 0
