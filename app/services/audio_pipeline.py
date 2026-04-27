from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydub import AudioSegment, effects

from app.config.settings import AppSettings
from app.models.domain import OutputFiles
from app.utils.files import slugify
from app.utils.system import has_ffmpeg


@dataclass(frozen=True)
class RenderedAudioSegment:
    path: Path
    language: str


class AudioPipeline:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def assemble(
        self,
        *,
        sequence: list[RenderedAudioSegment | Path | int],
        title: str,
        normalize_audio: bool,
        export_mp3: bool,
        export_m4a: bool,
    ) -> tuple[OutputFiles, float, list[str]]:
        combined = AudioSegment.silent(duration=0)
        warnings: list[str] = []
        previous_language: str | None = None

        for item in sequence:
            if isinstance(item, int):
                combined += AudioSegment.silent(duration=item)
                previous_language = None
            else:
                path = item.path if isinstance(item, RenderedAudioSegment) else item
                language = item.language if isinstance(item, RenderedAudioSegment) else None
                segment = AudioSegment.from_file(path)
                segment = self._smooth_segment(segment)
                if previous_language is not None and len(combined) > 0:
                    crossfade_ms = self._effective_crossfade_ms(combined, segment, previous_language, language)
                    if crossfade_ms > 0:
                        combined = combined.append(segment, crossfade=crossfade_ms)
                    else:
                        combined += segment
                else:
                    combined += segment
                previous_language = language or "unknown"

        if normalize_audio and len(combined) > 0:
            combined = effects.normalize(combined)

        stem = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
        wav_name = f"{stem}.wav"
        wav_path = self._settings.output_path / wav_name
        combined.export(wav_path, format="wav")

        mp3_name: str | None = None
        m4a_name: str | None = None
        ffmpeg_available = has_ffmpeg()
        if (export_mp3 or export_m4a) and not ffmpeg_available:
            warnings.append("FFmpeg no esta disponible; solo se exporto WAV.")

        if export_mp3 and ffmpeg_available:
            mp3_name = f"{stem}.mp3"
            combined.export(self._settings.output_path / mp3_name, format="mp3", bitrate="192k")

        if export_m4a and ffmpeg_available:
            m4a_name = f"{stem}.m4a"
            combined.export(self._settings.output_path / m4a_name, format="ipod")

        duration_seconds = round(len(combined) / 1000, 2)
        return OutputFiles(wav=wav_name, mp3=mp3_name, m4a=m4a_name), duration_seconds, warnings

    def _smooth_segment(self, segment: AudioSegment) -> AudioSegment:
        fade_ms = self._settings.audio_tuning.segment_fade_ms
        if len(segment) < 900:
            fade_ms = min(fade_ms, self._settings.audio_tuning.short_segment_fade_ms)
        if fade_ms <= 0 or len(segment) < fade_ms * 3:
            return segment
        return segment.fade_in(fade_ms).fade_out(fade_ms)

    def _effective_crossfade_ms(
        self,
        combined: AudioSegment,
        segment: AudioSegment,
        previous_language: str | None,
        language: str | None,
    ) -> int:
        if previous_language and language and previous_language != language:
            crossfade_ms = self._settings.audio_tuning.bilingual_crossfade_ms
        elif self._settings.audio_tuning.same_language_crossfade_ms is not None:
            crossfade_ms = self._settings.audio_tuning.same_language_crossfade_ms
        else:
            crossfade_ms = self._settings.audio_tuning.crossfade_ms
        if crossfade_ms <= 0:
            return 0
        if len(segment) < 900:
            return 0
        return min(crossfade_ms, max(0, len(combined) // 5), max(0, len(segment) // 5))
