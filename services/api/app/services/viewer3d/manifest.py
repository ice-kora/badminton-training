"""Build V3 3D viewer manifest from Motion Benchmark package (synthetic_demo OK)."""
from __future__ import annotations

from typing import Any, Optional

from app.services.benchmark_pkg import LITERATURE_BANNER, LITERATURE_RANGE_KINDS, SYNTHETIC_BANNER, benchmark_kind_for_status
from app.services.pose.landmarks import POSE_CONNECTIONS, POSE_LANDMARK_NAMES, bone_edges
from app.services.scoring.overlay import generate_synthetic_template_sequence

PLAYBACK_SPEEDS = [0.25, 0.5, 1.0]
VIEWER3D_NOTICE = "3D 标准动作（演示）· 非实时 · 工程演示基准（非教练标定）"
HUD_NA = "N/A"


def _mediapipe_to_world(lm: dict[str, Any]) -> dict[str, float]:
    """Map MediaPipe image-ish coords to a simple Y-up world frame."""
    x = float(lm.get("x") or 0.0)
    y = float(lm.get("y") or 0.0)
    z = float(lm.get("z") or 0.0)
    return {
        "x": round((x - 0.5) * 2.0, 5),
        "y": round((0.5 - y) * 2.0, 5),  # image y-down → world y-up
        "z": round(z * 2.0, 5),
    }


def _stage_markers(
    stages: list[dict[str, Any]],
    keyframes: list[dict[str, Any]],
    duration_ms: int,
) -> list[dict[str, Any]]:
    ordered = sorted(
        [s for s in stages if isinstance(s, dict) and s.get("code")],
        key=lambda s: int(s.get("sort_order") or 0),
    )
    if not ordered:
        return []

    # Prefer first keyframe per stage_code
    by_stage: dict[str, int] = {}
    for kf in keyframes:
        if not isinstance(kf, dict):
            continue
        sc = kf.get("stage_code")
        t = kf.get("t_ms")
        if sc is None or t is None:
            continue
        code = str(sc)
        ti = int(t)
        if code not in by_stage or ti < by_stage[code]:
            by_stage[code] = ti

    n = len(ordered)
    out: list[dict[str, Any]] = []
    for i, st in enumerate(ordered):
        code = str(st["code"])
        if code in by_stage:
            t_ms = by_stage[code]
        else:
            t_ms = int(round(duration_ms * i / max(1, n)))
        out.append(
            {
                "code": code,
                "name": st.get("name") or code,
                "sort_order": int(st.get("sort_order") or i + 1),
                "t_ms": t_ms,
                "label": st.get("name") or code,
            }
        )
    return out


def _hud_angles(metrics: list[dict[str, Any]], stage_code: Optional[str] = None) -> list[dict[str, Any]]:
    """Angle HUD placeholders — synthetic_demo mid-range or N/A. Never claim expert truth."""
    rows: list[dict[str, Any]] = []
    for m in metrics or []:
        if not isinstance(m, dict):
            continue
        unit = (m.get("unit") or "").lower()
        # Prefer degree metrics for HUD; include ratio as secondary placeholders
        if unit not in ("deg", "degree", "degrees", "ratio"):
            continue
        sc = m.get("stage_code")
        if stage_code and sc and str(sc) != str(stage_code):
            # still list but mark inactive
            active = False
        else:
            active = True if not stage_code else (not sc or str(sc) == str(stage_code))

        kind = str(m.get("range_kind") or "")
        rmin, rmax = m.get("range_min"), m.get("range_max")
        value: Any = HUD_NA
        value_label = HUD_NA
        if kind == "synthetic_demo" and rmin is not None and rmax is not None:
            mid = (float(rmin) + float(rmax)) / 2.0
            value = round(mid, 1)
            value_label = f"{value}{'' if unit == 'ratio' else '°'} (synthetic_demo)"
        elif kind in LITERATURE_RANGE_KINDS and rmin is not None and rmax is not None:
            mid = (float(rmin) + float(rmax)) / 2.0
            value = round(mid, 1)
            value_label = f"{value}{'' if unit == 'ratio' else '°'} (literature_cited)"
        elif rmin is None and rmax is None:
            value = HUD_NA
            value_label = HUD_NA

        rows.append(
            {
                "id": m.get("id"),
                "name": m.get("name") or m.get("id"),
                "unit": m.get("unit"),
                "stage_code": sc,
                "value": value,
                "display": value_label,
                "range_min": rmin,
                "range_max": rmax,
                "range_kind": kind or None,
                "active": active,
                "synthetic_demo": kind == "synthetic_demo",
                "literature_cited": kind in LITERATURE_RANGE_KINDS or kind == "literature_cited",
                "note": "占位 HUD · 非教练现场标定",
            }
        )
    if not rows:
        # Always show placeholder slots so UI is stable
        for label in ("肘屈曲", "击球高度相对肩", "躯干旋转代理"):
            rows.append(
                {
                    "id": None,
                    "name": label,
                    "unit": "deg",
                    "stage_code": None,
                    "value": HUD_NA,
                    "display": HUD_NA,
                    "range_min": None,
                    "range_max": None,
                    "range_kind": None,
                    "active": True,
                    "synthetic_demo": False,
                    "note": "占位 HUD · 无指标时显示 N/A",
                }
            )
    return rows


