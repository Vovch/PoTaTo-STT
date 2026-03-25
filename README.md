# Pipit Clone (Windows) - Parakeet TDT STT

Minimal Windows desktop MVP inspired by a voice-first “pipit”-style workflow.

Core flow:
- press and hold your **push-to-talk key(s)** (default: **Right Ctrl**; configure under **Options** — add several keys or mouse buttons, or capture any key/button by choosing **Add key…**)
- capture microphone audio
- transcribe (default: ONNX ASR / Parakeet TDT)
- paste into the app that had focus when you **pressed** the key (also mirrored in this window)

**Paste troubleshooting:** If text only appears here, click the target text field first, then use push-to-talk. Windows may block focus steal for elevated (Run as administrator) apps unless Pipit Clone is also elevated.

## How STT runs (Parakeet TDT on Windows)

This app auto-downloads a community “Parakeet Windows all-in-one package” (a `.7z`), runs `启动.bat`, and uses its local OpenAI-compatible API.

The API is expected at:
- `POST http://127.0.0.1:5092/v1/audio/transcriptions`

On first run, the service downloads the speech models (can take time).

## Install

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configure STT endpoint

Environment variables (optional):

- `PIPIT_STT_BACKEND` (default: `onnx_asr`; options: `onnx_asr`, `http`)
- `PIPIT_STT_API_URL` (default: `http://127.0.0.1:5092/v1/audio/transcriptions`)
- `PIPIT_STT_MODEL` (default: `parakeet`)
- `PIPIT_STT_TIMEOUT_SECONDS` (default: `120`)
- `PIPIT_ONNX_ASR_MODEL` (default: `nemo-parakeet-tdt-0.6b-v3`)
- `PIPIT_ONNX_ASR_PROVIDERS` (default: `DmlExecutionProvider,CPUExecutionProvider`; ignored when CPU-only is on)
- `PIPIT_CPU_ONLY` (default: `0`; set to `1` to run built-in ONNX ASR on **CPU only** and avoid GPU/DirectML VRAM for inference in this process)
- `PIPIT_PARKEET_WIN_URL` (default: HuggingFace link for `parakeet-win-0707.7z`)
- `PIPIT_PARKEET_INSTALL_DIR` (default: under `%LOCALAPPDATA%`)
- `PIPIT_PARKEET_AUTO_DOWNLOAD` (default: `1`)
- `PIPIT_PARKEET_SOURCE_FALLBACK` (default: `1`; auto-bootstraps `jianchang512/parakeet-api` if package URL is dead)

Example:

```powershell
$env:PIPIT_STT_API_URL="http://127.0.0.1:5092/v1/audio/transcriptions"
$env:PIPIT_STT_TIMEOUT_SECONDS="120"
```

Example (force HTTP backend):

```powershell
$env:PIPIT_STT_BACKEND="http"
```

Example (CPU-only ONNX inference — no DirectML/GPU in this app):

```powershell
$env:PIPIT_CPU_ONLY="1"
python -m pipit_clone
```

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m pipit_clone
```

## Build Windows executable (PyInstaller)

The build script creates a **one-folder** bundle under `dist\PipitClone\` (recommended for Qt, ONNX Runtime, and DirectML). Ship the **entire** `PipitClone` folder, not only `PipitClone.exe`.

From the project root:

```powershell
.\build_windows_exe.ps1
```

This creates `.venv` if needed, installs `requirements.txt` plus `requirements-build.txt` (PyInstaller), and runs `pipit_clone.spec`.

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller pipit_clone.spec --clean --noconfirm
Copy-Item -Force PipitCloneCPU.bat dist\PipitClone\PipitCloneCPU.bat
```

The build script copies **`PipitCloneCPU.bat`** into `dist\PipitClone\` next to `PipitClone.exe` (PyInstaller alone puts bundled data under `_internal`, so the batch file is copied separately). Use it to start the app with **`PIPIT_CPU_ONLY=1`** (ONNX on CPU only). The same `PipitCloneCPU.bat` in the repo root can launch from source: it runs `PipitClone.exe` when present, otherwise `.venv\python` or `python -m pipit_clone`.

Use a **dedicated virtual environment** that only contains this app’s dependencies. If unrelated packages (for example large ML stacks) are installed in the same environment, PyInstaller may bundle them and the output will be much larger. If `venv` recreation fails with “access denied” on `.venv\Scripts\python.exe`, close other tools that use that interpreter (editor language servers, running instances of the app), then run the script again.

## Test (manual)

1. Launch Notepad (or any text field in any app).
2. Start `pipit_clone`.
3. Click into Notepad so the caret is active.
4. Hold your push-to-talk key (default **Right Ctrl**), speak, then release.
5. Expected:
   - transcript appears in the Pipit Clone window
   - same transcript is pasted at your active cursor

## Startup progress

The app now shows a progress bar:
- archive download progress (%) when available
- indeterminate progress during dependency install/model initialization
- ready/failed state once startup completes

## Notes / Limitations

- `PIPIT_CPU_ONLY=1` applies to the **built-in ONNX ASR** backend (`PIPIT_STT_BACKEND=onnx_asr`). The separate **HTTP** Parakeet service (`PIPIT_STT_BACKEND=http`) runs its own Python process and may still use GPU unless you configure that stack separately.
- This MVP uses “push-to-talk” (transcribe after you release the key), not true word-level streaming.
- First startup can be very long in fallback mode because Python dependencies and models are downloaded.
- If the Parakeet all-in-one package changes its local API contract, you may need to adjust `pipit_clone/stt_client.py`.
