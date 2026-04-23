from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "audio"


def timestamped_filename(title: str, suffix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{slugify(title)}.{suffix}"


def safe_name(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")
