"""
Audio capture layer.
Responsibilities: microphone recording, in-memory buffering, temp file management and cleanup.
"""

from src.audio.recorder import AudioData, Recorder

__all__ = ["Recorder", "AudioData"]
