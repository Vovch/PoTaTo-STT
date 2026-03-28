"""Pytest hooks for Qt tests (must set platform before PySide6 imports)."""

from __future__ import annotations

import os

# Headless CI / agents: avoid needing a real display for MainWindow tests.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
