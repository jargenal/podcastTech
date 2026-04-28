import unittest

from app.config.settings import AppSettings, _default_variants
from app.utils.text_parser import parse_input_document
from app.utils.text_processing import (
    TextProcessingDebug,
    adapt_text_for_speech,
    adapt_text_to_speech_spans,
    normalize_text,
    segment_spans_for_tts,
)


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
        self.assertIn("cloud watch", lowered)
        self.assertIn("es tri", lowered)
        self.assertIn("i si tú", lowered)

    def test_dot_notation_terms_are_adapted(self) -> None:
        adapted = adapt_text_for_speech(normalize_text("Node.js y Next.js corren en local."), self.settings)
        lowered = adapted.casefold()
        self.assertIn("nod ye es", lowered)
        self.assertIn("nekst ye es", lowered)

    def test_camel_case_tokens_are_split_for_speech(self) -> None:
        adapted = adapt_text_for_speech(normalize_text("La AccessKeyId se rota automaticamente."), self.settings)
        lowered = adapted.casefold()
        self.assertIn("access", lowered)
        self.assertIn("key", lowered)
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

    def test_complete_english_phrases_are_not_spanglishified(self) -> None:
        spans = adapt_text_to_speech_spans(
            normalize_text("El equipo dijo [EN]the backend service is failing under load[/EN] antes del deploy."),
            self.settings,
        )
        self.assertEqual(spans[1].language, "en")
        self.assertEqual(spans[1].text, "the backend service is failing under load")
        self.assertNotIn("servis", spans[1].text.casefold())
        self.assertNotIn("feilin", spans[1].text.casefold())

    def test_common_lowercase_technical_terms_are_preserved(self) -> None:
        adapted = adapt_text_for_speech(
            normalize_text("La API conecta el backend con el frontend usando un SDK."),
            self.settings,
        )
        lowered = adapted.casefold()
        self.assertIn("backend", lowered)
        self.assertIn("frontend", lowered)
        self.assertIn("ei pi ai", lowered)
        self.assertIn("es di kei", lowered)

    def test_compound_notation_splits_without_phonetic_rewrite(self) -> None:
        adapted = adapt_text_for_speech(
            normalize_text("Configura user.profile/readOnly junto a cacheControl."),
            self.settings,
        )
        lowered = adapted.casefold()
        self.assertIn("user profile read only", lowered)
        self.assertIn("cache control", lowered)
        self.assertNotIn("profail", lowered)

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

    def test_technical_paragraph_segmenter_avoids_same_language_microsegments(self) -> None:
        sequence = segment_spans_for_tts(
            [
                self._span("La API valida eventos de CloudWatch.", "es"),
                self._span("Luego procesa metric streams y alert rules.", "es"),
            ],
            max_chars=120,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=True,
            reading_mode="technical_paragraph",
            min_segment_chars=70,
        )
        speech_items = [item for item in sequence if not isinstance(item, int)]
        self.assertEqual(len(speech_items), 1)
        self.assertIn("Luego procesa", speech_items[0].text)

    def test_technical_paragraph_keeps_bilingual_spans_separate_with_short_pause(self) -> None:
        sequence = segment_spans_for_tts(
            [
                self._span("El sistema expone la API.", "es"),
                self._span("retry with exponential backoff.", "en"),
                self._span("Despues registra la metrica.", "es"),
            ],
            max_chars=160,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=True,
            reading_mode="technical_paragraph",
            min_segment_chars=70,
        )
        self.assertEqual([item for item in sequence if isinstance(item, int)], [70, 70])

    def test_prosody_safe_segmenter_defers_break_after_technical_token(self) -> None:
        debug = TextProcessingDebug()
        sequence = segment_spans_for_tts(
            [
                self._span(
                    "El servicio procesa eventos antes de sessionToken y despues mantiene la sesion activa para cerrar la transaccion.",
                    "es",
                )
            ],
            max_chars=58,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=True,
            reading_mode="technical_paragraph",
            min_segment_chars=40,
            settings=self.settings,
            debug=debug,
        )
        speech_items = [item for item in sequence if not isinstance(item, int)]
        self.assertTrue(any("sessiontoken y despues" in item.text.casefold() for item in speech_items))
        self.assertTrue(any(event["event"] == "deferred_break" for event in debug.segmentation_events))

    def test_short_english_span_is_sensitive_but_not_oversegmented(self) -> None:
        sequence = segment_spans_for_tts(
            [
                self._span("La recomendacion es", "es"),
                self._span("retry with exponential backoff", "en"),
                self._span("antes de reintentar la llamada.", "es"),
            ],
            max_chars=60,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=True,
            reading_mode="technical_paragraph",
            min_segment_chars=40,
            settings=self.settings,
        )
        english_items = [item for item in sequence if not isinstance(item, int) and item.language == "en"]
        self.assertEqual(len(english_items), 1)
        self.assertTrue(english_items[0].sensitive)
        self.assertIn("short_english_span", english_items[0].sensitivity_reasons)

    def test_camel_case_boundary_is_marked_sensitive(self) -> None:
        sequence = segment_spans_for_tts(
            [self._span("El cliente renueva sessionToken antes de llamar la API interna.", "es")],
            max_chars=90,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=True,
            reading_mode="technical_paragraph",
            min_segment_chars=40,
            settings=self.settings,
        )
        speech_items = [item for item in sequence if not isinstance(item, int)]
        self.assertTrue(speech_items[0].sensitive)
        self.assertIn("technical_anchor", speech_items[0].sensitivity_reasons)

    def test_common_technical_phrase_lexicon_is_applied(self) -> None:
        adapted, debug = self._adapt_debug("GitHub publica una REST API detrás de API Gateway y CloudWatch.")
        lowered = adapted.casefold()
        self.assertIn("guit jab", lowered)
        self.assertIn("rest ei pi ai", lowered)
        self.assertIn("ei pi ai gateway", lowered)
        self.assertIn("cloud watch", lowered)
        phrase_tokens = {item["token"].casefold(): item for item in debug.technical_tokens}
        self.assertEqual(phrase_tokens["rest api"]["reason"], "pronunciation_lexicon_phrase")
        self.assertEqual(phrase_tokens["api gateway"]["reason"], "pronunciation_lexicon_phrase")

    def test_mixed_case_tokens_use_component_verbalization(self) -> None:
        adapted, debug = self._adapt_debug("accessKeyId episodeId userName refreshToken profileImageURL")
        lowered = adapted.casefold()
        self.assertIn("access key ai di", lowered)
        self.assertIn("episode ai di", lowered)
        self.assertIn("user name", lowered)
        self.assertIn("refresh token", lowered)
        self.assertIn("profile image iu ar el", lowered)
        token_map = {item["token"]: item for item in debug.technical_tokens}
        self.assertEqual(token_map["episodeId"]["parts"][1]["output"], "ai di")
        self.assertEqual(token_map["profileImageURL"]["parts"][2]["strategy"], "technical_component")

    def test_alphanumeric_acronym_sequence_stays_articulated(self) -> None:
        adapted, debug = self._adapt_debug("Usa S3, EC2, IAM para validar permisos.")
        lowered = adapted.casefold()
        self.assertIn("es tri, i si tú, ai em", lowered)
        token_map = {item["token"]: item for item in debug.technical_tokens}
        self.assertEqual(token_map["EC2"]["output"], "i si tú")

    def test_terminal_punctuation_can_be_preserved_for_phrase_closure(self) -> None:
        sequence = segment_spans_for_tts(
            [self._span("El resultado queda inconsistente. Luego se valida después.", "es")],
            max_chars=80,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=False,
            reading_mode="technical_paragraph",
            min_segment_chars=40,
            settings=self.settings,
        )
        speech_items = [item for item in sequence if not isinstance(item, int)]
        self.assertTrue(speech_items[0].text.endswith("."))
        self.assertTrue(speech_items[-1].text.endswith("."))

    def test_benchmark_paragraph_splits_into_safe_prosody_groups(self) -> None:
        paragraph = (
            "Finalmente, este benchmark también debe revelar si el pipeline puede manejar una explicación técnica real "
            "sobre text preprocessing, speech synthesis, prompt engineering, embeddings, fine-tuning y tokenizer behavior, "
            "manteniendo una lectura natural de principio a fin, con pausas razonables, sin microcortes innecesarios y sin "
            "esa sensación de voz robotizada que suele aparecer después de ciertos términos especializados."
        )
        spans = adapt_text_to_speech_spans(normalize_text(paragraph), self.settings)
        sequence = segment_spans_for_tts(
            spans,
            max_chars=220,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=False,
            reading_mode="technical_paragraph",
            min_segment_chars=70,
            settings=self.settings,
        )
        speech_items = [item for item in sequence if not isinstance(item, int)]
        self.assertGreaterEqual(len(speech_items), 3)
        self.assertTrue(speech_items[-1].text.endswith("."))
        self.assertLessEqual(len(speech_items[-1].text), self.settings.audio_tuning.technical_density_max_chars + 80)
        protected_terms = [
            "text preprocessing",
            "speech synthesis",
            "prompt engineering",
            "embedins",
            "fain tiunin",
            "tokenaizer behavior",
        ]
        rendered = " ".join(item.text for item in speech_items).casefold()
        for term in protected_terms:
            self.assertIn(term, rendered)
        for item in speech_items:
            self.assertFalse(item.text.strip().endswith(("text", "speech", "prompt", "tokenaizer")))

    def test_paragraph_break_inserts_clean_pause(self) -> None:
        sequence = segment_spans_for_tts(
            [self._span("Primer párrafo técnico.\n\nSegundo párrafo con CloudWatch.", "es")],
            max_chars=220,
            sentence_pause_ms=220,
            bilingual_transition_pause_ms=70,
            strip_terminal_periods=False,
            reading_mode="technical_paragraph",
            min_segment_chars=70,
            settings=self.settings,
        )
        pauses = [item for item in sequence if isinstance(item, int)]
        self.assertIn(self.settings.audio_tuning.paragraph_pause_ms, pauses)

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

    def _adapt_debug(self, text: str):
        from app.utils.text_processing import adapt_text_for_speech_debug

        return adapt_text_for_speech_debug(normalize_text(text), self.settings)


if __name__ == "__main__":
    unittest.main()
