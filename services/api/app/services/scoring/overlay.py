"""Standard vs user skeleton overlay — visualization only (非评分叠加)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.services.benchmark_pkg import SYNTHETIC_BANNER, benchmark_kind_for_status
from app.services.pose.landmarks import POSE_LANDMARK_NAMES, bone_edges
from app.services.pose.preview import (
    FrameOutOfRange,
    PoseNotExtracted,
    PosePreviewError,
    load_keypoint_payload,
)
from app.services.scoring.stage_timeline import segment_at_frame, timeline_from_package

OVERLAY_NOTICE = "非评分叠加"
STANDARD_COLOR = "#50c878"  # green
USER_COLOR = "#4da3ff"  # blue


def _map_scrub(frame: int, src_count: int, dst_count: int) -> int:
    if dst_count <= 1 or src_count <= 1:
        return 0
    frame = max(0, min(frame, src_count - 1))
    return int(round(frame * (dst_count - 1) / (src_count - 1)))


def generate_synthetic_template_sequence(
    *,
    frame_count: int,
    duration_ms: int = 600,
) -> dict[str, Any]:
    """Simple stick-figure morph sequence when package has no template."""
    n = max(1, int(frame_count))
    frames: list[dict[str, Any]] = []
    for i in range(n):
        frac = i / max(1, n - 1)
        t_ms = int(round(duration_ms * frac))
        landmarks = []
        for li, name in enumerate(POSE_LANDMARK_NAMES):
            # Standing figure with slight arm swing over time
            x = 0.5 + 0.02 * ((li % 5) - 2)
            y = 0.12 + (li / 33.0) * 0.75
            if name in ("LEFT_WRIST", "LEFT_ELBOW", "LEFT_INDEX"):
                x -= 0.08 + 0.06 * frac
                y -= 0.05 * frac
            if name in ("RIGHT_WRIST", "RIGHT_ELBOW", "RIGHT_INDEX"):
                x += 0.08 + 0.10 * frac
                y -= 0.12 * frac
            landmarks.append(
                {
                    "name": name,
                    "x": round(x, 4),
                    "y": round(y, 4),
                    "z": 0.0,
                    "visibility": 1.0,
                }
            )
        frames.append({"timestamp_ms": t_ms, "landmarks": landmarks})
    return {
        "note": "SYNTHETIC_DEMO generated template — not coach-verified",
        "synthetic": True,
        "synthetic_demo": True,
        "landmark_names": list(POSE_LANDMARK_NAMES),
        "frames": frames,
        "source": "generated_synthetic_demo",
    }


def resolve_standard_sequence(
    package: Optional[dict[str, Any]],
    *,
    user_frame_count: int,
    user_duration_ms: int,
) -> tuple[dict[str, Any], str, bool]:
    """
    Return (sequence_payload, source_label, is_synthetic).

    Prefer package.synthetic_keypoint_template; else generate marked synthetic_demo.
    """
    if package and isinstance(package.get("synthetic_keypoint_template"), dict):
        tmpl = package["synthetic_keypoint_template"]
        frames = tmpl.get("frames") or []
        if frames:
            payload = {
                "landmark_names": tmpl.get("landmark_names") or list(POSE_LANDMARK_NAMES),
                "frames": frames,
                "note": tmpl.get("note") or "package synthetic_keypoint_template",
                "extractor": "benchmark_template",
            }
            return payload, "package_template", True

    gen = generate_synthetic_template_sequence(
        frame_count=max(4, min(user_frame_count, 24)),
        duration_ms=max(user_duration_ms, 600),
    )
    return gen, "generated_synthetic_demo", True


def _skeleton_side(
    *,
    landmarks: list,
    frame: int,
    frame_count: int,
    timestamp_ms: Optional[int],
    color: str,
    role: str,
    source: Optional[str] = None,
) -> dict[str, Any]:
    n = len(landmarks) or 33
    return {
        "role": role,
        "color": color,
        "frame": frame,
        "frame_count": frame_count,
        "timestamp_ms": timestamp_ms,
        "landmarks": landmarks,
        "bones": bone_edges(landmark_count=n),
        "landmark_count": n,
        "source": source,
    }


def build_overlay_json(
    *,
    video_id: int,
    keypoint_path: str | Path,
    frame: int = 0,
    package: Optional[dict[str, Any]] = None,
    timeline: Optional[dict[str, Any]] = None,
    landmark_count: Optional[int] = None,
    extractor: Optional[str] = None,
) -> dict[str, Any]:
    """Synced scrub overlay: green=standard, blue=user. Not a score."""
    if frame < 0:
        raise FrameOutOfRange("frame must be >= 0")

    user_payload = load_keypoint_payload(keypoint_path)
    user_frames = list(user_payload.get("frames") or [])
    if not user_frames:
        raise PoseNotExtracted("no frames in keypoint file")
    if frame >= len(user_frames):
        raise FrameOutOfRange(f"frame {frame} out of range (0..{len(user_frames) - 1})")

    user_entry = user_frames[frame]
    user_t0 = int(user_frames[0].get("timestamp_ms") or 0)
    user_t1 = int(user_frames[-1].get("timestamp_ms") or user_t0)
    user_dur = max(0, user_t1 - user_t0)

    std_seq, std_source, std_synthetic = resolve_standard_sequence(
        package,
        user_frame_count=len(user_frames),
        user_duration_ms=user_dur or 600,
    )
    std_frames = list(std_seq.get("frames") or [])
    if not std_frames:
        raise PosePreviewError("standard sequence empty")
    std_i = _map_scrub(frame, len(user_frames), len(std_frames))
    std_entry = std_frames[std_i]

    kind = None
    banner = None
    if package:
        status = str(package.get("verification_status") or "")
        kind = benchmark_kind_for_status(status)
        banner = package.get("banner")
        if kind == "synthetic_demo" and not banner:
            banner = SYNTHETIC_BANNER
    if std_synthetic:
        kind = kind or "synthetic_demo"
        banner = banner or SYNTHETIC_BANNER

    if timeline is None and package:
        try:
            timeline = timeline_from_package(user_payload, package)
        except Exception:  # noqa: BLE001
            timeline = None

    current_stage = None
    if timeline:
        current_stage = segment_at_frame(timeline, frame)

    user_side = _skeleton_side(
        landmarks=user_entry.get("landmarks") or [],
        frame=frame,
        frame_count=len(user_frames),
        timestamp_ms=user_entry.get("timestamp_ms"),
        color=USER_COLOR,
        role="user",
        source=extractor or user_payload.get("extractor"),
    )
    std_side = _skeleton_side(
        landmarks=std_entry.get("landmarks") or [],
        frame=std_i,
        frame_count=len(std_frames),
        timestamp_ms=std_entry.get("timestamp_ms"),
        color=STANDARD_COLOR,
        role="standard",
        source=std_source,
    )
    std_side["synthetic"] = std_synthetic
    std_side["synthetic_demo"] = True

    return {
        "video_id": video_id,
        "frame": frame,
        "frame_count": len(user_frames),
        "user": user_side,
        "standard": std_side,
        "colors": {"standard": STANDARD_COLOR, "user": USER_COLOR},
        "stage_timeline": timeline,
        "current_stage": current_stage,
        "benchmark_kind": kind or "synthetic_demo",
        "banner": banner or SYNTHETIC_BANNER,
        "notice": OVERLAY_NOTICE,
        "label": OVERLAY_NOTICE,
        "topology": "mediapipe_pose_33",
        "landmark_names": list(
            user_payload.get("landmark_names") or POSE_LANDMARK_NAMES
        )[: landmark_count or 33],
    }

