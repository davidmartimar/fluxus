# フ FLUXUS

A privacy-oriented, minimalist desktop widget for voice-to-text transcription with optional AI refinement.

Press a hotkey → speak → text is transcribed and copied to your clipboard, ready to paste anywhere.

---

## Features

- **Floating widget** — borderless, always-on-top window that stays out of the way
- **Global hotkey** — trigger recording from any application (`Ctrl+Shift+Space` by default)
- **Local STT** — transcription via [faster-whisper](https://github.com/SYSTRAN/faster-whisper); runs on NVIDIA (CUDA), or CPU on any machine
- **API fallback** — OpenAI Whisper API when local inference is not desired
- **LLM refinement** *(optional)* — cleans filler words and fixes grammar via OpenAI (gpt-4o-mini)
- **Command router** — keyword-triggered local actions (e.g. "Comando: Abre Youtube") bypass the LLM and run Python scripts directly
- **Auto-clipboard** — result is copied automatically; just press `Ctrl+V`
- **Portable** — distributed as a single `.exe` built with PyInstaller

---

## Requirements

- Python 3.14+
- Windows 10/11 (primary target)
- GPU acceleration is optional — the app runs on CPU on any machine

---

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/<your-org>/fluxus.git
cd fluxus

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure (optional)
copy .env.example .env
# Edit .env with your API keys and preferences

# 5. Run
python main.py
```

---

## Configuration

All settings are driven by environment variables. Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `FLUXUS_STT_ENGINE` | `local` | `local` (faster-whisper) or `api` (OpenAI Whisper) |
| `FLUXUS_WHISPER_MODEL` | `base` | `tiny` · `base` · `small` · `medium` · `large-v3` |
| `FLUXUS_WHISPER_DEVICE` | `auto` | `auto` (CUDA if available, else CPU) · `cuda` · `cpu` |
| `FLUXUS_LLM_ENABLED` | `false` | Enable LLM text refinement via OpenAI |
| `FLUXUS_LLM_MODEL` | `gpt-4o-mini` | OpenAI model for LLM refinement |
| `FLUXUS_HOTKEY` | `ctrl+shift+space` | Global hotkey to toggle recording |
| `OPENAI_API_KEY` | — | Required for `api` STT engine or LLM refinement |

### GPU support

| Hardware | Setting | Notes |
|---|---|---|
| NVIDIA (CUDA) | `FLUXUS_WHISPER_DEVICE=cuda` | Best performance |
| Any GPU / no GPU | `FLUXUS_WHISPER_DEVICE=cpu` | Works on all machines |
| Auto-detect | `FLUXUS_WHISPER_DEVICE=auto` | Default — tries CUDA, falls back to CPU |

---

## Architecture

```
main.py                  ← entry point
config/settings.py       ← central configuration via env vars
src/
  ui/        ← CustomTkinter floating widget
  audio/     ← sounddevice recording & temp buffer management
  stt/       ← STT interface; faster-whisper (local) + OpenAI (fallback)
  llm/       ← optional LLM refinement + cost tracking (OpenAI)
  commands/  ← keyword command dispatcher
  clipboard/ ← pyperclip copy + UI notification
```

---

## License

MIT
