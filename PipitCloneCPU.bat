@echo off
setlocal
cd /d "%~dp0"
set PIPIT_CPU_ONLY=1
if exist "PipitClone.exe" (
  start "" "%~dp0PipitClone.exe"
  exit /b 0
)
if exist ".venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m pipit_clone
) else (
  python -m pipit_clone
)
