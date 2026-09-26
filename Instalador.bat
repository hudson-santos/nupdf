@echo off
:: Atalho de conveniencia para uso direto/manual (duplo clique) - toda a
:: logica de instalacao mora em instalar.ps1 (fonte unica, reaproveitada
:: tambem pelo Instalador.exe via Inno Setup, ver Instalador.iss).
if "%~1"=="--maximizado" goto :inicio_instalador
start "Instalador NuPDF" /MAX /wait "%~f0" --maximizado
exit /b

:inicio_instalador
title Instalador NuPDF
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
