from __future__ import annotations

import json
from pathlib import Path


class LexiconFileCache:
    def __init__(self) -> None:
        self._cache: dict[Path, tuple[int, dict[str, str]]] = {}

    def load(self, path: Path) -> dict[str, str]:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return {}

        mtime_ns = stat.st_mtime_ns
        cached = self._cache.get(path)
        if cached and cached[0] == mtime_ns:
            return cached[1]

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Lexicon file must contain a JSON object: {path}")

        normalized = {str(key): str(value) for key, value in data.items()}
        self._cache[path] = (mtime_ns, normalized)
        return normalized


lexicon_file_cache = LexiconFileCache()
