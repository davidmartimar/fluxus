"""Windows-specific helpers so the borderless widget gets its own taskbar
entry and uses the FLUXUS icon instead of inheriting python.exe's identity.

No-ops on non-Windows platforms.
"""

from __future__ import annotations

import sys

_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_APPWINDOW = 0x00040000

_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_LR_DEFAULTSIZE = 0x00000040
_WM_SETICON = 0x0080
_ICON_SMALL = 0
_ICON_BIG = 1


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


def apply_taskbar_icon(window, ico_path: str) -> None:
    """Send WM_SETICON for both small and big sizes so the taskbar picks up
    our .ico even on borderless windows where Tk's iconbitmap path doesn't
    reach the shell. Schedules itself slightly after the deiconify in
    force_taskbar_entry so the HWND is fully visible to the shell first."""
    if sys.platform != "win32":
        return

    def _apply() -> None:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.LoadImageW.argtypes = [
                wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            user32.LoadImageW.restype = wintypes.HANDLE
            user32.SendMessageW.argtypes = [
                wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
            ]
            user32.SendMessageW.restype = wintypes.LPARAM

            hwnd = user32.GetParent(window.winfo_id())
            if not hwnd:
                return

            small = user32.LoadImageW(0, ico_path, _IMAGE_ICON, 16, 16, _LR_LOADFROMFILE)
            big = user32.LoadImageW(0, ico_path, _IMAGE_ICON, 32, 32, _LR_LOADFROMFILE)
            if small:
                user32.SendMessageW(hwnd, _WM_SETICON, _ICON_SMALL, small)
            if big:
                user32.SendMessageW(hwnd, _WM_SETICON, _ICON_BIG, big)
        except Exception as exc:
            print(f"[FLUXUS] WM_SETICON failed: {exc}")

    window.after(50, _apply)
