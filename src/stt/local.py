"""
Local STT engine backed by faster-whisper.

Loads a Whisper model on construction (or first warmup() call) and transcribes
in-memory float32 audio at 16 kHz. Device resolution honours settings.WHISPER_DEVICE:
"auto" tries CUDA via ctranslate2 and falls back to CPU silently.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from faster_whisper import WhisperModel

from config import settings
from src.audio import AudioData
from src.stt.base import STTEngine, STTError


def _cuda_runtime_available() -> bool:
    """Return True only if ctranslate2 sees a CUDA device AND the runtime DLLs load.

    On Windows, ctranslate2.get_cuda_device_count() reports >0 as long as the NVIDIA
    driver is present, even when CUDA 12 runtime libs (cublas64_12.dll, cuDNN) aren't
    installed. ctranslate2 loads those lazily during the first GPU op, and a missing
    DLL there can hang the process instead of raising. Probing the DLL upfront lets
    us fall back to CPU cleanly.
    """
    try:
        import ctranslate2  # type: ignore[import]

        if ctranslate2.get_cuda_device_count() <= 0:
            return False
    except Exception:
        return False

    if os.name != "nt":
        return True  # Linux/Mac: trust the package manager to provide CUDA libs.

    import ctypes

    try:
        ctypes.WinDLL("cublas64_12.dll")
    except OSError:
        print(
            "[FLUXUS stt] CUDA GPU detected, but cublas64_12.dll is not on PATH. "
            "Falling back to CPU. To enable GPU, install CUDA 12 runtime + cuDNN 9 "
            "(see faster-whisper README).",
            flush=True,
        )
        return False
    return True


_VALID_CHOICES = ("auto", "cuda", "cpu")


class LocalWhisperEngine(STTEngine):
    def __init__(self) -> None:
        self._model: Optional[WhisperModel] = None
        self._load_lock = threading.Lock()
        self._user_choice = settings.WHISPER_DEVICE  # "auto" | "cuda" | "cpu"
        self._device = self._resolve_device(self._user_choice)
        self._compute_type = "float16" if self._device == "cuda" else "int8"

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def user_choice(self) -> str:
        """The user's selected device mode ('auto' | 'cuda' | 'cpu')."""
        return self._user_choice

    def set_device(self, choice: str) -> None:
        """Override the device at runtime. Drops the loaded model so the next
        warmup()/transcribe() reloads on the new device."""
        if choice not in _VALID_CHOICES:
            raise ValueError(f"Unknown device choice: {choice!r}")
        with self._load_lock:
            self._user_choice = choice
            self._device = self._resolve_device(choice)
            self._compute_type = "float16" if self._device == "cuda" else "int8"
            self._model = None

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

            # Hard guard: explicit CUDA choice without runtime libs would hang during
            # transcribe (lazy DLL load). Surface a clean error instead.
            if self._device == "cuda" and not _cuda_runtime_available():
                if self._user_choice == "auto":
                    self._device = "cpu"
                    self._compute_type = "int8"
                else:
                    raise STTError(
                        "CUDA seleccionado pero falta cublas64_12.dll. "
                        "Instala CUDA 12 runtime + cuDNN 9 o usa CPU/Auto."
                    )

            try:
                self._model = WhisperModel(
                    settings.WHISPER_MODEL,
                    device=self._device,
                    compute_type=self._compute_type,
                )
                return
            except Exception as exc:
                # Auto-mode safety net for non-DLL CUDA failures (OOM, driver, etc.).
                if self._device == "cuda" and self._user_choice == "auto":
                    print(
                        f"[FLUXUS stt] CUDA load failed ({exc}); falling back to CPU.",
                        flush=True,
                    )
                    self._device = "cpu"
                    self._compute_type = "int8"
                    try:
                        self._model = WhisperModel(
                            settings.WHISPER_MODEL,
                            device="cpu",
                            compute_type="int8",
                        )
                        return
                    except Exception as cpu_exc:
                        raise STTError(
                            f"Could not load Whisper model '{settings.WHISPER_MODEL}' "
                            f"on CPU after CUDA fallback: {cpu_exc}"
                        ) from cpu_exc
                raise STTError(
                    f"Could not load Whisper model '{settings.WHISPER_MODEL}' "
                    f"on device '{self._device}': {exc}"
                ) from exc

    @property
    def device(self) -> str:
        """Device the model is *currently* loaded on (post-fallback)."""
        return self._device

    @staticmethod
    def _resolve_device(choice: str) -> str:
        if choice == "auto":
            return "cuda" if _cuda_runtime_available() else "cpu"
        return choice
