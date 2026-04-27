from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.models.domain import SpeechSpan


SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;:])\s+")
SENTENCE_WITH_PUNCTUATION = re.compile(r".+?(?:[.!?;:]+(?=\s|$)|$)", re.DOTALL)
INLINE_PRONUNCIATION = re.compile(r"\[PRON\](.+?)\[/PRON\]", re.IGNORECASE | re.DOTALL)
INLINE_ENGLISH = re.compile(r"\[EN\](.+?)\[/EN\]", re.IGNORECASE | re.DOTALL)
BRACKETED_INLINE_TOKEN = re.compile(r"\[(?!/?(?:PRON|EN)\b)([A-Za-z0-9][A-Za-z0-9+.#/_-]*)\]")
ACRONYM_TOKEN = re.compile(r"\b[A-Z]{2,}(?:[/-][A-Z]{2,})*\b")
WORD_TOKEN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")
TECHNICAL_TOKEN = re.compile(r"\b[A-Za-z0-9]+(?:[./_][A-Za-z0-9]+)*\b")
CAMEL_OR_DIGIT_BOUNDARY = re.compile(
    r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])"
)
LETTER_PRONUNCIATION = {
    "A": "ei",
    "B": "bi",
    "C": "si",
    "D": "di",
    "E": "i",
    "F": "ef",
    "G": "yi",
    "H": "eich",
    "I": "ai",
    "J": "jei",
    "K": "kei",
    "L": "el",
    "M": "em",
    "N": "en",
    "O": "ou",
    "P": "pi",
    "Q": "kiu",
    "R": "ar",
    "S": "es",
    "T": "ti",
    "U": "iu",
    "V": "vi",
    "W": "dobliu",
    "X": "eks",
    "Y": "uai",
    "Z": "zi",
}
NUMBER_PRONUNCIATION = {
    "0": "siro",
    "1": "uan",
    "2": "tu",
    "3": "tri",
    "4": "for",
    "5": "faiv",
    "6": "siks",
    "7": "seven",
    "8": "eit",
    "9": "nain",
}

if TYPE_CHECKING:
    from app.config.settings import AppSettings


@dataclass
class TextProcessingDebug:
    transformations: list[dict[str, str]] = field(default_factory=list)

    def add(self, *, token: str, output: str, reason: str) -> None:
        if token != output:
            self.transformations.append({"token": token, "output": output, "reason": reason})


