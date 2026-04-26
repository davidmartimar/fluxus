"""
Command router layer.
Responsibilities: inspect raw transcript for keyword triggers (e.g. "Comando: ..."),
dispatch to local Python handlers instead of forwarding to the LLM layer.
"""
