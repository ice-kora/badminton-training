"""Video quality precheck — engineering checks only (no pose / no scoring)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np


DEFAULT_POLICY: dict[str, Any] = {
    "duration_range_sec": [5, 60],
    "min_short_side": 720,
    "orientation": "portrait",
    "min_brightness": 40.0,
    "required_checks": ["duration", "resolution", "brightness", "orientation"],
    "client_checklist_items": ["full_body", "distance_ok", "racket_visible"],
    "deferred_checks": ["full_body", "distance"],
}


@dataclass
class VideoProbe:
    duration_ms: int
    width: int
    height: int
    fps: float
    frame_count: int
    mean_brightness: float
    orientation: str
    size_bytes: int


def orientation_from_size(width: int, height: int) -> str:
    if height >= width:
        return "portrait"
    return "landscape"


def probe_video(path: Path, brightness_sample_frames: int = 12) -> VideoProbe:
    """Probe duration/resolution/brightness via OpenCV (not pose)."""
    size_bytes = path.stat().st_size if path.exists() else 0
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise ValueError("无法打开视频文件（OpenCV VideoCapture 失败）")

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if fps > 0 and frame_count > 0:
            duration_ms = int(round(frame_count / fps * 1000))
        else:
            # Fallback: read until end counting frames
            counted = 0
            while True:
                ok, _ = cap.read()
                if not ok:
                    break
                counted += 1
            frame_count = counted
            fps = fps if fps > 0 else 30.0
            duration_ms = int(round(frame_count / fps * 1000))
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        luminances: list[float] = []
        if frame_count > 0:
            indices = np.linspace(
                0,
                max(frame_count - 1, 0),
                num=min(brightness_sample_frames, max(frame_count, 1)),
                dtype=int,
            )
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                luminances.append(float(np.mean(gray)))
        mean_brightness = float(np.mean(luminances)) if luminances else 0.0

        # Re-read size if props were zero
        if (width <= 0 or height <= 0) and luminances:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            if ok and frame is not None:
                height, width = frame.shape[:2]

        return VideoProbe(
            duration_ms=duration_ms,
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            mean_brightness=mean_brightness,
            orientation=orientation_from_size(width, height),
            size_bytes=size_bytes,
        )
    finally:
        cap.release()


def _policy_from_guide(guide: Any) -> dict[str, Any]:
    policy = dict(DEFAULT_POLICY)
    if guide is None:
        return policy
    raw = getattr(guide, "precheck_policy_json", None)
    if raw:
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                policy.update(loaded)
        except json.JSONDecodeError:
            pass
    # Column overrides if present
    dmin = getattr(guide, "duration_min_sec", None)
    dmax = getattr(guide, "duration_max_sec", None)
    if dmin is not None and dmax is not None:
        policy["duration_range_sec"] = [int(dmin), int(dmax)]
    if getattr(guide, "min_short_side", None):
        policy["min_short_side"] = int(guide.min_short_side)
    if getattr(guide, "min_brightness", None) is not None:
        policy["min_brightness"] = float(guide.min_brightness)
    if getattr(guide, "orientation", None):
        policy["orientation"] = guide.orientation
    return policy


def run_precheck(
    path: Path,
    guide: Any = None,
    client_checklist: Optional[dict[str, Any]] = None,
    client_hints: Optional[dict[str, Any]] = None,
    relax_orientation: bool = False,
) -> dict[str, Any]:
    """
    Return structured precheck report.
    Hard-fail required engineering checks block upload.
    Pose-related items are deferred_to_pose / client_checklist_only.
    """
    policy = _policy_from_guide(guide)
    if relax_orientation:
        policy["relax_orientation"] = True
    client_checklist = client_checklist or {}
    client_hints = client_hints or {}
    checks: list[dict[str, Any]] = []

    try:
        probe = probe_video(path)
    except Exception as exc:  # noqa: BLE001 — surface as failed probe
        return {
            "passed": False,
            "checks": [
                {
                    "id": "probe",
                    "status": "fail",
                    "message": f"视频探测失败: {exc}",
                    "evidence": {},
                }
            ],
            "probe": None,
            "policy": policy,
        }

    # --- duration ---
    dmin, dmax = policy.get("duration_range_sec", [5, 15])
    duration_sec = probe.duration_ms / 1000.0
    if duration_sec < float(dmin):
        checks.append(
            {
                "id": "duration",
                "status": "fail",
                "message": f"时长过短：{duration_sec:.1f}s，要求 {dmin}–{dmax}s",
                "evidence": {
                    "duration_ms": probe.duration_ms,
                    "duration_sec": duration_sec,
                    "min_sec": dmin,
                    "max_sec": dmax,
                },
            }
        )
    elif duration_sec > float(dmax):
        checks.append(
            {
                "id": "duration",
                "status": "fail",
                "message": f"时长过长：{duration_sec:.1f}s，要求 {dmin}–{dmax}s",
                "evidence": {
                    "duration_ms": probe.duration_ms,
                    "duration_sec": duration_sec,
                    "min_sec": dmin,
                    "max_sec": dmax,
                },
            }
        )
    else:
        checks.append(
            {
                "id": "duration",
                "status": "pass",
                "message": f"时长合格：{duration_sec:.1f}s",
                "evidence": {
                    "duration_ms": probe.duration_ms,
                    "duration_sec": duration_sec,
                    "min_sec": dmin,
                    "max_sec": dmax,
                },
            }
        )

    # --- resolution ---
    min_short = int(policy.get("min_short_side", 720))
    short_side = min(probe.width, probe.height)
    if short_side < min_short:
        checks.append(
            {
                "id": "resolution",
                "status": "fail",
                "message": (
                    f"分辨率过低：{probe.width}x{probe.height}，"
                    f"短边需 ≥ {min_short}（约 720p）"
                ),
                "evidence": {
                    "width": probe.width,
                    "height": probe.height,
                    "short_side": short_side,
                    "min_short_side": min_short,
                },
            }
        )
    else:
        checks.append(
            {
                "id": "resolution",
                "status": "pass",
                "message": f"分辨率合格：{probe.width}x{probe.height}",
                "evidence": {
                    "width": probe.width,
                    "height": probe.height,
                    "short_side": short_side,
                    "min_short_side": min_short,
                },
            }
        )

    # --- brightness ---
    min_bri = float(policy.get("min_brightness", 40.0))
    if probe.mean_brightness < min_bri:
        checks.append(
            {
                "id": "brightness",
                "status": "fail",
                "message": (
                    f"画面过暗：平均亮度 {probe.mean_brightness:.1f}，"
                    f"阈值 ≥ {min_bri}"
                ),
                "evidence": {
                    "mean_luminance": probe.mean_brightness,
                    "min_brightness": min_bri,
                },
            }
        )
    else:
        checks.append(
            {
                "id": "brightness",
                "status": "pass",
                "message": f"亮度合格：平均亮度 {probe.mean_brightness:.1f}",
                "evidence": {
                    "mean_luminance": probe.mean_brightness,
                    "min_brightness": min_bri,
                },
            }
        )

    # --- orientation ---
    required_orient = policy.get("orientation", "portrait")
    relax_orientation = bool(policy.get("relax_orientation", False))
    if probe.orientation != required_orient and not relax_orientation:
        checks.append(
            {
                "id": "orientation",
                "status": "fail",
                "message": (
                    f"方向不符：当前 {probe.orientation}，"
                    f"要求 {required_orient}"
                ),
                "evidence": {
                    "actual": probe.orientation,
                    "required": required_orient,
                    "width": probe.width,
                    "height": probe.height,
                },
            }
        )
    elif probe.orientation != required_orient and relax_orientation:
        checks.append(
            {
                "id": "orientation",
                "status": "pass",
                "message": (
                    f"方向已放宽（本地测试）：当前 {probe.orientation}，"
                    f"正式要求 {required_orient}"
                ),
                "evidence": {
                    "actual": probe.orientation,
                    "required": required_orient,
                    "relaxed": True,
                    "width": probe.width,
                    "height": probe.height,
                },
            }
        )
    else:
        checks.append(
            {
                "id": "orientation",
                "status": "pass",
                "message": f"方向合格：{probe.orientation}",
                "evidence": {
                    "actual": probe.orientation,
                    "required": required_orient,
                    "width": probe.width,
                    "height": probe.height,
                },
            }
        )

    # --- full_body / distance: honest deferral (no fake pose) ---
    # Optional client checklist confirmation
    client_items = policy.get("client_checklist_items") or []
    for item_id, label in [
        ("full_body", "全身入镜"),
        ("distance", "拍摄距离合适（不太近/不太远）"),
    ]:
        # Prefer client checklist key variants
        confirmed = bool(
            client_checklist.get(item_id)
            or client_checklist.get(f"{item_id}_ok")
            or client_checklist.get("distance_ok" if item_id == "distance" else "")
        )
        # frame_coverage_hints from client (silhouette only) — advisory
        hint = None
        if client_hints:
            hint = client_hints.get(item_id) or client_hints.get("subject_bbox")

        if item_id in (policy.get("deferred_checks") or []):
            if confirmed:
                checks.append(
                    {
                        "id": item_id,
                        "status": "client_checklist_only",
                        "message": f"{label}：已由用户确认（非姿态检测）",
                        "evidence": {
                            "client_confirmed": True,
                            "hint": hint,
                            "note": "server does not verify pose/body bbox",
                        },
                    }
                )
            else:
                # Not a hard fail unless listed in required_checks
                status = (
                    "fail"
                    if item_id in (policy.get("required_checks") or [])
                    else "deferred_to_pose"
                )
                msg = (
                    f"{label}：未确认，请对照剪影完成检查清单"
                    if status == "fail"
                    else f"{label}：服务端暂不检测，标记 deferred_to_pose（非姿态 AI）"
                )
                checks.append(
                    {
                        "id": item_id,
                        "status": status,
                        "message": msg,
                        "evidence": {
                            "client_confirmed": False,
                            "hint": hint,
                        },
                    }
                )

    # Client checklist items that are required as gates (if configured in required_checks)
    for key in client_items:
        if key in ("full_body", "distance", "distance_ok"):
            continue  # already handled
        if key in (policy.get("required_checks") or []):
            ok = bool(client_checklist.get(key))
            checks.append(
                {
                    "id": key,
                    "status": "pass" if ok else "fail",
                    "message": (
                        f"客户端检查项 {key} 已确认"
                        if ok
                        else f"请确认检查项：{key}"
                    ),
                    "evidence": {"client_confirmed": ok},
                }
            )

    required = set(policy.get("required_checks") or [])
    hard_failed = any(
        c["id"] in required and c["status"] == "fail" for c in checks
    )
    # Also fail if probe-level fail
    hard_failed = hard_failed or any(
        c["id"] == "probe" and c["status"] == "fail" for c in checks
    )

    return {
        "passed": not hard_failed,
        "checks": checks,
        "probe": {
            "duration_ms": probe.duration_ms,
            "width": probe.width,
            "height": probe.height,
            "fps": probe.fps,
            "frame_count": probe.frame_count,
            "mean_brightness": probe.mean_brightness,
            "orientation": probe.orientation,
            "size_bytes": probe.size_bytes,
        },
        "policy": policy,
    }
