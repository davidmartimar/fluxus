"""
FLUXUS — entry point.
Wires together all pipeline layers and launches the UI widget.
"""

import sys
import threading

from config import settings  # noqa: F401 — ensures env vars are loaded first
from src import runtime

# Before anything else imports libraries that write to stdout/stderr.
runtime.setup_logging()


_MIN_AUDIO_SECONDS = 0.3


def main() -> None:
    from src.clipboard import ClipboardError, Delivery, ForegroundTracker, copy_text, deliver
    from src.ui import App
    from src.audio import Recorder, default_input_device, list_input_devices
    from src.stt import create_engine
    from src.prefs import Prefs

    # Choices made in the UI last time; they override .env defaults.
    prefs = Prefs()

    app = App()
    devices = list_input_devices()
    device_names = dict(devices)

    # Mic: saved by name (indices change when devices are plugged/unplugged).
    initial_device = default_input_device()
    saved_mic = prefs.get("mic_name")
    if saved_mic:
        initial_device = next((i for i, n in devices if n == saved_mic), initial_device)
    recorder = Recorder(device=initial_device)
    stt = create_engine()

    saved_compute = prefs.get("compute")
    if saved_compute and saved_compute != stt.user_choice and hasattr(stt, "set_device"):
        try:
            stt.set_device(saved_compute)
        except Exception as exc:
            print(f"[FLUXUS] saved compute '{saved_compute}' not applied: {exc}")

    app.set_input_devices(devices, current=initial_device)
    app.set_compute_device(stt.user_choice)

    def change_device(index: int) -> None:
        recorder.set_device(index)
        prefs.update(mic_name=device_names.get(index))

    app.on_device_change = change_device
    app.on_ui_change = lambda changes: prefs.update(**changes)
    app.apply_ui_prefs(
        auto_paste=prefs.get("auto_paste"),
        compact=prefs.get("compact"),
        full_pos=prefs.get("full_pos"),
        compact_pos=prefs.get("compact_pos"),
    )

    # Remembers the window you were in, so the transcript can be pasted back there.
    focus = ForegroundTracker()
    focus.start()
    paste_target: list[int | None] = [None]  # set per recording, read by on_record_stop

    def copy_to_clipboard(text: str) -> None:
        try:
            copy_text(text)
        except ClipboardError as exc:
            app.notify_error(f"Copia fallida: {exc}")

    app.on_copy = copy_to_clipboard

    # Warm up the model in the background so the first transcribe doesn't pay model load cost.
    def warmup() -> None:
        model = getattr(stt, "model_name", "modelo")
        app.set_status(f"Cargando {model}…")
        try:
            stt.warmup()
            # Re-read after warmup: auto mode may have fallen back from CUDA to CPU.
            device = getattr(stt, "device", "?")
            model = getattr(stt, "model_name", "")
            app.set_status(f"Listo ({device.upper()} · {model})" if model else f"Listo ({device.upper()})")
        except Exception as exc:
            app.notify_error(f"Modelo no cargado: {exc}")

    def change_compute(choice: str) -> None:
        try:
            stt.set_device(choice)
        except Exception as exc:
            app.notify_error(f"Cambio de compute fallido: {exc}")
            return
        prefs.update(compute=choice)
        threading.Thread(target=warmup, daemon=True).start()

    app.on_compute_change = change_compute

    threading.Thread(target=warmup, daemon=True).start()

    # Both callbacks run in order on the UI's single pipeline worker.
    def on_record_start() -> None:
        paste_target[0] = focus.current_target()
        try:
            recorder.start()
        except Exception as exc:
            app.notify_error(f"Micrófono no disponible: {exc}")
            app.set_idle()

    def on_record_stop() -> None:
        if not recorder.is_recording:
            # start() failed and already reported the error.
            app.set_idle()
            return

        audio = recorder.stop()
        try:
            if audio.duration_seconds() < _MIN_AUDIO_SECONDS:
                app.notify_error("Audio demasiado corto")
                return

            app.set_status("Transcribiendo…")
            try:
                text = stt.transcribe(audio)
            except Exception as exc:
                app.notify_error(str(exc))
                return

            if not text:
                app.notify_error("Sin texto")
                return

            app.notify_done(text)
            try:
                result = deliver(text, paste_target[0], auto_paste=app.auto_paste)
            except ClipboardError as exc:
                app.notify_error(f"Copia fallida: {exc}")
                return
            app.set_status(
                "✓ Pegado" if result is Delivery.PASTED else "✓ Copiado al portapapeles"
            )
        finally:
            audio.clear()
            app.set_idle()

    app.on_record_start = on_record_start
    app.on_record_stop = on_record_stop

    app.run()


if __name__ == "__main__":
    if not runtime.acquire_single_instance():
        runtime.show_error("FLUXUS", "FLUXUS ya está abierto.")
        sys.exit(0)
    try:
        main()
    except Exception as exc:
        runtime.report_fatal(exc)
        sys.exit(1)
