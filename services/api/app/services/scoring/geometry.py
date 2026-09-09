"""Heuristic geometry helpers from MediaPipe-normalized landmarks (no coach standards)."""
from __future__ import annotations

import math
from typing import Any, Optional


def _lm_map(frame: dict[str, Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for i, lm in enumerate(frame.get("landmarks") or []):
        if not isinstance(lm, dict):
            continue
        name = lm.get("name") or str(i)
        out[str(name)] = {
            "x": float(lm.get("x") or 0.0),
            "y": float(lm.get("y") or 0.0),
            "z": float(lm.get("z") or 0.0),
            "visibility": float(lm.get("visibility") if lm.get("visibility") is not None else 1.0),
        }
    return out


def _angle_deg(a: dict[str, float], b: dict[str, float], c: dict[str, float]) -> float:
    """Angle ABC in degrees."""
    bax = a["x"] - b["x"]
    bay = a["y"] - b["y"]
    bcx = c["x"] - b["x"]
    bcy = c["y"] - b["y"]
    dot = bax * bcx + bay * bcy
    na = math.hypot(bax, bay)
    nc = math.hypot(bcx, bcy)
    if na < 1e-9 or nc < 1e-9:
        return 0.0
    cos_v = max(-1.0, min(1.0, dot / (na * nc)))
    return math.degrees(math.acos(cos_v))


def _vec_angle_from_vertical(ax: float, ay: float, bx: float, by: float) -> float:
    """Angle between vector A→B and upward vertical (0,-1) in image coords."""
    vx, vy = bx - ax, by - ay
    # upward = (0, -1)
    dot = vx * 0.0 + vy * (-1.0)
    n = math.hypot(vx, vy)
    if n < 1e-9:
        return 0.0
    cos_v = max(-1.0, min(1.0, dot / n))
    return math.degrees(math.acos(cos_v))


def pick_contact_frame(frames: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not frames:
        return None
    # Heuristic: frame where right wrist is highest (min y)
    best = frames[0]
    best_y = 1e9
    for fr in frames:
        m = _lm_map(fr)
        rw = m.get("RIGHT_WRIST")
        if not rw:
            continue
        if rw["y"] < best_y:
            best_y = rw["y"]
            best = fr
    return best


def pick_backswing_frame(frames: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not frames:
        return None
    if len(frames) == 1:
        return frames[0]
    # Roughly 25–40% into the clip
    idx = max(0, min(len(frames) - 1, int(len(frames) * 0.3)))
    return frames[idx]


def measure_metric(metric_id: str, frames: list[dict[str, Any]]) -> Optional[float]:
    """Return heuristic measured value for known metric ids, else None."""
    if not frames:
        return None
    contact = pick_contact_frame(frames)
    back = pick_backswing_frame(frames)
    cm = _lm_map(contact) if contact else {}
    bm = _lm_map(back) if back else {}

    def elbow_flexion(m: dict[str, dict[str, float]]) -> Optional[float]:
        s, e, w = m.get("RIGHT_SHOULDER"), m.get("RIGHT_ELBOW"), m.get("RIGHT_WRIST")
        if not (s and e and w):
            return None
        return _angle_deg(s, e, w)

    def contact_height_rel_shoulder(m: dict[str, dict[str, float]]) -> Optional[float]:
        s, w = m.get("RIGHT_SHOULDER"), m.get("RIGHT_WRIST")
        if not (s and w):
            return None
        # image y down: positive => wrist above shoulder
        return s["y"] - w["y"]

    def trunk_rotation(m: dict[str, dict[str, float]]) -> Optional[float]:
        ls, rs = m.get("LEFT_SHOULDER"), m.get("RIGHT_SHOULDER")
        lh, rh = m.get("LEFT_HIP"), m.get("RIGHT_HIP")
        if not (ls and rs and lh and rh):
            return None
        shoulder_ang = math.degrees(math.atan2(rs["y"] - ls["y"], rs["x"] - ls["x"]))
        hip_ang = math.degrees(math.atan2(rh["y"] - lh["y"], rh["x"] - lh["x"]))
        return abs(shoulder_ang - hip_ang)

    def contact_forward(m: dict[str, dict[str, float]]) -> Optional[float]:
        w = m.get("RIGHT_WRIST")
        lh, rh = m.get("LEFT_HIP"), m.get("RIGHT_HIP")
        if not (w and lh and rh):
            return None
        mid_x = (lh["x"] + rh["x"]) / 2.0
        return w["x"] - mid_x

    def racket_depression(m: dict[str, dict[str, float]]) -> Optional[float]:
        e, w = m.get("RIGHT_ELBOW"), m.get("RIGHT_WRIST")
        if not (e and w):
            return None
        return _vec_angle_from_vertical(e["x"], e["y"], w["x"], w["y"])

    def wrist_vs_shoulder_y(m: dict[str, dict[str, float]]) -> Optional[float]:
        s, w = m.get("RIGHT_SHOULDER"), m.get("RIGHT_WRIST")
        if not (s and w):
            return None
        return w["y"] - s["y"]

    def wrist_travel(frames_in: list[dict[str, Any]]) -> Optional[float]:
        pts = []
        for fr in frames_in:
            m = _lm_map(fr)
            w = m.get("RIGHT_WRIST")
            if w:
                pts.append((w["x"], w["y"]))
        if len(pts) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(pts)):
            total += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        return total

    def wrist_action_extent(frames_in: list[dict[str, Any]]) -> Optional[float]:
        angles = []
        for fr in frames_in:
            m = _lm_map(fr)
            e, w = m.get("RIGHT_ELBOW"), m.get("RIGHT_WRIST")
            if e and w:
                angles.append(_vec_angle_from_vertical(e["x"], e["y"], w["x"], w["y"]))
        if len(angles) < 2:
            return 0.0
        return max(angles) - min(angles)

    def elbow_rom(frames_in: list[dict[str, Any]]) -> Optional[float]:
        vals = []
        for fr in frames_in:
            m = _lm_map(fr)
            v = elbow_flexion(m)
            if v is not None:
                vals.append(v)
        if len(vals) < 2:
            return None
        return max(vals) - min(vals)

    def shoulder_line_rom(frames_in: list[dict[str, Any]]) -> Optional[float]:
        """Crude PROXY of shoulder rotation: excursion of shoulder-line angle in image plane."""
        angs = []
        for fr in frames_in:
            m = _lm_map(fr)
            ls, rs = m.get("LEFT_SHOULDER"), m.get("RIGHT_SHOULDER")
            if not (ls and rs):
                continue
            angs.append(math.degrees(math.atan2(rs["y"] - ls["y"], rs["x"] - ls["x"])))
        if len(angs) < 2:
            return None
        # unwrap-ish peak-to-peak on circular? use simple max-min for demo proxy
        return max(angs) - min(angs)

    def racket_vs_horizontal(m: dict[str, dict[str, float]]) -> Optional[float]:
        """PROXY: forearm (elbow→wrist) angle vs horizontal, degrees."""
        e, w = m.get("RIGHT_ELBOW"), m.get("RIGHT_WRIST")
        if not (e and w):
            return None
        vx, vy = w["x"] - e["x"], w["y"] - e["y"]
        # angle from +x horizontal; image y down
        ang = abs(math.degrees(math.atan2(vy, vx)))
        # map to acute-ish vs horizontal: 0 = horizontal
        if ang > 90:
            ang = 180 - ang
        return ang

    mid = metric_id
    if mid in ("elbow_flexion_at_contact",):
        return elbow_flexion(cm)
    if mid == "contact_height_rel_shoulder":
        return contact_height_rel_shoulder(cm)
    if mid in ("trunk_rotation_backswing", "trunk_coil_backswing", "trunk_x_factor_prep"):
        return trunk_rotation(bm)
    if mid == "contact_forward_of_body":
        return contact_forward(cm)
    if mid == "racket_face_depression":
        return racket_depression(cm)
    if mid == "racket_face_vs_net":
        return wrist_vs_shoulder_y(cm)
    if mid == "contact_softness":
        return wrist_travel(frames)
    if mid == "wrist_action_extent":
        return wrist_action_extent(frames)
    if mid == "elbow_flex_ext_rom":
        return elbow_rom(frames)
    if mid == "shoulder_rotation_rom":
        return shoulder_line_rom(frames)
    if mid == "wrist_flex_ext_rom":
        # MediaPipe Pose cannot reliably measure wrist flex/ext — leave null
        return None
    if mid == "racket_face_vs_horizontal_proxy":
        return racket_vs_horizontal(cm)
    if mid == "contact_height_lab_m":
        # Absolute lab meters not available from normalized MediaPipe
        return None
    # Unknown metric ids: do NOT silently invent elbow flexion for lit packages
    return None
