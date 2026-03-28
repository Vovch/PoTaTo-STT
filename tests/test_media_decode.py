from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from helpers import first_user_test_media, write_silence_wav_16k

from potato_stt.media_decode import (
    decode_to_temp_wav_16k_mono,
    extract_chunk_wav_16k_mono,
    probe_media_duration_seconds,
)


class TestMediaDecode(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_probe_16k_wav_duration(self) -> None:
        p = write_silence_wav_16k(self.tmp / "silence.wav", 0.5)
        d = probe_media_duration_seconds(p)
        self.assertTrue(0.45 <= d <= 0.55)

    def test_decode_to_temp_preserves_format(self) -> None:
        src = write_silence_wav_16k(self.tmp / "in.wav", 0.5)
        tmp, meas = decode_to_temp_wav_16k_mono(src)
        try:
            self.assertTrue(tmp.is_file())
            self.assertTrue(0.45 <= meas <= 0.55)
            d2 = probe_media_duration_seconds(tmp)
            self.assertLess(abs(d2 - meas), 0.05)
        finally:
            tmp.unlink(missing_ok=True)

    def test_extract_chunk_mid_file(self) -> None:
        src = write_silence_wav_16k(self.tmp / "long.wav", 35.0)
        chunk, meas = extract_chunk_wav_16k_mono(src, start_sec=10.0, duration_sec=5.0)
        try:
            self.assertTrue(chunk.is_file())
            self.assertTrue(4.8 <= meas <= 5.2)
            d = probe_media_duration_seconds(chunk)
            self.assertTrue(4.8 <= d <= 5.2)
        finally:
            chunk.unlink(missing_ok=True)


class TestUserTestFileMedia(unittest.TestCase):
    """Runs when repo-root test_file/ contains a media sample."""

    def test_user_media_probe_if_available(self) -> None:
        media = first_user_test_media()
        if media is None:
            self.skipTest("No media in test_file/ (add audio/video there to run this check)")
        d = probe_media_duration_seconds(media)
        self.assertGreater(d, 0.01)

    def test_user_media_extract_short_segment(self) -> None:
        media = first_user_test_media()
        if media is None:
            self.skipTest("No media in test_file/ (add audio/video there to run this check)")
        dur = probe_media_duration_seconds(media)
        take = min(2.0, max(0.5, dur * 0.1))
        try:
            chunk, meas = extract_chunk_wav_16k_mono(media, start_sec=0.0, duration_sec=take)
        except RuntimeError as e:
            if "ffmpeg" in str(e).lower():
                self.skipTest(f"FFmpeg required: {e}")
            raise
        try:
            self.assertTrue(chunk.is_file())
            self.assertGreater(meas, 0.1)
        finally:
            chunk.unlink(missing_ok=True)
