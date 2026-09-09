"""2D skeleton preview from stored keypoints — visualization only, no scoring."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from app.services.pose.landmarks import POSE_LANDMARK_NAMES, bone_edges

PREVIEW_NOTICE = "仅关键点可视化，非评分"


class PosePreviewError(Exception):
    """Base for preview failures."""


class PoseNotExtracted(PosePreviewError):
    """No PoseAnalysis / keypoint file."""


class FrameOutOfRange(PosePreviewError):
    """Requested scrub index invalid."""


def load_keypoint_payload(keypoint_path: str | Path) -> dict[str, Any]:
    path = Path(keypoint_path)
    if not path.is_file():
        raise PoseNotExtracted(f"keypoint file missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PosePreviewError(f"invalid keypoint json: {exc}") from exc
    if not isinstance(data, dict):
        raise PosePreviewError("keypoint json must be an object")
    return data


def _frame_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    frames = payload.get("frames") or []
    if not isinstance(frames, list):
        raise PosePreviewError("frames must be a list")
    return frames


def build_preview_json(
    *,
    video_id: int,
    keypoint_path: str | Path,
    frame: int = 0,
    landmark_count: Optional[int] = None,
    extractor: Optional[str] = None,
) -> dict[str, Any]:
    """
    Return one stored frame's normalized landmarks + MediaPipe bone edges.

    `frame` is the scrub index into the stored frames array (0 .. frame_count-1),
    not necessarily the source video frame_index (which may skip by stride).
    """
    if frame < 0:
        raise FrameOutOfRange("frame must be >= 0")
    payload = load_keypoint_payload(keypoint_path)
    frames = _frame_list(payload)
    if not frames:
        raise PoseNotExtracted("no frames in keypoint file")
    if frame >= len(frames):
        raise FrameOutOfRange(
            f"frame {frame} out of range (0..{len(frames) - 1})"
        )

    entry = frames[frame]
    landmarks = entry.get("landmarks") or []
    names = payload.get("landmark_names") or list(POSE_LANDMARK_NAMES)
    n = landmark_count or len(landmarks) or len(names)
    bones = bone_edges(landmark_count=n)

    return {
        "video_id": video_id,
        "frame": frame,
        "frame_count": len(frames),
        "source_frame_index": entry.get("frame_index"),
        "timestamp_ms": entry.get("timestamp_ms"),
        "landmarks": landmarks,
        "landmark_names": names,
        "landmark_count": n,
        "bones": bones,
        "normalized": True,
        "extractor": extractor or payload.get("extractor"),
        "topology": "mediapipe_pose_33",
        "mapping_note": (
            "FakePoseExtractor and MediaPipePoseExtractor both store 33 "
            "MediaPipe landmarks 1:1; bone list is full POSE_CONNECTIONS."
        ),
        "notice": PREVIEW_NOTICE,
    }


def render_preview_png(
    *,
    video_id: int,
    keypoint_path: str | Path,
    frame: int = 0,
    width: int = 360,
    height: int = 640,
    landmark_count: Optional[int] = None,
) -> bytes:
    """Debug PNG: draw skeleton on dark canvas from normalized landmarks."""
    preview = build_preview_json(
        video_id=video_id,
        keypoint_path=keypoint_path,
        frame=frame,
        landmark_count=landmark_count,
    )
    landmarks = preview["landmarks"]
    bones = preview["bones"]

    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (24, 24, 32)

    pts: list[Optional[tuple[int, int]]] = []
    for lm in landmarks:
        if not isinstance(lm, dict):
            pts.append(None)
            continue
        x = lm.get("x")
        y = lm.get("y")
        vis = lm.get("visibility", 1.0)
        if x is None or y is None or (vis is not None and float(vis) < 0.1):
            pts.append(None)
            continue
        px = int(round(float(x) * (width - 1)))
        py = int(round(float(y) * (height - 1)))
        pts.append((max(0, min(width - 1, px)), max(0, min(height - 1, py))))

    bone_color = (80, 200, 120)
    joint_color = (220, 220, 80)
    for edge in bones:
        a = edge["from"]
        b = edge["to"]
        if a >= len(pts) or b >= len(pts):
            continue
        pa, pb = pts[a], pts[b]
        if pa is None or pb is None:
            continue
        cv2.line(img, pa, pb, bone_color, 2, lineType=cv2.LINE_AA)

    for p in pts:
        if p is None:
            continue
        cv2.circle(img, p, 4, joint_color, -1, lineType=cv2.LINE_AA)

    label = f"v{video_id} f{frame}/{preview['frame_count'] - 1}  {PREVIEW_NOTICE}"
    cv2.putText(
        img,
        label,
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (180, 180, 200),
        1,
        cv2.LINE_AA,
    )

    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise PosePreviewError("failed to encode PNG")
    return buf.tobytes()
