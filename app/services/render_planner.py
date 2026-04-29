from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.config.settings import AppSettings
from app.models.domain import BlockType, GenerationOptions, ParsedDocument, SpeechSpan
from app.utils.text_processing import TextProcessingDebug


RenderStrategy = Literal["standard_memory_render", "safe_disk_render", "long_disk_render", "critical_disk_render"]
RiskLevel = Literal["low", "medium", "high", "critical"]


class RenderPlan(BaseModel):
    strategy: RenderStrategy
    risk_level: RiskLevel
    estimated_seconds: float | None = None
    estimated_minutes: float | None = None
    total_characters: int = 0
    total_items: int = 0
    speech_segments: int = 0
    pause_segments: int = 0
    paragraphs: int = 0
    pauses: int = 0
    technical_token_count: int = 0
    english_span_count: int = 0
    sensitive_segment_count: int = 0
    requested_output_formats: list[str] = Field(default_factory=list)
    requires_disk: bool = False
    allows_memory_assembly: bool = True
    requires_ffmpeg: bool = False
    ffmpeg_available: bool = False
    normalization_policy: str = "memory_normalize_or_disabled"
    quality_policy: str = "standard_quality_checks"
    segment_validation_policy: str = "basic_decode_validation"
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def summary(self) -> str:
        return ", ".join(self.reason_codes) if self.reason_codes else "low_risk_standard_memory"


