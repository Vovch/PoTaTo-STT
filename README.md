# Potato STT (Windows) — Parakeet TDT STT

Minimal Windows desktop voice-to-text app: push-to-talk, optional file transcription, and subtitles.

Core flow:
- press and hold your **push-to-talk key(s)** (default: **Right Ctrl**; configure under **Options** — add several keys or mouse buttons, or capture any key/button by choosing **Add key…**)
- capture microphone audio
- transcribe (default: ONNX ASR / Parakeet TDT)
- paste into the app that had focus when you **pressed** the key (also mirrored in this window)

**Paste troubleshooting:** If text only appears here, click the target text field first, then use push-to-talk. Windows may block focus steal for elevated (Run as administrator) apps unless Potato STT is also elevated.

## Transcribe existing audio or video files

Use **File → Transcribe media file…** (or the toolbar / tray) to pick an audio or video file. The app runs the same STT backend as push-to-talk and **appends the transcript in the Potato STT window only** (it does **not** paste into whatever app is focused).

**Long files:** Media longer than **`POTATO_STT_TRANSCRIBE_CHUNK_SECONDS`** (default **120** seconds) is transcribed **in time segments** (small temp WAVs per segment). That avoids decoding a multi-hour file into one huge WAV and stops ONNX from loading the whole recording at once, which could **freeze the PC** from RAM pressure. Shorter files still use a single decode as before.

**FFmpeg / ffprobe:** Native **16 kHz mono PCM `.wav`** segment reads use Python’s `wave` module only. For other formats and for **duration probing** on long files, **FFmpeg and ffprobe** must be on your PATH (for example `winget install ffmpeg`). Without them, use a 16 kHz mono PCM WAV or install FFmpeg.

**Subtitles:** After a successful run, you can save **`.srt`** or **`.vtt`** subtitles.

- With **`POTATO_STT_BACKEND=onnx_asr`**, cues use **token timestamps** from the ONNX model when available (best alignment).
- With **`POTATO_STT_BACKEND=http`**, the client requests **`verbose_json`** when possible to obtain timed **segments** from the service. If the server does not return timings, subtitles fall back to **splitting the transcript into sentences and spacing them evenly** across the file duration (approximate sync only).

Each HTTP chunk uses the same timeout as push-to-talk (`POTATO_STT_TIMEOUT_SECONDS`). Tune segment length with `POTATO_STT_TRANSCRIBE_CHUNK_SECONDS` (seconds, clamped between 30 and 600 in code).

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

Environment variables (optional). Names use the **`POTATO_STT_`** prefix; the app still accepts legacy **`PIPIT_`** names where noted for older setups.

