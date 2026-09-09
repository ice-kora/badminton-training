"""Pose extractor interface — keypoints only, never scores."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol


@dataclass
class PoseExtractResult:
    """Raw keypoint sequence metadata. No scores / correctness fields."""

    frame_count: int
    fps: float
    landmark_names: list[str]
    frames: list[dict[str, Any]]
    extractor: str
    sample_stride: int = 1
    max_seconds: float = 60.0
    processed_seconds: float = 0.0
    source_path: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self, *, video_id: int) -> dict[str, Any]:
        return {
            "video_id": video_id,
            "extractor": self.extractor,
            "fps": self.fps,
            "frame_stride": self.sample_stride,
            "max_seconds": self.max_seconds,
            "processed_seconds": self.processed_seconds,
            "landmark_names": self.landmark_names,
            "frame_count": self.frame_count,
            "frames": self.frames,
            "notice": "keypoints_only_no_scoring",
        }


class PoseExtractor(Protocol):
    name: str

    def extract(
        self,
        video_path: Path,
        *,
        max_seconds: float = 60.0,
        sample_stride: int = 2,
    ) -> PoseExtractResult:
        """Extract pose landmarks; must not compute scores or angles vs benchmarks."""
        ...
