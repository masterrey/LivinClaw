@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv was not found. Run setup.bat first.
  pause
  exit /b 1
)

if not exist "config.yaml" (
  echo ERROR: config.yaml was not found. Run setup.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m scripts.console_chat
if errorlevel 1 (
  echo.
  echo ERROR: Console chat exited with an error.
  pause
  exit /b 1
)

echo.
pause
endlocal