def _frames_from_sequence(seq: dict[str, Any]) -> list[dict[str, Any]]:
    frames_out: list[dict[str, Any]] = []
    for fr in seq.get("frames") or []:
        lms = fr.get("landmarks") or []
        joints = []
        for i, lm in enumerate(lms):
            name = lm.get("name") if isinstance(lm, dict) else None
            if not name and i < len(POSE_LANDMARK_NAMES):
                name = POSE_LANDMARK_NAMES[i]
            world = _mediapipe_to_world(lm if isinstance(lm, dict) else {})
            joints.append(
                {
                    "index": i,
                    "name": name or f"j{i}",
                    **world,
                    "visibility": float((lm or {}).get("visibility") or 1.0)
                    if isinstance(lm, dict)
                    else 1.0,
                }
            )
        frames_out.append(
            {
                "timestamp_ms": int(fr.get("timestamp_ms") or 0),
                "joints": joints,
            }
        )
    return frames_out


def build_viewer3d_manifest(
    *,
    skill_id: int,
    skill_code: str,
    skill_name: str,
    package: Optional[dict[str, Any]] = None,
    version_label: Optional[str] = None,
    version_status: Optional[str] = None,
    glb_url: Optional[str] = "/static/viewer3d/stick_figure.synthetic_demo.glb",
    web_viewer_url: Optional[str] = "/static/viewer3d/index.html",
) -> dict[str, Any]:
    """Assemble offline 3D standard-action viewer payload."""
    package = package or {}
    status = str(package.get("verification_status") or "synthetic_demo")
    kind = benchmark_kind_for_status(status) or "synthetic_demo"
    banner = package.get("banner") or (
        SYNTHETIC_BANNER if kind == "synthetic_demo"
        else LITERATURE_BANNER if kind == "literature_cited"
        else None
    )

    tmpl = package.get("synthetic_keypoint_template")
    if isinstance(tmpl, dict) and tmpl.get("frames"):
        seq = {
            "landmark_names": tmpl.get("landmark_names") or list(POSE_LANDMARK_NAMES),
            "frames": tmpl["frames"],
            "source": "package_template",
        }
        sequence_source = "package_template"
    else:
        seq = generate_synthetic_template_sequence(frame_count=8, duration_ms=800)
        sequence_source = "generated_synthetic_demo"

    frames = _frames_from_sequence(seq)
    if frames:
        duration_ms = int(frames[-1]["timestamp_ms"])
    else:
        duration_ms = 800

    stages = list(package.get("stages") or [])
    keyframes = list(package.get("keyframes") or [])
    markers = _stage_markers(stages, keyframes, duration_ms)
    metrics = list(package.get("metrics") or [])
    hud = _hud_angles(metrics)

    n_joints = len(frames[0]["joints"]) if frames else 33
    bones = bone_edges(landmark_count=n_joints)

    return {
        "skill_id": skill_id,
        "skill_code": skill_code,
        "skill_name": skill_name,
        "title": "3D 标准动作（演示）",
        "version_label": version_label,
        "version_status": version_status,
        "verification_status": status,
        "benchmark_kind": kind,
        "source": package.get("source") or "engineering_synthetic_demo",
        "banner": banner or (LITERATURE_BANNER if kind == "literature_cited" else SYNTHETIC_BANNER),
        "notice": (
            "3D 标准动作 · 文献科研参考标准 · 非实时 · 非教练现场标定"
            if kind == "literature_cited"
            else VIEWER3D_NOTICE
        ),
        "synthetic_demo": kind == "synthetic_demo",
        "literature_cited": kind == "literature_cited",
        "realtime": False,
        "playback_speeds": list(PLAYBACK_SPEEDS),
        "default_speed": 1.0,
        "duration_ms": duration_ms,
        "frame_count": len(frames),
        "topology": "mediapipe_pose_33",
        "landmark_names": list(seq.get("landmark_names") or POSE_LANDMARK_NAMES)[:n_joints],
        "bones": bones,
        "bone_index_pairs": [[a, b] for a, b in POSE_CONNECTIONS if a < n_joints and b < n_joints],
        "stages": markers,
        "keyframes": [
            {
                "code": kf.get("code"),
                "name": kf.get("name"),
                "stage_code": kf.get("stage_code"),
                "t_ms": kf.get("t_ms"),
            }
            for kf in keyframes
            if isinstance(kf, dict)
        ],
        "frames": frames,
        "hud_angles": hud,
        "sequence_source": sequence_source,
        "assets": {
            "glb_url": glb_url,
            "glb_note": "static synthetic_demo stick-figure · not mocap",
            "web_viewer_url": web_viewer_url,
            "renderer": "procedural_canvas_primary",
            "choice": (
                "Option A (shipped): WeChat native canvas + procedural skeleton "
                "driven by demo keypoints. Optional static GLB + Three.js HTML "
                "at assets.web_viewer_url for browser/web-view smoke (Option B)."
            ),
        },
        "controls": {
            "orbit": True,
            "zoom": True,
            "playback_speeds": list(PLAYBACK_SPEEDS),
            "jump_to_stage": True,
            "hud": True,
        },
    }
