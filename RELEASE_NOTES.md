# Release notes

## Potato STT v1.3 — 2026-03-28 (commit `8b77d78`)

**Subject:** Rename to Potato STT; file transcription, tests, and UI polish.

### Breaking changes and migration (from Pipit Clone)

- **Python package:** `pipit_clone` → `potato_stt`. Run with `python -m potato_stt`.
- **Windows bundle:** `dist\PotatoSTT\PotatoSTT.exe` (ship the whole folder). Launcher **`PotatoSTTCPU.bat`** replaces `PipitCloneCPU.bat` (CPU-only ONNX for this process).
- **Environment variables:** prefer **`POTATO_STT_*`**; legacy **`PIPIT_*`** is still read by `potato_stt/config.py` where documented in README.
- **Saved settings and startup:** `QSettings` org/app **`PotatoSTT` / `PotatoSTT`**; Run value name **`PotatoSTT`**. After upgrading, open **Options** again and re-enable “Launch at startup” if you use it.
- **Parakeet install path (default):** `%LOCALAPPDATA%\potato_stt\` (legacy installs may still live under `%LOCALAPPDATA%\pipit_clone\`).

### New and changed behavior

- **File → Transcribe media file…** (also toolbar and tray): transcribe an existing audio/video file; transcript is **appended only in the Potato STT window** (no paste into the previously focused app).
- **Long files:** time-based chunking using **`POTATO_STT_TRANSCRIBE_CHUNK_SECONDS`** (default 120s, clamped in code) to limit RAM and avoid full-file ONNX loads. **FFmpeg/ffprobe** on `PATH` needed for non–16 kHz mono WAV and for duration probing on long media.
- **Subtitles:** after a successful run, save **`.srt`** or **`.vtt`**. Subtitle cue layout uses improved word-boundary heuristics. ONNX backend uses token timestamps when available; HTTP backend prefers timed segments from the service, with an even-split fallback.
- **ONNX ASR:** if DirectML/GPU runs out of memory during model load, the app **falls back to CPU** and surfaces a status message. Set **`POTATO_STT_CPU_ONLY=1`** (or **`PIPIT_CPU_ONLY`**) to skip the GPU path from the start.
- **UI:** **File** and **Settings** menus, **QToolBar** (“Transcribe file”, “Options”); file-transcribe completion returns to a clear **Ready** state (fixes progress stuck on “Working” after a successful run).
- **Parakeet Windows installer:** child-process env includes **`POTATO_STT_DISABLE_PARAKEET_WEBOPEN`** (legacy **`PIPIT_DISABLE_PARAKEET_WEBOPEN`** still honored where applicable).

### Tests and tooling

- **Unit tests:** `tests/run_tests.py` (stdlib **unittest** discovery), with `tests/test_media_decode.py`, `tests/test_subtitle_export.py`, `tests/test_file_transcribe.py`, and `tests/helpers.py`.
- **`requirements-dev.txt`** and **`pytest.ini`** for optional pytest workflows.
- **`.gitignore`:** local media test folder pattern (e.g. `test_file/`) ignored.

### Packaging

- **PyInstaller:** `potato_stt.spec`; **`build_windows_exe.ps1`** builds `dist\PotatoSTT\` and copies **`PotatoSTTCPU.bat`** next to the executable.

---

## v1.2 — 2026-03-25

### Push-to-talk

- Configurable **push-to-talk keys** stored in `QSettings` (`push_to_talk_keys` JSON list).
- **Options** window: list of bindings, **Add key…** (capture any keyboard key or mouse button), **Remove selected**.
- Support for **multiple keys at once**: hold any configured key/button; recording continues while at least one binding is held; stops when the last one is released.
- **Default** when the list is empty: **Right Ctrl** (same as a fresh install).
- New modules: `pipit_clone/ptt_keys.py` (spec strings, matching, labels), `pipit_clone/ptt_capture.py` (modal capture via pynput).

### Windows startup

- **Launch Pipit Clone at Windows startup** (user logon) via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (`PipitClone` value).
- New module: `pipit_clone/win32_startup.py` (build launch command for frozen exe or `pythonw -m pipit_clone`).

### STT / language

- Removed **language / prompt** wiring that did not match the current Parakeet ONNX workflow: dropped `PIPIT_STT_PROMPT` / `stt_prompt`, HTTP `prompt` / `language` fields in `stt_client`, and the `language` argument to ONNX `transcribe_wav`.
- README and examples updated accordingly.

### UI / docs

- Main window **Options** (gear control), help/tray copy aligned with configurable PTT.
- `AGENTS.md` and `README.md` updated for push-to-talk and STT configuration.

### Technical

- Large updates in `pipit_clone/ui_main.py` (options UI, PTT listeners, startup checkbox, styling fixes as staged).

---

*Previous tags in this repo: `v1`, `v1.1`.*
