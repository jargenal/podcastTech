from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class RenderManifestItem(BaseModel):
    order: int
    kind: Literal["speech", "pause"]
    status: Literal["pending", "rendered", "validated", "reused", "failed", "assembled"] = "pending"
    render_order: int | None = None
    language: str | None = None
    text: str = ""
    path: str | None = None
    pause_ms: int | None = None
    sensitive: bool = False
    sensitivity_reasons: list[str] = Field(default_factory=list)
    terminal: bool = False
    attempts: int = 0
    validation: dict[str, object] = Field(default_factory=dict)
    duration_ms: int | None = None
    error: str | None = None


class RenderManifest(BaseModel):
    job_id: str
    title: str
    mode: Literal["long_render"] = "long_render"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_seconds: float | None = None
    trigger_reason: str = ""
    total_items: int = 0
    total_speech_segments: int = 0
    output_files: dict[str, str | None] = Field(default_factory=dict)
    items: list[RenderManifestItem] = Field(default_factory=list)


class RenderManifestStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.manifest: RenderManifest | None = None

    def initialize(
        self,
        *,
        job_id: str,
        title: str,
        estimated_seconds: float | None,
        trigger_reason: str,
        total_items: int,
        total_speech_segments: int,
    ) -> RenderManifest:
        if self.path.exists():
            self.manifest = RenderManifest.model_validate_json(self.path.read_text(encoding="utf-8"))
            return self.manifest

        self.manifest = RenderManifest(
            job_id=job_id,
            title=title,
            estimated_seconds=estimated_seconds,
            trigger_reason=trigger_reason,
            total_items=total_items,
            total_speech_segments=total_speech_segments,
        )
        self.save()
        return self.manifest

    def upsert_item(self, item: RenderManifestItem) -> None:
        manifest = self._require_manifest()
        for index, current in enumerate(manifest.items):
            if current.order == item.order:
                manifest.items[index] = item
                break
        else:
            manifest.items.append(item)
        manifest.items.sort(key=lambda entry: entry.order)

    def mark_outputs(self, output_files: dict[str, str | None]) -> None:
        manifest = self._require_manifest()
        manifest.output_files = output_files

    def save(self) -> None:
        manifest = self._require_manifest()
        manifest.updated_at = datetime.utcnow()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _require_manifest(self) -> RenderManifest:
        if self.manifest is None:
            if not self.path.exists():
                raise RuntimeError("Render manifest has not been initialized.")
            self.manifest = RenderManifest.model_validate_json(self.path.read_text(encoding="utf-8"))
        return self.manifest
