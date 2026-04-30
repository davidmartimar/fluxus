"""
Main application window for FLUXUS.

A borderless, always-on-top floating widget built with CustomTkinter.
Draggable via click-and-drag on the window body.
The record button toggles between idle and recording states.
A collapsible mic picker shows the active input device and lets the user pick another.
External layers (audio, STT, etc.) wire in via the callback properties:
    app.on_record_start  — called when recording begins
    app.on_record_stop   — called when recording stops; receives no args
    app.on_device_change — called with the new device index when the user picks a mic
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from config import settings

_ICON_PATH = Path(__file__).parent / "fluxus_icon.png"

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Palette ──────────────────────────────────────────────────────────────────
_CLR_BG = "#1a1a1a"
_CLR_SURFACE = "#2b2b2b"
_CLR_IDLE = "#FF4444"
_CLR_RECORDING = "#bf3a3a"
_CLR_TEXT = "#e0e0e0"
_CLR_SUBTEXT = "#888888"


class App(ctk.CTk):
    """FLUXUS floating widget."""

    def __init__(self) -> None:
        super().__init__(fg_color=_CLR_BG)

        # ── Callbacks (wired by pipeline in main.py) ─────────────────────────
        self.on_record_start: Optional[Callable[[], None]] = None
        self.on_record_stop: Optional[Callable[[], None]] = None
        self.on_device_change: Optional[Callable[[int], None]] = None

        # ── Internal state ────────────────────────────────────────────────────
        self._recording = False
        self._drag_x = 0
        self._drag_y = 0
        self._device_labels: dict[str, int] = {}

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
        self.geometry("300x160")
        self.resizable(False, False)
        self.overrideredirect(True)           # borderless
        self.wm_attributes("-topmost", True)  # always-on-top
        self.wm_attributes("-alpha", settings.WINDOW_OPACITY)
        # Taskbar / Alt-Tab icon (requires a real .ico or .png via iconphoto)
        if _ICON_PATH.exists():
            from PIL import ImageTk
            _raw = Image.open(_ICON_PATH).resize((32, 32))
            self._tk_icon = ImageTk.PhotoImage(_raw)
            self.iconphoto(True, self._tk_icon)
        self._center_window()

    def _center_window(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 300, 160
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

        ctk.CTkLabel(
            title_bar,
            text=" FLUXUS",
            image=self._icon_img_small,
            compound="left",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=_CLR_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(6, 0), pady=4)

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
        self._record_btn.grid(row=2, column=0, sticky="ew")

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _bind_drag(self) -> None:
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event) -> None:
        x = self.winfo_x() + (event.x - self._drag_x)
        y = self.winfo_y() + (event.y - self._drag_y)
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
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self._recording = True
        self._record_btn.configure(
            text="■ Detener",
            fg_color=_CLR_RECORDING,
            hover_color="#a33030",
        )
        self.set_status("Grabando…")
        if self.on_record_start:
            threading.Thread(target=self.on_record_start, daemon=True).start()

    def _stop_recording(self) -> None:
        self._recording = False
        self._record_btn.configure(
            text="● Grabar",
            fg_color=_CLR_IDLE,
            hover_color="#cc3333",
        )
        self.set_status("Procesando…")
        if self.on_record_stop:
            threading.Thread(target=self.on_record_stop, daemon=True).start()

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

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, text: str) -> None:
        """Update the status label (thread-safe)."""
        self.after(0, lambda: self._status_label.configure(text=text))

    def notify_done(self, text: str) -> None:
        """Called by the pipeline when text is ready and copied to clipboard."""
        self.set_status(f"✓ Copiado — {text[:40]}{'…' if len(text) > 40 else ''}")
        self.after(4000, lambda: self.set_status("Listo"))

    def notify_error(self, message: str) -> None:
        """Called by the pipeline on any error."""
        self.set_status(f"✗ {message}")
        self.after(4000, lambda: self.set_status("Listo"))

    def run(self) -> None:
        """Start the Tkinter main loop."""
        self.mainloop()
