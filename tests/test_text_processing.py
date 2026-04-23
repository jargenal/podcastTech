import unittest

from app.config.settings import AppSettings, _default_variants
from app.utils.text_parser import parse_input_document
from app.utils.text_processing import adapt_text_for_speech, adapt_text_to_speech_spans, normalize_text, segment_spans_for_tts


def build_settings() -> AppSettings:
    return AppSettings(variants=_default_variants())


class TextProcessingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = build_settings()

    def test_bracketed_acronyms_are_cleaned_and_spelled(self) -> None:
        adapted = adapt_text_for_speech(normalize_text("Activa [MFA] para la cuenta root."), self.settings)
        self.assertNotIn("[", adapted)
        self.assertIn("em ef ei", adapted.casefold())

    def test_common_cloud_terms_use_runtime_overrides(self) -> None:
        adapted = adapt_text_for_speech(normalize_text("CloudWatch protege datos en S3 y EC2."), self.settings)
        lowered = adapted.casefold()
        self.assertIn("claud uoch", lowered)
        self.assertIn("es tri", lowered)
        self.assertIn("i si tu", lowered)

    def test_dot_notation_terms_are_adapted(self) -> None:
        adapted = adapt_text_for_speech(normalize_text("Node.js y Next.js corren en local."), self.settings)
        lowered = adapted.casefold()
        self.assertIn("nod ye es", lowered)
        self.assertIn("nekst ye es", lowered)

    def test_camel_case_tokens_are_split_for_speech(self) -> None:
        adapted = adapt_text_for_speech(normalize_text("La AccessKeyId se rota automaticamente."), self.settings)
        lowered = adapted.casefold()
        self.assertIn("access", lowered)
        self.assertIn("kei", lowered)
        self.assertIn("ai di", lowered)

    def test_parser_applies_adaptation_inside_text_blocks(self) -> None:
        document = parse_input_document(
            "[TEXTO]\nUsa IAM Identity Center con MFA.\n\n[PAUSA]\n900\n",
            settings=self.settings,
            selected_variant="es_latam",
            selected_voice=None,
            selected_english_voice=None,
            source_filename="demo.md",
        )
        self.assertEqual(len(document.blocks), 2)
        self.assertIn("ai em identity center", document.blocks[0].text.casefold())
        self.assertEqual(document.blocks[1].pause_ms, 900)

    def test_en_spans_are_preserved_as_english_without_spanish_lexicon(self) -> None:
        spans = adapt_text_to_speech_spans(
            normalize_text("Este episodio cubre [EN]preview environment[/EN] en detalle."),
            self.settings,
        )
        self.assertEqual([span.language for span in spans], ["es", "en", "es"])
        self.assertIn("preview environment", spans[1].text)
        self.assertNotIn("priviu", spans[1].text.casefold())

    def test_parser_keeps_bilingual_span_metadata(self) -> None:
        document = parse_input_document(
            "[TEXTO]\nHoy veremos [EN]machine learning[/EN] aplicado.\n",
            settings=self.settings,
            selected_variant="es_latam",
            selected_voice=None,
            selected_english_voice=None,
            source_filename="demo.md",
        )
        self.assertEqual([span.language for span in document.blocks[0].spans], ["es", "en", "es"])
        self.assertEqual(document.blocks[0].spans[1].text, "machine learning")

    def test_segmenter_preserves_language_per_chunk(self) -> None:
        sequence = segment_spans_for_tts(
            [
                self._span("Hola mundo.", "es"),
                self._span("machine learning changes fast.", "en"),
            ],
            max_chars=40,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=120,
            strip_terminal_periods=True,
        )
        speech_items = [item for item in sequence if not isinstance(item, int)]
        self.assertEqual([item.language for item in speech_items], ["es", "en"])
        self.assertEqual(speech_items[1].text, "machine learning changes fast")

    def test_segmenter_inserts_pause_on_language_switch(self) -> None:
        sequence = segment_spans_for_tts(
            [
                self._span("Hola equipo.", "es"),
                self._span("machine learning.", "en"),
                self._span("Seguimos en espanol.", "es"),
            ],
            max_chars=60,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=120,
            strip_terminal_periods=True,
        )
        self.assertEqual(sequence[1], 120)
        self.assertEqual(sequence[3], 120)

    def test_parser_supports_optional_english_voice_tag(self) -> None:
        document = parse_input_document(
            "[VOZ_EN]\nenglish_voice.wav\n[TEXTO]\nHola [EN]cloud adoption[/EN].\n",
            settings=self.settings,
            selected_variant="es_latam",
            selected_voice=None,
            selected_english_voice=None,
            source_filename="demo.md",
        )
        self.assertEqual(document.english_voice, "english_voice.wav")

    @staticmethod
    def _span(text: str, language: str):
        from app.models.domain import SpeechSpan

        return SpeechSpan(text=text, language=language)


if __name__ == "__main__":
    unittest.main()
