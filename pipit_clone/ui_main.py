from __future__ import annotations

import math
import os
import sys
import tempfile
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QEvent, QObject, QRectF, QSettings, QSize, Qt, Signal, Slot, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QEnterEvent,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from pynput import keyboard, mouse

from pipit_clone.audio_utils import float_to_int16_pcm, write_wav_from_int16_pcm
from pipit_clone.config import Settings
from pipit_clone.onnx_asr_engine import OnnxAsrEngine
from pipit_clone.parakeet_windows_installer import ensure_parakeet_service
from pipit_clone.stt_client import transcribe_wav
from pipit_clone.transcript_utils import finalize_sentence_for_clipboard, normalize_phrase_spacing
from pipit_clone.win32_paste import (
    get_foreground_hwnd,
    is_window,
    send_ctrl_v_keybd_event,
    set_foreground_hwnd,
    set_windows_app_user_model_id,
)
from pipit_clone.ptt_capture import capture_ptt_binding
from pipit_clone.ptt_keys import (
    DEFAULT_PTT_SPECS,
    event_matches_any_spec_keyboard,
    event_matches_any_spec_mouse,
    keyboard_token_for_event,
    load_ptt_specs,
    mouse_token_for_button,
    needs_keyboard_listener,
    needs_mouse_listener,
    save_ptt_specs,
    spec_label,
    specs_summary_phrase,
)
from pipit_clone.win32_startup import (
    is_run_at_startup_enabled,
    set_run_at_startup_enabled,
)

# QSettings key (same org/app as push-to-talk keys).
START_MINIMIZED_SETTING = "ui/start_minimized"


def build_app_icon() -> QIcon:
    """Raster icon for window + tray (no bundled image assets)."""
    icon = QIcon()

    def _render(size: int) -> QPixmap:
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        margin = max(1, size // 16)
        p.setBrush(QColor("#2563eb"))
        p.setPen(QColor("#1e40af"))
        p.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, size // 6, size // 6)
        p.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPixelSize(max(8, int(size * 0.45)))
        font.setBold(True)
        p.setFont(font)
        p.drawText(pm.rect(), int(Qt.AlignCenter), "P")
        p.end()
        return pm

    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_render(s))
    return icon


def build_gear_icon(color: QColor, pixel_size: int = 20) -> QIcon:
    """Vector gear centered in the pixmap (no font metrics / QToolButton baseline quirks)."""
    pm = QPixmap(pixel_size, pixel_size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    cx = pixel_size * 0.5
    cy = pixel_size * 0.5
    pen = QPen(color)
    pen.setWidthF(max(1.0, pixel_size / 14.0))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    teeth = 8
    r_tip = pixel_size * 0.36
    r_valley = pixel_size * 0.22
    path = QPainterPath()
    for i in range(teeth * 2):
        a = 2 * math.pi * i / (teeth * 2) - math.pi / 2
        r = r_tip if i % 2 == 0 else r_valley
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)
    hole_r = pixel_size * 0.10
    p.drawEllipse(QRectF(cx - hole_r, cy - hole_r, 2 * hole_r, 2 * hole_r))
    p.end()
    icon = QIcon()
    icon.addPixmap(pm)
    return icon


class GearIconButton(QAbstractButton):
    """Square button that paints the icon truly centered (avoids QToolButton style icon offset)."""

    _side = 32

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._px = 20
        self._icon = QIcon()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(self._side, self._side)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def setIcon(self, icon: QIcon) -> None:
        self._icon = icon
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self._side, self._side)

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect()
        bg = self.palette().color(QPalette.ColorRole.Window)
        if self.underMouse():
            bg = self.palette().color(QPalette.ColorRole.AlternateBase)
        p.fillRect(r, bg)
        border = QColor("#c0c0c0")
        if self.underMouse():
            border = QColor("#909090")
        p.setPen(QPen(border))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        if not self._icon.isNull():
            pm = self._icon.pixmap(self._px, self._px)
            x = (self.width() - pm.width()) // 2
            y = (self.height() - pm.height()) // 2
            p.drawPixmap(x, y, pm)
        p.end()


class _CaptureNotifier(QObject):
    """Marshals capture result to the UI thread."""

    finished = Signal(object)


