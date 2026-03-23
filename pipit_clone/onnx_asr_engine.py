from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

import onnx_asr
import onnxruntime as ort


class OnnxAsrEngine:
    def __init__(self, *, model_name: str, providers: list[str]) -> None:
        self._model_name = model_name
        self._providers = providers
        self._lock = threading.Lock()
        self._model = None

    def _ensure_model(self, on_status: Optional[Callable[[str], None]] = None):
        with self._lock:
            if self._model is not None:
                return self._model
            available = ort.get_available_providers()
            preferred = [p for p in self._providers if p in available]
            if not preferred:
                preferred = ["CPUExecutionProvider"]
            self._providers = preferred
            if on_status is not None:
                on_status(
                    f"Loading ONNX ASR model '{self._model_name}' "
                    f"(providers={','.join(self._providers)})..."
                )
            self._model = onnx_asr.load_model(
                self._model_name,
                providers=self._providers,
            )
            if on_status is not None:
                on_status(f"ONNX ASR ready ({self._providers[0]}).")
            return self._model

    def warmup(self, on_status: Optional[Callable[[str], None]] = None) -> None:
        self._ensure_model(on_status=on_status)

    def transcribe_wav(
        self, wav_path: str | Path, *, language: Optional[str] = None
    ) -> str:
        model = self._ensure_model()
        kwargs: dict[str, str] = {}
        if language:
            # onnx-asr uses `language` for Whisper/Canary; Parakeet TDT models ignore it.
            kwargs["language"] = language
        text = model.recognize(str(wav_path), **kwargs)
        if isinstance(text, str):
            return text.strip()
        return str(text).strip()

