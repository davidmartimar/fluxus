"""
FLUXUS — entry point.
Initialises configuration and launches the UI widget.
"""

from config import settings  # noqa: F401 — ensures env vars are loaded first


def main() -> None:
    # UI import deferred so config is always loaded before CustomTkinter initialises
    from src.ui import App  # type: ignore[import]
    app = App()
    app.run()


if __name__ == "__main__":
    main()
