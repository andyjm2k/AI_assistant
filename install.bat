@echo off
REM CATBot automated installer (Windows). Run from project root.
REM Calls install.ps1; requires PowerShell.

set "ROOT=%~dp0"
if not "%ROOT:~-1%"=="" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set EXIT=%ERRORLEVEL%
if %EXIT% neq 0 exit /b %EXIT%
exit /b 0
