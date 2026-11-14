"""Multi-monitor helpers: keep the widget inside a visible work area.

A saved position may point at a monitor that is no longer connected, or the
full view may not fit where the compact button was. clamp_to_work_area()
moves a window rect into the work area (screen minus taskbar) of the nearest
monitor. Windows only; elsewhere falls back to the primary screen size.
"""

from __future__ import annotations

import sys
from typing import Optional

Rect = tuple[int, int, int, int]  # left, top, right, bottom

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _MONITOR_DEFAULTTONEAREST = 2

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    _user32 = ctypes.windll.user32
    _user32.MonitorFromRect.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD]
    _user32.MonitorFromRect.restype = wintypes.HANDLE
    _user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]


def work_area(x: int, y: int, w: int, h: int, fallback: Optional[Rect] = None) -> Optional[Rect]:
    """Work area of the monitor nearest to the given rect."""
    if sys.platform != "win32":
        return fallback
    try:
        rect = wintypes.RECT(x, y, x + w, y + h)
        mon = _user32.MonitorFromRect(ctypes.byref(rect), _MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if mon and _user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except Exception as exc:
        print(f"[FLUXUS] monitor query failed: {exc}")
    return fallback


def clamp(x: int, y: int, w: int, h: int, area: Optional[Rect]) -> tuple[int, int]:
    """Move (x, y) so the w×h rect lies fully inside `area` (if it fits)."""
    if area is None:
        return x, y
    left, top, right, bottom = area
    x = max(left, min(x, right - w))
    y = max(top, min(y, bottom - h))
    return x, y
