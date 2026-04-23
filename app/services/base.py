from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseTTSService(ABC):
    engine_name: str

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Return availability and diagnostic message."""

    @abstractmethod
    def synthesize_segment(
        self,
        *,
        text: str,
        output_path: Path,
        speaker_wav: Path | None,
        variant: str,
        language: str | None,
        speed: float,
        temperature: float,
    ) -> None:
        """Generate speech for a single segment."""
