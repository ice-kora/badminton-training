"""MediaPipe Tasks PoseLandmarker extractor (keypoints only)."""
from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.services.pose.base import PoseExtractResult
from app.services.pose.landmarks import POSE_LANDMARK_NAMES
from app.services.pose.null_extractor import PoseExtractorUnavailable

logger = logging.getLogger(__name__)

# Official MediaPipe lite pose landmarker bundle
DEFAULT_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)


def ensure_pose_model(model_path: Path, url: str = DEFAULT_MODEL_URL) -> Path:
    """Download pose landmarker .task if missing."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path
    logger.info("Downloading MediaPipe pose model to %s", model_path)
    tmp = model_path.with_suffix(model_path.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, str(tmp))
        tmp.replace(model_path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    return model_path


def mediapipe_available() -> bool:
    try:
        from mediapipe.tasks.python import vision  # noqa: F401

        return True
    except Exception:
        return False


class MediaPipePoseExtractor:
    name = "mediapipe_pose"

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)

    def extract(
        self,
        video_path: Path,
        *,
        max_seconds: float = 60.0,
        sample_stride: int = 2,
    ) -> PoseExtractResult:
        try:
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core import base_options as mp_base
            from mediapipe import Image as MpImage
            from mediapipe import ImageFormat
        except Exception as exc:  # pragma: no cover
            raise PoseExtractorUnavailable(
                f"mediapipe import failed: {exc}"
            ) from exc

        ensure_pose_model(self.model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=mp_base.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        landmarker = vision.PoseLandmarker.create_from_options(options)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            landmarker.close()
            raise RuntimeError(f"Cannot open video: {video_path}")

        frames_out: list[dict] = []
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 10.0)
            if fps <= 0:
                fps = 10.0
            max_frames_by_time = int(max_seconds * fps)
            idx = 0
            while True:
                ok, frame_bgr = cap.read()
                if not ok:
                    break
                if idx >= max_frames_by_time:
                    break
                if idx % max(1, sample_stride) == 0:
                    t_ms = int(round(1000.0 * idx / fps))
                    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    mp_image = MpImage(image_format=ImageFormat.SRGB, data=np.asarray(rgb))
                    result = landmarker.detect_for_video(mp_image, t_ms)
                    landmarks = _pack_landmarks(result)
                    frames_out.append(
                        {
                            "frame_index": idx,
                            "timestamp_ms": t_ms,
                            "landmarks": landmarks,
                        }
                    )
                idx += 1
        finally:
            cap.release()
            landmarker.close()

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


def _pack_landmarks(result) -> Optional[list[dict]]:
    poses = getattr(result, "pose_landmarks", None) or []
    if not poses:
        return None
    lm_list = poses[0]
    out: list[dict] = []
    for i, name in enumerate(POSE_LANDMARK_NAMES):
        if i >= len(lm_list):
            break
        lm = lm_list[i]
        out.append(
            {
                "name": name,
                "x": float(getattr(lm, "x", 0.0)),
                "y": float(getattr(lm, "y", 0.0)),
                "z": float(getattr(lm, "z", 0.0)),
                "visibility": float(
                    getattr(lm, "visibility", getattr(lm, "presence", 0.0)) or 0.0
                ),
            }
        )
    return out
