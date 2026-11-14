"""
User preferences changed from the UI, persisted between sessions.

Stored as JSON in %LOCALAPPDATA%\\FLUXUS\\prefs.json. A choice made in the UI
wins over the .env / environment default (which only sets the first-run value).

Keys (all optional):
    mic_name       str   input device name (indices change between sessions)
    compute        str   "auto" | "cuda" | "cpu"
    auto_paste     bool  "Pegar" switch
    compact        bool  compact (button-only) mode
    full_pos       [x,y] window position in full mode (screen pixels)
    compact_pos    [x,y] window position in compact mode (screen pixels)
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from config import settings

_KNOWN_KEYS = {"mic_name", "compute", "auto_paste", "compact", "full_pos", "compact_pos"}


def _valid(key: str, value: Any) -> bool:
    if key == "mic_name":
        return isinstance(value, str) and bool(value)
    if key == "compute":
        return value in ("auto", "cuda", "cpu")
    if key in ("auto_paste", "compact"):
        return isinstance(value, bool)
    if key in ("full_pos", "compact_pos"):
        return (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        )
    return False


class Prefs:
    """Small thread-safe JSON store. Unknown or malformed entries are ignored,
    so a hand-edited or corrupted file never prevents FLUXUS from starting."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or settings.DATA_DIR / "prefs.json"
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._load()

    @property
    def path(self) -> Path:
        return self._path

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def update(self, **changes: Any) -> None:
        """Merge valid changes and save. Invalid ones are dropped silently."""
        with self._lock:
            changed = False
            for key, value in changes.items():
                if key in _KNOWN_KEYS and _valid(key, value):
                    value = list(value) if isinstance(value, tuple) else value
                    if self._data.get(key) != value:
                        self._data[key] = value
                        changed = True
            if changed:
                self._save()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if k in _KNOWN_KEYS and _valid(k, v)}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self._path)  # atomic: never leaves a half-written file
        except OSError as exc:
            print(f"[FLUXUS prefs] could not save {self._path}: {exc}")
