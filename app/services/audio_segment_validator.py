from __future__ import annotations

from pathlib import Path

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
    reason: str = "ok"


class AudioSegmentValidator:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def validate(self, path: Path, *, text: str = "") -> SegmentValidationResult:
        if not path.exists() or path.stat().st_size <= 44:
            return SegmentValidationResult(ok=False, path=str(path), reason="missing_or_empty_file")

        try:
            audio = AudioSegment.from_file(path)
        except Exception as exc:
            return SegmentValidationResult(ok=False, path=str(path), reason=f"decode_failed:{exc}")

        duration_ms = len(audio)
        dBFS = None if audio.dBFS == float("-inf") else round(audio.dBFS, 2)
        result = SegmentValidationResult(
            ok=True,
            path=str(path),
            duration_ms=duration_ms,
            channels=audio.channels,
            frame_rate=audio.frame_rate,
            sample_width=audio.sample_width,
            dBFS=dBFS,
        )

        if duration_ms < self._settings.long_render.min_segment_duration_ms:
            result.ok = False
            result.reason = "too_short"
            return result

        if dBFS is None or dBFS < self._settings.long_render.silence_threshold_db:
            result.ok = False
            result.reason = "near_silent"
            return result

        # Long technical chunks can be short after normalization, but a long text
        # producing a tiny clip is usually a failed XTTS render worth retrying.
        if len(text) >= 80 and duration_ms < 900:
            result.ok = False
            result.reason = "implausibly_short_for_text"
            return result

        return result
