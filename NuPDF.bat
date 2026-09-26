@echo off
rem Executa o NuPDF a partir desta pasta de desenvolvimento (sem console).
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py" %*
