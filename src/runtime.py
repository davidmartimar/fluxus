"""
Process-level setup that has to run before the UI: log redirection for the
windowed (no-console) build, a single-instance guard and a last-resort error box.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from config import settings

_LOG_MAX_BYTES = 1_000_000
_MUTEX_NAME = "Local\\FLUXUS.single-instance"
_ERROR_ALREADY_EXISTS = 183

_mutex_handle = None  # kept alive for the whole process


def log_path() -> Path:
    return settings.DATA_DIR / "fluxus.log"


def setup_logging() -> None:
    """In the windowed .exe there is no console: sys.stdout/stderr are None, so
    print() is lost and libraries that write progress bars (model download)
    crash. Point both at a log file instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if path.exists() and path.stat().st_size > _LOG_MAX_BYTES else "a"
        stream = open(path, mode, encoding="utf-8", buffering=1, errors="replace")
    except OSError:
        import io

        stream = io.StringIO()  # never fail startup just because of logging
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def acquire_single_instance() -> bool:
    """Return False if another FLUXUS is already running (two instances would
    register the global hotkey twice)."""
    global _mutex_handle
    if sys.platform != "win32":
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    return kernel32.GetLastError() != _ERROR_ALREADY_EXISTS


def show_error(title: str, message: str) -> None:
    """Native message box — works even if Tk failed to start."""
    print(f"[FLUXUS] {title}: {message}")
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)  # MB_ICONERROR


def report_fatal(exc: BaseException) -> None:
    traceback.print_exception(exc)
    show_error(
        "FLUXUS — error al arrancar",
        f"{exc}\n\nDetalles en:\n{log_path()}",
    )
