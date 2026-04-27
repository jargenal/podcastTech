from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class BlockType(str, Enum):
    text = "text"
    pause = "pause"


class SpeechSpan(BaseModel):
    text: str
    language: str = "es"
    sensitive: bool = False
    sensitivity_reasons: list[str] = Field(default_factory=list)


class ParsedBlock(BaseModel):
    kind: BlockType
    text: str | None = None
    pause_ms: int | None = None
    spans: list[SpeechSpan] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    title: str = "Podcast técnico"
    variant: str = "es_latam"
    voice: str | None = None
    english_voice: str | None = None
    blocks: list[ParsedBlock] = Field(default_factory=list)
    source_filename: str | None = None


class GenerationOptions(BaseModel):
    variant: str = "es_latam"
    speaker_wav: str | None = None
    english_speaker_wav: str | None = None
    speed: float = 1.0
    english_speed: float | None = None
    segment_length: int = 260
    temperature: float = 0.65
    english_temperature: float | None = None
    normalize_audio: bool = True
    export_mp3: bool = False
    export_m4a: bool = False
    playlist_ids: list[str] = Field(default_factory=list)


class OutputFiles(BaseModel):
    wav: str
    mp3: str | None = None
    m4a: str | None = None


class HistoryItem(BaseModel):
    job_id: str
    title: str
    variant: str
    voice_name: str | None = None
    created_at: datetime
    duration_seconds: float | None = None
    estimated_seconds: float | None = None
    output_files: OutputFiles
    source_filename: str | None = None
    engine: Literal["xtts_v2"] = "xtts_v2"
    char_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    playlist_ids: list[str] = Field(default_factory=list)


class Playlist(BaseModel):
    id: str
    name: str
    created_at: datetime
    system: bool = False
    item_count: int = 0


class JobEvent(BaseModel):
    event: str
    payload: dict


class JobState(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.pending
    progress: int = 0
    message: str = "En cola"
    logs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    result: HistoryItem | None = None
    error: str | None = None
