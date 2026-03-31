#!/usr/bin/env python3
"""Run the full test suite from the repo .venv (for Git pre-commit).

Also: ``python scripts/run_commit_tests.py --install-hook`` writes ``.git/hooks/pre-commit``.
Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _venv_python(root: Path) -> Path | None:
    if sys.platform == "win32":
        p = root / ".venv" / "Scripts" / "python.exe"
    else:
        p = root / ".venv" / "bin" / "python"
    return p if p.is_file() else None


# Prefer repo .venv so commits work on Windows without a global python3 (and avoid Store stubs).
_HOOK_BODY = """#!/bin/sh
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 1
if [ -f "$ROOT/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/.venv/Scripts/python.exe"
elif [ -f "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
exec "$PY" "$ROOT/scripts/run_commit_tests.py"
"""


def _install_pre_commit_hook() -> int:
    root = _repo_root()
    r = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        print("run_commit_tests: not a git repository (git rev-parse failed).", file=sys.stderr)
        return 1
    git_dir = Path(r.stdout.strip())
    hook = git_dir / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(_HOOK_BODY, encoding="utf-8", newline="\n")
    if os.name != "nt":
        mode = hook.stat().st_mode
        hook.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed Git pre-commit hook: {hook}")
    return 0


def _run_pytest(root: Path) -> int:
    py = _venv_python(root)
    if py is None:
        print(
            "run_commit_tests: no .venv found. Create it and install deps, e.g.\n"
            "  python -m venv .venv\n"
            "  .\\.venv\\Scripts\\pip install -r requirements.txt -r requirements-dev.txt",
            file=sys.stderr,
        )
        return 1
    cmd = [
        str(py),
        "-m",
        "pytest",
        "tests",
        "-q",
        "--tb=short",
    ]
    print("pre-commit: running", " ".join(cmd), file=sys.stderr)
    return subprocess.call(cmd, cwd=root)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--install-hook",
        action="store_true",
        help="Write .git/hooks/pre-commit to run this script on every commit.",
    )
    args = p.parse_args(argv)
    if args.install_hook:
        return _install_pre_commit_hook()
    return _run_pytest(_repo_root())


if __name__ == "__main__":
    raise SystemExit(main())
