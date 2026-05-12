@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: send_message.bat "@task Do something"
  echo        send_message.bat "@ask What is your status?"
  echo        send_message.bat "@note Prefer short answers"
  echo.
  echo Directives:
  echo   @task  - add a task for autonomous execution
  echo   @ask   - ask the agent a question
  echo   @note  - store a note in working memory
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv was not found. Run setup.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m scripts.send_message %*

echo.
pause
endlocal
