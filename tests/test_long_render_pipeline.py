import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydub.generators import Sine

from app.config.settings import AppSettings, _default_variants
from app.models.domain import GenerationOptions, SpeechSpan
from app.services.audio_pipeline import AudioPipeline, RenderedAudioSegment
from app.services.disk_audio_assembler import DiskAudioAssembler
from app.services.generation_service import GenerationService
from app.services.history_service import HistoryService
from app.services.job_manager import JobManager
from app.services.render_manifest import RenderManifestItem, RenderManifestStore


class _NoopTTS:
    engine_name = "noop"


class LongRenderPipelineTestCase(unittest.TestCase):
    def test_long_render_decision_uses_duration_or_segment_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = AppSettings(
                variants=_default_variants(),
                output_dir=str(root),
                history_file=str(root / "history.json"),
                playlists_file=str(root / "playlists.json"),
            )
            service = GenerationService(
                settings=settings,
                tts_service=_NoopTTS(),  # type: ignore[arg-type]
                audio_pipeline=AudioPipeline(settings),
                history_service=HistoryService(settings),
                job_manager=JobManager(),
            )

            options = GenerationOptions()
            short_plan = [SpeechSpan(text="Texto breve.")]
            self.assertEqual(service._long_render_decision(options=options, estimated_seconds=100, sequence_plan=short_plan)[0], False)
            self.assertEqual(service._long_render_decision(options=options, estimated_seconds=1300, sequence_plan=short_plan)[0], True)

            many_segments = [SpeechSpan(text=f"Segmento {index}.") for index in range(settings.long_render.auto_enable_min_segments)]
            enabled, reason = service._long_render_decision(
                options=options,
                estimated_seconds=100,
                sequence_plan=many_segments,
            )
            self.assertTrue(enabled)
            self.assertIn("speech_segments", reason)

    def test_render_manifest_persists_segment_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manifest.json"
            store = RenderManifestStore(path)
            store.initialize(
                job_id="job",
                title="Long render",
                estimated_seconds=1500,
                trigger_reason="test",
                total_items=2,
                total_speech_segments=1,
            )
            store.upsert_item(
                RenderManifestItem(
                    order=1,
                    kind="speech",
                    status="validated",
                    render_order=1,
                    language="es",
                    text="Prueba de segmento.",
                    path="segment-0001.wav",
                    attempts=1,
                    validation={"ok": True, "duration_ms": 1000},
                    duration_ms=1000,
                )
            )
            store.save()

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "long_render")
            self.assertEqual(payload["items"][0]["status"], "validated")
            self.assertEqual(payload["items"][0]["validation"]["duration_ms"], 1000)

    def test_disk_assembler_writes_debug_and_concat_plan_without_final_memory_concat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = AppSettings(variants=_default_variants(), output_dir=str(root))
            assembler = DiskAudioAssembler(settings, AudioPipeline(settings))

            first = root / "first.wav"
            second = root / "second.wav"
            with Sine(440).to_audio_segment(duration=1000).export(first, format="wav"):
                pass
            with Sine(550).to_audio_segment(duration=900).export(second, format="wav"):
                pass

            def fake_run(command, check, capture_output, text):  # noqa: ANN001
                Path(command[-1]).write_bytes(b"RIFF----WAVEfmt ")
                return object()

            debug_path = root / "debug" / "long.json"
            render_dir = root / "renders" / "job"
            with patch("app.services.disk_audio_assembler.has_ffmpeg", return_value=True), patch(
                "app.services.disk_audio_assembler.subprocess.run",
                side_effect=fake_run,
            ):
                output_files, duration_seconds, warnings = assembler.assemble(
                    sequence=[
                        RenderedAudioSegment(path=first, language="es", order=1, text="Primer segmento."),
                        250,
                        RenderedAudioSegment(
                            path=second,
                            language="es",
                            order=2,
                            text="Segmento sensible con accessKeyId.",
                            sensitive=True,
                            sensitivity_reasons=("camel_or_pascal_case",),
                            terminal=True,
                        ),
                    ],
                    title="Long Render",
                    render_dir=render_dir,
                    normalize_audio=False,
                    export_mp3=False,
                    export_m4a=False,
                    debug_path=debug_path,
                    job_id="job",
                )

            self.assertEqual(output_files.wav.endswith(".wav"), True)
            self.assertGreater(duration_seconds, 2)
            self.assertEqual(warnings, [])
            self.assertTrue((render_dir / "concat.txt").exists())
            payload = json.loads(debug_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "long_render")
            self.assertEqual(len(payload["items"]), 3)
            self.assertEqual(payload["items"][2]["join_strategy"], "disk_concat_first_segment")
            self.assertEqual(payload["items"][2]["crossfade_ms"], 0)


if __name__ == "__main__":
    unittest.main()
