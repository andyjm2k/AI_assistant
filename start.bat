@echo off
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

call "%ROOT%\venv\Scripts\activate.bat"
"%ROOT%\venv\Scripts\python.exe" "%ROOT%\scripts\start_all.py"
pause
