"""
LLM refinement layer (optional).
Responsibilities: send raw transcript to LLM, clean filler words / grammar,
return final text only, log estimated cost per call.
Activated when config.settings.LLM_ENABLED is True.
"""
