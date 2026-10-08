@echo off
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py --yes --no-preview %*
) else (
  python main.py --yes --no-preview %*
)
endlocal
