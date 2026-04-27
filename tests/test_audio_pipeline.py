import json
import tempfile
import unittest
from pathlib import Path

from pydub import AudioSegment

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


if __name__ == "__main__":
    unittest.main()
