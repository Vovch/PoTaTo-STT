# Agent instructions (Potato STT)

Minimal Windows desktop voice-to-text MVP (PySide6, configurable push-to-talk key, Parakeet / ONNX ASR). See `README.md` for user-facing setup and behavior.

## Best practices for this repository

- **Scope:** Keep diffs minimal and tied to the request. Avoid drive-by refactors, unrelated file churn, and extra documentation unless the user asks for it.
- **Consistency:** Match naming, layout, and patterns already used in `potato_stt/`. Reuse helpers instead of duplicating logic.
- **Windows-first:** The app targets desktop Windows (audio, tray, global hotkeys, optional EXE). Consider tray, minimized startup, and focus behavior when changing the main window or options.
- **Contracts:** Environment variables, model paths, and STT behavior belong in `README.md` when user-visible; keep code and docs aligned when those contracts change.
- **Dependencies:** Prefer the versions pinned in `requirements.txt` / `requirements-build.txt`. If you add or upgrade a package, say so and update the appropriate requirements file.
- **Qt / settings:** `QSettings` uses org/app `PotatoSTT` / `PotatoSTT` in several places; keep keys consistent when adding persisted UI state.

## Always verify your work

Before you consider a task done:

1. **Run what you changed.** After editing Python, at minimum import the affected modules or launch the app so obvious errors surface (see [Running and building after changes](#running-and-building-after-changes) below).
2. **Check diagnostics** on files you edited (editor/linter diagnostics; fix new issues you introduced).
3. **Prefer automated checks when they exist.** If the project adds formatters, linters, or tests later, run the commands documented here and keep them green.
4. **If you cannot run the app** (headless environment, missing audio/GPU), say what you verified instead (syntax, `py_compile`, import checks, partial command output) and what remains for a human.

Skipping verification because a change “looks obvious” is not acceptable.

### Running and building after changes

Use the repo-root `.venv` (create it if missing: `python -m venv .venv`).

**Minimum after most code changes**

```powershell
Set-Location <repo-root>
.\.venv\Scripts\python.exe -c "import potato_stt.ui_main; print('import ok')"
```

For UI, startup, or integration paths, also start the app briefly (it should not exit immediately with a traceback):

```powershell
.\.venv\Scripts\Activate.ps1
python -m potato_stt
```

**When to run a full Windows EXE build**

Run `.\build_windows_exe.ps1` from the repository root when your changes could affect the frozen bundle, for example:

- `potato_stt/ui_main.py` or other entry/import paths used by the packaged app
- `potato_stt.spec`, PyInstaller hooks, or `requirements.txt` / `requirements-build.txt`
- Native DLL loading, resource paths, or anything that behaves differently under PyInstaller

The script installs runtime + build requirements into `.venv`, runs PyInstaller, and writes `dist\PotatoSTT\` (ship the entire folder, not only `PotatoSTT.exe`). Confirm the script exits successfully; when you have an interactive desktop, optionally smoke-test `dist\PotatoSTT\PotatoSTT.exe`.

Trivial edits (comments only, typo in markdown with no build impact, etc.) do not require a full EXE build, but still run an import or relevant check when practical.

## Environment

- **OS:** Windows is the primary target for the desktop app.
- **Python:** Use a virtual environment at the repo root.

**Bootstrap (venv + `requirements.txt` + `requirements-dev.txt` + Git pre-commit hook):** from the repo root, run once per clone:

```powershell
Set-Location <repo-root>
.\scripts\bootstrap_dev.ps1
```

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
.\scripts\install_git_hooks.ps1
```

Optional extras: `requirements-build.txt` (see `build_windows_exe.ps1`).

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python -m potato_stt
```

## Testing

**Automated (stdlib unittest, no extra install):** from the repo root:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\python.exe tests\run_tests.py
```

Optional **pytest** (after `pip install -r requirements-dev.txt`):

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

This includes **`tests/test_ui_e2e.py`**: Qt **MainWindow** flows with **mocked** transcription (no ONNX download, no Parakeet, no global hotkeys). Uses offscreen Qt (`QT_QPA_PLATFORM` set in `tests/conftest.py`) so it can run without a visible display.

The stdlib runner **`tests/run_tests.py`** skips `test_ui_e2e.py` (it requires pytest + pytest-qt).

**Git pre-commit:** `.\scripts\bootstrap_dev.ps1` installs the hook automatically. Otherwise, after dev deps are in `.venv`:

```powershell
Set-Location <repo-root>
.\scripts\install_git_hooks.ps1
```

Or: `.\.venv\Scripts\python.exe scripts\run_commit_tests.py --install-hook` (use your venv Python on Windows if plain `python` is a Store alias). The hook prefers the repo `.venv` interpreter, then falls back to `python3`/`python`. Uninstall by deleting `.git/hooks/pre-commit`. Each `git commit` runs `pytest tests -q --tb=short` via the venv.

Tests build small synthetic WAVs in a temp directory. Optional **local media** checks run when you add audio/video under **`test_file/`** (see `tests/helpers.py`); if the folder is empty or missing, those cases are skipped.

**Manual:** use the flow in `README.md` (Notepad or another app, focus the caret, hold push-to-talk, speak, release) when you change capture, STT, or paste behavior in ways the unit tests do not cover.

## Build / packaging (when relevant)

- **Windows EXE:** `.\build_windows_exe.ps1` from repo root (requires `requirements-build.txt` / PyInstaller as in the script). Output: `dist\PotatoSTT\` including `PotatoSTT.exe` and `_internal\`. CPU-only launcher: `PotatoSTTCPU.bat` in the same folder.

## Code style

- Keep changes **minimal and scoped** to the request; match existing patterns in `potato_stt/`.
- Do not add unsolicited docs or refactors outside the task.
- Environment variables and STT wiring are documented in `README.md`; keep code and env docs aligned when you change contracts.

## How this file should work

- **Operational commands** over vague advice: prefer concrete PowerShell snippets and “done means X.”
- **Single source of truth:** project-wide agent rules live here; nested `AGENTS.md` files are only needed if the repo grows a monorepo layout.
- **Conflicts:** if instructions disagree, `README.md` wins for product behavior; update this file when tooling or workflows change.
