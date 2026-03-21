# Pipit Clone (Windows) - Parakeet TDT STT

Minimal Windows desktop MVP inspired by a voice-first “pipit”-style workflow.

Core flow:
- press and hold Right Alt
- capture microphone audio
- send it to a local Parakeet TDT STT endpoint
- paste transcript into the currently active app (and also show it in the UI)

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
- `PIPIT_STT_PROMPT` (default: `en`, use `ja` for Japanese)
- `PIPIT_STT_TIMEOUT_SECONDS` (default: `120`)
- `PIPIT_ONNX_ASR_MODEL` (default: `nemo-parakeet-tdt-0.6b-v3`)
- `PIPIT_ONNX_ASR_PROVIDERS` (default: `DmlExecutionProvider,CPUExecutionProvider`)
- `PIPIT_PARKEET_WIN_URL` (default: HuggingFace link for `parakeet-win-0707.7z`)
- `PIPIT_PARKEET_INSTALL_DIR` (default: under `%LOCALAPPDATA%`)
- `PIPIT_PARKEET_AUTO_DOWNLOAD` (default: `1`)
- `PIPIT_PARKEET_SOURCE_FALLBACK` (default: `1`; auto-bootstraps `jianchang512/parakeet-api` if package URL is dead)

Example:

```powershell
$env:PIPIT_STT_API_URL="http://127.0.0.1:5092/v1/audio/transcriptions"
$env:PIPIT_STT_PROMPT="en"
$env:PIPIT_STT_TIMEOUT_SECONDS="120"
```

Example (force HTTP backend):

```powershell
$env:PIPIT_STT_BACKEND="http"
```

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m pipit_clone
```

## Test (manual)

1. Launch Notepad (or any text field in any app).
2. Start `pipit_clone`.
3. Click into Notepad so the caret is active.
4. Hold **Right Ctrl**, speak, then release.
5. Expected:
   - transcript appears in the Pipit Clone window
   - same transcript is pasted at your active cursor

## Startup progress

The app now shows a progress bar:
- archive download progress (%) when available
- indeterminate progress during dependency install/model initialization
- ready/failed state once startup completes

## Notes / Limitations

- This MVP uses “push-to-talk” (transcribe after you release Right Alt), not true word-level streaming.
- First startup can be very long in fallback mode because Python dependencies and models are downloaded.
- If the Parakeet all-in-one package changes its local API contract, you may need to adjust `pipit_clone/stt_client.py`.

