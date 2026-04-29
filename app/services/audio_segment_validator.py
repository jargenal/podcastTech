from __future__ import annotations

from pathlib import Path
import re

from pydantic import BaseModel
from pydub import AudioSegment

from app.config.settings import AppSettings


class SegmentValidationResult(BaseModel):
    ok: bool
    path: str
    duration_ms: int = 0
    channels: int | None = None
    frame_rate: int | None = None
    sample_width: int | None = None
    dBFS: float | None = None
    max_dBFS: float | None = None
    rms: int | None = None
    file_size_bytes: int = 0
    expected_min_duration_ms: int | None = None
    reason: str = "ok"


class AudioSegmentValidator:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def validate(self, path: Path, *, text: str = "") -> SegmentValidationResult:
        file_size_bytes = path.stat().st_size if path.exists() else 0
        if not path.exists() or file_size_bytes <= 44:
            return SegmentValidationResult(ok=False, path=str(path), reason="missing_or_empty_file")

        try:
            audio = AudioSegment.from_file(path)
        except Exception as exc:
            return SegmentValidationResult(ok=False, path=str(path), reason=f"decode_failed:{exc}")

        duration_ms = len(audio)
        dBFS = None if audio.dBFS == float("-inf") else round(audio.dBFS, 2)
        max_dBFS = None if audio.max_dBFS == float("-inf") else round(audio.max_dBFS, 2)
        expected_min_duration_ms = _expected_min_duration_ms(text)
        result = SegmentValidationResult(
            ok=True,
            path=str(path),
            duration_ms=duration_ms,
            channels=audio.channels,
            frame_rate=audio.frame_rate,
            sample_width=audio.sample_width,
            dBFS=dBFS,
            max_dBFS=max_dBFS,
            rms=audio.rms,
            file_size_bytes=file_size_bytes,
            expected_min_duration_ms=expected_min_duration_ms,
        )

        if duration_ms < self._settings.long_render.min_segment_duration_ms:
            result.ok = False
            result.reason = "too_short"
            return result

        if dBFS is None or dBFS < self._settings.long_render.silence_threshold_db:
            result.ok = False
            result.reason = "near_silent"
            return result

        if audio.rms <= 0:
            result.ok = False
            result.reason = "zero_rms"
            return result

        if max_dBFS is not None and max_dBFS >= -0.05:
            result.ok = False
            result.reason = "possible_clipping"
            return result

        if audio.frame_rate < 16000:
            result.ok = False
            result.reason = "sample_rate_too_low"
            return result

        if audio.channels < 1 or audio.sample_width < 2:
            result.ok = False
            result.reason = "unsupported_pcm_shape"
            return result

        # Long technical chunks can be short after cleanup, but a substantial
        # text producing a tiny clip is usually a failed or truncated XTTS render.
        if expected_min_duration_ms is not None and duration_ms < expected_min_duration_ms:
            result.ok = False
            result.reason = "implausibly_short_for_text"
            return result

        return result


def _expected_min_duration_ms(text: str) -> int | None:
    words = re.findall(r"\w+", text)
    if len(words) < 10:
        return None
    # Very conservative lower bound: 330 words per minute is faster than normal
    # technical narration, but catches hard truncation without rejecting brisk reads.
    return max(900, int(len(words) / 330 * 60_000))
