"""
STT (Speech-to-Text) layer.
Responsibilities: abstract STT interface, local faster-whisper engine, OpenAI API fallback.
Engine selection is driven by config.settings.STT_ENGINE.
"""

from config import settings
from src.stt.base import STTEngine, STTError


def create_engine() -> STTEngine:
    """Build the STT engine selected by settings.STT_ENGINE."""
    engine = settings.STT_ENGINE.lower()
    if engine == "local":
        from src.stt.local import LocalWhisperEngine

        return LocalWhisperEngine()
    raise STTError(f"Unsupported STT engine: {settings.STT_ENGINE!r}")


__all__ = ["STTEngine", "STTError", "create_engine"]