- `POTATO_STT_BACKEND` (default: `onnx_asr`; options: `onnx_asr`, `http`) — legacy: `PIPIT_STT_BACKEND`
- `POTATO_STT_API_URL` (default: `http://127.0.0.1:5092/v1/audio/transcriptions`) — legacy: `PIPIT_STT_API_URL`
- `POTATO_STT_MODEL` (default: `parakeet`) — legacy: `PIPIT_STT_MODEL`
- `POTATO_STT_TIMEOUT_SECONDS` (default: `120`) — legacy: `PIPIT_STT_TIMEOUT_SECONDS`
- `POTATO_STT_TRANSCRIBE_CHUNK_SECONDS` (default: `120`; long **file** transcription segment length) — legacy: `PIPIT_TRANSCRIBE_CHUNK_SECONDS`
- `POTATO_STT_ONNX_ASR_MODEL` (default: `nemo-parakeet-tdt-0.6b-v3`) — legacy: `PIPIT_ONNX_ASR_MODEL`
- `POTATO_STT_ONNX_ASR_PROVIDERS` (default: `DmlExecutionProvider,CPUExecutionProvider`; ignored when CPU-only is on) — legacy: `PIPIT_ONNX_ASR_PROVIDERS`
- `POTATO_STT_CPU_ONLY` (default: `0`; set to `1` for **CPU-only** ONNX in this process) — legacy: `PIPIT_CPU_ONLY`
- `POTATO_STT_PARAKEET_WIN_URL` (default: HuggingFace link for `parakeet-win-0707.7z`) — legacy: `PIPIT_PARKEET_WIN_URL`
- `POTATO_STT_PARAKEET_INSTALL_DIR` (default: under `%LOCALAPPDATA%\potato_stt\`) — legacy: `PIPIT_PARKEET_INSTALL_DIR`
- `POTATO_STT_PARAKEET_LAUNCH_TIMEOUT_SECONDS` (default: `1800`) — legacy: `PIPIT_PARKEET_LAUNCH_TIMEOUT_SECONDS`
- `POTATO_STT_PARAKEET_AUTO_DOWNLOAD` (default: `1`) — legacy: `PIPIT_PARKEET_AUTO_DOWNLOAD`
- `POTATO_STT_PARAKEET_SOURCE_FALLBACK` (default: `1`) — legacy: `PIPIT_PARKEET_SOURCE_FALLBACK`

Example:

```powershell
$env:POTATO_STT_API_URL="http://127.0.0.1:5092/v1/audio/transcriptions"
$env:POTATO_STT_TIMEOUT_SECONDS="120"
```

Example (force HTTP backend):

```powershell
$env:POTATO_STT_BACKEND="http"
```

Example (CPU-only ONNX inference — no DirectML/GPU in this app):

```powershell
$env:POTATO_STT_CPU_ONLY="1"
python -m potato_stt
```

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m potato_stt
```

## Build Windows executable (PyInstaller)

The build script creates a **one-folder** bundle under `dist\PotatoSTT\` (recommended for Qt, ONNX Runtime, and DirectML). Ship the **entire** `PotatoSTT` folder, not only `PotatoSTT.exe`.

From the project root:

```powershell
.\build_windows_exe.ps1
```

This creates `.venv` if needed, installs `requirements.txt` plus `requirements-build.txt` (PyInstaller), and runs `potato_stt.spec`.

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller potato_stt.spec --clean --noconfirm
Copy-Item -Force PotatoSTTCPU.bat dist\PotatoSTT\PotatoSTTCPU.bat
```

The build script copies **`PotatoSTTCPU.bat`** into `dist\PotatoSTT\` next to `PotatoSTT.exe` (PyInstaller alone puts bundled data under `_internal`, so the batch file is copied separately). Use it to start the app with **`POTATO_STT_CPU_ONLY=1`** (ONNX on CPU only). The same `PotatoSTTCPU.bat` in the repo root can launch from source: it runs `PotatoSTT.exe` when present, otherwise `.venv\python` or `python -m potato_stt`.

Use a **dedicated virtual environment** that only contains this app’s dependencies. If unrelated packages (for example large ML stacks) are installed in the same environment, PyInstaller may bundle them and the output will be much larger. If `venv` recreation fails with “access denied” on `.venv\Scripts\python.exe`, close other tools that use that interpreter (editor language servers, running instances of the app), then run the script again.

## Test (manual)

1. Launch Notepad (or any text field in any app).
2. Start Potato STT (`python -m potato_stt` or `PotatoSTT.exe`).
3. Click into Notepad so the caret is active.
4. Hold your push-to-talk key (default **Right Ctrl**), speak, then release.
5. Expected:
   - transcript appears in the Potato STT window
   - same transcript is pasted at your active cursor

## Startup progress

The app shows a progress bar:
- archive download progress (%) when available
- indeterminate progress during dependency install/model initialization
- ready/failed state once startup completes

## Notes / Limitations

- If **DirectML runs out of GPU memory** during ONNX load, the app **retries on CPU** automatically and shows a status message. Set `POTATO_STT_CPU_ONLY=1` to skip the GPU path entirely (recommended on low-VRAM systems).
- `POTATO_STT_CPU_ONLY=1` applies to the **built-in ONNX ASR** backend (`POTATO_STT_BACKEND=onnx_asr`). The separate **HTTP** Parakeet service (`POTATO_STT_BACKEND=http`) runs its own Python process and may still use GPU unless you configure that stack separately.
- This MVP uses “push-to-talk” (transcribe after you release the key), not true word-level streaming.
- First startup can be very long in fallback mode because Python dependencies and models are downloaded.
- If the Parakeet all-in-one package changes its local API contract, you may need to adjust `potato_stt/stt_client.py`.
