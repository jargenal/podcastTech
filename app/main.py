from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config.settings import ROOT_DIR, get_settings
from app.routes.web import router
from app.services.audio_pipeline import AudioPipeline
from app.services.generation_service import GenerationService
from app.services.history_service import HistoryService
from app.services.job_manager import JobManager
from app.services.xtts_service import XTTSService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.job_manager = JobManager()
    app.state.history_service = HistoryService(settings)
    app.state.tts_service = XTTSService(settings)
    app.state.audio_pipeline = AudioPipeline(settings)
    app.state.generation_service = GenerationService(
        settings=settings,
        tts_service=app.state.tts_service,
        audio_pipeline=app.state.audio_pipeline,
        history_service=app.state.history_service,
        job_manager=app.state.job_manager,
    )
    yield


app = FastAPI(title="PodcastTech Offline TTS", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "app" / "static")), name="static")
app.include_router(router)