class RenderPlanner:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def plan(
        self,
        *,
        raw_text: str,
        document: ParsedDocument,
        sequence_plan: list[SpeechSpan | int],
        options: GenerationOptions,
        estimated_seconds: float | None,
        text_debug: TextProcessingDebug,
        ffmpeg_available: bool,
    ) -> RenderPlan:
        safety = self._settings.render_safety
        total_characters = sum(len(block.text or "") for block in document.blocks) or len(raw_text.strip())
        total_items = len(sequence_plan)
        speech_items = [item for item in sequence_plan if not isinstance(item, int)]
        speech_segments = len(speech_items)
        pause_segments = total_items - speech_segments
        paragraphs = sum(_paragraph_count(block.text or "") for block in document.blocks if block.kind == BlockType.text)
        pauses = sum(1 for block in document.blocks if block.kind == BlockType.pause) + pause_segments
        technical_token_count = len(text_debug.technical_tokens)
        english_span_count = sum(
            1
            for block in document.blocks
            for span in block.spans
            if span.language == "en"
        ) or sum(1 for item in speech_items if item.language == "en")
        english_speech_segment_count = sum(1 for item in speech_items if item.language == "en")
        sensitive_segment_count = sum(1 for item in speech_items if item.sensitive)
        requested_output_formats = ["wav"]
        if options.export_mp3:
            requested_output_formats.append("mp3")
        if options.export_m4a:
            requested_output_formats.append("m4a")

        reason_codes: list[str] = []
        warnings: list[str] = []
        risk_score = 0

        estimated_minutes = round(estimated_seconds / 60, 2) if estimated_seconds is not None else None
        if estimated_seconds is not None:
            if estimated_seconds >= safety.critical_disk_min_estimated_seconds:
                reason_codes.append("estimated_duration_critical")
                risk_score = max(risk_score, 4)
            elif estimated_seconds >= safety.long_disk_min_estimated_seconds:
                reason_codes.append("estimated_duration_over_20_minutes")
                risk_score = max(risk_score, 3)
            elif estimated_seconds >= safety.safe_disk_min_estimated_seconds:
                reason_codes.append("estimated_duration_prefers_disk")
                risk_score = max(risk_score, 2)
            if estimated_seconds > safety.memory_max_estimated_seconds:
                reason_codes.append("estimated_duration_over_safe_memory_limit")
                risk_score = max(risk_score, 2)

        if speech_segments >= safety.critical_disk_min_speech_segments:
            reason_codes.append("speech_segments_critical")
            risk_score = max(risk_score, 4)
        elif speech_segments >= safety.long_disk_min_speech_segments:
            reason_codes.append("speech_segments_over_long_disk_threshold")
            risk_score = max(risk_score, 3)
        elif speech_segments >= safety.safe_disk_min_speech_segments:
            reason_codes.append("speech_segments_prefers_disk")
            risk_score = max(risk_score, 2)
        if speech_segments > safety.memory_max_speech_segments:
            reason_codes.append("speech_segments_over_safe_memory_limit")
            risk_score = max(risk_score, 2)
        if total_items > safety.memory_max_total_items:
            reason_codes.append("total_items_over_safe_memory_limit")
            risk_score = max(risk_score, 2)
        if total_characters > safety.memory_max_characters:
            reason_codes.append("characters_over_safe_memory_limit")
            risk_score = max(risk_score, 2)

        technical_density = technical_token_count / max(total_characters, 1)
        english_ratio = english_speech_segment_count / max(speech_segments, 1)
        sensitive_ratio = sensitive_segment_count / max(speech_segments, 1)
        if technical_density >= safety.technical_density_high_ratio:
            reason_codes.append("technical_density_high")
            risk_score = max(risk_score, 2)
        if english_ratio >= safety.english_span_high_ratio:
            reason_codes.append("english_span_density_high")
            risk_score = max(risk_score, 2)
        if sensitive_ratio >= safety.sensitive_segment_high_ratio:
            reason_codes.append("sensitive_segment_density_high")
            risk_score = max(risk_score, 2)
        if options.export_mp3 or options.export_m4a:
            reason_codes.append("compressed_export_requires_stable_wav_base")

        if self._settings.long_render.force or options.long_render is True:
            reason_codes.append("disk_render_forced")
            risk_score = max(risk_score, 3)
        elif options.long_render is False and risk_score >= 2:
            warnings.append("long_render=false fue ignorado porque el plan requiere ensamblado seguro en disco.")

        if not self._settings.long_render.enabled and risk_score >= 2:
            warnings.append("long_render.enabled=false fue ignorado porque el plan requiere ensamblado seguro en disco.")

        strategy: RenderStrategy
        if risk_score >= 4:
            strategy = "critical_disk_render"
        elif risk_score >= 3:
            strategy = "long_disk_render"
        elif risk_score >= 2:
            strategy = "safe_disk_render"
        else:
            strategy = "standard_memory_render"

        requires_disk = strategy != "standard_memory_render"
        allows_memory_assembly = not requires_disk
        requires_ffmpeg = requires_disk or options.export_mp3 or options.export_m4a
        if requires_ffmpeg and not ffmpeg_available:
            if requires_disk:
                warnings.append("FFmpeg no esta disponible y el plan requiere render en disco; el job fallara antes de ensamblar.")
            else:
                warnings.append("FFmpeg no esta disponible; las exportaciones MP3/M4A se omitiran.")

        risk_level: RiskLevel = "low"
        if strategy == "safe_disk_render":
            risk_level = "medium"
        elif strategy == "long_disk_render":
            risk_level = "high"
        elif strategy == "critical_disk_render":
            risk_level = "critical"

        normalization_policy = "memory_normalize_or_disabled"
        quality_policy = "standard_quality_checks"
        segment_validation_policy = "basic_decode_validation"
        if requires_disk:
            normalization_policy = (
                "ffmpeg_final_loudnorm"
                if options.normalize_audio and self._settings.long_render.normalize_final_with_ffmpeg
                else "ffmpeg_final_or_disabled"
            )
            quality_policy = "strict_segment_validation"
            segment_validation_policy = "decode_duration_loudness_plausibility"

        return RenderPlan(
            strategy=strategy,
            risk_level=risk_level,
            estimated_seconds=estimated_seconds,
            estimated_minutes=estimated_minutes,
            total_characters=total_characters,
            total_items=total_items,
            speech_segments=speech_segments,
            pause_segments=pause_segments,
            paragraphs=paragraphs,
            pauses=pauses,
            technical_token_count=technical_token_count,
            english_span_count=english_span_count,
            sensitive_segment_count=sensitive_segment_count,
            requested_output_formats=requested_output_formats,
            requires_disk=requires_disk,
            allows_memory_assembly=allows_memory_assembly,
            requires_ffmpeg=requires_ffmpeg,
            ffmpeg_available=ffmpeg_available,
            normalization_policy=normalization_policy,
            quality_policy=quality_policy,
            segment_validation_policy=segment_validation_policy,
            reason_codes=reason_codes,
            warnings=warnings,
        )


def _paragraph_count(text: str) -> int:
    return len([part for part in text.split("\n\n") if part.strip()]) if text.strip() else 0
