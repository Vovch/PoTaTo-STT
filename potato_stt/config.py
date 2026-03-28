from __future__ import annotations

import os
from dataclasses import dataclass


def _env_str(primary: str, legacy: str | None = None, *, default: str) -> str:
    """Prefer POTATO_STT_*; accept legacy PIPIT_* for existing setups."""
    v = os.environ.get(primary)
    if v is not None and str(v).strip():
        return str(v).strip()
    if legacy is not None:
        v = os.environ.get(legacy)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def _env_int(primary: str, legacy: str | None = None, *, default: int) -> int:
    raw = os.environ.get(primary)
    if raw is None or not str(raw).strip():
        if legacy is not None:
            raw = os.environ.get(legacy)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


def _env_float(primary: str, legacy: str | None = None, *, default: float) -> float:
    raw = os.environ.get(primary)
    if raw is None or not str(raw).strip():
        if legacy is not None:
            raw = os.environ.get(legacy)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    stt_backend: str = _env_str("POTATO_STT_BACKEND", "PIPIT_STT_BACKEND", default="onnx_asr")
    # Parakeet TDT Windows all-in-one runs locally and exposes an OpenAI-style API.
    # API docs (community/packaging): http://127.0.0.1:5092/v1
    stt_api_url: str = _env_str(
        "POTATO_STT_API_URL",
        "PIPIT_STT_API_URL",
        default="http://127.0.0.1:5092/v1/audio/transcriptions",
    )
    stt_model: str = _env_str("POTATO_STT_MODEL", "PIPIT_STT_MODEL", default="parakeet")
    stt_response_format: str = _env_str(
        "POTATO_STT_RESPONSE_FORMAT",
        "PIPIT_STT_RESPONSE_FORMAT",
        default="json",
    )
    stt_timeout_seconds: int = _env_int(
        "POTATO_STT_TIMEOUT_SECONDS",
        "PIPIT_STT_TIMEOUT_SECONDS",
        default=120,
    )
    onnx_asr_model: str = _env_str(
        "POTATO_STT_ONNX_ASR_MODEL",
        "PIPIT_ONNX_ASR_MODEL",
        default="nemo-parakeet-tdt-0.6b-v3",
    )
    # Prefer DirectML (AMD-friendly on Windows), then CPU fallback.
    onnx_asr_providers: str = _env_str(
        "POTATO_STT_ONNX_ASR_PROVIDERS",
        "PIPIT_ONNX_ASR_PROVIDERS",
        default="DmlExecutionProvider,CPUExecutionProvider",
    )
    # When 1, ONNX ASR uses CPU only (no DirectML/GPU); ignores *_ONNX_ASR_PROVIDERS.
    cpu_only: bool = _env_int("POTATO_STT_CPU_ONLY", "PIPIT_CPU_ONLY", default=0) == 1
    # Long files are transcribed in segments to limit RAM (full-file ONNX can freeze the system).
    transcribe_chunk_seconds: float = _env_float(
        "POTATO_STT_TRANSCRIBE_CHUNK_SECONDS",
        "PIPIT_TRANSCRIBE_CHUNK_SECONDS",
        default=120.0,
    )

    # Download/extract the official Windows all-in-one package on first run.
    parakeet_win_url: str = _env_str(
        "POTATO_STT_PARAKEET_WIN_URL",
        "PIPIT_PARKEET_WIN_URL",
        default="https://huggingface.co/mortimerme/repocollect/resolve/main/parakeet-win-0707.7z?download=true",
    )
    # Where the downloaded package will be extracted.
    parakeet_install_dir: str = _env_str(
        "POTATO_STT_PARAKEET_INSTALL_DIR",
        "PIPIT_PARKEET_INSTALL_DIR",
        default=os.path.join(
            os.environ.get("LOCALAPPDATA", os.getcwd()),
            "potato_stt",
            "parakeet-win",
        ),
    )
    parakeet_launch_timeout_seconds: int = _env_int(
        "POTATO_STT_PARAKEET_LAUNCH_TIMEOUT_SECONDS",
        "PIPIT_PARKEET_LAUNCH_TIMEOUT_SECONDS",
        default=1800,
    )
    parakeet_auto_download: bool = (
        _env_int("POTATO_STT_PARAKEET_AUTO_DOWNLOAD", "PIPIT_PARKEET_AUTO_DOWNLOAD", default=1) == 1
    )
    parakeet_source_fallback: bool = (
        _env_int(
            "POTATO_STT_PARAKEET_SOURCE_FALLBACK",
            "PIPIT_PARKEET_SOURCE_FALLBACK",
            default=1,
        )
        == 1
    )
