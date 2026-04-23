from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import AsyncIterator

from app.models.domain import HistoryItem, JobState, JobStatus


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._subscribers: dict[str, list[asyncio.Queue[str]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def create(self, job_id: str) -> JobState:
        state = JobState(job_id=job_id)
        async with self._lock:
            self._jobs[job_id] = state
        return state

    async def get(self, job_id: str) -> JobState | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def snapshot(self, job_id: str) -> dict:
        state = await self.get(job_id)
        if state is None:
            return {}
        return state.model_dump(mode="json")

    async def update_status(self, job_id: str, *, status: JobStatus, message: str, progress: int | None = None) -> None:
        async with self._lock:
            state = self._jobs[job_id]
            state.status = status
            state.message = message
            if progress is not None:
                state.progress = progress
        await self._publish(job_id, "progress", {"status": status.value, "message": message, "progress": progress})

    async def add_log(self, job_id: str, message: str) -> None:
        async with self._lock:
            state = self._jobs[job_id]
            state.logs.append(message)
            state.logs = state.logs[-300:]
        await self._publish(job_id, "log", {"message": message})

    async def add_warning(self, job_id: str, message: str) -> None:
        async with self._lock:
            state = self._jobs[job_id]
            state.warnings.append(message)
        await self._publish(job_id, "warning", {"message": message})

    async def complete(self, job_id: str, result: HistoryItem) -> None:
        async with self._lock:
            state = self._jobs[job_id]
            state.status = JobStatus.completed
            state.progress = 100
            state.message = "Audio generado"
            state.result = result
        await self._publish(job_id, "completed", {"result": result.model_dump(mode="json")})

    async def fail(self, job_id: str, error: str) -> None:
        async with self._lock:
            state = self._jobs[job_id]
            state.status = JobStatus.failed
            state.message = "Error en la generación"
            state.error = error
        await self._publish(job_id, "failed", {"error": error})

    async def subscribe(self, job_id: str) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers[job_id].append(queue)
        initial = await self.snapshot(job_id)
        await queue.put(self._format_event("snapshot", initial))

        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[job_id].remove(queue)

    async def _publish(self, job_id: str, event: str, payload: dict) -> None:
        data = self._format_event(event, payload)
        for queue in list(self._subscribers.get(job_id, [])):
            await queue.put(data)

    @staticmethod
    def _format_event(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
