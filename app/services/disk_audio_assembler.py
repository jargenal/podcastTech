from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from pydub import AudioSegment, effects

from app.config.settings import AppSettings
from app.models.domain import OutputFiles
from app.services.audio_pipeline import AudioPipeline, RenderedAudioSegment
from app.utils.files import slugify
from app.utils.system import has_ffmpeg


class DiskAudioAssembler:
    def __init__(self, settings: AppSettings, audio_pipeline: AudioPipeline) -> None:
        self._settings = settings
        self._audio_pipeline = audio_pipeline

    def assemble(
        self,
        *,
        sequence: list[RenderedAudioSegment | int],
        title: str,
        render_dir: Path,
        normalize_audio: bool,
        export_mp3: bool,
        export_m4a: bool,
        debug_path: Path | None = None,
        job_id: str | None = None,
        debug_metadata: dict[str, object] | None = None,
    ) -> tuple[OutputFiles, float, list[str]]:
        if not self._settings.long_render.assemble_with_ffmpeg_concat:
            raise RuntimeError(
                "El render en disco requiere long_render.assemble_with_ffmpeg_concat=true; "
                "no se permite fallback silencioso a ensamblado en memoria."
            )

        if not has_ffmpeg():
            raise RuntimeError("long_render requiere FFmpeg para ensamblar desde disco sin cargar todo el audio en RAM.")

        processed_dir = render_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        concat_path = render_dir / "concat.txt"
        warnings: list[str] = []
        trace_items: list[dict[str, object]] = []
        concat_files: list[Path] = []
        cursor_ms = 0
        previous_item: RenderedAudioSegment | None = None

        for final_order, item in enumerate(sequence, start=1):
            if isinstance(item, int):
                path = processed_dir / f"{final_order:05d}-pause.wav"
                pause = self._target_format(AudioSegment.silent(duration=item))
                with pause.export(path, format="wav"):
                    pass
                start_ms = cursor_ms
                cursor_ms += item
                concat_files.append(path)
                trace_items.append(
                    {
                        "order": final_order,
                        "kind": "pause",
                        "path": path.name,
                        "pause_ms": item,
                        "start_ms": start_ms,
                        "end_ms": cursor_ms,
                    }
                )
                previous_item = None
                continue

            prepared, segment_trace = self._audio_pipeline.prepare_segment_for_assembly(item)
            if normalize_audio and self._settings.long_render.normalize_per_segment:
                prepared = effects.normalize(prepared)
            prepared = self._target_format(prepared)

            path = processed_dir / f"{final_order:05d}-speech-{item.order:04d}.wav"
            with prepared.export(path, format="wav"):
                pass

            start_ms = cursor_ms
            cursor_ms += len(prepared)
            concat_files.append(path)
            trace_items.append(
                {
                    "order": final_order,
                    "kind": "speech",
                    "render_order": item.order,
                    "path": path.name,
                    "source_path": str(item.path),
                    "language": item.language,
                    "text": item.text,
                    "sensitive": item.sensitive,
                    "sensitivity_reasons": list(item.sensitivity_reasons),
                    "terminal": item.terminal,
                    "raw_duration_ms": segment_trace["raw_duration_ms"],
                    "duration_ms": len(prepared),
                    "cleanup": segment_trace["cleanup"],
                    "start_ms": start_ms,
                    "end_ms": cursor_ms,
                    "join_strategy": self._join_strategy(previous_item, item),
                    "crossfade_ms": 0,
                    "fade_policy": self._audio_pipeline._fade_policy(item, len(prepared)),  # noqa: SLF001
                    "temp_path": str(item.path),
                    "processed_path": str(path),
                }
            )
            previous_item = item

        if not concat_files:
            raise RuntimeError("No hay audio para ensamblar.")

        concat_path.write_text("".join(f"file '{_ffmpeg_concat_path(path)}'\n" for path in concat_files), encoding="utf-8")

        stem = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
        wav_name = f"{stem}.wav"
        wav_path = self._settings.output_path / wav_name

        self._run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ]
        )

        if normalize_audio and self._settings.long_render.normalize_final_with_ffmpeg:
            normalized_path = wav_path.with_name(f"{wav_path.stem}.normalized.wav")
            self._run_ffmpeg(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(wav_path),
                    "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11",
                    str(normalized_path),
                ]
            )
            normalized_path.replace(wav_path)
        elif normalize_audio and not self._settings.long_render.normalize_per_segment:
            warnings.append("long_render omitio normalizacion en memoria; activa normalize_final_with_ffmpeg para normalizar el WAV final.")

        mp3_name: str | None = None
        m4a_name: str | None = None
        if export_mp3:
            mp3_name = f"{stem}.mp3"
            self._run_ffmpeg(
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
        if export_m4a:
            m4a_name = f"{stem}.m4a"
            self._run_ffmpeg(
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

        duration_seconds = round(cursor_ms / 1000, 2)
        if debug_path is not None:
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "title": title,
                        "mode": "long_render",
                        "duration_seconds": duration_seconds,
                        "render_dir": str(render_dir),
                        "concat_file": str(concat_path),
                        "long_render": self._settings.long_render.model_dump(mode="json"),
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

        if self._settings.long_render.cleanup_after_success and not self._settings.long_render.keep_temp_segments:
            shutil.rmtree(render_dir, ignore_errors=True)

        return OutputFiles(wav=wav_name, mp3=mp3_name, m4a=m4a_name), duration_seconds, warnings

    def _target_format(self, segment: AudioSegment) -> AudioSegment:
        return (
            segment
            .set_frame_rate(self._settings.long_render.concat_sample_rate)
            .set_channels(self._settings.long_render.concat_channels)
            .set_sample_width(2)
        )

    def _join_strategy(self, previous_item: RenderedAudioSegment | None, item: RenderedAudioSegment) -> str:
        if previous_item is None:
            return "disk_concat_first_segment"
        if previous_item.language != item.language:
            return "disk_concat_language_boundary"
        if previous_item.sensitive or item.sensitive:
            return "disk_concat_sensitive_no_crossfade"
        return "disk_concat_no_crossfade"

    @staticmethod
    def _run_ffmpeg(command: list[str]) -> None:
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(f"FFmpeg fallo durante long_render: {details}") from exc


def _ffmpeg_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")
