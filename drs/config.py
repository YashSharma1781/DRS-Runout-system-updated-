"""Central configuration for the Third Umpire DRS application."""

from __future__ import annotations

from dataclasses import dataclass

BGR = tuple[int, int, int]


@dataclass(frozen=True)
class Config:
    # Window
    title: str = "Third Umpire - Decision Review System"
    initial_width: int = 960
    initial_height: int = 540
    min_width: int = 640
    min_height: int = 420

    # Playback
    speeds: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0, 2.0)
    default_speed: float = 1.0
    step_small: int = 1
    step_large: int = 25

    # Review sequence timing (milliseconds)
    pending_ms: int = 2500
    dot_interval_ms: int = 400

    # Colours (BGR, as used by OpenCV)
    background: BGR = (22, 22, 22)
    pending_color: BGR = (0, 165, 255)
    out_color: BGR = (40, 40, 215)
    not_out_color: BGR = (60, 160, 40)
    text_color: BGR = (255, 255, 255)

    video_filetypes: tuple[tuple[str, str], ...] = (
        ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
        ("All files", "*.*"),
    )


CONFIG = Config()