from __future__ import annotations

import inspect
import os
from pathlib import Path

from app.config.settings import AppSettings
from app.services.base import BaseTTSService


class XTTSService(BaseTTSService):
    engine_name = "xtts_v2"

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._tts = None
        self._load_error: str | None = None
        self._apply_runtime_limits()

    def is_available(self) -> tuple[bool, str]:
        try:
            import torch  # noqa: F401
            from TTS.api import TTS  # noqa: F401
        except Exception as exc:  # pragma: no cover - import failure is environment-specific
            return False, f"Dependencias XTTS no disponibles: {exc}"

        if self._load_error:
            return False, self._load_error
        return True, "XTTS listo para cargar en demanda."

    def synthesize_segment(
        self,
        *,
        text: str,
        output_path: Path,
        speaker_wav: Path | None,
        variant: str,
        language: str | None,
        speed: float,
        temperature: float,
    ) -> None:
        if speaker_wav is None:
            raise RuntimeError("XTTS requiere una voz de referencia WAV para sintetizar.")

        tts = self._ensure_model()
        variant_profile = self._settings.variants.get(variant) or self._settings.variants[self._settings.default_variant]
        signature = inspect.signature(tts.tts_to_file)
        kwargs = {
            "text": text,
            "file_path": str(output_path),
        }
        if "speaker_wav" in signature.parameters:
            kwargs["speaker_wav"] = str(speaker_wav)
        if "language" in signature.parameters:
            kwargs["language"] = language or variant_profile.tts_language
        if "speed" in signature.parameters:
            kwargs["speed"] = speed
        if "temperature" in signature.parameters:
            kwargs["temperature"] = temperature

        tts.tts_to_file(**kwargs)

    def _ensure_model(self):
        if self._tts is not None:
            return self._tts

        try:
            # XTTS still hits unsupported ops on MPS for some speaker-encoder paths.
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            import torch
            from TTS.api import TTS

            self._apply_runtime_limits(torch)
            device = self._resolve_device(torch)
            self._tts = TTS(self._settings.tts.xtts_model_name).to(device)
            return self._tts
        except Exception as exc:  # pragma: no cover - depends on local XTTS install/model cache
            self._load_error = (
                "No se pudo cargar XTTS v2. Verifica dependencias, cache offline del modelo "
                f"y compatibilidad de PyTorch con Apple Silicon. Detalle: {exc}"
            )
            raise RuntimeError(self._load_error) from exc

    def _resolve_device(self, torch_module) -> str:
        preference = self._settings.tts.device_preference
        if preference == "cpu":
            return "cpu"
        if preference == "mps":
            return "mps" if torch_module.backends.mps.is_available() else "cpu"
        if torch_module.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _apply_runtime_limits(self, torch_module=None) -> None:
        eco_mode = self._settings.eco_mode
        if not eco_mode.enabled:
            return

        thread_count = str(max(1, eco_mode.max_torch_threads))
        os.environ.setdefault("OMP_NUM_THREADS", thread_count)
        os.environ.setdefault("MKL_NUM_THREADS", thread_count)
        os.environ.setdefault("OPENBLAS_NUM_THREADS", thread_count)
        os.environ.setdefault("VECLIB_MAXIMUM_THREADS", thread_count)
        os.environ.setdefault("NUMEXPR_NUM_THREADS", thread_count)

        if torch_module is None:
            return

        try:
            torch_module.set_num_threads(max(1, eco_mode.max_torch_threads))
        except Exception:
            pass

        try:
            torch_module.set_num_interop_threads(max(1, eco_mode.max_interop_threads))
        except Exception:
            pass
