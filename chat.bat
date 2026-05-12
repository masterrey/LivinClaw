@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: .venv was not found. Run setup.bat first.
  pause
  exit /b 1
)

if not exist "config.yaml" (
  echo ERROR: config.yaml was not found. Run setup.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate .venv
  pause
  exit /b 1
)

python scripts\console_chat.py
if errorlevel 1 (
  echo.
  echo ERROR: Console chat exited with an error.
  pause
  exit /b 1
)

echo.
pause
endlocal
