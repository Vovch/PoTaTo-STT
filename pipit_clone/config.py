from __future__ import annotations

import os
from dataclasses import dataclass


def _getenv_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def _getenv_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    stt_backend: str = _getenv_str("PIPIT_STT_BACKEND", "onnx_asr")
    # Parakeet TDT Windows all-in-one runs locally and exposes an OpenAI-style API.
    # API docs (community/packaging): http://127.0.0.1:5092/v1
    stt_api_url: str = _getenv_str(
        "PIPIT_STT_API_URL",
        "http://127.0.0.1:5092/v1/audio/transcriptions",
    )
    stt_model: str = _getenv_str("PIPIT_STT_MODEL", "parakeet")
    stt_response_format: str = _getenv_str("PIPIT_STT_RESPONSE_FORMAT", "json")
    stt_timeout_seconds: int = _getenv_int("PIPIT_STT_TIMEOUT_SECONDS", 120)
    onnx_asr_model: str = _getenv_str("PIPIT_ONNX_ASR_MODEL", "nemo-parakeet-tdt-0.6b-v3")
    # Prefer DirectML (AMD-friendly on Windows), then CPU fallback.
    onnx_asr_providers: str = _getenv_str(
        "PIPIT_ONNX_ASR_PROVIDERS",
        "DmlExecutionProvider,CPUExecutionProvider",
    )
    # When 1, ONNX ASR uses CPU only (no DirectML/GPU); ignores PIPIT_ONNX_ASR_PROVIDERS.
    cpu_only: bool = _getenv_int("PIPIT_CPU_ONLY", 0) == 1

    # Download/extract the official Windows all-in-one package on first run.
    parakeet_win_url: str = _getenv_str(
        "PIPIT_PARKEET_WIN_URL",
        "https://huggingface.co/mortimerme/repocollect/resolve/main/parakeet-win-0707.7z?download=true",
    )
    # Where the downloaded package will be extracted.
    parakeet_install_dir: str = _getenv_str(
        "PIPIT_PARKEET_INSTALL_DIR",
        os.path.join(os.environ.get("LOCALAPPDATA", os.getcwd()), "pipit_clone", "parakeet-win"),
    )
    parakeet_launch_timeout_seconds: int = _getenv_int("PIPIT_PARKEET_LAUNCH_TIMEOUT_SECONDS", 1800)
    parakeet_auto_download: bool = _getenv_int("PIPIT_PARKEET_AUTO_DOWNLOAD", 1) == 1
    parakeet_source_fallback: bool = _getenv_int("PIPIT_PARKEET_SOURCE_FALLBACK", 1) == 1

