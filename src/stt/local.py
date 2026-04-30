"""
Local STT engine backed by faster-whisper.

Loads a Whisper model on construction (or first warmup() call) and transcribes
in-memory float32 audio at 16 kHz. Device resolution honours settings.WHISPER_DEVICE:
"auto" tries CUDA via ctranslate2 and falls back to CPU silently.
"""

from __future__ import annotations

import threading
from typing import Optional

from faster_whisper import WhisperModel

from config import settings
from src.audio import AudioData
from src.stt.base import STTEngine, STTError


class LocalWhisperEngine(STTEngine):
    def __init__(self) -> None:
        self._model: Optional[WhisperModel] = None
        self._load_lock = threading.Lock()
        self._device = self._resolve_device()
        self._compute_type = "float16" if self._device == "cuda" else "int8"

    # ── Public API ────────────────────────────────────────────────────────────

    def warmup(self) -> None:
        """Load the model now so the first transcribe() doesn't block on disk I/O."""
        self._ensure_loaded()

    def transcribe(self, audio: AudioData) -> str:
        if len(audio.samples) == 0:
            return ""

        self._ensure_loaded()
        assert self._model is not None  # for type checker

        language = None if settings.WHISPER_LANGUAGE == "auto" else settings.WHISPER_LANGUAGE

        try:
            segments, _info = self._model.transcribe(
                audio.samples,
                language=language,
                vad_filter=True,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as exc:
            raise STTError(f"faster-whisper failed: {exc}") from exc

    # ── Internal ──────────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            try:
                self._model = WhisperModel(
                    settings.WHISPER_MODEL,
                    device=self._device,
                    compute_type=self._compute_type,
                )
            except Exception as exc:
                raise STTError(
                    f"Could not load Whisper model '{settings.WHISPER_MODEL}' "
                    f"on device '{self._device}': {exc}"
                ) from exc

    @staticmethod
    def _resolve_device() -> str:
        choice = settings.WHISPER_DEVICE
        if choice != "auto":
            return choice
        try:
            import ctranslate2  # type: ignore[import]

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
        except Exception:
            pass
        return "cpu"
