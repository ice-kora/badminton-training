"""Select pose extractor backend."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings
from app.services.pose.base import PoseExtractor
from app.services.pose.fake_extractor import FakePoseExtractor
from app.services.pose.mediapipe_extractor import (
    MediaPipePoseExtractor,
    mediapipe_available,
)
from app.services.pose.null_extractor import NullPoseExtractor

logger = logging.getLogger(__name__)


def get_pose_extractor(prefer: str | None = None) -> PoseExtractor:
    """
    prefer / settings.pose_extractor:
      auto | mediapipe | fake | null
    """
    settings = get_settings()
    mode = (prefer or settings.pose_extractor or "auto").strip().lower()
    model_path = Path(settings.pose_model_path)

    if mode == "fake":
        return FakePoseExtractor()
    if mode == "null":
        return NullPoseExtractor()
    if mode == "mediapipe":
        if not mediapipe_available():
            raise RuntimeError("POSE_EXTRACTOR=mediapipe but mediapipe is not importable")
        return MediaPipePoseExtractor(model_path)

    # auto
    if mediapipe_available():
        try:
            return MediaPipePoseExtractor(model_path)
        except Exception as exc:  # pragma: no cover
            logger.warning("MediaPipePoseExtractor init failed: %s", exc)
    return NullPoseExtractor()
