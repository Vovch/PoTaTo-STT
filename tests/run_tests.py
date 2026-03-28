#!/usr/bin/env python3
"""Discover and run unit tests (stdlib unittest; no pytest required).

Skips ``test_ui_e2e.py`` (pytest + pytest-qt). Use ``python -m pytest tests`` for those.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
for p in (str(ROOT), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Pytest + pytest-qt only (see tests/test_ui_e2e.py); stdlib runner skips them.
_SKIP_UNITTEST = frozenset({"test_ui_e2e.py"})


def main() -> int:
    loader = unittest.TestLoader()
    tests_dir = Path(__file__).parent
    suite = unittest.TestSuite()
    for path in sorted(tests_dir.glob("test_*.py")):
        if path.name in _SKIP_UNITTEST:
            continue
        suite.addTests(loader.loadTestsFromName(path.stem))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
