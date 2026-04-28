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
    technical_verbalization_mode: Literal["conservative", "expanded"] = Field(
        "expanded",
        description="expanded verbalizes mixedCase technical identifiers using reusable component rules.",
    )
    alphanumeric_acronym_mode: Literal["lexicon", "spell_letters_digits"] = Field(
        "lexicon",
        description="Controls how acronyms with digits such as S3 and EC2 are verbalized.",
    )
    mixed_case_id_pronunciation: Literal["compact", "spelled"] = Field(
        "compact",
        description="compact uses a joined pronunciation for Id suffixes to avoid artificial pauses.",
    )
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
    paragraph_pause_ms: int = Field(380, description="Clean silence inserted between text paragraphs.")
    technical_density_threshold: int = Field(4, description="Technical tokens that trigger shorter, safer chunks.")
    technical_density_max_chars: int = Field(165, description="Max chunk size for high-density technical sentences.")
    max_technical_tokens_per_segment: int = Field(4, description="Soft limit for fragile technical tokens per chunk.")
    prosody_group_min_chars: int = Field(80, description="Minimum size before splitting at comma/connector groups.")
    segment_fade_ms: int = 28
    segment_fade_in_ms: int = Field(6, description="Fade-in for rendered TTS chunks.")
    segment_fade_out_ms: int = Field(0, description="Fade-out for rendered TTS chunks; 0 preserves final syllables.")
    terminal_segment_fade_out_ms: int = Field(0, description="Fade-out at final/pause boundaries.")
    terminal_segment_tail_silence_ms: int = Field(160, description="Small closure pad after terminal segments.")
    terminal_long_token_extra_tail_silence_ms: int = Field(
        60,
        description="Extra clean tail when the terminal word is long or technically fragile.",
    )
    short_segment_fade_ms: int = Field(8, description="Max fade for very short segments to avoid losing consonants.")
    crossfade_ms: int = 18
    same_language_crossfade_ms: int | None = Field(12, description="Crossfade used only between same-language audio.")
    bilingual_crossfade_ms: int = Field(0, description="Crossfade for language switches; 0 preserves word edges.")
    same_language_crossfade_for_sensitive_segments_ms: int = Field(
        0,
        description="Crossfade used when either side has fragile technical or bilingual content.",
    )
    disable_fades_for_sensitive_segments: bool = Field(
        True,
        description="Skip per-segment fades on fragile technical or bilingual segments.",
    )
    min_chars_for_crossfade: int = Field(95, description="Do not crossfade segments shorter than this text length.")
    segment_join_strategy: Literal["conservative", "balanced"] = Field(
        "conservative",
        description="conservative preserves word edges; balanced allows more smoothing between ordinary segments.",
    )
    bilingual_transition_pause_ms: int = 120
    technical_bilingual_transition_pause_ms: int = Field(70, description="Short pause for Spanish/English transitions.")
    min_segment_chars: int = Field(70, description="Short same-language chunks below this size are merged when possible.")
    protected_token_context_words_before: int = Field(
        2,
        description="Words before a fragile technical token where segment breaks are avoided.",
    )
    protected_token_context_words_after: int = Field(
        3,
        description="Words after a fragile technical token where segment breaks are avoided.",
    )
    avoid_segment_break_after_technical_token: bool = True
    avoid_segment_break_before_technical_token: bool = True
    protected_zone_max_overflow_chars: int = Field(
        80,
        description="Allowed overflow beyond max segment length to keep protected technical islands together.",
    )
    sensitive_segment_detection: bool = True
    preserve_terminal_punctuation: bool = Field(True, description="Keep final punctuation to help TTS phrase closure.")
    strip_terminal_periods: bool = False
    enable_safe_audio_cleanup: bool = Field(True, description="Conservatively trims only detected silence, not speech.")
    silence_trim_threshold_db: int = Field(-48, description="dBFS threshold used for safe silence detection.")
    max_leading_silence_trim_ms: int = Field(250, description="Max leading silence removed from a TTS chunk.")
    max_trailing_silence_trim_ms: int = Field(1200, description="Max trailing silence excess removed from a TTS chunk.")
    preserved_trailing_silence_ms: int = Field(220, description="Silence kept before adding clean terminal tails.")


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
