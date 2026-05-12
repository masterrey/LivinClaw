@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: .venv was not found. Run setup.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate .venv
  pause
  exit /b 1
)

python -m pip install -r requirements-ui.txt
if errorlevel 1 (
  echo ERROR: Failed to install UI dependencies from requirements-ui.txt
  pause
  exit /b 1
)

echo UI setup complete.
pause
endlocal
