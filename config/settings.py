"""
Central configuration for FLUXUS.
Override values via a .env file or environment variables.
"""

import os
import sys
from pathlib import Path

# Packaged build (PyInstaller): user files (.env) live next to FLUXUS.exe.
# Source checkout: project root.
FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
# Per-user writable data (logs, future persisted settings).
DATA_DIR = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "FLUXUS"

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover — dependency missing, fall back to OS env only
    print("[FLUXUS] python-dotenv not installed; .env file will be ignored.")
else:
    # Real environment variables take precedence over the file.
    load_dotenv(APP_DIR / ".env", override=False)

# --- STT ---
STT_ENGINE = os.getenv("FLUXUS_STT_ENGINE", "local")  # "local" | "api"
# Model size: tiny | base | small | medium | large-v3 | large-v3-turbo.
# Empty (default) = pick by device: large-v3-turbo on CUDA, small on CPU.
WHISPER_MODEL = os.getenv("FLUXUS_WHISPER_MODEL", "").strip()
WHISPER_MODEL_CUDA_DEFAULT = "large-v3-turbo"
WHISPER_MODEL_CPU_DEFAULT = "small"
# Device for local STT: "auto" tries CUDA first, then falls back to CPU.
# NVIDIA users: "cuda" | AMD/Intel GPU users: "cpu" (ROCm builds not bundled)
WHISPER_DEVICE = os.getenv("FLUXUS_WHISPER_DEVICE", "auto")  # "auto" | "cuda" | "cpu"
# Language hint for transcription. "auto" lets Whisper detect (slower, error-prone on short clips).
WHISPER_LANGUAGE = os.getenv("FLUXUS_LANGUAGE", "es")  # "es" | "en" | "auto"

# Style hint: Whisper imitates the punctuation/casing of this text. A well-punctuated
# sample sentence in the target language noticeably improves commas, accents and "¿?".
# Unset → built-in sample for the selected language; set to empty to disable.
_DEFAULT_PROMPTS = {
    "es": "Hola, ¿qué tal? Te escribo para confirmar la reunión del martes: revisaremos el informe, los próximos pasos y el presupuesto.",
    "en": "Hi, how are you? I'm writing to confirm Tuesday's meeting: we'll review the report, next steps and the budget.",
}
WHISPER_INITIAL_PROMPT = os.getenv(
    "FLUXUS_INITIAL_PROMPT", _DEFAULT_PROMPTS.get(WHISPER_LANGUAGE, "")
).strip()
# Comma-separated words Whisper should favour (names, jargon): "FLUXUS, Kubernetes, Marcasombra"
WHISPER_HOTWORDS = os.getenv("FLUXUS_HOTWORDS", "").strip()

# Voice-activity filter (drops silence → avoids hallucinated text on quiet clips).
# Lower threshold = keeps softer speech; more padding = doesn't clip word starts/ends.
VAD_THRESHOLD = float(os.getenv("FLUXUS_VAD_THRESHOLD", "0.35"))
VAD_SPEECH_PAD_MS = int(os.getenv("FLUXUS_VAD_SPEECH_PAD_MS", "600"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- LLM (OpenAI only) ---
LLM_ENABLED = os.getenv("FLUXUS_LLM_ENABLED", "false").lower() == "true"
LLM_MODEL = os.getenv("FLUXUS_LLM_MODEL", "gpt-4o-mini")

# --- Audio ---
AUDIO_SAMPLE_RATE = 16000  # Hz — optimal for Whisper
AUDIO_CHANNELS = 1

# --- UI ---
HOTKEY = os.getenv("FLUXUS_HOTKEY", "ctrl+shift+space")
# After transcribing, paste into the window you were in (text is always copied too).
# Initial state of the "Pegar" switch in the title bar.
AUTO_PASTE = os.getenv("FLUXUS_AUTO_PASTE", "true").lower() == "true"
WINDOW_OPACITY = 0.92
