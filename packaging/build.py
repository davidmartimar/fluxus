"""
Build the Windows distributable with PyInstaller.

    .venv\\Scripts\\python.exe packaging\\build.py          # → dist\\FLUXUS\\FLUXUS.exe
    .venv\\Scripts\\python.exe packaging\\build.py --zip    # also dist\\FLUXUS-<date>.zip

One-folder build (not --onefile): onefile would unpack ~hundreds of MB of
ctranslate2/onnxruntime into %TEMP% on every launch, making startup slow.

Not bundled on purpose:
  - Whisper models: downloaded on first run to the Hugging Face cache
    (%USERPROFILE%\\.cache\\huggingface), shared with the dev setup.
  - CUDA 12 runtime / cuDNN: picked up from PATH like in dev; without them
    "Auto" falls back to CPU.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "FLUXUS"


def _data(src: str, dest: str) -> list[str]:
    return ["--add-data", f"{ROOT / src}{os.pathsep}{dest}"]


def pyinstaller_args() -> list[str]:
    return [
        str(ROOT / "main.py"),
        "--name", APP_NAME,
        "--onedir",
        "--windowed",             # no console window
        "--noconfirm",
        "--clean",
        "--icon", str(ROOT / "src" / "ui" / "fluxus_icon.ico"),
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),  # keep the generated .spec out of the repo root
        *_data("src/ui/fluxus_icon.png", "src/ui"),
        *_data("src/ui/fluxus_icon.ico", "src/ui"),
        # CustomTkinter themes/fonts are data files, not imports.
        "--collect-data", "customtkinter",
        # Silero VAD model (assets/silero_vad_v6.onnx).
        "--collect-data", "faster_whisper",
        # Native inference libraries.
        "--collect-binaries", "ctranslate2",
        # faster-whisper imports onnxruntime lazily inside the VAD function,
        # so PyInstaller's import scan can't see it.
        "--hidden-import", "onnxruntime",
        "--collect-binaries", "onnxruntime",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", action="store_true", help="also create a .zip of the build")
    args = parser.parse_args()

    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        print("PyInstaller not installed: pip install -r requirements-dev.txt", file=sys.stderr)
        return 1

    pyinstaller.run(pyinstaller_args())

    out = DIST / APP_NAME
    # Ship the config template next to the exe; the user copies it to .env.
    shutil.copy2(ROOT / ".env.example", out / ".env.example")
    print(f"\nBuilt: {out / (APP_NAME + '.exe')}")

    if args.zip:
        stamp = dt.date.today().strftime("%Y%m%d")
        archive = shutil.make_archive(str(DIST / f"{APP_NAME}-{stamp}"), "zip", DIST, APP_NAME)
        print(f"Zip:   {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
