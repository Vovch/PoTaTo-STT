from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import requests


def _coerce_to_text(payload: Any) -> Optional[str]:
    """
    Try to normalize different STT service response formats into a plain text string.
    """
    if payload is None:
        return None
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return None

    # OpenAI-style: {"text": "..."}
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    # Some wrappers: {"segments": [{"text": "..."}]}
    segments = payload.get("segments")
    if isinstance(segments, list):
        parts: list[str] = []
        for seg in segments:
            if isinstance(seg, dict):
                seg_text = seg.get("text")
                if isinstance(seg_text, str) and seg_text.strip():
                    parts.append(seg_text.strip())
        if parts:
            return " ".join(parts).strip()

    # Fallback: dump JSON for debugging.
    return None


def transcribe_wav(
    wav_path: str | Path,
    *,
    api_url: str,
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    response_format: Optional[str] = None,
    language: Optional[str] = None,
    timeout_seconds: int = 120,
) -> str:
    wav_path = Path(wav_path)
    if not wav_path.exists():
        raise FileNotFoundError(str(wav_path))

    with wav_path.open("rb") as f:
        files = {"file": (wav_path.name, f, "audio/wav")}
        data = {}

        # Parakeet packaged service follows an OpenAI-like multipart contract:
        # - model=parakeet
        # - prompt=en|ja
        # - response_format=json|srt|...
        # But other wrappers might use a different schema; keep `language` as fallback.
        if model is not None:
            data["model"] = model
        if prompt is not None:
            data["prompt"] = prompt
        if response_format is not None:
            data["response_format"] = response_format
        if language is not None and all(k not in data for k in ("prompt", "model")):
            data["language"] = language

        resp = requests.post(
            api_url,
            files=files,
            data=data,
            timeout=timeout_seconds,
        )

    resp.raise_for_status()

    # Best-effort parse.
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        payload = resp.text

    text = _coerce_to_text(payload)
    if text is not None:
        return text

    # As a last resort, try to stringify the JSON response.
    if isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False)
    if isinstance(payload, str):
        return payload.strip()

    return str(payload)

