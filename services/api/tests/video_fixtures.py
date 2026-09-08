"""Generate tiny synthetic videos for precheck tests (OpenCV, no pose)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def write_solid_video(
    path: Path,
    *,
    width: int,
    height: int,
    fps: float = 10.0,
    duration_sec: float = 8.0,
    color_bgr: tuple[int, int, int] = (180, 180, 180),
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"VideoWriter failed to open {path}")
    n = max(1, int(round(duration_sec * fps)))
    frame = np.full((height, width, 3), color_bgr, dtype=np.uint8)
    # Slight temporal variation so codecs keep frames
    for i in range(n):
        f = frame.copy()
        cv2.putText(
            f,
            str(i),
            (10, min(height - 10, 40)),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        writer.write(f)
    writer.release()
    return path
