"""Pure image-rendering helpers: letterboxing, banners and the splash screen.

Nothing here touches Tkinter, so these functions are easy to test.
"""

from __future__ import annotations

from enum import Enum, auto

import cv2
import numpy as np

from .config import BGR, CONFIG, Config

FONT = cv2.FONT_HERSHEY_DUPLEX


class ReviewState(Enum):
    IDLE = auto()
    PENDING = auto()
    RESULT = auto()


class Verdict(Enum):
    OUT = "OUT"
    NOT_OUT = "NOT OUT"


def letterbox(frame: np.ndarray, width: int, height: int, fill: BGR) -> np.ndarray:
    """Scale ``frame`` to fit inside width x height, preserving aspect ratio."""
    h, w = frame.shape[:2]
    scale = min(width / w, height / h)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(frame, (new_w, new_h), interpolation=interp)

    top = (height - new_h) // 2
    left = (width - new_w) // 2
    return cv2.copyMakeBorder(
        resized, top, height - new_h - top, left, width - new_w - left,
        cv2.BORDER_CONSTANT, value=fill,
    )


def _text_scale(text: str, max_w: float, max_h: float) -> float:
    (tw, th), _ = cv2.getTextSize(text, FONT, 1.0, 1)
    return max(0.2, min(max_w / tw, max_h / th))


def _draw_centered(img: np.ndarray, text: str, cy: int, scale: float,
                   color: BGR, visible: str | None = None) -> None:
    """Draw text centred on (width/2, cy). ``visible`` is a prefix of ``text``
    that is actually drawn, while ``text`` is used to keep the layout stable."""
    thickness = max(1, round(scale * 2))
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, thickness)
    x = (img.shape[1] - tw) // 2
    y = cy + th // 2
    cv2.putText(img, visible if visible is not None else text, (x, y), FONT,
                scale, color, thickness, cv2.LINE_AA)


def _blend_rect(img: np.ndarray, p1: tuple[int, int], p2: tuple[int, int],
                color: BGR, alpha: float) -> None:
    layer = img.copy()
    cv2.rectangle(layer, p1, p2, color, -1)
    cv2.addWeighted(layer, alpha, img, 1 - alpha, 0, dst=img)


def _banner(img: np.ndarray, text: str, color: BGR, cfg: Config,
            dots: int | None = None) -> None:
    h, w = img.shape[:2]
    band_h = max(70, h // 5)
    y1 = (h - band_h) // 2
    y2 = y1 + band_h
    _blend_rect(img, (0, y1), (w, y2), color, 0.85)
    cv2.line(img, (0, y1), (w, y1), cfg.text_color, 2, cv2.LINE_AA)
    cv2.line(img, (0, y2), (w, y2), cfg.text_color, 2, cv2.LINE_AA)

    if dots is None:
        scale = _text_scale(text, w * 0.8, band_h * 0.5)
        _draw_centered(img, text, h // 2, scale, cfg.text_color)
    else:
        layout = text + "..."
        scale = _text_scale(layout, w * 0.8, band_h * 0.5)
        _draw_centered(img, layout, h // 2, scale, cfg.text_color,
                       visible=text + "." * dots)


def _badge(img: np.ndarray, cfg: Config) -> None:
    label = "THIRD UMPIRE REVIEW"
    scale = max(0.4, img.shape[1] / 1600)
    thickness = max(1, round(scale * 2))
    (tw, th), _ = cv2.getTextSize(label, FONT, scale, thickness)
    pad = 10
    _blend_rect(img, (12, 12), (12 + tw + 2 * pad, 12 + th + 2 * pad), (0, 0, 0), 0.65)
    cv2.putText(img, label, (12 + pad, 12 + pad + th), FONT, scale,
                cfg.text_color, thickness, cv2.LINE_AA)


def apply_review_overlay(img: np.ndarray, state: ReviewState, verdict: Verdict | None,
                         dots: int = 0, cfg: Config = CONFIG) -> np.ndarray:
    """Draw the review banner onto ``img`` (in place) and return it."""
    if state is ReviewState.IDLE:
        return img

    _badge(img, cfg)
    if state is ReviewState.PENDING:
        _banner(img, "DECISION PENDING", cfg.pending_color, cfg, dots=dots % 4)
    elif verdict is Verdict.OUT:
        _banner(img, "OUT", cfg.out_color, cfg)
    elif verdict is Verdict.NOT_OUT:
        _banner(img, "NOT OUT", cfg.not_out_color, cfg)
    return img


def make_splash(width: int, height: int, cfg: Config = CONFIG) -> np.ndarray:
    """Start-up screen shown until a video is loaded."""
    img = np.full((height, width, 3), cfg.background, dtype=np.uint8)
    title_scale = _text_scale("THIRD UMPIRE", width * 0.6, height * 0.12)
    _draw_centered(img, "THIRD UMPIRE", int(height * 0.38), title_scale, cfg.text_color)
    _draw_centered(img, "DECISION REVIEW SYSTEM", int(height * 0.50),
                   title_scale * 0.55, cfg.pending_color)
    hint_scale = _text_scale("Press Ctrl+O to open a video", width * 0.5, height * 0.05)
    _draw_centered(img, "Press Ctrl+O to open a video", int(height * 0.68),
                   hint_scale, (170, 170, 170))
    return img