import json
import tempfile
import unittest
from pathlib import Path

from pydub import AudioSegment
from pydub.generators import Sine

from app.config.settings import AppSettings, _default_variants
from app.services.audio_pipeline import AudioPipeline, RenderedAudioSegment


class AudioPipelineTraceTestCase(unittest.TestCase):
    def test_assembly_writes_segment_trace_with_sensitive_join_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = AppSettings(variants=_default_variants(), output_dir=str(root))
            pipeline = AudioPipeline(settings)

            first = root / "first.wav"
            second = root / "second.wav"
            with AudioSegment.silent(duration=1000).export(first, format="wav"):
                pass
            with AudioSegment.silent(duration=1000).export(second, format="wav"):
                pass

            debug_path = root / "debug" / "job.json"
            pipeline.assemble(
                sequence=[
                    RenderedAudioSegment(path=first, language="es", order=1, text="Texto normal de entrada."),
                    RenderedAudioSegment(
                        path=second,
                        language="es",
                        order=2,
                        text="Renueva sessionToken antes de continuar.",
                        sensitive=True,
                        sensitivity_reasons=("camel_or_pascal_case",),
                    ),
                ],
                title="trace demo",
                normalize_audio=False,
                export_mp3=False,
                export_m4a=False,
                debug_path=debug_path,
                job_id="job",
            )

            payload = json.loads(debug_path.read_text(encoding="utf-8"))
            speech_items = [item for item in payload["items"] if item["kind"] == "speech"]
            self.assertEqual(len(speech_items), 2)
            self.assertEqual(speech_items[1]["join_strategy"], "sensitive_conservative")
            self.assertEqual(speech_items[1]["crossfade_ms"], 0)
            self.assertEqual(speech_items[1]["fade_policy"], "disabled_sensitive_segment")
            self.assertIn("start_ms", speech_items[1])
            self.assertIn("end_ms", speech_items[1])

    def test_terminal_segment_trace_includes_tail_closure_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = AppSettings(variants=_default_variants(), output_dir=str(root))
            pipeline = AudioPipeline(settings)

            segment_path = root / "terminal.wav"
            with Sine(440).to_audio_segment(duration=1000).export(segment_path, format="wav"):
                pass

            debug_path = root / "debug" / "terminal.json"
            pipeline.assemble(
                sequence=[
                    RenderedAudioSegment(
                        path=segment_path,
                        language="es",
                        order=1,
                        text="El resultado queda inconsistente.",
                        terminal=True,
                    ),
                ],
                title="terminal trace",
                normalize_audio=False,
                export_mp3=False,
                export_m4a=False,
                debug_path=debug_path,
                job_id="terminal",
            )

            payload = json.loads(debug_path.read_text(encoding="utf-8"))
            speech_item = [item for item in payload["items"] if item["kind"] == "speech"][0]
            self.assertTrue(speech_item["terminal"])
            self.assertIn("tail_220ms", speech_item["fade_policy"])
            self.assertEqual(speech_item["duration_ms"], 1220)
            self.assertTrue(speech_item["cleanup"]["terminal_word_protected"])

    def test_safe_cleanup_trims_only_excess_silence_before_clean_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = AppSettings(variants=_default_variants(), output_dir=str(root))
            pipeline = AudioPipeline(settings)

            segment_path = root / "cleanup.wav"
            audio = AudioSegment.silent(duration=400) + AudioSegment.silent(duration=1000) + AudioSegment.silent(duration=700)
            with audio.export(segment_path, format="wav"):
                pass

            debug_path = root / "debug" / "cleanup.json"
            pipeline.assemble(
                sequence=[
                    RenderedAudioSegment(
                        path=segment_path,
                        language="es",
                        order=1,
                        text="Cierre después.",
                        terminal=True,
                    ),
                ],
                title="cleanup trace",
                normalize_audio=False,
                export_mp3=False,
                export_m4a=False,
                debug_path=debug_path,
                job_id="cleanup",
            )

            payload = json.loads(debug_path.read_text(encoding="utf-8"))
            speech_item = [item for item in payload["items"] if item["kind"] == "speech"][0]
            self.assertEqual(speech_item["cleanup"]["trim_policy"], "safe_silence_only")
            self.assertLessEqual(speech_item["cleanup"]["trimmed_leading_ms"], settings.audio_tuning.max_leading_silence_trim_ms)
            self.assertGreaterEqual(speech_item["cleanup"]["trimmed_trailing_ms"], 1)


if __name__ == "__main__":
    unittest.main()
