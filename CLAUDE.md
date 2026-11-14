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
  llm/       ← optional LLM refinement via OpenAI (gpt-4o-mini), cost tracking
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
- `FLUXUS_WHISPER_MODEL`: `tiny` | `base` | `small` | `medium` | `large-v3` | `large-v3-turbo` (unset = `large-v3-turbo` on CUDA, `small` on CPU)
- `FLUXUS_HOTWORDS` / `FLUXUS_INITIAL_PROMPT`: vocabulary and punctuation-style hints for Whisper
- `FLUXUS_LLM_ENABLED`: `true` / `false`
- `FLUXUS_LLM_MODEL`: OpenAI model for refinement (default `gpt-4o-mini`)
- `FLUXUS_WHISPER_DEVICE`: `auto` (CUDA → CPU fallback) | `cuda` | `cpu`
- `FLUXUS_HOTKEY`: default `ctrl+shift+space`
- `FLUXUS_AUTO_PASTE`: `true` / `false` — initial state of the title-bar "Pegar" switch

## Branch / PR strategy

One PR per layer, in dependency order:

| Branch | Scope | Status |
|--------|-------|--------|
| `feat/project-scaffold` | Structure, requirements, config, CLAUDE.md | ✅ #1 |
| `feat/ui-shell` | Floating CustomTkinter window + hotkey | ✅ #2 |
| `feat/audio-capture` | sounddevice recording module | ✅ #4 |
| `feat/stt-local` | faster-whisper integration + STT interface | ✅ #5 (+ #7 CUDA probe, #9 quality) |
| `feat/clipboard-notify` | Auto-copy + auto-paste into previous window, "Pegar" switch | ✅ #10 |
| `feat/packaging` | PyInstaller .exe build | 🚧 in progress |
| `feat/stt-api-fallback` | OpenAI Whisper API fallback | ⏳ |
| `feat/command-router` | Keyword command dispatcher | ⏳ |
| `feat/llm-layer` | LLM refinement + cost logging | ⏳ |

Improvements backlog (not tied to a layer):

| Branch | Scope | Status |
|--------|-------|--------|
| `feat/persist-settings` | Remember mic, compute device, "Pegar" switch and window position between sessions | ⏳ |
| `feat/recording-feedback` | Mic level meter while recording + configurable max recording length | ⏳ |
| `chore/tests` | pytest suite for hardware-free parts (AudioData, device resolution, paste decisions, UI state machine) | ⏳ |
