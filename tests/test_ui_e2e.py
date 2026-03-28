"""
UI-level end-to-end checks: real MainWindow + Qt event loop, mocked STT and no global hotkeys.

Also covers real engine startup with stubbed loads: ONNX calls into onnx_asr.load_model;
Parakeet uses a stubbed downloader when the Windows package is not installed.

Requires: pip install -r requirements-dev.txt (pytest + pytest-qt).
Run: python -m pytest tests/test_ui_e2e.py -v
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from potato_stt.config import Settings as RealSettings
from potato_stt.subtitle_export import cues_to_srt


@pytest.fixture
def main_window(qtbot, monkeypatch):
    """MainWindow with ONNX/Parakeet startup and pynput registration disabled."""

    def _skip_engine(self) -> None:
        self._stt_engine_ready = True

    monkeypatch.setattr(
        "potato_stt.ui_main.MainWindow._ensure_engine_and_start_hotkey",
        _skip_engine,
    )
    monkeypatch.setattr(
        "potato_stt.ui_main.MainWindow._register_hotkey",
        lambda self: None,
    )

    from potato_stt.ui_main import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: w._stt_engine_ready, timeout=5000)
    return w


def test_main_window_smoke_visible(main_window) -> None:
    main_window.show()
    assert main_window.isVisible()
    assert "Potato STT" in main_window.windowTitle()


def test_file_transcribe_appends_transcript(main_window, qtbot, monkeypatch, tmp_path) -> None:
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFF")  # path only passed to mock

    def _fake_transcribe(*_args, **_kwargs):
        return "Synthetic line for e2e.", []

    monkeypatch.setattr(
        "potato_stt.ui_main.transcribe_file_to_text_and_cues",
        _fake_transcribe,
    )

    main_window._start_file_transcribe(wav)

    def _done() -> bool:
        return "Synthetic line for e2e." in main_window._transcript.toPlainText()

    qtbot.waitUntil(_done, timeout=8000)
    assert "ready." in main_window._status_label.text().lower()


def test_file_transcribe_writes_subtitles_when_save_dialog_ok(
    main_window, qtbot, monkeypatch, tmp_path
) -> None:
    wav = tmp_path / "clip.wav"
    out_srt = tmp_path / "saved_subs.srt"
    cues = [(0.0, 1.0, "hello e2e")]
    srt_body = cues_to_srt(cues)

    def _fake_transcribe(*_args, **_kwargs):
        return "hello e2e", list(cues)

    monkeypatch.setattr(
        "potato_stt.ui_main.transcribe_file_to_text_and_cues",
        _fake_transcribe,
    )

    dlg = MagicMock(
        side_effect=[
            (str(out_srt), "SubRip (*.srt)"),
        ]
    )
    monkeypatch.setattr("potato_stt.ui_main.QFileDialog.getSaveFileName", dlg)

    main_window._start_file_transcribe(wav)

    def _saved() -> bool:
        return out_srt.is_file()

    qtbot.waitUntil(_saved, timeout=8000)
    text = out_srt.read_text(encoding="utf-8")
    assert "hello e2e" in text
    assert "00:00:00,000" in text
    dlg.assert_called_once()
    assert "ready." in main_window._status_label.text().lower()


def test_file_transcribe_error_resets_to_ready_status(main_window, qtbot, monkeypatch, tmp_path) -> None:
    wav = tmp_path / "clip.wav"

    def _boom(*_args, **_kwargs):
        raise RuntimeError("forced failure for e2e")

    monkeypatch.setattr(
        "potato_stt.ui_main.transcribe_file_to_text_and_cues",
        _boom,
    )

    main_window._start_file_transcribe(wav)

    def _ready_after_error() -> bool:
        t = main_window._status_label.text().lower()
        return "ready." in t and "hold" in t

    qtbot.waitUntil(_ready_after_error, timeout=8000)


def test_options_window_opens(main_window, qtbot) -> None:
    main_window._open_options()
    assert main_window._options_win is not None
    qtbot.waitExposed(main_window._options_win)
    assert main_window._options_win.isVisible()


def test_onnx_backend_starts_model_load_when_model_missing(qtbot, monkeypatch) -> None:
    """Real _ensure_engine path: first ONNX load calls onnx_asr.load_model (simulated missing model)."""

    def _settings_onnx_missing_model():
        return replace(
            RealSettings(),
            stt_backend="onnx_asr",
            cpu_only=True,
            onnx_asr_model="missing-model-xyz-e2e",
        )

    monkeypatch.setattr("potato_stt.ui_main.Settings", _settings_onnx_missing_model)

    load_calls: list[tuple[object, object]] = []

    def _fake_load_model(model_name, path=None, *, providers=None, **kwargs):
        load_calls.append((model_name, providers))
        raise RuntimeError("simulated model missing for e2e")

    monkeypatch.setattr(
        "potato_stt.onnx_asr_engine.onnx_asr.load_model",
        _fake_load_model,
    )
    monkeypatch.setattr(
        "potato_stt.ui_main.MainWindow._register_hotkey",
        lambda self: None,
    )

    from potato_stt.ui_main import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)

    def _load_started() -> bool:
        return len(load_calls) >= 1

    qtbot.waitUntil(_load_started, timeout=20000)
    assert load_calls[0][0] == "missing-model-xyz-e2e"
    assert list(load_calls[0][1] or []) == ["CPUExecutionProvider"]

    qtbot.waitUntil(
        lambda: "runtimeerror" in w._status_label.text().lower(),
        timeout=20000,
    )
    assert not w._stt_engine_ready


def test_parakeet_backend_starts_package_download_when_not_installed(
    qtbot, monkeypatch, tmp_path
) -> None:
    """No 启动.bat: app enters first-run download path (network stubbed)."""
    install = tmp_path / "parakeet-empty"
    install.mkdir()

    def _settings_parakeet_no_package():
        return replace(
            RealSettings(),
            stt_backend="parakeet",
            parakeet_install_dir=str(install),
            parakeet_auto_download=True,
            parakeet_source_fallback=False,
            parakeet_launch_timeout_seconds=5,
        )

    monkeypatch.setattr("potato_stt.ui_main.Settings", _settings_parakeet_no_package)

    download_attempts: list[str] = []

    def _no_network_download(url: str, dest_path, *, on_progress=None):
        download_attempts.append(url)
        raise RuntimeError("e2e abort before HTTP")

    monkeypatch.setattr(
        "potato_stt.parakeet_windows_installer._is_port_open",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        "potato_stt.parakeet_windows_installer._download_with_progress",
        _no_network_download,
    )
    monkeypatch.setattr(
        "potato_stt.ui_main.MainWindow._register_hotkey",
        lambda self: None,
    )

    from potato_stt.ui_main import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)

    def _download_started() -> bool:
        return len(download_attempts) >= 1

    qtbot.waitUntil(_download_started, timeout=20000)
    assert len(download_attempts) == 1

    qtbot.waitUntil(
        lambda: "timeouterror" in w._status_label.text().lower(),
        timeout=30000,
    )
    assert not w._stt_engine_ready
