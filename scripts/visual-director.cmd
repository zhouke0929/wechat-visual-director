@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0visual-director.ps1" %*
exit /b %errorlevel%
