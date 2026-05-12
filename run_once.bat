@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv was not found. Run setup.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" alive_agent/main.py --once

echo.
pause
endlocal
