"""Null extractor when MediaPipe is unavailable."""
from __future__ import annotations

from pathlib import Path

from app.services.pose.base import PoseExtractResult


class PoseExtractorUnavailable(RuntimeError):
    """Raised when no real pose backend can run."""


class NullPoseExtractor:
    name = "null"

    def extract(
        self,
        video_path: Path,
        *,
        max_seconds: float = 60.0,
        sample_stride: int = 2,
    ) -> PoseExtractResult:
        raise PoseExtractorUnavailable(
            f"MediaPipe Pose unavailable; cannot extract keypoints from {video_path}"
        )
