from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from pathlib import Path

from app.config.settings import AppSettings
from app.models.domain import BlockType, GenerationOptions, HistoryItem, JobStatus, ParsedDocument, SpeechSpan
from app.services.audio_pipeline import AudioPipeline, RenderedAudioSegment
from app.services.base import BaseTTSService
from app.services.history_service import HistoryService
from app.services.job_manager import JobManager
from app.utils.files import safe_name
from app.utils.text_parser import parse_input_document
from app.utils.text_processing import TextProcessingDebug, estimate_duration_seconds, segment_spans_for_tts


class GenerationService:
    def __init__(
        self,
        *,
        settings: AppSettings,
        tts_service: BaseTTSService,
        audio_pipeline: AudioPipeline,
        history_service: HistoryService,
        job_manager: JobManager,
    ) -> None:
        self._settings = settings
        self._tts = tts_service
        self._audio_pipeline = audio_pipeline
        self._history = history_service
        self._jobs = job_manager

    async def generate(
        self,
        *,
        job_id: str,
        raw_text: str,
        options: GenerationOptions,
        title_hint: str | None,
        source_filename: str | None,
    ) -> None:
        try:
            await self._jobs.update_status(job_id, status=JobStatus.running, message="Preparando texto", progress=5)
            text_debug = TextProcessingDebug()
            document = parse_input_document(
                raw_text,
                settings=self._settings,
                selected_variant=options.variant,
                selected_voice=options.speaker_wav,
                selected_english_voice=options.english_speaker_wav,
                source_filename=source_filename or title_hint,
                debug=text_debug,
            )
            if not document.blocks:
                raise RuntimeError("No se encontro contenido de texto utilizable para sintetizar.")

            if title_hint:
                document.title = title_hint

            speaker_wav = self._resolve_voice_path(document, options, language="es")
            if speaker_wav is None:
                raise RuntimeError(
                    "No hay voz de referencia disponible. Coloca un .wav en /voices o sube uno desde la interfaz."
                )
            english_speaker_wav = self._resolve_voice_path(document, options, language="en", fallback=speaker_wav)

            total_characters = sum(len(block.text or "") for block in document.blocks)
            estimated_seconds = estimate_duration_seconds(
                " ".join(block.text or "" for block in document.blocks if block.kind == BlockType.text),
                options.speed,
            )
            await self._jobs.add_log(job_id, f"Documento analizado: {len(document.blocks)} bloques, {total_characters} caracteres.")
            await self._jobs.add_log(job_id, f"Voz activa: {speaker_wav.name} | variante: {document.variant}.")
            if english_speaker_wav and english_speaker_wav != speaker_wav:
                await self._jobs.add_log(job_id, f"Voz inglesa activa: {english_speaker_wav.name}.")
            if self._settings.eco_mode.enabled:
                await self._jobs.add_log(
                    job_id,
                    "Modo eco activo: limite de hilos aplicado y enfriamiento entre segmentos habilitado.",
                )

            sequence_plan = self._build_sequence(document, options.segment_length, debug=text_debug)
            total_steps = max(len(sequence_plan), 1)
            await self._jobs.add_log(job_id, f"Plan de render: {total_steps} items entre segmentos y pausas.")

            job_temp_dir = self._settings.temp_path / job_id
            job_temp_dir.mkdir(parents=True, exist_ok=True)

            audio_sequence: list[RenderedAudioSegment | int] = []
            rendered_segments = 0
            for index, item in enumerate(sequence_plan, start=1):
                progress = 10 + int((index - 1) / total_steps * 75)
                await self._jobs.update_status(
                    job_id,
                    status=JobStatus.running,
                    message=f"Procesando item {index}/{total_steps}",
                    progress=progress,
                )

                if isinstance(item, int):
                    audio_sequence.append(item)
                    await self._jobs.add_log(job_id, f"Silencio insertado: {item} ms.")
                    await asyncio.sleep(0)
                    continue

                rendered_segments += 1
                segment_path = job_temp_dir / f"segment-{rendered_segments:04d}.wav"
                await self._jobs.add_log(
                    job_id,
                    f"Sintetizando segmento {rendered_segments} [{item.language}]: {item.text[:90]}...",
                )
                await asyncio.to_thread(
                    self._tts.synthesize_segment,
                    text=item.text,
                    output_path=segment_path,
                    speaker_wav=english_speaker_wav if item.language == "en" else speaker_wav,
                    variant=document.variant,
                    language=item.language,
                    speed=options.english_speed if item.language == "en" and options.english_speed is not None else options.speed,
                    temperature=(
                        options.english_temperature
                        if item.language == "en" and options.english_temperature is not None
                        else options.temperature
                    ),
                )
                audio_sequence.append(
                    RenderedAudioSegment(
                        path=segment_path,
                        language=item.language,
                        order=rendered_segments,
                        text=item.text,
                        sensitive=item.sensitive,
                        sensitivity_reasons=tuple(item.sensitivity_reasons),
                        terminal=self._is_terminal_sequence_item(sequence_plan, index - 1),
                    )
                )
                cooldown_seconds = self._segment_cooldown_seconds()
                if cooldown_seconds > 0 and index < total_steps:
                    await asyncio.sleep(cooldown_seconds)
                await asyncio.sleep(0)

            await self._jobs.update_status(job_id, status=JobStatus.running, message="Montando audio final", progress=90)
            output_files, duration_seconds, pipeline_warnings = await asyncio.to_thread(
                self._audio_pipeline.assemble,
                sequence=audio_sequence,
                title=document.title,
                normalize_audio=options.normalize_audio,
                export_mp3=options.export_mp3,
                export_m4a=options.export_m4a,
                debug_path=self._settings.output_path / "debug" / f"{job_id}.json",
                job_id=job_id,
                debug_metadata={
                    "transformations": text_debug.transformations,
                    "technical_tokens": text_debug.technical_tokens,
                    "protected_zones": text_debug.protected_zones,
                    "segmentation_events": text_debug.segmentation_events,
                    "segment_merges": text_debug.segment_merges,
                    "sensitive_segments": text_debug.sensitive_segments,
                },
            )

            for warning in pipeline_warnings:
                await self._jobs.add_warning(job_id, warning)

            item = HistoryItem(
                job_id=job_id,
                title=document.title,
                variant=document.variant,
                voice_name=speaker_wav.name,
                created_at=datetime.utcnow(),
                duration_seconds=duration_seconds,
                estimated_seconds=estimated_seconds,
                output_files=output_files,
                source_filename=source_filename,
                char_count=total_characters,
                warnings=pipeline_warnings,
                playlist_ids=options.playlist_ids,
            )
            self._history.append(item)
            await self._jobs.complete(job_id, item)
        except Exception as exc:
            await self._jobs.add_log(job_id, f"Fallo en el job: {exc}")
            await self._jobs.fail(job_id, str(exc))
        finally:
            job_temp_dir = self._settings.temp_path / job_id
            if job_temp_dir.exists():
                shutil.rmtree(job_temp_dir, ignore_errors=True)

    def _resolve_voice_path(
        self,
        document: ParsedDocument,
        options: GenerationOptions,
        *,
        language: str,
        fallback: Path | None = None,
    ) -> Path | None:
        if language == "en":
            candidates: list[str | None] = [document.english_voice, options.english_speaker_wav, document.voice, options.speaker_wav]
        else:
            candidates = [document.voice, options.speaker_wav]
        variant_profile = self._settings.variants.get(document.variant)
        if variant_profile:
            candidates.append(variant_profile.default_voice)
            if variant_profile.fallback_variant:
                fallback = self._settings.variants.get(variant_profile.fallback_variant)
                if fallback:
                    candidates.append(fallback.default_voice)
        candidates.append(self._settings.default_voice)

        for value in candidates:
            if not value:
                continue
            path = Path(value)
            if not path.is_absolute():
                path = self._settings.voices_path / safe_name(path.name)
            if path.exists() and path.suffix.lower() == ".wav":
                return path

        # Last resort: use any available reference voice so renders do not depend
        # on a perfectly aligned per-variant setup.
        available_voices = sorted(self._settings.voices_path.glob("*.wav"))
        if available_voices:
            return available_voices[0]
        return fallback

    def _build_sequence(
        self,
        document: ParsedDocument,
        segment_length: int,
        *,
        debug: TextProcessingDebug | None = None,
    ) -> list[SpeechSpan | int]:
        sequence: list[SpeechSpan | int] = []
        for block in document.blocks:
            if block.kind == BlockType.pause and block.pause_ms is not None:
                sequence.append(block.pause_ms)
                continue
            if block.spans:
                sequence.extend(
                    segment_spans_for_tts(
                        block.spans,
                        max_chars=segment_length,
                        sentence_pause_ms=self._settings.audio_tuning.sentence_pause_ms,
                        bilingual_transition_pause_ms=self._bilingual_transition_pause_ms(),
                        strip_terminal_periods=self._strip_terminal_periods(),
                        reading_mode=self._settings.audio_tuning.reading_mode,
                        min_segment_chars=self._settings.audio_tuning.min_segment_chars,
                        settings=self._settings,
                        debug=debug,
                    )
                )
        return sequence

    def _bilingual_transition_pause_ms(self) -> int:
        if self._settings.audio_tuning.reading_mode == "technical_paragraph":
            return self._settings.audio_tuning.technical_bilingual_transition_pause_ms
        return self._settings.audio_tuning.bilingual_transition_pause_ms

    def _strip_terminal_periods(self) -> bool:
        if self._settings.audio_tuning.preserve_terminal_punctuation:
            return False
        return self._settings.audio_tuning.strip_terminal_periods

    def _is_terminal_sequence_item(self, sequence: list[SpeechSpan | int], index: int) -> bool:
        if index >= len(sequence) - 1:
            return True
        next_item = sequence[index + 1]
        return isinstance(next_item, int)

    def _segment_cooldown_seconds(self) -> float:
        if not self._settings.eco_mode.enabled:
            return 0.0
        return max(0, self._settings.eco_mode.inter_segment_cooldown_ms) / 1000
