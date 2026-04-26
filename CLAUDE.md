# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Architecture

FLUXUS is a layered pipeline. Each layer lives in its own package under `src/` and is independently replaceable.

```
main.py                  ← entry point, boots UI
config/settings.py       ← all runtime config (STT engine, LLM toggle, hotkey, etc.)
src/
  ui/        ← CustomTkinter floating widget (borderless, always-on-top, global hotkey)
  audio/     ← sounddevice recording, in-memory buffer, temp file cleanup
  stt/       ← abstract STT interface; local faster-whisper engine + OpenAI API fallback
  llm/       ← optional LLM refinement (gpt-4o-mini / claude-haiku), cost tracking
  commands/  ← keyword router: "Comando: ..." → local Python handler, bypasses LLM
  clipboard/ ← pyperclip copy + visual notification back to UI
```

**Execution flow:**
1. Hotkey / button → `audio` starts recording
2. Stop → raw audio → `stt` (local CUDA or API fallback)
3. Raw transcript → `commands` router (if keyword match → execute locally and stop)
4. If no command → optional `llm` refinement
5. Final text → `clipboard` copy + UI notification
6. Temp audio purged

## Configuration

All tuneable values are in `config/settings.py`, read from environment variables.
Copy `.env.example` (to be created) to `.env` and fill in API keys — never commit `.env`.

Key settings:
- `FLUXUS_STT_ENGINE`: `local` (default) or `api`
- `FLUXUS_WHISPER_MODEL`: `tiny` | `base` | `small` | `medium` | `large-v3`
- `FLUXUS_LLM_ENABLED`: `true` / `false`
- `FLUXUS_LLM_PROVIDER`: `openai` | `anthropic`
- `FLUXUS_HOTKEY`: default `ctrl+shift+space`

## Branch / PR strategy

One PR per layer, in dependency order:

| Branch | Scope |
|--------|-------|
| `feat/project-scaffold` | Structure, requirements, config, CLAUDE.md |
| `feat/ui-shell` | Floating CustomTkinter window + hotkey |
| `feat/audio-capture` | sounddevice recording module |
| `feat/stt-local` | faster-whisper integration + STT interface |
| `feat/stt-api-fallback` | OpenAI Whisper API fallback |
| `feat/llm-layer` | LLM refinement + cost logging |
| `feat/command-router` | Keyword command dispatcher |
| `feat/clipboard-notify` | pyperclip copy + UI feedback |
| `feat/packaging` | PyInstaller .exe build |
