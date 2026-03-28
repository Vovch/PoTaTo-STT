from __future__ import annotations

from pathlib import Path

import numpy as np

from potato_stt.audio_utils import write_wav_from_int16_pcm


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def write_silence_wav_16k(path: Path, seconds: float) -> Path:
    samples = int(seconds * 16000)
    pcm = np.zeros(samples, dtype=np.int16)
    write_wav_from_int16_pcm(pcm, path, sample_rate=16000)
    return path


def first_user_test_media() -> Path | None:
    folder = repo_root() / "test_file"
    if not folder.is_dir():
        return None
    exts = {
        ".wav",
        ".mp3",
        ".m4a",
        ".aac",
        ".flac",
        ".ogg",
        ".opus",
        ".wma",
        ".mp4",
        ".mkv",
        ".webm",
        ".mov",
        ".avi",
    }
    candidates = sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts
    )
    return candidates[0] if candidates else None
