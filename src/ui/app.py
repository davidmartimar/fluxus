"""
Main application window for FLUXUS.

A borderless, always-on-top floating widget built with CustomTkinter.
Draggable via click-and-drag on the window body.
The record button toggles between idle and recording states.
A collapsible mic picker shows the active input device and lets the user pick another.
The transcript stays visible until the next recording starts; the user clicks Copiar
to copy it to the clipboard.
on_record_start / on_record_stop run in order on a single background worker thread,
so a quick start→stop can never overtake each other.
External layers (audio, STT, etc.) wire in via the callback properties:
    app.on_record_start  — called when recording begins
    app.on_record_stop   — called when recording stops; receives no args. The pipeline
                           MUST call app.set_idle() when it's done (success or error);
                           until then the record button and hotkey are disabled.
    app.on_device_change — called with the new device index when the user picks a mic
    app.on_compute_change — called with 'auto'|'cuda'|'cpu' when the user picks a compute target
    app.on_copy          — called with the transcript text when the user clicks Copiar
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from config import settings
from src.ui._taskbar import (
    apply_taskbar_icon,
    force_taskbar_entry,
    set_app_user_model_id,
)

_ICON_PATH = Path(__file__).parent / "fluxus_icon.png"
_ICO_PATH = Path(__file__).parent / "fluxus_icon.ico"
_APP_USER_MODEL_ID = "dorvincrew.fluxus"

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Palette ──────────────────────────────────────────────────────────────────
_CLR_BG = "#1a1a1a"
_CLR_SURFACE = "#2b2b2b"
_CLR_IDLE = "#FF4444"
_CLR_RECORDING = "#bf3a3a"
_CLR_BUSY = "#444444"
_CLR_TEXT = "#e0e0e0"
_CLR_SUBTEXT = "#888888"

_COMPUTE_LABELS = {
    "Auto": "auto",
    "GPU (CUDA)": "cuda",
    "CPU": "cpu",
}
_COMPUTE_REVERSE = {v: k for k, v in _COMPUTE_LABELS.items()}

_ERROR_RESET_MS = 4000

# Record-button states
_IDLE = "idle"
_RECORDING = "recording"
_PROCESSING = "processing"


class App(ctk.CTk):
    """FLUXUS floating widget."""

    def __init__(self) -> None:
        # Must run before the HWND is created so the taskbar groups under our identity.
        set_app_user_model_id(_APP_USER_MODEL_ID)
        super().__init__(fg_color=_CLR_BG)

        # ── Callbacks (wired by pipeline in main.py) ─────────────────────────
        self.on_record_start: Optional[Callable[[], None]] = None
        self.on_record_stop: Optional[Callable[[], None]] = None
        self.on_device_change: Optional[Callable[[int], None]] = None
        self.on_compute_change: Optional[Callable[[str], None]] = None
        self.on_copy: Optional[Callable[[str], None]] = None

        # ── Internal state ────────────────────────────────────────────────────
        self._state = _IDLE
        self._status_seq = 0  # bumped on every status change; lets stale resets bail out
        self._drag_dx = 0
        self._drag_dy = 0
        # Single worker → record start/stop callbacks always run in click order.
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fluxus-pipeline")
        self._device_labels: dict[str, int] = {}
        self._current_transcript: str = ""

        # ── Load icon ────────────────────────────────────────────────────────
        self._icon_img_large = ctk.CTkImage(
            light_image=Image.open(_ICON_PATH),
            dark_image=Image.open(_ICON_PATH),
            size=(22, 22),
        )
        self._icon_img_small = ctk.CTkImage(
            light_image=Image.open(_ICON_PATH),
            dark_image=Image.open(_ICON_PATH),
            size=(16, 16),
        )

        self._build_window()
        self._build_widgets()
        self._bind_drag()
        self._bind_hotkey()

    # ── Window setup ─────────────────────────────────────────────────────────

    def _build_window(self) -> None:
        self.title("FLUXUS")
        self.geometry("300x285")
        self.resizable(False, False)
        self.overrideredirect(True)           # borderless
        self.wm_attributes("-topmost", True)  # always-on-top
        self.wm_attributes("-alpha", settings.WINDOW_OPACITY)
        # Title-bar / Alt-Tab icon (Tk-level, used inside the app window).
        if _ICON_PATH.exists():
            from PIL import ImageTk
            _raw = Image.open(_ICON_PATH).resize((32, 32))
            self._tk_icon = ImageTk.PhotoImage(_raw)
            self.iconphoto(True, self._tk_icon)
        # Windows taskbar reads from the window-class icon, which iconphoto
        # doesn't reliably set on borderless windows — point iconbitmap at a
        # real .ico so the FLUXUS logo (not the Tk default) shows up there.
        if _ICO_PATH.exists():
            try:
                self.iconbitmap(default=str(_ICO_PATH))
            except Exception as exc:
                print(f"[FLUXUS] iconbitmap failed: {exc}")
        self._center_window()
        # overrideredirect strips the window from the Windows taskbar; re-add it
        # via WS_EX_APPWINDOW so users can find/focus FLUXUS like any other app.
        force_taskbar_entry(self)
        if _ICO_PATH.exists():
            apply_taskbar_icon(self, str(_ICO_PATH))

    def _center_window(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 300, 285
        x = (sw - w) // 2
        y = sh - h - 80  # near taskbar by default
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── Widgets ───────────────────────────────────────────────────────────────

    def _build_widgets(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Title bar row
        title_bar = ctk.CTkFrame(self, fg_color=_CLR_SURFACE, height=28, corner_radius=0)
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_bar,
            text=" FLUXUS",
            image=self._icon_img_small,
            compound="left",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=_CLR_TEXT,
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w", padx=(6, 0), pady=4)
        # Only the title bar drags the window, so selecting transcript text doesn't.
        self._drag_handles = (title_bar, title_label)

        self._close_btn = ctk.CTkButton(
            title_bar,
            text="✕",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#4a1a1a",
            text_color=_CLR_SUBTEXT,
            font=ctk.CTkFont(size=11),
            corner_radius=0,
            command=self.destroy,
        )
        self._close_btn.grid(row=0, column=1, sticky="e")

        # Body
        body = ctk.CTkFrame(self, fg_color=_CLR_BG, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(10, 12))
        body.grid_columnconfigure(0, weight=1)

        self._status_label = ctk.CTkLabel(
            body,
            text="Listo",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_CLR_SUBTEXT,
            anchor="center",
        )
        self._status_label.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        # Mic picker — collapsed by default, expands on click and re-collapses on selection.
        self._mic_frame = ctk.CTkFrame(body, fg_color="transparent", height=24)
        self._mic_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._mic_frame.grid_columnconfigure(0, weight=1)
        self._mic_frame.grid_propagate(False)

        self._mic_btn = ctk.CTkButton(
            self._mic_frame,
            text="🎤 (sin micrófono) ▾",
            fg_color="transparent",
            hover_color=_CLR_SURFACE,
            text_color=_CLR_SUBTEXT,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            height=22,
            corner_radius=4,
            command=self._expand_mic_picker,
        )
        self._mic_btn.grid(row=0, column=0, sticky="ew")

        self._mic_combo = ctk.CTkComboBox(
            self._mic_frame,
            values=[],
            font=ctk.CTkFont(family="Segoe UI", size=10),
            height=22,
            command=self._on_mic_chosen,
            state="readonly",
        )
        self._mic_combo.grid(row=0, column=0, sticky="ew")
        self._mic_combo.grid_remove()

        # Compute picker — same collapse/expand pattern as the mic picker.
        self._compute_frame = ctk.CTkFrame(body, fg_color="transparent", height=24)
        self._compute_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._compute_frame.grid_columnconfigure(0, weight=1)
        self._compute_frame.grid_propagate(False)

        self._compute_btn = ctk.CTkButton(
            self._compute_frame,
            text="🖥 Auto ▾",
            fg_color="transparent",
            hover_color=_CLR_SURFACE,
            text_color=_CLR_SUBTEXT,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            height=22,
            corner_radius=4,
            command=self._expand_compute_picker,
        )
        self._compute_btn.grid(row=0, column=0, sticky="ew")

        self._compute_combo = ctk.CTkComboBox(
            self._compute_frame,
            values=list(_COMPUTE_LABELS.keys()),
            font=ctk.CTkFont(family="Segoe UI", size=10),
            height=22,
            command=self._on_compute_chosen,
            state="readonly",
        )
        self._compute_combo.grid(row=0, column=0, sticky="ew")
        self._compute_combo.grid_remove()

        # Transcript area — textbox (selectable, read-only) + Copiar button.
        transcript_frame = ctk.CTkFrame(body, fg_color="transparent")
        transcript_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        transcript_frame.grid_columnconfigure(0, weight=1)
        transcript_frame.grid_rowconfigure(0, weight=1)

        self._transcript_textbox = ctk.CTkTextbox(
            transcript_frame,
            height=70,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=_CLR_SURFACE,
            text_color=_CLR_TEXT,
            border_width=0,
            corner_radius=6,
            wrap="word",
        )
        self._transcript_textbox.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._transcript_textbox.configure(state="disabled")

        self._copy_btn = ctk.CTkButton(
            transcript_frame,
            text="Copiar",
            width=64,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=_CLR_SURFACE,
            hover_color="#3a3a3a",
            text_color=_CLR_SUBTEXT,
            text_color_disabled="#555",
            corner_radius=6,
            state="disabled",
            command=self._on_copy_click,
        )
        self._copy_btn.grid(row=0, column=1, sticky="ns")

        body.grid_rowconfigure(3, weight=1)

        self._record_btn = ctk.CTkButton(
            body,
            text="● Grabar",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=_CLR_IDLE,
            hover_color="#cc3333",
            height=36,
            corner_radius=8,
            command=self._toggle_record,
        )
        self._record_btn.grid(row=4, column=0, sticky="ew")

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _bind_drag(self) -> None:
        for widget in self._drag_handles:
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_motion)

    # Screen coordinates (x_root/y_root) so it doesn't matter which handle got the event.
    def _on_drag_start(self, event) -> None:
        self._drag_dx = event.x_root - self.winfo_x()
        self._drag_dy = event.y_root - self.winfo_y()

    def _on_drag_motion(self, event) -> None:
        x = event.x_root - self._drag_dx
        y = event.y_root - self._drag_dy
        self.geometry(f"+{x}+{y}")

    # ── Hotkey ────────────────────────────────────────────────────────────────

    def _bind_hotkey(self) -> None:
        try:
            import keyboard  # type: ignore[import]
            keyboard.add_hotkey(settings.HOTKEY, self._hotkey_pressed)
        except Exception as exc:
            print(f"[FLUXUS] Hotkey registration failed: {exc}")

    def _hotkey_pressed(self) -> None:
        # keyboard callbacks fire on a background thread — schedule on main thread
        self.after(0, self._toggle_record)

    # ── Record toggle ─────────────────────────────────────────────────────────

    def _toggle_record(self) -> None:
        if self._state == _IDLE:
            self._start_recording()
        elif self._state == _RECORDING:
            self._stop_recording()
        # _PROCESSING: ignore until the pipeline calls set_idle().

    def _start_recording(self) -> None:
        self._set_state(_RECORDING)
        self.clear_transcript()
        self.set_status("Grabando…")
        self._submit(self.on_record_start)

    def _stop_recording(self) -> None:
        self._set_state(_PROCESSING)
        self.set_status("Procesando…")
        self._submit(self.on_record_stop)

    def _set_state(self, state: str) -> None:
        self._state = state
        if state == _IDLE:
            self._record_btn.configure(
                text="● Grabar", fg_color=_CLR_IDLE, hover_color="#cc3333", state="normal"
            )
        elif state == _RECORDING:
            self._record_btn.configure(
                text="■ Detener", fg_color=_CLR_RECORDING, hover_color="#a33030", state="normal"
            )
        else:
            self._record_btn.configure(
                text="… Procesando", fg_color=_CLR_BUSY, state="disabled"
            )

    def _submit(self, callback: Optional[Callable[[], None]]) -> None:
        if callback is None:
            if self._state == _PROCESSING:
                self._set_state(_IDLE)
            return
        self._worker.submit(self._run_callback, callback)

    def _run_callback(self, callback: Callable[[], None]) -> None:
        # Safety net: an uncaught error in the pipeline must never leave the UI stuck.
        try:
            callback()
        except Exception as exc:
            print(f"[FLUXUS] pipeline error: {exc!r}")
            self.notify_error(str(exc) or exc.__class__.__name__)
            self.set_idle()

    def set_idle(self) -> None:
        """Return the record button to idle (thread-safe). Call when processing ends
        or when a recording couldn't start."""
        self.after(0, lambda: self._set_state(_IDLE))

    # ── Mic picker ────────────────────────────────────────────────────────────

    def set_input_devices(
        self,
        devices: list[tuple[int, str]],
        current: Optional[int] = None,
    ) -> None:
        """Populate the mic picker. `devices` is [(index, name), ...]."""
        self._device_labels = {}
        labels: list[str] = []
        for idx, name in devices:
            label = self._unique_label(name, labels)
            self._device_labels[label] = idx
            labels.append(label)

        self._mic_combo.configure(values=labels or [""])

        chosen_label: Optional[str] = None
        if current is not None:
            for label, idx in self._device_labels.items():
                if idx == current:
                    chosen_label = label
                    break
        if chosen_label is None and labels:
            chosen_label = labels[0]

        if chosen_label is not None:
            self._mic_combo.set(chosen_label)
            self._update_mic_btn_label(chosen_label)
        else:
            self._mic_btn.configure(text="🎤 (sin micrófono) ▾")

    @staticmethod
    def _unique_label(name: str, existing: list[str]) -> str:
        # sounddevice can list the same device name twice (different APIs); disambiguate.
        if name not in existing:
            return name
        n = 2
        while f"{name} ({n})" in existing:
            n += 1
        return f"{name} ({n})"

    def _update_mic_btn_label(self, label: str) -> None:
        short = label if len(label) <= 32 else label[:31] + "…"
        self._mic_btn.configure(text=f"🎤 {short} ▾")

    def _expand_mic_picker(self) -> None:
        self._mic_btn.grid_remove()
        self._mic_combo.grid()
        self._mic_combo.focus_set()

    def _on_mic_chosen(self, label: str) -> None:
        self._mic_combo.grid_remove()
        self._mic_btn.grid()
        self._update_mic_btn_label(label)
        idx = self._device_labels.get(label)
        if idx is not None and self.on_device_change:
            self.on_device_change(idx)

    # ── Compute picker ────────────────────────────────────────────────────────

    def set_compute_device(self, choice: str) -> None:
        """Programmatically reflect the active compute mode in the picker.
        choice: 'auto' | 'cuda' | 'cpu'."""
        label = _COMPUTE_REVERSE.get(choice, "Auto")
        self.after(0, lambda: self._render_compute(label))

    def _render_compute(self, label: str) -> None:
        self._compute_combo.set(label)
        self._compute_btn.configure(text=f"🖥 {label} ▾")

    def _expand_compute_picker(self) -> None:
        self._compute_btn.grid_remove()
        self._compute_combo.grid()
        self._compute_combo.focus_set()

    def _on_compute_chosen(self, label: str) -> None:
        self._compute_combo.grid_remove()
        self._compute_btn.grid()
        self._compute_btn.configure(text=f"🖥 {label} ▾")
        choice = _COMPUTE_LABELS.get(label, "auto")
        if self.on_compute_change:
            self.on_compute_change(choice)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, text: str) -> None:
        """Update the status label (thread-safe)."""
        self.after(0, lambda: self._apply_status(text))

    def _apply_status(self, text: str) -> int:
        self._status_seq += 1
        self._status_label.configure(text=text)
        return self._status_seq

    def show_transcript(self, text: str) -> None:
        """Display the transcript in the textbox and enable Copiar (thread-safe)."""
        self.after(0, lambda: self._render_transcript(text))

    def clear_transcript(self) -> None:
        """Clear the transcript textbox and disable Copiar (thread-safe)."""
        self.after(0, lambda: self._render_transcript(""))

    def _render_transcript(self, text: str) -> None:
        self._current_transcript = text
        self._transcript_textbox.configure(state="normal")
        self._transcript_textbox.delete("1.0", "end")
        if text:
            self._transcript_textbox.insert("1.0", text)
        self._transcript_textbox.configure(state="disabled")
        self._copy_btn.configure(state="normal" if text else "disabled")

    def _on_copy_click(self) -> None:
        text = self._current_transcript
        if not text:
            return
        if self.on_copy:
            self.on_copy(text)
        self.set_status("✓ Copiado al portapapeles")

    def notify_done(self, text: str) -> None:
        """Called by the pipeline when transcription is ready."""
        self.show_transcript(text)
        self.set_status("Transcripción lista")

    def notify_error(self, message: str) -> None:
        """Called by the pipeline on any error."""
        self.after(0, lambda: self._show_error(message))

    def _show_error(self, message: str) -> None:
        seq = self._apply_status(f"✗ {message}")

        def reset() -> None:
            # Only clear our own error, and only while idle — never overwrite
            # "Grabando…" or a newer message that arrived in the meantime.
            if self._status_seq == seq and self._state == _IDLE:
                self._apply_status("Listo")

        self.after(_ERROR_RESET_MS, reset)

    def destroy(self) -> None:
        try:
            import keyboard  # type: ignore[import]
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._worker.shutdown(wait=False, cancel_futures=True)
        super().destroy()

    def run(self) -> None:
        """Start the Tkinter main loop."""
        self.mainloop()
