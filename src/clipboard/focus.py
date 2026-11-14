"""
Foreground-window tracking and auto-paste (Windows).

FLUXUS can be triggered two ways, and the paste target differs:
  - Global hotkey from another app: that app stays in the foreground; paste there.
  - Click on the widget: FLUXUS takes focus, so the target is the *previous*
    external window. A tiny background poller remembers it.

Safety rule: we only paste if, when the transcript is ready, the foreground is
either the target itself or FLUXUS (in which case focus is handed back to the
target). If the user moved to some other app meanwhile, we don't paste — the
text is still on the clipboard.

On non-Windows platforms everything degrades to "no target" (copy only).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional

_IS_WIN = sys.platform == "win32"
_POLL_SECONDS = 0.25
_MODIFIERS = ("ctrl", "shift", "alt", "windows")

if _IS_WIN:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _SW_RESTORE = 9


def _foreground() -> Optional[int]:
    if not _IS_WIN:
        return None
    return _user32.GetForegroundWindow() or None


def _is_own(hwnd: int) -> bool:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


def _is_valid(hwnd: Optional[int]) -> bool:
    return bool(hwnd) and bool(_user32.IsWindow(hwnd)) and bool(_user32.IsWindowVisible(hwnd))


class ForegroundTracker:
    """Remembers the last foreground window that doesn't belong to FLUXUS."""

    def __init__(self) -> None:
        self._last_external: Optional[int] = None
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        if not _IS_WIN or self._started:
            return
        self._started = True
        threading.Thread(target=self._poll, name="fluxus-focus", daemon=True).start()

    def current_target(self) -> Optional[int]:
        """Window a transcript started *now* should be pasted into."""
        if not _IS_WIN:
            return None
        fg = _foreground()
        if fg and not _is_own(fg):
            self._remember(fg)
            return fg
        with self._lock:
            return self._last_external if _is_valid(self._last_external) else None

    def _remember(self, hwnd: int) -> None:
        with self._lock:
            self._last_external = hwnd

    def _poll(self) -> None:
        while True:
            try:
                fg = _foreground()
                if fg and not _is_own(fg):
                    self._remember(fg)
            except Exception:
                pass
            time.sleep(_POLL_SECONDS)


def paste_into(target: Optional[int]) -> bool:
    """Send Ctrl+V to `target` if it's safe to do so. Returns True if pasted.
    Assumes the text is already on the clipboard."""
    if not _IS_WIN or not _is_valid(target):
        return False

    fg = _foreground()
    if fg != target:
        if fg and not _is_own(fg):
            return False  # user moved to another app — don't paste there
        # FLUXUS has focus (user clicked the widget): hand focus back to the target.
        if _user32.IsIconic(target):
            _user32.ShowWindow(target, _SW_RESTORE)
        _user32.SetForegroundWindow(target)
        for _ in range(20):  # up to ~0.5 s for the switch to land
            if _foreground() == target:
                break
            time.sleep(0.025)
        else:
            return False

    try:
        import keyboard  # type: ignore[import]

        # The stop hotkey (e.g. ctrl+shift+space) may still be held; Ctrl+V with
        # Shift down becomes Ctrl+Shift+V, which is a different command in many apps.
        deadline = time.time() + 1.5
        while any(keyboard.is_pressed(m) for m in _MODIFIERS):
            if time.time() > deadline:
                return False
            time.sleep(0.02)
        if _foreground() != target:
            return False
        keyboard.send("ctrl+v")
        return True
    except Exception as exc:
        print(f"[FLUXUS clipboard] auto-paste failed: {exc}")
        return False
