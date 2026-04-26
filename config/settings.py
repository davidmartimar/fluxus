"""
Central configuration for FLUXUS.
Override values via a .env file or environment variables.
"""

import os

# --- STT ---
STT_ENGINE = os.getenv("FLUXUS_STT_ENGINE", "local")  # "local" | "api"
WHISPER_MODEL = os.getenv("FLUXUS_WHISPER_MODEL", "base")  # tiny | base | small | medium | large-v3
WHISPER_DEVICE = os.getenv("FLUXUS_WHISPER_DEVICE", "auto")  # "auto" | "cuda" | "cpu"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- LLM ---
LLM_ENABLED = os.getenv("FLUXUS_LLM_ENABLED", "false").lower() == "true"
LLM_PROVIDER = os.getenv("FLUXUS_LLM_PROVIDER", "openai")  # "openai" | "anthropic"
LLM_MODEL = os.getenv("FLUXUS_LLM_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- Audio ---
AUDIO_SAMPLE_RATE = 16000  # Hz — optimal for Whisper
AUDIO_CHANNELS = 1

# --- UI ---
HOTKEY = os.getenv("FLUXUS_HOTKEY", "ctrl+shift+space")
WINDOW_OPACITY = 0.92
