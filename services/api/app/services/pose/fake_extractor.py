"""Deterministic fake extractor for pytest — keypoints only, no scores."""
from __future__ import annotations

from pathlib import Path

import cv2

from app.services.pose.base import PoseExtractResult
from app.services.pose.landmarks import POSE_LANDMARK_NAMES


class FakePoseExtractor:
    """Writes synthetic landmarks; never claims correctness or scores."""

    name = "fake_pose"

    def extract(
        self,
        video_path: Path,
        *,
        max_seconds: float = 60.0,
        sample_stride: int = 2,
    ) -> PoseExtractResult:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 10.0)
            if fps <= 0:
                fps = 10.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            max_frames_by_time = int(max_seconds * fps)
            frames_out: list[dict] = []
            idx = 0
            while True:
                ok, _frame = cap.read()
                if not ok:
                    break
                if idx >= max_frames_by_time:
                    break
                if idx % max(1, sample_stride) == 0:
                    t_ms = int(round(1000.0 * idx / fps))
                    landmarks = []
                    for li, name in enumerate(POSE_LANDMARK_NAMES):
                        landmarks.append(
                            {
                                "name": name,
                                "x": round((li % 11) / 10.0, 4),
                                "y": round(((li * 3 + idx) % 17) / 16.0, 4),
                                "z": 0.0,
                                "visibility": 1.0,
                            }
                        )
                    frames_out.append(
                        {
                            "frame_index": idx,
                            "timestamp_ms": t_ms,
                            "landmarks": landmarks,
                        }
                    )
                idx += 1
                if total > 0 and idx >= total:
                    break
        finally:
            cap.release()

        processed = (frames_out[-1]["timestamp_ms"] / 1000.0) if frames_out else 0.0
        return PoseExtractResult(
            frame_count=len(frames_out),
            fps=fps,
            landmark_names=list(POSE_LANDMARK_NAMES),
            frames=frames_out,
            extractor=self.name,
            sample_stride=sample_stride,
            max_seconds=max_seconds,
            processed_seconds=processed,
            source_path=str(video_path),
        )
