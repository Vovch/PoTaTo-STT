# Release notes

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
