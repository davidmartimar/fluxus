"""
FLUXUS — entry point.
Wires together all pipeline layers and launches the UI widget.
"""

import threading

from config import settings  # noqa: F401 — ensures env vars are loaded first


_MIN_AUDIO_SECONDS = 0.3


def main() -> None:
    from src.ui import App
    from src.audio import Recorder
    from src.stt import create_engine

    app = App()
    recorder = Recorder()
    stt = create_engine()

    # Warm up the model in the background so the first transcribe doesn't pay model load cost.
    def warmup() -> None:
        app.set_status("Cargando modelo…")
        try:
            stt.warmup()
            app.set_status("Listo")
        except Exception as exc:
            app.notify_error(f"Modelo no cargado: {exc}")

    threading.Thread(target=warmup, daemon=True).start()

    def on_record_start() -> None:
        recorder.start()

    def on_record_stop() -> None:
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

            if text:
                app.notify_done(text)
            else:
                app.notify_error("Sin texto")
        finally:
            audio.clear()

    app.on_record_start = on_record_start
    app.on_record_stop = on_record_stop

    app.run()


if __name__ == "__main__":
    main()
