from __future__ import annotations

import json
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
    order: int = 0
    text: str = ""
    sensitive: bool = False
    sensitivity_reasons: tuple[str, ...] = ()


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
        debug_path: Path | None = None,
        job_id: str | None = None,
        debug_metadata: dict[str, object] | None = None,
    ) -> tuple[OutputFiles, float, list[str]]:
        combined = AudioSegment.silent(duration=0)
        warnings: list[str] = []
        previous_item: RenderedAudioSegment | None = None
        trace_items: list[dict[str, object]] = []
        final_order = 0

        for item in sequence:
            final_order += 1
            if isinstance(item, int):
                start_ms = len(combined)
                combined += AudioSegment.silent(duration=item)
                trace_items.append(
                    {
                        "order": final_order,
                        "kind": "pause",
                        "pause_ms": item,
                        "start_ms": start_ms,
                        "end_ms": len(combined),
                    }
                )
                previous_item = None
            else:
                rendered = item if isinstance(item, RenderedAudioSegment) else RenderedAudioSegment(path=item, language="unknown")
                path = rendered.path
                language = rendered.language
                with path.open("rb") as audio_file:
                    segment = AudioSegment.from_file(audio_file)
                raw_duration_ms = len(segment)
                segment = self._smooth_segment(segment, sensitive=rendered.sensitive)
                join_strategy = self._join_strategy(previous_item, rendered)
                if previous_item is not None and len(combined) > 0:
                    crossfade_ms = self._effective_crossfade_ms(combined, segment, previous_item, rendered)
                    start_ms = max(0, len(combined) - crossfade_ms)
                    if crossfade_ms > 0:
                        combined = combined.append(segment, crossfade=crossfade_ms)
                    else:
                        combined += segment
                else:
                    crossfade_ms = 0
                    start_ms = len(combined)
                    combined += segment
                trace_items.append(
                    {
                        "order": final_order,
                        "kind": "speech",
                        "render_order": rendered.order,
                        "path": path.name,
                        "language": language,
                        "text": rendered.text,
                        "sensitive": rendered.sensitive,
                        "sensitivity_reasons": list(rendered.sensitivity_reasons),
                        "raw_duration_ms": raw_duration_ms,
                        "duration_ms": len(segment),
                        "start_ms": start_ms,
                        "end_ms": len(combined),
                        "join_strategy": join_strategy,
                        "crossfade_ms": crossfade_ms,
                        "fade_policy": self._fade_policy(rendered.sensitive, len(segment)),
                    }
                )
                previous_item = rendered

        if normalize_audio and len(combined) > 0:
            combined = effects.normalize(combined)

        stem = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
        wav_name = f"{stem}.wav"
        wav_path = self._settings.output_path / wav_name
        with combined.export(wav_path, format="wav"):
            pass

        mp3_name: str | None = None
        m4a_name: str | None = None
        ffmpeg_available = has_ffmpeg()
        if (export_mp3 or export_m4a) and not ffmpeg_available:
            warnings.append("FFmpeg no esta disponible; solo se exporto WAV.")

        if export_mp3 and ffmpeg_available:
            mp3_name = f"{stem}.mp3"
            with combined.export(self._settings.output_path / mp3_name, format="mp3", bitrate="192k"):
                pass

        if export_m4a and ffmpeg_available:
            m4a_name = f"{stem}.m4a"
            with combined.export(self._settings.output_path / m4a_name, format="ipod"):
                pass

        duration_seconds = round(len(combined) / 1000, 2)
        if debug_path is not None:
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "title": title,
                        "duration_seconds": duration_seconds,
                        "audio_tuning": self._settings.audio_tuning.model_dump(mode="json"),
                        "text_processing": debug_metadata or {},
                        "items": trace_items,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        return OutputFiles(wav=wav_name, mp3=mp3_name, m4a=m4a_name), duration_seconds, warnings

    def _smooth_segment(self, segment: AudioSegment, *, sensitive: bool) -> AudioSegment:
        if sensitive and self._settings.audio_tuning.disable_fades_for_sensitive_segments:
            return segment
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
        previous_item: RenderedAudioSegment,
        item: RenderedAudioSegment,
    ) -> int:
        if item.text and len(item.text) < self._settings.audio_tuning.min_chars_for_crossfade:
            return 0
        if previous_item.sensitive or item.sensitive:
            crossfade_ms = self._settings.audio_tuning.same_language_crossfade_for_sensitive_segments_ms
        elif previous_item.language and item.language and previous_item.language != item.language:
            crossfade_ms = self._settings.audio_tuning.bilingual_crossfade_ms
        elif self._settings.audio_tuning.same_language_crossfade_ms is not None:
            crossfade_ms = self._settings.audio_tuning.same_language_crossfade_ms
        else:
            crossfade_ms = self._settings.audio_tuning.crossfade_ms
        if self._settings.audio_tuning.segment_join_strategy == "conservative":
            crossfade_ms = min(crossfade_ms, self._settings.audio_tuning.same_language_crossfade_ms or crossfade_ms)
        if crossfade_ms <= 0:
            return 0
        if len(segment) < 900:
            return 0
        return min(crossfade_ms, max(0, len(combined) // 5), max(0, len(segment) // 5))

    def _join_strategy(self, previous_item: RenderedAudioSegment | None, item: RenderedAudioSegment) -> str:
        if previous_item is None:
            return "first_segment"
        if previous_item.language != item.language:
            return "language_boundary"
        if previous_item.sensitive or item.sensitive:
            return "sensitive_conservative"
        return self._settings.audio_tuning.segment_join_strategy

    def _fade_policy(self, sensitive: bool, duration_ms: int) -> str:
        if sensitive and self._settings.audio_tuning.disable_fades_for_sensitive_segments:
            return "disabled_sensitive_segment"
        if duration_ms < 900:
            return f"short_segment_{self._settings.audio_tuning.short_segment_fade_ms}ms"
        return f"default_{self._settings.audio_tuning.segment_fade_ms}ms"
