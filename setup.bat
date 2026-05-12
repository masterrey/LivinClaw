@echo off
setlocal
cd /d "%~dp0"

echo [1/6] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python was not found in PATH.
  echo Install Python 3.10+ and enable "Add Python to PATH", then run setup.bat again.
  pause
  exit /b 1
)

echo [2/6] Creating local virtual environment (.venv) if needed...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create .venv
    pause
    exit /b 1
  )
) else (
  echo .venv already exists.
)

echo [3/6] Activating .venv...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate .venv
  pause
  exit /b 1
)

echo [4/6] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo ERROR: Failed to upgrade pip
  pause
  exit /b 1
)

echo [5/6] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Failed to install dependencies
  pause
  exit /b 1
)

echo [6/6] Bootstrapping local config and workspace files...
python scripts/bootstrap_first_run.py
if errorlevel 1 (
  echo ERROR: Failed to bootstrap config/workspace
  pause
  exit /b 1
)

echo.
echo Setup completed successfully.
echo Next steps:
echo   1) Start LM Studio and load a chat model
echo   2) (Optional) test endpoint: curl http://127.0.0.1:1234/v1/models
echo   3) Run tests: run_tests.bat
echo   4) Run one tick: run_once.bat
echo   5) Run continuous mode: run_alive.bat
echo See FIRST_RUN.md for details.
pause
endlocal
