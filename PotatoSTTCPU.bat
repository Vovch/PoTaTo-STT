@echo off
setlocal
REM Launch Potato STT with built-in ONNX ASR on CPU only (no DirectML in this process).
set POTATO_STT_CPU_ONLY=1
if exist "PotatoSTT.exe" (
  start "" "%~dp0PotatoSTT.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m potato_stt
) else (
  python -m potato_stt
)
