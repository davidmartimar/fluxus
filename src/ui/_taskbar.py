"""Windows-specific helpers so the borderless widget gets its own taskbar
entry and uses the FLUXUS icon instead of inheriting python.exe's identity.

No-ops on non-Windows platforms.
"""

from __future__ import annotations

import sys

_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_APPWINDOW = 0x00040000


def set_app_user_model_id(app_id: str) -> None:
    """Detach from the host python.exe so the taskbar uses our window icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as exc:
        print(f"[FLUXUS] AppUserModelID set failed: {exc}")


def force_taskbar_entry(window) -> None:
    """A Tk window with overrideredirect(True) is hidden from the taskbar.
    Toggle WS_EX_APPWINDOW on its top-level HWND to bring it back."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            return

        if ctypes.sizeof(ctypes.c_void_p) == 8:
            get_long = ctypes.windll.user32.GetWindowLongPtrW
            set_long = ctypes.windll.user32.SetWindowLongPtrW
        else:
            get_long = ctypes.windll.user32.GetWindowLongW
            set_long = ctypes.windll.user32.SetWindowLongW

        style = get_long(hwnd, _GWL_EXSTYLE)
        style = (style & ~_WS_EX_TOOLWINDOW) | _WS_EX_APPWINDOW
        set_long(hwnd, _GWL_EXSTYLE, style)

        # Re-show so the new style is picked up by the shell.
        window.withdraw()
        window.after(10, window.deiconify)
    except Exception as exc:
        print(f"[FLUXUS] Taskbar entry fix failed: {exc}")
