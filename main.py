"""Entry point:  python main.py [path/to/video.mp4] [--debug]"""

from __future__ import annotations

import argparse
import logging
import tkinter as tk
from pathlib import Path

from drs.app import DRSApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Third Umpire Decision Review System")
    parser.add_argument("video", nargs="?", type=Path, help="video file to load on start-up")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    root = tk.Tk()
    DRSApp(root, args.video)
    root.mainloop()


if __name__ == "__main__":
    main()