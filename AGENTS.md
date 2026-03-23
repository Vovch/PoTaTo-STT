# Agent instructions (Pipit Clone)

Minimal Windows desktop voice-to-text MVP (PySide6, push-to-talk with **Right Ctrl**, Parakeet / ONNX ASR). See `README.md` for user-facing setup and behavior.

## Always verify your work

Before you consider a task done:

1. **Run what you changed.** After editing Python, at minimum import or launch the app so obvious errors surface (e.g. activate the venv and run `python -m pipit_clone`, or a focused one-liner that exercises the module you touched).
2. **Check diagnostics** on files you edited (editor/linter diagnostics; fix new issues you introduced).
3. **Prefer automated checks when they exist.** If the project adds formatters, linters, or tests later, run the commands documented below and keep them green.
4. **If you cannot run the app** (headless environment, missing audio/GPU), say what you verified instead (syntax, static reasoning, partial command output) and what remains for a human.

Skipping verification because a change “looks obvious” is not acceptable.

## Environment

- **OS:** Windows is the primary target for the desktop app.
- **Python:** Use a virtual environment at the repo root.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional extras: `requirements-docker.txt`, `requirements-build.txt` (see `Dockerfile`, `build_windows_exe.ps1`).

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m pipit_clone
```

## Testing

There is no automated test suite in this repo yet. Use the **manual** flow in `README.md` (Notepad or another app, focus the caret, hold Right Ctrl, speak, release) when you change behavior that affects capture, STT, or paste.

If you add tests or CI, document the exact commands here and treat them as mandatory before merge.

## Build / packaging (when relevant)

- **Windows EXE:** `.\build_windows_exe.ps1` from repo root (requires `requirements-build.txt` / PyInstaller as in the script).
- **Docker (Linux GUI / X11):** see `docker-compose.yml` and `Dockerfile` — not a substitute for Windows desktop validation.

## Code style

- Keep changes **minimal and scoped** to the request; match existing patterns in `pipit_clone/`.
- Do not add unsolicited docs or refactors outside the task.
- Environment variables and STT wiring are documented in `README.md`; keep code and env docs aligned when you change contracts.

## How this file should work

- **Operational commands** over vague advice: prefer concrete PowerShell snippets and “done means X.”
- **Single source of truth:** project-wide agent rules live here; nested `AGENTS.md` files are only needed if the repo grows a monorepo layout.
- **Conflicts:** if instructions disagree, `README.md` wins for product behavior; update this file when tooling or workflows change.
