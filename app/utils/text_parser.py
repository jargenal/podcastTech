from __future__ import annotations

from app.config.settings import AppSettings
from app.models.domain import BlockType, ParsedBlock, ParsedDocument
from app.utils.text_processing import adapt_text_to_speech_spans, normalize_text, render_speech_spans


KNOWN_TAGS = {"TITULO", "IDIOMA", "VOZ", "VOZ_EN", "TEXTO", "PAUSA"}


def parse_input_document(
    raw_text: str,
    *,
    settings: AppSettings,
    selected_variant: str,
    selected_voice: str | None,
    selected_english_voice: str | None,
    source_filename: str | None = None,
) -> ParsedDocument:
    text = raw_text.strip()
    variant_profile = settings.variants.get(selected_variant)
    block_language = variant_profile.tts_language if variant_profile else settings.default_language
    if not text:
        return ParsedDocument(
            title="Podcast técnico",
            variant=selected_variant,
            voice=selected_voice,
            english_voice=selected_english_voice,
            blocks=[],
            source_filename=source_filename,
        )

    if not _has_tags(text):
        spans = adapt_text_to_speech_spans(normalize_text(text), settings, default_language=block_language)
        cleaned = render_speech_spans(spans)
        return ParsedDocument(
            title=source_filename or "Podcast técnico",
            variant=selected_variant,
            voice=selected_voice,
            english_voice=selected_english_voice,
            blocks=[ParsedBlock(kind=BlockType.text, text=cleaned, spans=spans)] if cleaned else [],
            source_filename=source_filename,
        )

    lines = [line.rstrip() for line in text.splitlines()]
    title = source_filename or "Podcast técnico"
    variant = selected_variant
    voice = selected_voice
    english_voice = selected_english_voice
    blocks: list[ParsedBlock] = []
    current_tag: str | None = None
    current_buffer: list[str] = []

    def flush() -> None:
        nonlocal block_language, current_tag, current_buffer, title, variant, voice, english_voice
        value = "\n".join(line for line in current_buffer if line.strip()).strip()
        if current_tag == "TITULO" and value:
            title = value
        elif current_tag == "IDIOMA" and value:
            variant = value if value in settings.variants else selected_variant
            variant_profile = settings.variants.get(variant)
            block_language = variant_profile.tts_language if variant_profile else settings.default_language
        elif current_tag == "VOZ" and value:
            voice = value
        elif current_tag == "VOZ_EN" and value:
            english_voice = value
        elif current_tag == "TEXTO" and value:
            spans = adapt_text_to_speech_spans(normalize_text(value), settings, default_language=block_language)
            blocks.append(ParsedBlock(kind=BlockType.text, text=render_speech_spans(spans), spans=spans))
        elif current_tag == "PAUSA":
            pause_ms = _parse_pause(value, settings.default_pause_ms)
            blocks.append(ParsedBlock(kind=BlockType.pause, pause_ms=pause_ms))
        current_tag = None
        current_buffer = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            tag = stripped[1:-1].strip().upper()
            if tag in KNOWN_TAGS:
                flush()
                current_tag = tag
                continue
        if not stripped and current_tag is None:
            continue
        if current_tag is None:
            current_tag = "TEXTO"
        current_buffer.append(line)

    flush()

    blocks = [block for block in blocks if (block.text or block.pause_ms)]
    return ParsedDocument(
        title=title,
        variant=variant,
        voice=voice,
        english_voice=english_voice,
        blocks=blocks,
        source_filename=source_filename,
    )


def _has_tags(text: str) -> bool:
    return any(line.strip().upper() in {f"[{tag}]" for tag in KNOWN_TAGS} for line in text.splitlines())


def _parse_pause(value: str, default_ms: int) -> int:
    try:
        return max(0, int(value.strip()))
    except (TypeError, ValueError):
        return default_ms