class PttCaptureDialog(QDialog):
    """Modal capture: first key or mouse button wins; Cancel / Escape abort."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add push-to-talk key")
        self.setModal(True)
        self._cancel = threading.Event()
        self._notifier = _CaptureNotifier(self)
        self._notifier.finished.connect(self._on_capture_finished)
        self._captured_spec = ""
        self._capture_started = False
        v = QVBoxLayout(self)
        v.addWidget(
            QLabel(
                "Press a keyboard key or click a mouse button.\n"
                "Escape cancels. The first input is saved."
            )
        )
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        bb.rejected.connect(self._on_cancel_clicked)
        v.addWidget(bb)

    def reject(self) -> None:
        self._cancel.set()
        super().reject()

    def closeEvent(self, event: QEvent) -> None:
        self._cancel.set()
        super().closeEvent(event)

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        if not self._capture_started:
            self._capture_started = True
            threading.Thread(target=self._run_capture, daemon=True).start()

    def _run_capture(self) -> None:
        spec = capture_ptt_binding(cancel_event=self._cancel, timeout_seconds=120.0)
        self._notifier.finished.emit(spec)

    @Slot()
    def _on_cancel_clicked(self) -> None:
        self._cancel.set()

    @Slot(object)
    def _on_capture_finished(self, spec: object) -> None:
        if isinstance(spec, str) and spec:
            self._captured_spec = spec
            self.accept()
        else:
            self.reject()

    def captured_spec(self) -> Optional[str]:
        return self._captured_spec or None


class OptionsWindow(QWidget):
    """Separate top-level window for app settings."""

    def __init__(self, main_window: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._main = main_window
        self._settings = QSettings("PipitClone", "PipitClone")
        self.setWindowTitle("Options")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        if sys.platform == "win32":
            self._startup_cb = QCheckBox("Launch Pipit Clone at Windows startup")
            self._startup_cb.setChecked(is_run_at_startup_enabled())
            self._startup_cb.toggled.connect(self._on_startup_toggled)
            layout.addWidget(self._startup_cb)
        else:
            _hint = QLabel("Launch at startup is only available on Windows.")
            _hint.setWordWrap(True)
            layout.addWidget(_hint)

        self._start_min_cb = QCheckBox("Start minimized")
        self._start_min_cb.setChecked(
            bool(self._settings.value(START_MINIMIZED_SETTING, False, type=bool))
        )
        self._start_min_cb.setToolTip(
            "When a system tray icon is available, the main window stays hidden until you open it from the tray. "
            "Otherwise the window opens minimized to the taskbar."
        )
        self._start_min_cb.toggled.connect(self._on_start_minimized_toggled)
        layout.addWidget(self._start_min_cb)

        layout.addWidget(QLabel("Push-to-talk keys (hold any of these):"))
        self._ptt_list = QListWidget()
        self._ptt_list.setMinimumHeight(120)
        layout.addWidget(self._ptt_list)
        _btn_row = QHBoxLayout()
        self._add_ptt_btn = QPushButton("Add key…")
        self._add_ptt_btn.clicked.connect(self._on_add_ptt_clicked)
        self._remove_ptt_btn = QPushButton("Remove selected")
        self._remove_ptt_btn.clicked.connect(self._on_remove_ptt_clicked)
        _btn_row.addWidget(self._add_ptt_btn)
        _btn_row.addWidget(self._remove_ptt_btn)
        _btn_row.addStretch(1)
        layout.addLayout(_btn_row)
        _ptt_help = QLabel(
            "Recording continues while at least one bound key or button is held. "
            "If you remove every key, Right Ctrl is used again."
        )
        _ptt_help.setWordWrap(True)
        _ptt_help.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(_ptt_help)

        layout.addStretch(1)
        self._populate_ptt_list()

    def _populate_ptt_list(self) -> None:
        self._ptt_list.clear()
        for spec in load_ptt_specs(self._settings):
            it = QListWidgetItem(spec_label(spec))
            it.setData(Qt.ItemDataRole.UserRole, spec)
            self._ptt_list.addItem(it)

    def _save_ptt_list_from_ui(self) -> None:
        specs: list[str] = []
        for i in range(self._ptt_list.count()):
            item = self._ptt_list.item(i)
            d = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(d, str):
                specs.append(d)
        if not specs:
            specs = list(DEFAULT_PTT_SPECS)
        save_ptt_specs(self._settings, specs)
        fn = getattr(self._main, "_on_ptt_key_setting_changed", None)
        if fn is not None:
            fn()
        self._populate_ptt_list()

    @Slot()
    def _on_add_ptt_clicked(self) -> None:
        dlg = PttCaptureDialog(self)
        dlg.resize(420, 140)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        spec = dlg.captured_spec()
        if not spec:
            return
        for i in range(self._ptt_list.count()):
            if self._ptt_list.item(i).data(Qt.ItemDataRole.UserRole) == spec:
                QMessageBox.information(self, "Push-to-talk", "That key is already in the list.")
                return
        it = QListWidgetItem(spec_label(spec))
        it.setData(Qt.ItemDataRole.UserRole, spec)
        self._ptt_list.addItem(it)
        self._save_ptt_list_from_ui()

    @Slot()
    def _on_remove_ptt_clicked(self) -> None:
        row = self._ptt_list.currentRow()
        if row < 0:
            return
        self._ptt_list.takeItem(row)
        self._save_ptt_list_from_ui()

    def sync_ptt_from_settings(self) -> None:
        self._populate_ptt_list()

    @Slot(bool)
    def _on_startup_toggled(self, checked: bool) -> None:
        try:
            set_run_at_startup_enabled(checked)
        except OSError as e:
            self._startup_cb.blockSignals(True)
            self._startup_cb.setChecked(not checked)
            self._startup_cb.blockSignals(False)
            QMessageBox.warning(
                self,
                "Startup setting",
                f"Could not update the Windows startup entry:\n{e}",
            )

    @Slot(bool)
    def _on_start_minimized_toggled(self, checked: bool) -> None:
        self._settings.setValue(START_MINIMIZED_SETTING, bool(checked))


class AppSignals(QObject):
    statusChanged = Signal(str)
    transcriptAppend = Signal(str)
    transcriptReady = Signal(str)
    errorOccurred = Signal(str)
    recordingActive = Signal(bool)


class RecordingOverlay(QWidget):
    """Small always-on-top marker; does not take focus or block mouse input."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setObjectName("RecordingOverlay")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)
        dot = QLabel("●")
        dot.setStyleSheet("color: #ff4444; font-size: 18px;")
        label = QLabel("Recording")
        label.setStyleSheet("color: #f0f0f0; font-size: 14px; font-weight: bold;")
        layout.addWidget(dot)
        layout.addWidget(label)

        self.setStyleSheet(
            "#RecordingOverlay { background-color: rgba(30, 30, 35, 230); "
            "border-radius: 8px; border: 1px solid #555555; }"
        )


