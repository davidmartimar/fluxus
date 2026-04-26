"""
FLUXUS — entry point.
Wires together all pipeline layers and launches the UI widget.
"""

from config import settings  # noqa: F401 — ensures env vars are loaded first


def main() -> None:
    from src.ui import App
    from src.audio import Recorder

    app = App()
    recorder = Recorder()

    def on_record_start() -> None:
        recorder.start()

    def on_record_stop() -> None:
        audio = recorder.stop()
        # Subsequent PRs will pass `audio` to the STT layer here.
        # For now, report duration so the pipeline is visibly working.
        app.set_status(f"Audio capturado — {audio.duration_seconds():.1f}s")
        audio.clear()

    app.on_record_start = on_record_start
    app.on_record_stop = on_record_stop

    app.run()


if __name__ == "__main__":
    main()
