"""
Abstract STT interface.

Concrete engines (local faster-whisper, OpenAI API) implement STTEngine.transcribe().
The pipeline depends only on this interface, so engines are swappable via settings.STT_ENGINE.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.audio import AudioData


class STTError(Exception):
    """Raised when an STT engine fails to transcribe (model error, network, etc.)."""


class STTEngine(ABC):
    """Speech-to-text engine contract."""

    @abstractmethod
    def transcribe(self, audio: AudioData) -> str:
        """Return the transcript for `audio`. May raise STTError."""

    def warmup(self) -> None:
        """Optional: pre-load model weights so the first transcribe() is fast. Default: no-op."""
        return None
