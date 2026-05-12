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

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv was not found. Run setup.bat first.
  pause
  exit /b 1
)

echo Sending message to inbox...
".venv\Scripts\python.exe" -m scripts.send_message %*
if errorlevel 1 (
  echo ERROR: Failed to append message to inbox.
  pause
  exit /b 1
)

echo Running interactive tick...
".venv\Scripts\python.exe" alive_agent/main.py --interactive
if errorlevel 1 (
  echo ERROR: Interactive tick failed.
  pause
  exit /b 1
)

echo.
".venv\Scripts\python.exe" -m scripts.show_latest_outbox
pause
endlocal
