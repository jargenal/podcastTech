from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import AppSettings
from app.models.domain import BlockType, GenerationOptions, HistoryItem, Playlist, SpeechSpan
from app.utils.files import safe_name
from app.utils.system import has_ffmpeg
from app.utils.text_parser import parse_input_document
from app.utils.text_processing import TextProcessingDebug, segment_spans_for_tts


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    settings: AppSettings = request.app.state.settings
    history_items = request.app.state.history_service.list_items()[:8]
    playlists = request.app.state.history_service.list_playlists()
    engine_ok, engine_message = request.app.state.tts_service.is_available()
    context = {
        "request": request,
        "settings": settings,
        "variants": settings.variants,
        "voices": _list_voices(settings),
        "history_items": history_items,
        "playlist_map": request.app.state.history_service.get_playlist_map(),
        "playlists": playlists,
        "engine_ok": engine_ok,
        "engine_message": engine_message,
        "ffmpeg_available": has_ffmpeg(),
    }
    return templates.TemplateResponse("index.html", context)


@router.post("/generate")
async def generate(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    settings: AppSettings = request.app.state.settings
    form = await request.form()

    text_input, source_filename = await _resolve_text_input(form, settings)
    title = str(form.get("title") or "").strip() or None
    variant = str(form.get("variant") or settings.default_variant)
    voice_name = str(form.get("voice_name") or "").strip() or None
    english_voice_name = str(form.get("english_voice_name") or "").strip() or None
    speed = float(form.get("speed") or settings.default_speed)
    english_speed = float(form.get("english_speed") or settings.default_english_speed)
    segment_length = int(form.get("segment_length") or settings.default_segment_length)
    temperature = float(form.get("temperature") or settings.default_temperature)
    english_temperature = float(form.get("english_temperature") or settings.default_english_temperature)
    normalize_audio = str(form.get("normalize_audio") or "true").lower() == "true"
    export_mp3 = str(form.get("export_mp3") or "false").lower() == "true"
    export_m4a = str(form.get("export_m4a") or "false").lower() == "true"
    long_render = _resolve_optional_bool(form.get("long_render"))
    playlist_ids = _resolve_playlist_selection(form, request.app.state.history_service)

    voice_upload = form.get("voice_upload")
    english_voice_upload = form.get("english_voice_upload")

    voice_name = await _store_uploaded_voice(voice_upload, settings, detail="La voz de referencia debe ser un archivo .wav") or voice_name
    english_voice_name = (
        await _store_uploaded_voice(english_voice_upload, settings, detail="La voz inglesa debe ser un archivo .wav")
        or english_voice_name
    )

    if not text_input.strip():
        raise HTTPException(status_code=400, detail="Debes subir un archivo .txt/.md o escribir texto manualmente.")

    if variant not in settings.variants:
        variant = settings.default_variant

    options = GenerationOptions(
        variant=variant,
        speaker_wav=voice_name,
        english_speaker_wav=english_voice_name,
        speed=max(0.7, min(speed, 1.4)),
        english_speed=max(0.7, min(english_speed, 1.4)),
        segment_length=max(120, min(segment_length, 450)),
        temperature=max(0.1, min(temperature, 1.2)),
        english_temperature=max(0.1, min(english_temperature, 1.2)),
        normalize_audio=normalize_audio,
        export_mp3=export_mp3,
        export_m4a=export_m4a,
        long_render=long_render,
        playlist_ids=playlist_ids,
    )

    job_id = uuid4().hex[:12]
    await request.app.state.job_manager.create(job_id)
    background_tasks.add_task(
        request.app.state.generation_service.generate,
        job_id=job_id,
        raw_text=text_input,
        options=options,
        title_hint=title,
        source_filename=source_filename,
    )
    return JSONResponse({"job_id": job_id, "events_url": f"/events/{job_id}"})


@router.post("/preview-text")
async def preview_text(request: Request) -> JSONResponse:
    settings: AppSettings = request.app.state.settings
    form = await request.form()
    text_input, source_filename = await _resolve_text_input(form, settings, archive=False)
    if not text_input.strip():
        raise HTTPException(status_code=400, detail="Debes subir un archivo .txt/.md o escribir texto manualmente.")

    variant = str(form.get("variant") or settings.default_variant)
    if variant not in settings.variants:
        variant = settings.default_variant
    segment_length = max(120, min(int(form.get("segment_length") or settings.default_segment_length), 450))

    debug = TextProcessingDebug()
    document = parse_input_document(
        text_input,
        settings=settings,
        selected_variant=variant,
        selected_voice=str(form.get("voice_name") or "").strip() or None,
        selected_english_voice=str(form.get("english_voice_name") or "").strip() or None,
        source_filename=source_filename,
        debug=debug,
    )
    preview_lines: list[str] = []
    blocks_payload: list[dict[str, object]] = []
    segments_payload: list[dict[str, object]] = []
    for block in document.blocks:
        if block.text:
            preview_lines.append(block.text)
            blocks_payload.append(
                {
                    "kind": block.kind.value,
                    "text": block.text,
                    "spans": [
                        {
                            "language": span.language,
                            "text": span.text,
                            "sensitive": span.sensitive,
                            "sensitivity_reasons": span.sensitivity_reasons,
                        }
                        for span in block.spans
                    ],
                }
            )
            segments_payload.extend(_preview_segments(block.spans, settings, segment_length=segment_length, debug=debug))
        elif block.pause_ms is not None:
            preview_lines.append(f"[PAUSA {block.pause_ms} ms]")
            blocks_payload.append({"kind": block.kind.value, "pause_ms": block.pause_ms})
            segments_payload.append({"kind": "pause", "pause_ms": block.pause_ms, "source": "block"})

    debug_payload = {
        "reading_mode": settings.audio_tuning.reading_mode,
        "spans": [
            {
                "language": span.language,
                "text": span.text,
                "sensitive": span.sensitive,
                "sensitivity_reasons": span.sensitivity_reasons,
            }
            for block in document.blocks
            for span in block.spans
            if block.kind == BlockType.text
        ],
        "segments": segments_payload,
        "transformations": debug.transformations,
        "technical_tokens": debug.technical_tokens,
        "protected_zones": debug.protected_zones,
        "segmentation_events": debug.segmentation_events,
        "segment_merges": debug.segment_merges,
        "sensitive_segments": debug.sensitive_segments,
    }
    debug_text = "\n\n[DEBUG TTS]\n" + _format_preview_debug(debug_payload)

    return JSONResponse(
        {
            "title": document.title,
            "variant": document.variant,
            "preview_text": ("\n\n".join(preview_lines).strip() + debug_text).strip(),
            "blocks": blocks_payload,
            "debug": debug_payload,
        }
    )


def _preview_segments(
    spans: list[SpeechSpan],
    settings: AppSettings,
    *,
    segment_length: int,
    debug: TextProcessingDebug,
) -> list[dict[str, object]]:
    sequence = segment_spans_for_tts(
        spans,
        max_chars=segment_length,
        sentence_pause_ms=settings.audio_tuning.sentence_pause_ms,
        bilingual_transition_pause_ms=(
            settings.audio_tuning.technical_bilingual_transition_pause_ms
            if settings.audio_tuning.reading_mode == "technical_paragraph"
            else settings.audio_tuning.bilingual_transition_pause_ms
        ),
        strip_terminal_periods=False if settings.audio_tuning.preserve_terminal_punctuation else settings.audio_tuning.strip_terminal_periods,
        reading_mode=settings.audio_tuning.reading_mode,
        min_segment_chars=settings.audio_tuning.min_segment_chars,
        settings=settings,
        debug=debug,
    )
    payload: list[dict[str, object]] = []
    for item in sequence:
        if isinstance(item, int):
            payload.append({"kind": "pause", "pause_ms": item, "source": "segmenter"})
        else:
            payload.append(
                {
                    "kind": "speech",
                    "language": item.language,
                    "text": item.text,
                    "sensitive": item.sensitive,
                    "sensitivity_reasons": item.sensitivity_reasons,
                }
            )
    return payload


def _format_preview_debug(payload: dict[str, object]) -> str:
    lines = [f"reading_mode: {payload['reading_mode']}"]
    lines.append("spans:")
    for span in payload["spans"]:  # type: ignore[index]
        lines.append(f"- [{span['language']}] {span['text']}")  # type: ignore[index]
    lines.append("segmentos:")
    for segment in payload["segments"]:  # type: ignore[index]
        if segment["kind"] == "pause":  # type: ignore[index]
            lines.append(f"- [PAUSA] {segment['pause_ms']} ms ({segment['source']})")  # type: ignore[index]
        else:
            marker = " sensitive" if segment.get("sensitive") else ""  # type: ignore[attr-defined]
            reasons = ", ".join(segment.get("sensitivity_reasons") or [])  # type: ignore[attr-defined]
            suffix = f" ({reasons})" if reasons else ""
            lines.append(f"- [{segment['language']}]{marker} {segment['text']}{suffix}")  # type: ignore[index]
    lines.append("protected_zones:")
    protected_zones = payload["protected_zones"]  # type: ignore[index]
    if protected_zones:
        for zone in protected_zones:
            lines.append(f"- {zone['word']} [{zone['language']}] {', '.join(zone['reasons'])}")
    else:
        lines.append("- ninguna")
    lines.append("segment_merges:")
    segment_merges = payload["segment_merges"]  # type: ignore[index]
    if segment_merges:
        for merge in segment_merges:
            lines.append(f"- {merge['reason']}: {merge['incoming_text']}")
    else:
        lines.append("- ninguno")
    lines.append("no_cut_events:")
    segmentation_events = payload["segmentation_events"]  # type: ignore[index]
    if segmentation_events:
        for event in segmentation_events:
            lines.append(f"- {event['reason']}: {event['previous_word']} -> {event['next_word']}")
    else:
        lines.append("- ninguno")
    lines.append("transformaciones:")
    transformations = payload["transformations"]  # type: ignore[index]
    if transformations:
        for item in transformations:
            lines.append(f"- {item['token']} -> {item['output']} ({item['reason']})")
    else:
        lines.append("- ninguna")
    lines.append("tokens_tecnicos:")
    technical_tokens = payload["technical_tokens"]  # type: ignore[index]
    if technical_tokens:
        for item in technical_tokens:
            lines.append(f"- {item['token']} -> {item['output']} ({item['reason']})")
            for part in item.get("parts") or []:
                lines.append(f"  - {part['input']} -> {part['output']} ({part['strategy']})")
    else:
        lines.append("- ninguno")
    return "\n".join(lines)


@router.post("/playlists")
async def create_playlist(request: Request):
    form = await request.form()
    name = str(form.get("name") or form.get("playlist_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Debes indicar un nombre para la playlist.")
    playlist = request.app.state.history_service.create_playlist(name)
    redirect_to = str(form.get("redirect_to") or f"/history?playlist={playlist.id}")
    return RedirectResponse(url=redirect_to, status_code=303)


@router.get("/events/{job_id}")
async def events(request: Request, job_id: str) -> StreamingResponse:
    stream = request.app.state.job_manager.subscribe(job_id)
    return StreamingResponse(stream, media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/audio/{filename}")
async def audio_file(request: Request, filename: str) -> FileResponse:
    path = _resolve_output_file(request, filename)
    media_type, _ = mimetypes.guess_type(path.name)
    return FileResponse(
        path,
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.get("/download/{filename}")
async def download_file(request: Request, filename: str) -> FileResponse:
    path = _resolve_output_file(request, filename)
    return FileResponse(path, filename=path.name)


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request, format: str | None = None):  # noqa: A002
    history_service = request.app.state.history_service
    playlists = history_service.list_playlists()
    playlist_map = {playlist.id: playlist for playlist in playlists}
    playlist_query = str(request.query_params.get("playlist_q") or "").strip()
    episode_query = str(request.query_params.get("episode_q") or "").strip()
    show_all_playlists = str(request.query_params.get("show_all") or "").strip() in {"1", "true", "yes"}
    filtered_playlists = _filter_playlists(playlists, playlist_query)
    visible_playlists = filtered_playlists if show_all_playlists else filtered_playlists[:5]
    visible_playlist_ids = {playlist.id for playlist in visible_playlists}
    selected_playlist_id = str(request.query_params.get("playlist") or "").strip() or None
    if selected_playlist_id not in playlist_map or (visible_playlists and selected_playlist_id not in visible_playlist_ids):
        if selected_playlist_id in playlist_map and not show_all_playlists and not playlist_query:
            visible_playlists = [playlist_map[selected_playlist_id], *[
                playlist for playlist in visible_playlists if playlist.id != selected_playlist_id
            ]][:5]
        selected_playlist_id = visible_playlists[0].id if visible_playlists else None

    all_items = history_service.list_items()
    items = all_items
    if selected_playlist_id and selected_playlist_id in playlist_map:
        items = [item for item in items if selected_playlist_id in item.playlist_ids]
    if episode_query:
        items = _filter_history_items(items, episode_query, playlist_map)
    if format == "json":
        return JSONResponse(_serialize_history_items(items, playlist_map))
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "history_items": items,
            "playlist_map": playlist_map,
            "playlists": playlists,
            "visible_playlists": visible_playlists,
            "selected_playlist_id": selected_playlist_id,
            "selected_playlist": playlist_map.get(selected_playlist_id) if selected_playlist_id else None,
            "total_items_count": len(all_items),
            "playlist_query": playlist_query,
            "episode_query": episode_query,
            "show_all_playlists": show_all_playlists,
            "has_more_playlists": len(filtered_playlists) > len(visible_playlists),
            "settings": request.app.state.settings,
            "engine_ok": request.app.state.tts_service.is_available()[0],
            "engine_message": request.app.state.tts_service.is_available()[1],
            "ffmpeg_available": has_ffmpeg(),
        },
    )


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    settings: AppSettings = request.app.state.settings
    engine_ok, engine_message = request.app.state.tts_service.is_available()
    payload = {
        "status": "ok",
        "engine": request.app.state.tts_service.engine_name,
        "engine_available": engine_ok,
        "engine_message": engine_message,
        "ffmpeg_available": has_ffmpeg(),
        "default_variant": settings.default_variant,
        "eco_mode": settings.eco_mode.model_dump(mode="json"),
        "long_render": settings.long_render.model_dump(mode="json"),
        "voices_available": _list_voices(settings),
    }
    return JSONResponse(payload)


def _list_voices(settings: AppSettings) -> list[str]:
    return sorted(path.name for path in settings.voices_path.glob("*.wav"))


def _resolve_output_file(request: Request, filename: str) -> Path:
    safe_filename = safe_name(filename)
    path = request.app.state.settings.output_path / safe_filename
    if not path.exists():
        history_match = request.app.state.history_service.find_output(safe_filename)
        if history_match is None or not history_match.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        path = history_match
    return path


def _is_uploaded_file(value: object) -> bool:
    return isinstance(value, UploadFile) or (
        hasattr(value, "filename") and
        hasattr(value, "read")
    )


async def _resolve_text_input(form, settings: AppSettings, *, archive: bool = True) -> tuple[str, str | None]:
    text_input = str(form.get("text_input") or "")
    source_filename: str | None = None
    text_file = form.get("text_file")
    if not _is_uploaded_file(text_file) or not text_file.filename:
        return text_input, source_filename

    suffix = Path(text_file.filename).suffix.lower()
    if suffix not in {".txt", ".md"}:
        raise HTTPException(status_code=400, detail="El archivo de entrada debe ser .txt o .md")

    raw_bytes = await text_file.read()
    try:
        text_input = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text_input = raw_bytes.decode("utf-8", errors="ignore")

    source_filename = safe_name(text_file.filename)
    if archive:
        archived_input = settings.input_path / f"{uuid4().hex[:8]}-{source_filename}"
        archived_input.write_text(text_input, encoding="utf-8")
    return text_input, source_filename


async def _store_uploaded_voice(upload, settings: AppSettings, *, detail: str) -> str | None:
    if not _is_uploaded_file(upload) or not upload.filename:
        return None
    if Path(upload.filename).suffix.lower() != ".wav":
        raise HTTPException(status_code=400, detail=detail)
    voice_name = safe_name(upload.filename)
    voice_path = settings.voices_path / voice_name
    voice_path.write_bytes(await upload.read())
    return voice_name


def _resolve_playlist_selection(form, history_service) -> list[str]:
    playlist_ids = [value for value in form.getlist("playlist_ids") if value]
    quick_name = str(form.get("new_playlist_name") or "").strip()
    if quick_name:
        if playlist_ids == [history_service.DEFAULT_PLAYLIST_ID]:
            playlist_ids = []
        playlist = history_service.create_playlist(quick_name)
        playlist_ids.append(playlist.id)
    return history_service.normalize_playlist_ids(playlist_ids)


def _resolve_optional_bool(value: object) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "force"}:
        return True
    if normalized in {"0", "false", "no", "off", "standard"}:
        return False
    return None


def _serialize_history_items(items: list[HistoryItem], playlist_map: dict[str, Playlist]) -> list[dict]:
    payload: list[dict] = []
    for item in items:
        serialized = item.model_dump(mode="json")
        serialized["playlist_names"] = [
            playlist_map[playlist_id].name
            for playlist_id in item.playlist_ids
            if playlist_id in playlist_map
        ]
        payload.append(serialized)
    return payload


def _filter_playlists(playlists: list[Playlist], query: str) -> list[Playlist]:
    if not query:
        return playlists
    needle = query.casefold()
    return [playlist for playlist in playlists if needle in playlist.name.casefold()]


def _filter_history_items(items: list[HistoryItem], query: str, playlist_map: dict[str, Playlist]) -> list[HistoryItem]:
    needle = query.casefold()
    filtered: list[HistoryItem] = []
    for item in items:
        haystacks = [
            item.title,
            item.variant,
            item.voice_name or "",
            item.source_filename or "",
            " ".join(
                playlist_map[playlist_id].name
                for playlist_id in item.playlist_ids
                if playlist_id in playlist_map
            ),
        ]
        if any(needle in value.casefold() for value in haystacks if value):
            filtered.append(item)
    return filtered
