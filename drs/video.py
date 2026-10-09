"""Thin, safe wrapper around ``cv2.VideoCapture``."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


class VideoError(RuntimeError):
    """Raised when a video cannot be opened or decoded."""


class VideoSource:
    """Random-access video reader that avoids unnecessary seeks."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise VideoError(f"File not found: {self.path}")

        self._cap = cv2.VideoCapture(str(self.path))
        if not self._cap.isOpened():
            raise VideoError(f"Could not open video: {self.path}")

        count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if count <= 0:
            self._cap.release()
            raise VideoError("Video contains no readable frames.")

        fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.frame_count: int = count
        self.fps: float = fps if fps and fps > 0 else 30.0
        self.index: int = -1      # index of the frame most recently returned
        self._next: int = 0       # index the decoder will return on the next read
        log.info("Opened %s (%d frames @ %.2f fps)", self.path.name, count, self.fps)

    @property
    def frame_interval_ms(self) -> float:
        return 1000.0 / self.fps

    def read_at(self, index: int) -> np.ndarray | None:
        """Return the BGR frame at ``index`` (clamped to the valid range)."""
        index = max(0, min(index, self.frame_count - 1))
        if index != self._next:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)

        ok, frame = self._cap.read()
        if not ok or frame is None:
            log.warning("Failed to read frame %d", index)
            self._next = -1       # force a seek on the next read
            return None

        self.index = index
        self._next = index + 1
        return frame

    def release(self) -> None:
        self._cap.release()

    def __enter__(self) -> "VideoSource":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()