class MainWindow(QMainWindow):
    def __init__(self, app_icon: Optional[QIcon] = None) -> None:
        super().__init__()
        self.setWindowTitle("Pipit Clone (Parakeet TDT STT) — Push-to-talk")
        self.setMinimumWidth(820)

        self._app_icon = app_icon if app_icon is not None else build_app_icon()
        self.setWindowIcon(self._app_icon)

        self.settings = Settings()
        self._qsettings = QSettings("PipitClone", "PipitClone")
        self._ptt_specs: list[str] = load_ptt_specs(self._qsettings)
        self._stt_engine_ready = False

        self._status_label = QLabel("Initializing...")
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._help_label = QLabel("")
        self._help_label.setWordWrap(True)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFormat("Starting...")

        self._quit_btn = QPushButton("Quit")
        self._quit_btn.clicked.connect(self.close)

        self._options_win: Optional[OptionsWindow] = None

        _header = QHBoxLayout()
        self._options_btn = GearIconButton()
        self._options_btn.setToolTip("Options")
        _gear_px = 20
        self._options_btn.setIcon(
            build_gear_icon(self.palette().color(QPalette.ColorRole.WindowText), pixel_size=_gear_px)
        )
        self._options_btn.clicked.connect(self._open_options)
        _header.addWidget(self._options_btn)
        _header.addStretch(1)

        root = QWidget()
        layout = QVBoxLayout()
        layout.addLayout(_header)
        layout.addWidget(self._help_label)
        layout.addWidget(self._status_label)
        layout.addWidget(self._progress)
        layout.addLayout(QHBoxLayout())
        layout.addWidget(self._transcript)
        layout.addWidget(self._quit_btn)
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.signals = AppSignals()
        self.signals.statusChanged.connect(self._on_status_update)
        self.signals.transcriptAppend.connect(self._append_transcript)
        self.signals.transcriptReady.connect(self._paste_transcript_to_active_app)
        self.signals.errorOccurred.connect(self._on_error)
        self.signals.recordingActive.connect(self._on_recording_overlay)

        self._recording_overlay = RecordingOverlay()
        self._recording_overlay.hide()

        # Microphone state.
        self._sample_rate = 16000
        self._channels = 1
        self._pcm_lock = threading.Lock()
        self._pcm_blocks: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._transcribing = False
        self._ptt_hold_tokens: set[str] = set()
        self._onnx_engine: Optional[OnnxAsrEngine] = None
        # Window that had focus when push-to-talk started (for paste target).
        self._paste_target_hwnd: Optional[int] = None

        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None

        self._tray_icon: Optional[QSystemTrayIcon] = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            tray = QSystemTrayIcon(self)
            tray.setIcon(self._app_icon)
            tray.setToolTip(f"Pipit Clone — hold {specs_summary_phrase(self._ptt_specs)} to talk")
            tray_menu = QMenu()
            act_show = QAction("Show", self)
            act_show.triggered.connect(self._show_from_tray)
            tray_menu.addAction(act_show)
            act_quit = QAction("Quit", self)
            act_quit.triggered.connect(self._quit_from_tray)
            tray_menu.addAction(act_quit)
            tray.setContextMenu(tray_menu)
            tray.activated.connect(self._on_tray_activated)
            tray.show()
            self._tray_icon = tray

        self._update_ptt_help_text()

        # Start engine ensure in background, then register hotkey.
        threading.Thread(target=self._ensure_engine_and_start_hotkey, daemon=True).start()

    def has_system_tray(self) -> bool:
        return self._tray_icon is not None

    def changeEvent(self, event: QEvent) -> None:
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self._tray_icon is not None
            and self.windowState() & Qt.WindowState.WindowMinimized
        ):
            QTimer.singleShot(0, self._hide_to_tray)
        super().changeEvent(event)

    def _hide_to_tray(self) -> None:
        if self._tray_icon is None:
            return
        if not (self.windowState() & Qt.WindowState.WindowMinimized):
            return
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.hide()

    @Slot()
    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    @Slot(QSystemTrayIcon.ActivationReason)
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    @Slot()
    def _quit_from_tray(self) -> None:
        self._shutdown()
        QApplication.quit()

    def _shutdown(self) -> None:
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self._stop_hotkey_listeners()
        try:
            self._stop_recording()
        except Exception:
            pass

    def closeEvent(self, event):  # type: ignore[no-untyped-def]
        self._shutdown()
        super().closeEvent(event)

    def _stop_hotkey_listeners(self) -> None:
        for attr in ("_keyboard_listener", "_mouse_listener"):
            lst = getattr(self, attr, None)
            if lst is not None:
                try:
                    lst.stop()
                except Exception:
                    pass
                setattr(self, attr, None)

    def _update_ptt_help_text(self) -> None:
        ptt = specs_summary_phrase(self._ptt_specs)
        text = f"Hold {ptt} to record. Release to transcribe."
        if self._tray_icon is not None:
            text += (
                " Minimize the window to send it to the system tray "
                "(double-click the tray icon to restore)."
            )
            self._tray_icon.setToolTip(f"Pipit Clone — hold {ptt} to talk")
        self._help_label.setText(text)

    @Slot()
    def _on_ptt_key_setting_changed(self) -> None:
        self._ptt_specs = load_ptt_specs(self._qsettings)
        self._update_ptt_help_text()
        self.restart_ptt_listeners()

    def restart_ptt_listeners(self) -> None:
        if not self._stt_engine_ready:
            return
        self._stop_hotkey_listeners()
        self._register_hotkey()

    @Slot()
    def _open_options(self) -> None:
        if self._options_win is None:
            self._options_win = OptionsWindow(self)
        self._options_win.sync_ptt_from_settings()
        self._options_win.show()
        self._options_win.raise_()
        self._options_win.activateWindow()

    @Slot(str)
    def _append_transcript(self, text: str) -> None:
        current = self._transcript.toPlainText().strip()
        line = finalize_sentence_for_clipboard(text)
        if not current:
            self._transcript.setPlainText(line + "\n")
        else:
            self._transcript.setPlainText(current + "\n" + line + "\n")
        self._transcript.ensureCursorVisible()

    def _position_recording_overlay(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self._recording_overlay.adjustSize()
        w = self._recording_overlay.width()
        h = self._recording_overlay.height()
        margin = 24
        x = geo.left() + (geo.width() - w) // 2
        y = geo.top() + geo.height() - h - margin
        self._recording_overlay.move(x, y)

    @Slot(bool)
    def _on_recording_overlay(self, active: bool) -> None:
        if active:
            self._position_recording_overlay()
            self._recording_overlay.show()
        else:
            self._recording_overlay.hide()

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._status_label.setText(f"Error: {msg}")
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat("Failed")

    @Slot(str)
    def _on_status_update(self, msg: str) -> None:
        self._status_label.setText(msg)
        lower = msg.lower()
        if lower.startswith("error:") or " exited " in lower or "failed" in lower:
            self._progress.setRange(0, 1)
            self._progress.setValue(0)
            self._progress.setFormat("Failed")
            return
        if "downloading..." in lower and "%" in msg:
            pct_str = msg.split("%", 1)[0].split()[-1]
            try:
                pct = int(float(pct_str))
                self._progress.setRange(0, 100)
                self._progress.setValue(max(0, min(100, pct)))
                self._progress.setFormat(f"Downloading from internet — {pct}%")
                return
            except Exception:
                pass
        if "model download" in lower and "%" in msg:
            pct_str = msg.split("%", 1)[0].split()[-1]
            try:
                pct = int(float(pct_str))
                self._progress.setRange(0, 100)
                self._progress.setValue(max(0, min(100, pct)))
                self._progress.setFormat(f"Downloading model from internet — {pct}%")
                return
            except Exception:
                pass
        # Indeterminate bar + label: network/model fetch without a numeric percent yet.
        if (
            "waiting for parakeet service to finish model download" in lower
            or "downloading parakeet windows package" in lower
            or "package url failed, downloading" in lower
        ):
            self._progress.setRange(0, 0)
            self._progress.setFormat("Downloading from internet...")
            return
        if "preparing parakeet http stt engine" in lower:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Preparing STT (may download from internet)...")
            return
        if "extracting package" in lower:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Extracting downloaded package...")
            return
        if "installing fallback dependencies" in lower:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Installing dependencies (downloading from internet)...")
            return
        if "loading onnx asr model" in lower:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Loading model...")
            return
        if "preparing onnx asr engine" in lower:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Preparing ONNX model...")
            return
        if "ready." in lower:
            self._progress.setRange(0, 1)
            self._progress.setValue(1)
            self._progress.setFormat("Ready")
        elif "transcribing" in lower:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Transcribing...")
        else:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Working...")

    @Slot(str)
    def _paste_transcript_to_active_app(self, text: str) -> None:
        # Do not use strip() alone — it removes the trailing space after . ! ? that
        # normalize_phrase_spacing adds for continued typing after paste.
        text = finalize_sentence_for_clipboard(text)
        if not text:
            return

        # Save/restore clipboard so pasting doesn't permanently overwrite user clipboard.
        clipboard = QApplication.clipboard()
        previous = clipboard.text()
        clipboard.setText(text)
        QApplication.processEvents()
        time.sleep(0.02)

        try:
            # Put focus back on the app that was active when recording started (not Pipit).
            our_hwnd = int(self.winId()) if self.winId() else 0
            target = self._paste_target_hwnd
            if target and target != our_hwnd and is_window(target):
                set_foreground_hwnd(target)
            elif target == our_hwnd:
                # Recording started with our window focused; try paste without stealing focus.
                pass

            # Native Win32 injection is more reliable than pynput for cross-app paste.
            send_ctrl_v_keybd_event()
        except Exception as e:
            self.signals.errorOccurred.emit(f"Paste failed: {type(e).__name__}: {e}")
            return

        # Restore clipboard on Qt main thread to avoid COM initialization errors on Windows.
        QTimer.singleShot(400, lambda: clipboard.setText(previous))

    def _ensure_engine_and_start_hotkey(self) -> None:
        def _on_status(s: str) -> None:
            self.signals.statusChanged.emit(s)

        try:
            if self.settings.stt_backend.lower() == "onnx_asr":
                if self.settings.cpu_only:
                    providers = ["CPUExecutionProvider"]
                else:
                    providers = [
                        p.strip() for p in self.settings.onnx_asr_providers.split(",") if p.strip()
                    ]
                self._onnx_engine = OnnxAsrEngine(
                    model_name=self.settings.onnx_asr_model,
                    providers=providers,
                )
                _on_status("Preparing ONNX ASR engine (first model load may take time)...")
                self._onnx_engine.warmup(on_status=_on_status)
            else:
                api_url = self.settings.stt_api_url
                # stt_api_url is .../v1/audio/transcriptions
                api_base = api_url.rsplit("/audio/transcriptions", 1)[0]
                api_host = "127.0.0.1"
                api_port = 5092
                _on_status("Preparing Parakeet HTTP STT engine (download/first model load may take time)...")
                ensure_parakeet_service(
                    api_host=api_host,
                    api_port=api_port,
                    api_base_url=api_base,
                    parakeet_win_url=self.settings.parakeet_win_url,
                    install_dir=self.settings.parakeet_install_dir,
                    auto_download=self.settings.parakeet_auto_download,
                    source_fallback=self.settings.parakeet_source_fallback,
                    launch_timeout_seconds=self.settings.parakeet_launch_timeout_seconds,
                    on_status=_on_status,
                )
        except Exception as e:
            self.signals.errorOccurred.emit(f"{type(e).__name__}: {e}")
            return

        self._stt_engine_ready = True
        _on_status(f"Ready. Hold {specs_summary_phrase(self._ptt_specs)} to talk.")
        self._register_hotkey()

    def _add_ptt_token(self, token: str) -> None:
        before = len(self._ptt_hold_tokens)
        self._ptt_hold_tokens.add(token)
        if before == 0 and len(self._ptt_hold_tokens) > 0:
            self.signals.statusChanged.emit(
                f"{specs_summary_phrase(self._ptt_specs)} — recording..."
            )
            self._start_recording()

    def _remove_ptt_token(self, token: str) -> None:
        self._ptt_hold_tokens.discard(token)
        if len(self._ptt_hold_tokens) == 0:
            self._stop_recording_and_transcribe()

    def _register_hotkey(self) -> None:
        self._stop_hotkey_listeners()
        self._ptt_hold_tokens.clear()
        self._ptt_specs = load_ptt_specs(self._qsettings)
        specs = self._ptt_specs

        try:
            if needs_keyboard_listener(specs):

                def on_press(key) -> None:  # type: ignore[no-untyped-def]
                    if not event_matches_any_spec_keyboard(specs, key):
                        return
                    self._add_ptt_token(keyboard_token_for_event(key))

                def on_release(key) -> None:  # type: ignore[no-untyped-def]
                    if not event_matches_any_spec_keyboard(specs, key):
                        return
                    self._remove_ptt_token(keyboard_token_for_event(key))

                self._keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
                self._keyboard_listener.daemon = True
                self._keyboard_listener.start()

            if needs_mouse_listener(specs):

                def on_click(x, y, button, pressed) -> None:  # type: ignore[no-untyped-def]
                    if not event_matches_any_spec_mouse(specs, button):
                        return
                    tok = mouse_token_for_button(button)
                    if pressed:
                        self._add_ptt_token(tok)
                    else:
                        self._remove_ptt_token(tok)

                self._mouse_listener = mouse.Listener(on_click=on_click)
                self._mouse_listener.daemon = True
                self._mouse_listener.start()
        except Exception as e:
            self.signals.errorOccurred.emit(f"Hotkey init failed: {type(e).__name__}: {e}")

    def _start_recording(self) -> None:
        if self._recording or self._transcribing:
            return

        try:
            self._paste_target_hwnd = get_foreground_hwnd()
        except Exception:
            self._paste_target_hwnd = None

        self._pcm_blocks = []
        self._recording = True
        self.signals.statusChanged.emit(
            f"Recording... (release {specs_summary_phrase(self._ptt_specs)} to transcribe)"
        )

        def callback(indata, frames, time_info, status):  # type: ignore[no-untyped-def]
            if not self._recording:
                return
            if status:
                return
            pcm = float_to_int16_pcm(indata)
            with self._pcm_lock:
                self._pcm_blocks.append(pcm)

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="float32",
            blocksize=1024,
            callback=callback,
        )
        self._stream.start()
        self.signals.recordingActive.emit(True)

    def _stop_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self.signals.recordingActive.emit(False)

        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

    def _stop_recording_and_transcribe(self) -> None:
        if not self._recording:
            return

        if self._transcribing:
            # If we are already transcribing, just stop recording and drop audio.
            self._stop_recording()
            self.signals.statusChanged.emit("Transcription busy; try again.")
            return

        self._stop_recording()

        with self._pcm_lock:
            blocks = self._pcm_blocks
            self._pcm_blocks = []

        if not blocks:
            self.signals.statusChanged.emit("No audio captured.")
            return

        pcm = np.concatenate(blocks)
        # Skip extremely short clips (accidental ctrl taps).
        if pcm.shape[0] < int(self._sample_rate * 0.35):
            self.signals.statusChanged.emit(
                f"Too short; hold {specs_summary_phrase(self._ptt_specs)} and speak more."
            )
            return

        self._transcribing = True
        self.signals.statusChanged.emit("Transcribing...")

        def _job(pcm_data: np.ndarray) -> None:
            try:
                with tempfile.TemporaryDirectory(prefix="pipit-audio-") as tmpdir:
                    wav_path = os.path.join(tmpdir, f"talk_{int(time.time()*1000)}.wav")
                    write_wav_from_int16_pcm(pcm_data, wav_path, sample_rate=self._sample_rate)

                    t0 = time.time()
                    if self.settings.stt_backend.lower() == "onnx_asr":
                        if self._onnx_engine is None:
                            raise RuntimeError("ONNX ASR engine is not initialized.")
                        text = self._onnx_engine.transcribe_wav(wav_path)
                    else:
                        text = transcribe_wav(
                            wav_path,
                            api_url=self.settings.stt_api_url,
                            model=self.settings.stt_model,
                            response_format=self.settings.stt_response_format,
                            timeout_seconds=self.settings.stt_timeout_seconds,
                        )
                    took = time.time() - t0
                    cleaned = normalize_phrase_spacing(text)
                    if cleaned:
                        self.signals.transcriptAppend.emit(cleaned)
                        self.signals.transcriptReady.emit(cleaned)
                    self.signals.statusChanged.emit(
                        f"Transcribed in {took:.1f}s. Ready. Hold "
                        f"{specs_summary_phrase(self._ptt_specs)} to talk."
                    )
            except Exception as e:
                self.signals.errorOccurred.emit(f"{type(e).__name__}: {e}")
            finally:
                self._transcribing = False

        threading.Thread(target=_job, args=(pcm,), daemon=True).start()


def _normalize_application_font(app: QApplication) -> None:
    """Windows high-DPI defaults sometimes leave QFont.pointSize() at -1; Qt then warns if
    something calls setPointSize with that value. Force a positive point size.
    """
    f = QFont(app.font())
    if f.pointSize() > 0:
        return
    px = f.pixelSize()
    if px > 0:
        f.setPointSize(max(1, int(round(px * 72.0 / 96.0))))
    else:
        f.setPointSize(9)
    app.setFont(f)


def main() -> None:
    if sys.platform == "win32":
        set_windows_app_user_model_id()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication([])
    _normalize_application_font(app)
    app_icon = build_app_icon()
    app.setWindowIcon(app_icon)
    w = MainWindow(app_icon=app_icon)
    start_minimized = bool(
        w._qsettings.value(START_MINIMIZED_SETTING, False, type=bool)
    )
    if start_minimized:
        if not w.has_system_tray():
            w.showMinimized()
        # else: tray is already shown in MainWindow.__init__; main window stays hidden
    else:
        w.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()

