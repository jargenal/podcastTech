from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.config.settings import AppSettings
from app.models.domain import HistoryItem, Playlist


class HistoryService:
    DEFAULT_PLAYLIST_ID = "default"
    DEFAULT_PLAYLIST_NAME = "Default"

    def __init__(self, settings: AppSettings) -> None:
        self._history_path = settings.history_path
        self._playlists_path = settings.playlists_path
        self._ensure_storage()

    def list_items(self) -> list[HistoryItem]:
        data = self._read_payload(self._history_path, [])
        items = [HistoryItem.model_validate(item) for item in data]
        normalized = False
        valid_playlist_ids = {playlist.id for playlist in self.list_playlists()}
        for item in items:
            playlist_ids = [playlist_id for playlist_id in item.playlist_ids if playlist_id in valid_playlist_ids]
            if not playlist_ids:
                item.playlist_ids = [self.DEFAULT_PLAYLIST_ID]
                normalized = True
            elif playlist_ids != item.playlist_ids:
                item.playlist_ids = playlist_ids
                normalized = True

        items = sorted(items, key=lambda item: item.created_at, reverse=True)
        if normalized:
            self._write_items(items)
        return items

    def append(self, item: HistoryItem) -> None:
        items = self.list_items()
        item.playlist_ids = self.normalize_playlist_ids(item.playlist_ids)
        items = [item, *items]
        self._write_items(items[:100])

    def list_playlists(self) -> list[Playlist]:
        data = self._read_payload(self._playlists_path, [])
        playlists = [Playlist.model_validate(entry) for entry in data]
        playlists = self._ensure_default_playlist(playlists)
        counts = self._playlist_counts_from_payload(self._read_payload(self._history_path, []))
        ordered: list[Playlist] = []
        for playlist in playlists:
            playlist.item_count = counts.get(playlist.id, 0)
            ordered.append(playlist)
        ordered.sort(key=lambda playlist: (playlist.id != self.DEFAULT_PLAYLIST_ID, playlist.name.lower()))
        return ordered

    def create_playlist(self, name: str) -> Playlist:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Debes indicar un nombre para la playlist.")

        playlists = self.list_playlists()
        existing = next((playlist for playlist in playlists if playlist.name.casefold() == normalized_name.casefold()), None)
        if existing:
            return existing

        playlist = Playlist(
            id=uuid4().hex[:10],
            name=normalized_name,
            created_at=datetime.utcnow(),
            system=False,
        )
        self._write_playlists([*playlists, playlist])
        return playlist

    def normalize_playlist_ids(self, playlist_ids: list[str] | None) -> list[str]:
        selected = []
        valid_ids = {playlist.id for playlist in self.list_playlists()}
        for playlist_id in playlist_ids or []:
            if playlist_id in valid_ids and playlist_id not in selected:
                selected.append(playlist_id)
        return selected or [self.DEFAULT_PLAYLIST_ID]

    def get_playlist_map(self) -> dict[str, Playlist]:
        return {playlist.id: playlist for playlist in self.list_playlists()}

    def find_output(self, filename: str) -> Path | None:
        for item in self.list_items():
            files = item.output_files.model_dump()
            for value in files.values():
                if value == filename:
                    return self._history_path.parent / filename
        return None

    def _ensure_storage(self) -> None:
        if not self._history_path.exists():
            self._history_path.write_text("[]", encoding="utf-8")
        if not self._playlists_path.exists():
            default_playlist = Playlist(
                id=self.DEFAULT_PLAYLIST_ID,
                name=self.DEFAULT_PLAYLIST_NAME,
                created_at=datetime.utcnow(),
                system=True,
            )
            self._write_playlists([default_playlist])
        else:
            self._write_playlists(self._ensure_default_playlist(self._read_playlists()))

    def _ensure_default_playlist(self, playlists: list[Playlist]) -> list[Playlist]:
        if any(playlist.id == self.DEFAULT_PLAYLIST_ID for playlist in playlists):
            return playlists
        return [
            Playlist(
                id=self.DEFAULT_PLAYLIST_ID,
                name=self.DEFAULT_PLAYLIST_NAME,
                created_at=datetime.utcnow(),
                system=True,
            ),
            *playlists,
        ]

    def _playlist_counts_from_payload(self, payload: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in payload:
            playlist_ids = item.get("playlist_ids") or [self.DEFAULT_PLAYLIST_ID]
            for playlist_id in playlist_ids:
                counts[playlist_id] = counts.get(playlist_id, 0) + 1
        return counts

    def _read_playlists(self) -> list[Playlist]:
        data = self._read_payload(self._playlists_path, [])
        return [Playlist.model_validate(entry) for entry in data]

    def _write_items(self, items: list[HistoryItem]) -> None:
        payload = [entry.model_dump(mode="json") for entry in items]
        self._history_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def _write_playlists(self, playlists: list[Playlist]) -> None:
        serialized = []
        for playlist in playlists:
            serialized.append(playlist.model_dump(mode="json", exclude={"item_count"}))
        self._playlists_path.write_text(json.dumps(serialized, indent=2, ensure_ascii=True), encoding="utf-8")

    @staticmethod
    def _read_payload(path: Path, fallback: list) -> list:
        if not path.exists():
            return fallback
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else fallback
