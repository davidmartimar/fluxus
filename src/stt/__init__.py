"""
STT (Speech-to-Text) layer.
Responsibilities: abstract STT interface, local faster-whisper engine, OpenAI API fallback.
Engine selection is driven by config.settings.STT_ENGINE.
"""