def normalize_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("–", "-")
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"`{1,3}", "", cleaned)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"_(.*?)_", r"\1", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = BRACKETED_INLINE_TOKEN.sub(r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def adapt_text_for_speech(text: str, settings: AppSettings) -> str:
    return _adapt_text_for_speech(text, settings)


def adapt_text_for_speech_debug(text: str, settings: AppSettings) -> tuple[str, TextProcessingDebug]:
    debug = TextProcessingDebug()
    adapted = _adapt_text_for_speech(text, settings, debug=debug)
    return adapted, debug


def _adapt_text_for_speech(text: str, settings: AppSettings, *, debug: TextProcessingDebug | None = None) -> str:
    if not text or not settings.speech.enabled:
        return text.strip()

    placeholders: dict[str, str] = {}
    adapted = text
    if settings.speech.restore_spanish_accents:
        adapted = _restore_spanish_accents(adapted, settings.speech.accent_lexicon)
    adapted = _extract_inline_pronunciations(adapted, placeholders)
    adapted = _extract_english_spans(adapted, placeholders, settings)
    adapted = _apply_pronunciation_lexicon(adapted, settings)
    adapted = _adapt_technical_tokens(adapted, settings, debug=debug)
    if settings.speech.spell_acronyms:
        adapted = _expand_acronyms(adapted)
    adapted = _restore_placeholders(adapted, placeholders)
    adapted = re.sub(r"\s{2,}", " ", adapted)
    adapted = re.sub(r"\s+([,.;:!?])", r"\1", adapted)
    return adapted.strip()


def adapt_text_to_speech_spans(
    text: str,
    settings: AppSettings,
    *,
    default_language: str = "es",
    debug: TextProcessingDebug | None = None,
) -> list[SpeechSpan]:
    if not text.strip():
        return []

    placeholders: dict[str, str] = {}
    prepared = _extract_inline_pronunciations(text, placeholders)
    spans: list[SpeechSpan] = []
    cursor = 0

    for match in INLINE_ENGLISH.finditer(prepared):
        before = prepared[cursor:match.start()]
        spans.extend(_build_speech_spans(before, settings, language=default_language, placeholders=placeholders, debug=debug))
        spans.extend(_build_speech_spans(match.group(1), settings, language="en", placeholders=placeholders, debug=debug))
        cursor = match.end()

    spans.extend(_build_speech_spans(prepared[cursor:], settings, language=default_language, placeholders=placeholders, debug=debug))
    return _merge_adjacent_spans(spans)


def render_speech_spans(spans: list[SpeechSpan]) -> str:
    rendered = " ".join(span.text.strip() for span in spans if span.text.strip())
    rendered = re.sub(r"\s{2,}", " ", rendered)
    rendered = re.sub(r"\s+([,.;:!?])", r"\1", rendered)
    return rendered.strip()


def segment_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return []

    segments: list[str] = []
    for paragraph in paragraphs:
        sentences = [part.strip() for part in SENTENCE_BOUNDARY.split(paragraph) if part.strip()]
        current = ""
        for sentence in sentences or [paragraph]:
            if len(sentence) > max_chars:
                if current:
                    segments.append(current.strip())
                    current = ""
                segments.extend(_split_long_sentence(sentence, max_chars))
                continue
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > max_chars:
                segments.append(current.strip())
                current = sentence
            else:
                current = candidate
        if current:
            segments.append(current.strip())
    return segments


def segment_text_for_tts(
    text: str,
    *,
    max_chars: int,
    sentence_pause_ms: int,
    strip_terminal_periods: bool,
) -> list[str | int]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return []

    sequence: list[str | int] = []
    for paragraph in paragraphs:
        sentences = _extract_sentences(paragraph)
        for index, sentence in enumerate(sentences):
            chunks = _segment_sentence(sentence, max_chars=max_chars, strip_terminal_periods=strip_terminal_periods)
            sequence.extend(chunk for chunk in chunks if chunk)
            if index < len(sentences) - 1 and sentence_pause_ms > 0:
                sequence.append(sentence_pause_ms)
    return sequence


def segment_spans_for_tts(
    spans: list[SpeechSpan],
    *,
    max_chars: int,
    sentence_pause_ms: int,
    bilingual_transition_pause_ms: int,
    strip_terminal_periods: bool,
    reading_mode: str = "standard",
    min_segment_chars: int = 0,
) -> list[SpeechSpan | int]:
    if reading_mode == "technical_paragraph":
        return _segment_spans_for_technical_paragraph(
            spans,
            max_chars=max_chars,
            sentence_pause_ms=sentence_pause_ms,
            bilingual_transition_pause_ms=bilingual_transition_pause_ms,
            strip_terminal_periods=strip_terminal_periods,
            min_segment_chars=min_segment_chars,
        )

    sequence: list[SpeechSpan | int] = []
    previous_language: str | None = None
    for span in spans:
        if (
            previous_language is not None and
            span.language != previous_language and
            bilingual_transition_pause_ms > 0 and
            "en" in {previous_language, span.language}
        ):
            sequence.append(bilingual_transition_pause_ms)
        items = segment_text_for_tts(
            span.text,
            max_chars=max_chars,
            sentence_pause_ms=sentence_pause_ms,
            strip_terminal_periods=strip_terminal_periods,
        )
        for item in items:
            if isinstance(item, int):
                sequence.append(item)
            elif item:
                sequence.append(SpeechSpan(text=item, language=span.language))
        previous_language = span.language
    return sequence


def _segment_spans_for_technical_paragraph(
    spans: list[SpeechSpan],
    *,
    max_chars: int,
    sentence_pause_ms: int,
    bilingual_transition_pause_ms: int,
    strip_terminal_periods: bool,
    min_segment_chars: int,
) -> list[SpeechSpan | int]:
    sequence: list[SpeechSpan | int] = []
    pending_pause = 0
    previous_language: str | None = None

    for span in spans:
        transition_pause = 0
        if (
            previous_language is not None
            and span.language != previous_language
            and bilingual_transition_pause_ms > 0
            and "en" in {previous_language, span.language}
        ):
            transition_pause = bilingual_transition_pause_ms

        items = segment_text_for_tts(
            span.text,
            max_chars=max_chars,
            sentence_pause_ms=sentence_pause_ms,
            strip_terminal_periods=strip_terminal_periods,
        )
        span_sequence: list[SpeechSpan | int] = [
            SpeechSpan(text=item, language=span.language) if isinstance(item, str) else item for item in items
        ]

        if transition_pause:
            pending_pause = max(pending_pause, transition_pause)

        for item in span_sequence:
            if isinstance(item, int):
                pending_pause = max(pending_pause, item)
                continue
            if _try_merge_short_segment(sequence, item, min_segment_chars=min_segment_chars, max_chars=max_chars):
                pending_pause = 0
                continue
            if pending_pause > 0:
                sequence.append(pending_pause)
                pending_pause = 0
            sequence.append(item)

        previous_language = span.language

    return sequence


def _try_merge_short_segment(
    sequence: list[SpeechSpan | int],
    item: SpeechSpan,
    *,
    min_segment_chars: int,
    max_chars: int,
) -> bool:
    if min_segment_chars <= 0 or len(item.text) >= min_segment_chars or not sequence:
        return False
    previous = sequence[-1]
    if isinstance(previous, int) or previous.language != item.language:
        return False
    candidate = _cleanup_spacing(f"{previous.text} {item.text}")
    if len(candidate) > max_chars:
        return False
    previous.text = candidate
    return True


def estimate_duration_seconds(text: str, speed: float) -> float:
    words = len(text.split())
    wpm = 155 * max(speed, 0.5)
    minutes = words / max(wpm, 1)
    return round(minutes * 60, 1)


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    buffer = ""
    parts = re.split(r"(?<=,)\s+|\s+", sentence)
    for part in parts:
        candidate = f"{buffer} {part}".strip()
        if buffer and len(candidate) > max_chars:
            chunks.append(buffer.strip())
            buffer = part
        else:
            buffer = candidate
    if buffer:
        chunks.append(buffer.strip())
    return chunks


def _extract_sentences(paragraph: str) -> list[str]:
    matches = [match.group(0).strip() for match in SENTENCE_WITH_PUNCTUATION.finditer(paragraph) if match.group(0).strip()]
    return matches or [paragraph.strip()]


def _segment_sentence(sentence: str, *, max_chars: int, strip_terminal_periods: bool) -> list[str]:
    parts = _split_long_sentence(sentence, max_chars) if len(sentence) > max_chars else [sentence.strip()]
    if not parts:
        return []

    cleaned_parts: list[str] = []
    for index, part in enumerate(parts):
        cleaned = part.strip()
        if strip_terminal_periods and index == len(parts) - 1:
            cleaned = re.sub(r"[.;:]+\s*$", "", cleaned).strip()
        cleaned_parts.append(cleaned)
    return [part for part in cleaned_parts if part]


def _extract_inline_pronunciations(text: str, placeholders: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        explicit = inner.split("|", 1)
        spoken = explicit[1] if len(explicit) == 2 else explicit[0]
        key = _store_placeholder(placeholders, spoken.strip())
        return key

    return INLINE_PRONUNCIATION.sub(replace, text)


def _extract_english_spans(text: str, placeholders: dict[str, str], settings: AppSettings) -> str:
    def replace(match: re.Match[str]) -> str:
        spoken = _adapt_english_phrase(match.group(1).strip(), settings)
        key = _store_placeholder(placeholders, spoken)
        return key

    return INLINE_ENGLISH.sub(replace, text)


def _store_placeholder(placeholders: dict[str, str], value: str) -> str:
    key = f"@@zzpron{len(placeholders)}@@"
    placeholders[key] = value
    return key


def _restore_placeholders(text: str, placeholders: dict[str, str]) -> str:
    restored = text
    for key, value in placeholders.items():
        restored = restored.replace(key, value)
    return restored


def _adapt_technical_tokens(text: str, settings: AppSettings, *, debug: TextProcessingDebug | None = None) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if not _looks_technical_token(token):
            return token

        adapted, reason = _adapt_technical_token(token, settings)
        if debug and adapted:
            debug.add(token=token, output=adapted, reason=reason)
        return adapted or token

    return TECHNICAL_TOKEN.sub(replace, text)


def _apply_lexicon(text: str, lexicon: dict[str, str]) -> str:
    adapted = text
    for source, target in sorted(lexicon.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(source)}(?![A-Za-z0-9])", re.IGNORECASE)
        adapted = pattern.sub(lambda match: _preserve_case(match.group(0), target), adapted)
    return adapted


def _apply_pronunciation_lexicon(text: str, settings: AppSettings) -> str:
    adapted = text
    for source, target in sorted(settings.speech.pronunciation_lexicon.items(), key=lambda item: len(item[0]), reverse=True):
        if not _should_apply_pronunciation_entry(source, settings):
            continue
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(source)}(?![A-Za-z0-9])", re.IGNORECASE)
        adapted = pattern.sub(lambda match: _preserve_case(match.group(0), target), adapted)
    return adapted


def _should_apply_pronunciation_entry(source: str, settings: AppSettings) -> bool:
    if settings.speech.adapt_plain_english_terms_with_lexicon:
        return True
    if any(char in source for char in "./_+-") or any(char.isdigit() for char in source):
        return True
    compact = source.replace(" ", "")
    if compact.isupper() or (len(compact) <= 4 and compact.isalpha()):
        return True
    if any(char.isupper() for char in source):
        return True
    # Plain lowercase English terms often sound more natural when XTTS receives
    # the real token instead of a Spanish phonetic approximation.
    return False


def _restore_spanish_accents(text: str, accent_lexicon: dict[str, str]) -> str:
    restored = text
    for source, target in sorted(accent_lexicon.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"(?<![A-Za-zÁÉÍÓÚáéíóúÑñÜü]){re.escape(source)}(?![A-Za-zÁÉÍÓÚáéíóúÑñÜü])", re.IGNORECASE)
        restored = pattern.sub(lambda match: _preserve_case(match.group(0), target), restored)
    return restored


def _expand_acronyms(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        parts = re.split(r"[/-]", token)
        spelled_parts: list[str] = []
        for part in parts:
            letters = [LETTER_PRONUNCIATION[char] for char in part if char in LETTER_PRONUNCIATION]
            if letters:
                spelled_parts.append(" ".join(letters))
        return " ".join(spelled_parts) or token

    return ACRONYM_TOKEN.sub(replace, text)


def _looks_technical_token(token: str) -> bool:
    if len(token) <= 2:
        return False
    has_separator = any(char in token for char in "./_")
    has_digits = any(char.isdigit() for char in token)
    has_upper = any(char.isupper() for char in token)
    has_lower = any(char.islower() for char in token)
    return has_separator or (has_digits and (has_upper or has_lower)) or (has_upper and has_lower)


def _adapt_technical_token(token: str, settings: AppSettings) -> tuple[str, str]:
    direct = _lexicon_lookup(token, settings.speech.pronunciation_lexicon)
    if direct:
        if _should_apply_pronunciation_entry(token, settings):
            return _preserve_case(token, direct), "pronunciation_lexicon"
        return token, "preserved_plain_english_token"

    parts = [part for part in CAMEL_OR_DIGIT_BOUNDARY.split(token) if part]
    expanded_parts: list[str] = []
    for part in parts:
        expanded_parts.extend(subpart for subpart in re.split(r"[./_]", part) if subpart)

    if (
        settings.speech.technical_adaptation_aggressiveness == "conservative"
        and len(expanded_parts) <= 1
        and _looks_like_english_phrase_token(token)
    ):
        return token, "preserved_technical_token"

    spoken_parts = [
        _adapt_technical_part(part, settings, from_compound=len(expanded_parts) > 1) for part in expanded_parts
    ]
    spoken_parts = [part for part in spoken_parts if part]
    spoken = " ".join(spoken_parts).strip()
    return spoken, "technical_token_policy"


def _adapt_technical_part(part: str, settings: AppSettings, *, from_compound: bool = False) -> str:
    direct = _lexicon_lookup(part, settings.speech.pronunciation_lexicon)
    if direct and _should_apply_pronunciation_entry(part, settings):
        return _preserve_case(part, direct)
    if part.isdigit():
        return _pronounce_number_token(part)
    if part.isupper() and len(part) >= 2:
        return " ".join(LETTER_PRONUNCIATION[char] for char in part if char in LETTER_PRONUNCIATION)
    if from_compound and part.isalpha() and len(part) <= 3:
        return " ".join(LETTER_PRONUNCIATION[char] for char in part.upper() if char in LETTER_PRONUNCIATION)
    if settings.speech.technical_adaptation_aggressiveness == "aggressive" and from_compound and part.isalpha():
        return _spanglishify_word(part)
    if settings.speech.technical_adaptation_aggressiveness == "aggressive" and any(char.isupper() for char in part):
        return _spanglishify_word(part)
    if settings.speech.technical_adaptation_aggressiveness == "aggressive" and any(char.isdigit() for char in part):
        return _spanglishify_word(part)
    return part


def _looks_like_english_phrase_token(token: str) -> bool:
    return token.isalpha() and any(char.isupper() for char in token) and any(char.islower() for char in token)


def _pronounce_number_token(token: str) -> str:
    return " ".join(NUMBER_PRONUNCIATION.get(char, char) for char in token)


def _lexicon_lookup(token: str, lexicon: dict[str, str]) -> str | None:
    lowered = token.casefold()
    for source, target in lexicon.items():
        if source.casefold() == lowered:
            return target
    return None


def _adapt_english_phrase(text: str, settings: AppSettings) -> str:
    if settings.speech.preserve_english_spans:
        return _cleanup_spacing(text)

    adapted = text
    if settings.speech.adapt_english_spans_with_lexicon:
        adapted = _apply_lexicon(adapted, settings.speech.pronunciation_lexicon)
    if settings.speech.spell_acronyms and settings.speech.pronunciation_mode == "aggressive":
        adapted = _expand_acronyms(adapted)

    if not settings.speech.spanglishify_english_spans:
        return _cleanup_spacing(adapted)

    def replace(match: re.Match[str]) -> str:
        return _spanglishify_word(match.group(0))

    return WORD_TOKEN.sub(replace, adapted)


def _build_speech_spans(
    text: str,
    settings: AppSettings,
    *,
    language: str,
    placeholders: dict[str, str],
    debug: TextProcessingDebug | None = None,
) -> list[SpeechSpan]:
    cleaned = text.strip()
    if not cleaned:
        return []

    if not settings.speech.enabled:
        restored = _restore_placeholders(_cleanup_spacing(cleaned), placeholders)
        return [SpeechSpan(text=restored, language=language)] if restored else []

    if language == "en":
        restored = _restore_placeholders(_cleanup_spacing(cleaned), placeholders)
        return [SpeechSpan(text=restored, language="en")] if restored else []

    adapted = _adapt_text_for_speech(cleaned, settings, debug=debug)
    adapted = _restore_placeholders(adapted, placeholders)
    adapted = _cleanup_spacing(adapted)
    return [SpeechSpan(text=adapted, language=language)] if adapted else []


def _merge_adjacent_spans(spans: list[SpeechSpan]) -> list[SpeechSpan]:
    merged: list[SpeechSpan] = []
    for span in spans:
        text = _cleanup_spacing(span.text)
        if not text:
            continue
        if merged and merged[-1].language == span.language:
            merged[-1].text = _cleanup_spacing(f"{merged[-1].text} {text}")
            continue
        merged.append(SpeechSpan(text=text, language=span.language))
    return merged


def _cleanup_spacing(text: str) -> str:
    cleaned = re.sub(r"\s{2,}", " ", text.strip())
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip()


def _spanglishify_word(word: str) -> str:
    lower = word.lower()
    if len(lower) <= 2:
        return lower

    adapted = lower
    replacements = [
        ("queue", "kiu"),
        ("tion", "shon"),
        ("sion", "shon"),
        ("ture", "cher"),
        ("ing", "in"),
        ("ph", "f"),
        ("th", "d"),
        ("sh", "sh"),
        ("ck", "k"),
        ("qu", "ku"),
        ("x", "ks"),
        ("ee", "i"),
        ("ea", "i"),
        ("oo", "u"),
        ("ou", "au"),
        ("ow", "ou"),
        ("ay", "ei"),
        ("ey", "ei"),
        ("igh", "ai"),
        ("gh", "g"),
        ("w", "u"),
    ]
    for source, target in replacements:
        adapted = adapted.replace(source, target)

    if adapted.endswith("y"):
        adapted = f"{adapted[:-1]}i"

    adapted = re.sub(r"([aeiou])r\b", r"\1r", adapted)
    adapted = re.sub(r"([bcdfghjklmnpqrstvwxyz])e\b", r"\1", adapted)
    adapted = re.sub(r"\s{2,}", " ", adapted)
    return adapted.strip()


def _preserve_case(original: str, replacement: str) -> str:
    if original.isupper():
        if " " in replacement:
            return replacement
        return replacement.upper()
    if original[:1].isupper() and original[1:].islower():
        return replacement[:1].upper() + replacement[1:]
    return replacement
