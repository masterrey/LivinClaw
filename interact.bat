@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: interact.bat "@task Create a summary of the current architecture"
  echo        interact.bat "@ask What is your current status?"
  echo        interact.bat "@note Prefer short answers during first-run tests"
  echo.
  echo This sends a message safely to the inbox and immediately runs one interactive tick.
  pause
  exit /b 1
)

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

echo Sending message to inbox...
python -m scripts.send_message %*
if errorlevel 1 (
  echo ERROR: Failed to append message to inbox.
  pause
  exit /b 1
)

echo Running interactive tick...
python alive_agent/main.py --interactive
if errorlevel 1 (
  echo ERROR: Interactive tick failed.
  pause
  exit /b 1
)

echo.
python scripts\show_latest_outbox.py
pause
endlocal
