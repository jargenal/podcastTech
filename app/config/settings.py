from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config.default_lexicons import _default_pronunciation_lexicon, _default_spanish_accent_lexicon
from app.config.runtime_lexicons import lexicon_file_cache


ROOT_DIR = Path(__file__).resolve().parents[2]
SETTINGS_PATH = ROOT_DIR / "settings.json"
PRONUNCIATION_OVERRIDES_PATH = ROOT_DIR / "app" / "config" / "lexicons" / "pronunciation_overrides.json"
ACCENT_OVERRIDES_PATH = ROOT_DIR / "app" / "config" / "lexicons" / "accent_overrides.json"


class VariantProfile(BaseModel):
    label: str
    tts_language: str = "es"
    default_voice: str | None = None
    fallback_variant: str | None = None


class TTSConfig(BaseModel):
    engine: Literal["xtts_v2"] = "xtts_v2"
    xtts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    device_preference: Literal["auto", "mps", "cpu"] = "cpu"


def _relative_to_root(path: Path) -> str:
    return str(path.relative_to(ROOT_DIR))


class SpeechConfig(BaseModel):
    enabled: bool = True
    spell_acronyms: bool = True
    pronunciation_mode: Literal["conservative", "aggressive"] = Field(
        "conservative",
        description="Conservative avoids phonetic rewrites unless a token clearly benefits from adaptation.",
    )
    technical_adaptation_aggressiveness: Literal["conservative", "balanced", "aggressive"] = Field(
        "conservative",
        description="Controls how strongly camelCase, dotted, slash and mixed technical tokens are rewritten.",
    )
    preserve_english_spans: bool = Field(True, description="Keep [EN] spans as real English text for the TTS model.")
    adapt_english_spans_with_lexicon: bool = Field(False, description="Apply pronunciation lexicon inside [EN] spans.")
    spanglishify_english_spans: bool = Field(False, description="Apply legacy phonetic English-to-Spanish rewriting.")
    adapt_plain_english_terms_with_lexicon: bool = Field(
        False,
        description="Rewrite lowercase English technical words such as backend/cache using the pronunciation lexicon.",
    )
    pronunciation_lexicon_overrides_file: str = Field(
        default_factory=lambda: _relative_to_root(PRONUNCIATION_OVERRIDES_PATH)
    )
    restore_spanish_accents: bool = True
    accent_lexicon_overrides_file: str = Field(
        default_factory=lambda: _relative_to_root(ACCENT_OVERRIDES_PATH)
    )

    @property
    def pronunciation_lexicon(self) -> dict[str, str]:
        return {
            **_default_pronunciation_lexicon(),
            **lexicon_file_cache.load(ROOT_DIR / self.pronunciation_lexicon_overrides_file),
        }

    @property
    def accent_lexicon(self) -> dict[str, str]:
        return {
            **_default_spanish_accent_lexicon(),
            **lexicon_file_cache.load(ROOT_DIR / self.accent_lexicon_overrides_file),
        }


class EcoModeConfig(BaseModel):
    enabled: bool = True
    max_torch_threads: int = 4
    max_interop_threads: int = 1
    inter_segment_cooldown_ms: int = 250


class AudioTuningConfig(BaseModel):
    reading_mode: Literal["standard", "technical_paragraph"] = Field(
        "technical_paragraph",
        description="technical_paragraph favors longer fluent chunks and fewer pauses for bilingual technical prose.",
    )
    sentence_pause_ms: int = 220
    segment_fade_ms: int = 28
    short_segment_fade_ms: int = Field(8, description="Max fade for very short segments to avoid losing consonants.")
    crossfade_ms: int = 18
    same_language_crossfade_ms: int | None = Field(12, description="Crossfade used only between same-language audio.")
    bilingual_crossfade_ms: int = Field(0, description="Crossfade for language switches; 0 preserves word edges.")
    bilingual_transition_pause_ms: int = 120
    technical_bilingual_transition_pause_ms: int = Field(70, description="Short pause for Spanish/English transitions.")
    min_segment_chars: int = Field(70, description="Short same-language chunks below this size are merged when possible.")
    strip_terminal_periods: bool = True


class AppSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8040
    app_title: str = "PodcastTech Offline TTS"
    default_language: str = "es"
    default_variant: str = "es_latam"
    default_voice: str | None = "voices/default_es_mx.wav"
    default_speed: float = 1.0
    default_english_speed: float = 1.0
    default_segment_length: int = 220
    default_temperature: float = 0.65
    default_english_temperature: float = 0.45
    default_pause_ms: int = 700
    normalize_audio: bool = True
    output_format: Literal["wav", "mp3", "m4a"] = "wav"
    output_dir: str = "output"
    input_dir: str = "input"
    voices_dir: str = "voices"
    temp_dir: str = "temp"
    history_file: str = "output/history.json"
    playlists_file: str = "output/playlists.json"
    variants: dict[str, VariantProfile] = Field(default_factory=dict)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    speech: SpeechConfig = Field(default_factory=SpeechConfig)
    eco_mode: EcoModeConfig = Field(default_factory=EcoModeConfig)
    audio_tuning: AudioTuningConfig = Field(default_factory=AudioTuningConfig)

    @property
    def output_path(self) -> Path:
        return ROOT_DIR / self.output_dir

    @property
    def input_path(self) -> Path:
        return ROOT_DIR / self.input_dir

    @property
    def voices_path(self) -> Path:
        return ROOT_DIR / self.voices_dir

    @property
    def temp_path(self) -> Path:
        return ROOT_DIR / self.temp_dir

    @property
    def history_path(self) -> Path:
        return ROOT_DIR / self.history_file

    @property
    def playlists_path(self) -> Path:
        return ROOT_DIR / self.playlists_file


def _default_variants() -> dict[str, VariantProfile]:
    return {
        "es_latam": VariantProfile(
            label="Español Latinoamericano",
            tts_language="es",
            default_voice="voices/default_es_mx.wav",
            fallback_variant="es_neutro",
        ),
        "es_neutro": VariantProfile(
            label="Español Neutro",
            tts_language="es",
            default_voice="voices/default_es_mx.wav",
            fallback_variant="es_latam",
        ),
        "es_es": VariantProfile(
            label="Español España",
            tts_language="es",
            default_voice="voices/default_es_mx.wav",
            fallback_variant="es_neutro",
        ),
    }


def ensure_settings_file(path: Path = SETTINGS_PATH) -> None:
    if path.exists():
        return

    data = AppSettings(variants=_default_variants()).model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def ensure_lexicon_override_files() -> None:
    PRONUNCIATION_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PRONUNCIATION_OVERRIDES_PATH.exists():
        PRONUNCIATION_OVERRIDES_PATH.write_text("{}\n", encoding="utf-8")
    if not ACCENT_OVERRIDES_PATH.exists():
        ACCENT_OVERRIDES_PATH.write_text("{}\n", encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    ensure_settings_file()
    ensure_lexicon_override_files()
    raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    raw.setdefault("variants", _default_variants())
    speech_defaults = SpeechConfig().model_dump(mode="json")
    raw_speech = raw.setdefault("speech", {})
    if isinstance(raw_speech, dict):
        merged_speech = {**speech_defaults, **raw_speech}
        if "pronunciation_lexicon" in raw_speech:
            PRONUNCIATION_OVERRIDES_PATH.write_text(
                json.dumps(raw_speech["pronunciation_lexicon"], indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if "accent_lexicon" in raw_speech:
            ACCENT_OVERRIDES_PATH.write_text(
                json.dumps(raw_speech["accent_lexicon"], indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        merged_speech.pop("pronunciation_lexicon", None)
        merged_speech.pop("accent_lexicon", None)
        raw["speech"] = merged_speech
    else:
        raw["speech"] = speech_defaults
    raw.setdefault("eco_mode", EcoModeConfig().model_dump(mode="json"))
    raw.setdefault("audio_tuning", AudioTuningConfig().model_dump(mode="json"))
    settings = AppSettings.model_validate(raw)

    settings.output_path.mkdir(parents=True, exist_ok=True)
    settings.input_path.mkdir(parents=True, exist_ok=True)
    settings.voices_path.mkdir(parents=True, exist_ok=True)
    settings.temp_path.mkdir(parents=True, exist_ok=True)
    settings.history_path.parent.mkdir(parents=True, exist_ok=True)
    settings.playlists_path.parent.mkdir(parents=True, exist_ok=True)
    if not settings.history_path.exists():
        settings.history_path.write_text("[]", encoding="utf-8")

    return settings
