"""
Audio capture layer.
Responsibilities: microphone recording, in-memory buffering, temp file management and cleanup.
"""

from src.audio.recorder import (
    AudioData,
    Recorder,
    default_input_device,
    list_input_devices,
)

__all__ = [
    "AudioData",
    "Recorder",
    "default_input_device",
    "list_input_devices",
]
