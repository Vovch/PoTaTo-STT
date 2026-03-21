from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)
from pynput import keyboard
from pynput.keyboard import Controller

from pipit_clone.audio_utils import float_to_int16_pcm, write_wav_from_int16_pcm
from pipit_clone.config import Settings
from pipit_clone.onnx_asr_engine import OnnxAsrEngine
from pipit_clone.parakeet_windows_installer import ensure_parakeet_service
from pipit_clone.stt_client import transcribe_wav


class AppSignals(QObject):
    statusChanged = Signal(str)
    transcriptAppend = Signal(str)
    transcriptReady = Signal(str)
    errorOccurred = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pipit Clone (Parakeet TDT STT) - Right Ctrl Push-to-Talk")
        self.setMinimumWidth(820)

        self.settings = Settings()
        self._status_label = QLabel("Initializing...")
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._help_label = QLabel("Hold Right Ctrl to record. Release to transcribe.")
        self._help_label.setWordWrap(True)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFormat("Starting...")

        self._quit_btn = QPushButton("Quit")
        self._quit_btn.clicked.connect(self.close)

        root = QWidget()
        layout = QVBoxLayout()
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

        # Microphone state.
        self._sample_rate = 16000
        self._channels = 1
        self._pcm_lock = threading.Lock()
        self._pcm_blocks: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._transcribing = False
        self._ctrl_down = False
        self._kb_controller = Controller()
        self._onnx_engine: Optional[OnnxAsrEngine] = None

        # Hotkey listener.
        self._hotkey_listener: Optional[keyboard.Listener] = None

        # Start engine ensure in background, then register hotkey.
        threading.Thread(target=self._ensure_engine_and_start_hotkey, daemon=True).start()

    def closeEvent(self, event):  # type: ignore[no-untyped-def]
        try:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
        except Exception:
            pass
        try:
            self._stop_recording()
        except Exception:
            pass
        super().closeEvent(event)

    @Slot(str)
    def _append_transcript(self, text: str) -> None:
        current = self._transcript.toPlainText().strip()
        if not current:
            self._transcript.setPlainText(text.strip() + "\n")
        else:
            self._transcript.setPlainText(current + "\n" + text.strip() + "\n")
        self._transcript.ensureCursorVisible()

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
                self._progress.setFormat(f"Download {pct}%")
                return
            except Exception:
                pass
        if "model download" in lower and "%" in msg:
            pct_str = msg.split("%", 1)[0].split()[-1]
            try:
                pct = int(float(pct_str))
                self._progress.setRange(0, 100)
                self._progress.setValue(max(0, min(100, pct)))
                self._progress.setFormat(f"Model {pct}%")
                return
            except Exception:
                pass
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
        text = text.strip()
        if not text:
            return

        # Save/restore clipboard so pasting doesn't permanently overwrite user clipboard.
        clipboard = QApplication.clipboard()
        previous = clipboard.text()
        clipboard.setText(text)
        # Let clipboard update propagate before simulating Ctrl+V.
        QApplication.processEvents()
        time.sleep(0.03)

        try:
            self._kb_controller.press(keyboard.Key.ctrl_l)
            self._kb_controller.press("v")
            self._kb_controller.release("v")
            self._kb_controller.release(keyboard.Key.ctrl_l)
        except Exception as e:
            self.signals.errorOccurred.emit(f"Paste failed: {type(e).__name__}: {e}")
            return

        # Restore clipboard on Qt main thread to avoid COM initialization errors on Windows.
        QTimer.singleShot(250, lambda: clipboard.setText(previous))

    def _ensure_engine_and_start_hotkey(self) -> None:
        def _on_status(s: str) -> None:
            self.signals.statusChanged.emit(s)

        try:
            if self.settings.stt_backend.lower() == "onnx_asr":
                providers = [p.strip() for p in self.settings.onnx_asr_providers.split(",") if p.strip()]
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

        _on_status("Ready. Hold Right Ctrl to talk.")
        self._register_hotkey()

    def _register_hotkey(self) -> None:
        if self._hotkey_listener is not None:
            return

        def _is_ptt_key(key) -> bool:  # type: ignore[no-untyped-def]
            # Support Right Ctrl variants across layouts:
            # - Right Ctrl (ctrl_r)
            # - virtual-key 163
            if key == keyboard.Key.ctrl_r:
                return True

            vk = getattr(key, "vk", None)
            return vk == 163

        def on_press(key) -> None:
            if _is_ptt_key(key):
                # Start recording on the press.
                if not self._ctrl_down:
                    self._ctrl_down = True
                    self.signals.statusChanged.emit("Right Ctrl detected. Recording...")
                    self._start_recording()

        def on_release(key) -> None:
            if _is_ptt_key(key):
                self._ctrl_down = False
                self._stop_recording_and_transcribe()

        try:
            self._hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as e:
            self.signals.errorOccurred.emit(f"Hotkey init failed: {type(e).__name__}: {e}")

    def _start_recording(self) -> None:
        if self._recording or self._transcribing:
            return

        self._pcm_blocks = []
        self._recording = True
        self.signals.statusChanged.emit("Recording... (release Right Ctrl to transcribe)")

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

    def _stop_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False

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
            self.signals.statusChanged.emit("Too short; hold Right Ctrl and speak more.")
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
                            prompt=self.settings.stt_prompt,
                            response_format=self.settings.stt_response_format,
                            timeout_seconds=self.settings.stt_timeout_seconds,
                        )
                    took = time.time() - t0
                    cleaned = text.strip()
                    if cleaned:
                        self.signals.transcriptAppend.emit(cleaned)
                        self.signals.transcriptReady.emit(cleaned)
                    self.signals.statusChanged.emit(f"Transcribed in {took:.1f}s. Ready. Hold Right Ctrl to talk.")
            except Exception as e:
                self.signals.errorOccurred.emit(f"{type(e).__name__}: {e}")
            finally:
                self._transcribing = False

        threading.Thread(target=_job, args=(pcm,), daemon=True).start()


def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication([])
    w = MainWindow()
    w.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()

