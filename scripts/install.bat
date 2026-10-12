@echo off
rem Doble clic para instalar: ejecuta install.ps1 sin cambiar la política de ejecución del sistema.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
