from __future__ import annotations

import shutil


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None
