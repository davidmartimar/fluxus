"""
Audio recorder using sounddevice.

Records microphone input into a numpy array (in-memory).
No audio is written to disk unless explicitly requested via as_wav_bytes().
The recorded buffer is discarded when clear() is called.

Usage:
    recorder = Recorder()
    recorder.start()
    # ... user speaks ...
    audio = recorder.stop()          # returns AudioData
    wav_bytes = audio.as_wav_bytes() # for OpenAI API
    numpy_arr = audio.samples        # for faster-whisper
    audio.clear()                    # purge from memory
"""

from __future__ import annotations

import io
import wave
import threading
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import sounddevice as sd

from config import settings


@dataclass
class AudioData:
    """Immutable container for a single recording."""

    samples: np.ndarray  # float32, shape (n_samples,), mono
    sample_rate: int

    def as_wav_bytes(self) -> bytes:
        """Encode to WAV and return as bytes (for OpenAI Whisper API)."""
        pcm = (self.samples * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def as_wav_file_like(self) -> io.BytesIO:
        """Return a named BytesIO suitable for openai.audio.transcriptions.create()."""
        buf = io.BytesIO(self.as_wav_bytes())
        buf.name = "audio.wav"
        return buf

    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate

    def clear(self) -> None:
        """Zero out the buffer and release the numpy array."""
        self.samples[:] = 0
        self.samples = np.array([], dtype=np.float32)


def list_input_devices() -> list[tuple[int, str]]:
    """Return [(index, name), ...] for every device that supports microphone input."""
    out: list[tuple[int, str]] = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) > 0:
            out.append((idx, dev["name"]))
    return out


def default_input_device() -> Optional[int]:
    """Return the system's default input device index, or None if unavailable."""
    try:
        idx = sd.default.device[0]
        return int(idx) if idx is not None and idx >= 0 else None
    except Exception:
        return None


class Recorder:
    """Starts and stops microphone recording on demand."""

    def __init__(self, device: Optional[int] = None) -> None:
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._device: Optional[int] = device

    # ── Public API ────────────────────────────────────────────────────────────

    def set_device(self, device: Optional[int]) -> None:
        """Change the input device. Applies to the *next* start(); ignored mid-recording."""
        self._device = device

    def start(self) -> None:
        """Begin capturing audio from the configured (or default) microphone."""
        if self._recording:
            return
        with self._lock:
            self._chunks.clear()
            self._recording = True

        self._stream = sd.InputStream(
            device=self._device,
            samplerate=settings.AUDIO_SAMPLE_RATE,
            channels=settings.AUDIO_CHANNELS,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> AudioData:
        """
        Stop recording and return the captured audio.
        Raises RuntimeError if called without a prior start().
        """
        if not self._recording:
            raise RuntimeError("Recorder is not currently recording.")

        self._recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if self._chunks:
                samples = np.concatenate(self._chunks, axis=0).flatten()
            else:
                samples = np.array([], dtype=np.float32)
            self._chunks.clear()

        return AudioData(samples=samples, sample_rate=settings.AUDIO_SAMPLE_RATE)

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ── Internal ──────────────────────────────────────────────────────────────

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            print(f"[FLUXUS audio] {status}")
        if self._recording:
            with self._lock:
                self._chunks.append(indata.copy())
