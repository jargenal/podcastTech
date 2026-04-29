from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydub import AudioSegment, effects
from pydub.silence import detect_leading_silence

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
    terminal: bool = False


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
                segment, segment_trace = self.prepare_segment_for_assembly(rendered)
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
                        "terminal": rendered.terminal,
                        "raw_duration_ms": segment_trace["raw_duration_ms"],
                        "duration_ms": len(segment),
                        "cleanup": segment_trace["cleanup"],
                        "start_ms": start_ms,
                        "end_ms": len(combined),
                        "join_strategy": join_strategy,
                        "crossfade_ms": crossfade_ms,
                        "fade_policy": self._fade_policy(rendered, len(segment)),
                        "temp_path": str(path),
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
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(wav_path),
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    str(self._settings.output_path / mp3_name),
                ]
            )

        if export_m4a and ffmpeg_available:
            m4a_name = f"{stem}.m4a"
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(wav_path),
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    str(self._settings.output_path / m4a_name),
                ]
            )

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

    def prepare_segment_for_assembly(self, rendered: RenderedAudioSegment) -> tuple[AudioSegment, dict[str, object]]:
        with rendered.path.open("rb") as audio_file:
            segment = AudioSegment.from_file(audio_file)
        raw_duration_ms = len(segment)
        segment, cleanup_trace = self._sanitize_segment(segment, rendered)
        segment = self._smooth_segment(segment, rendered=rendered)
        return segment, {
            "raw_duration_ms": raw_duration_ms,
            "duration_ms": len(segment),
            "cleanup": cleanup_trace,
        }

    def _sanitize_segment(
        self,
        segment: AudioSegment,
        rendered: RenderedAudioSegment,
    ) -> tuple[AudioSegment, dict[str, object]]:
        trace: dict[str, object] = {
            "enabled": self._settings.audio_tuning.enable_safe_audio_cleanup,
            "trimmed_leading_ms": 0,
            "trimmed_trailing_ms": 0,
            "trim_policy": "none",
        }
        if not self._settings.audio_tuning.enable_safe_audio_cleanup or len(segment) == 0:
            return segment, trace

        threshold = self._settings.audio_tuning.silence_trim_threshold_db
        leading_silence = detect_leading_silence(segment, silence_threshold=threshold, chunk_size=10)
        leading_trim = min(leading_silence, self._settings.audio_tuning.max_leading_silence_trim_ms)
        if leading_trim > 0:
            segment = segment[leading_trim:]
            trace["trimmed_leading_ms"] = leading_trim

        trailing_silence = detect_leading_silence(segment.reverse(), silence_threshold=threshold, chunk_size=10)
        preserved = self._settings.audio_tuning.preserved_trailing_silence_ms
        trailing_trim = max(0, trailing_silence - preserved)
        trailing_trim = min(trailing_trim, self._settings.audio_tuning.max_trailing_silence_trim_ms)
        if trailing_trim > 0:
            segment = segment[:-trailing_trim]
            trace["trimmed_trailing_ms"] = trailing_trim

        if leading_trim or trailing_trim:
            trace["trim_policy"] = "safe_silence_only"
        trace["terminal_word"] = _last_word(rendered.text)
        trace["terminal_word_protected"] = _needs_extra_terminal_tail(rendered)
        return segment, trace

    def _smooth_segment(self, segment: AudioSegment, *, rendered: RenderedAudioSegment) -> AudioSegment:
        if rendered.sensitive and self._settings.audio_tuning.disable_fades_for_sensitive_segments:
            return self._with_terminal_tail(segment, rendered=rendered)
        fade_in_ms = self._settings.audio_tuning.segment_fade_in_ms
        fade_out_ms = (
            self._settings.audio_tuning.terminal_segment_fade_out_ms
            if rendered.terminal
            else self._settings.audio_tuning.segment_fade_out_ms
        )
        if self._settings.audio_tuning.segment_fade_ms > 0:
            fade_in_ms = min(fade_in_ms, self._settings.audio_tuning.segment_fade_ms)
            fade_out_ms = min(fade_out_ms, self._settings.audio_tuning.segment_fade_ms)
        if len(segment) < 900:
            fade_in_ms = min(fade_in_ms, self._settings.audio_tuning.short_segment_fade_ms)
            fade_out_ms = min(fade_out_ms, self._settings.audio_tuning.short_segment_fade_ms)
        if len(segment) < max(fade_in_ms + fade_out_ms, 1) * 3:
            return self._with_terminal_tail(segment, rendered=rendered)
        if fade_in_ms > 0:
            segment = segment.fade_in(fade_in_ms)
        if fade_out_ms > 0:
            segment = segment.fade_out(fade_out_ms)
        return self._with_terminal_tail(segment, rendered=rendered)

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

    def _fade_policy(self, rendered: RenderedAudioSegment, duration_ms: int) -> str:
        tail = self._terminal_tail_ms(rendered)
        if rendered.sensitive and self._settings.audio_tuning.disable_fades_for_sensitive_segments:
            return f"disabled_sensitive_segment_tail_{tail}ms" if tail else "disabled_sensitive_segment"
        if duration_ms < 900:
            return f"short_segment_{self._settings.audio_tuning.short_segment_fade_ms}ms_tail_{tail}ms"
        fade_out = (
            self._settings.audio_tuning.terminal_segment_fade_out_ms
            if rendered.terminal
            else self._settings.audio_tuning.segment_fade_out_ms
        )
        return (
            f"in_{self._settings.audio_tuning.segment_fade_in_ms}ms_"
            f"out_{fade_out}ms_tail_{tail}ms"
        )

    def _with_terminal_tail(self, segment: AudioSegment, *, rendered: RenderedAudioSegment) -> AudioSegment:
        tail_ms = self._terminal_tail_ms(rendered)
        if tail_ms <= 0:
            return segment
        return segment + AudioSegment.silent(duration=tail_ms)

    def _terminal_tail_ms(self, rendered: RenderedAudioSegment) -> int:
        if not rendered.terminal:
            return 0
        tail_ms = self._settings.audio_tuning.terminal_segment_tail_silence_ms
        if _needs_extra_terminal_tail(rendered):
            tail_ms += self._settings.audio_tuning.terminal_long_token_extra_tail_silence_ms
        return tail_ms


def _last_word(text: str) -> str:
    words = [word.strip(".,;:!?()[]{}\"'") for word in text.split() if word.strip(".,;:!?()[]{}\"'")]
    return words[-1] if words else ""


def _needs_extra_terminal_tail(rendered: RenderedAudioSegment) -> bool:
    word = _last_word(rendered.text)
    return rendered.terminal and (rendered.sensitive or len(word) >= 11 or any(char.isupper() for char in word))


def _run_ffmpeg(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"FFmpeg fallo durante exportacion de audio: {details}") from exc
