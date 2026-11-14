"""
FLUXUS — entry point.
Wires together all pipeline layers and launches the UI widget.
"""

import threading

from config import settings  # noqa: F401 — ensures env vars are loaded first


_MIN_AUDIO_SECONDS = 0.3


def main() -> None:
    from src.clipboard import ClipboardError, Delivery, ForegroundTracker, copy_text, deliver
    from src.ui import App
    from src.audio import Recorder, default_input_device, list_input_devices
    from src.stt import create_engine

    app = App()
    initial_device = default_input_device()
    recorder = Recorder(device=initial_device)
    stt = create_engine()

    devices = list_input_devices()
    app.set_input_devices(devices, current=initial_device)
    app.on_device_change = recorder.set_device
    app.set_compute_device(stt.user_choice)

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
    main()
