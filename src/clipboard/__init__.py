"""
Clipboard & notification layer.
Responsibilities: copy final text to system clipboard via pyperclip and,
optionally, paste it into the window the user was working in.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from src.clipboard.focus import ForegroundTracker, paste_into


class ClipboardError(Exception):
    """Raised when the system clipboard can't be written."""


class Delivery(Enum):
    PASTED = "pasted"   # copied + pasted into the target window
    COPIED = "copied"   # copied only (auto-paste off, or not safe to paste)


def copy_text(text: str) -> None:
    import pyperclip

    try:
        pyperclip.copy(text)
    except Exception as exc:
        raise ClipboardError(str(exc)) from exc


def deliver(text: str, target: Optional[int], auto_paste: bool) -> Delivery:
    """Copy `text` and, if enabled and safe, paste it into `target`."""
    copy_text(text)
    if auto_paste and paste_into(target):
        return Delivery.PASTED
    return Delivery.COPIED


__all__ = ["ClipboardError", "Delivery", "ForegroundTracker", "copy_text", "deliver"]
