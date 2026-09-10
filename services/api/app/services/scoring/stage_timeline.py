"""Heuristic stage timeline: map benchmark stages onto a user pose sequence.

Uses demo stage markers / relative keyframe timing — not coach-verified cuts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def _load_pose(pose_json: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(pose_json, (str, Path)):
        return json.loads(Path(pose_json).read_text(encoding="utf-8"))
    return pose_json


def _user_span_ms(frames: list[dict[str, Any]]) -> tuple[int, int]:
    if not frames:
        return 0, 0
    times = []
    for f in frames:
        t = f.get("timestamp_ms")
        if t is not None:
            times.append(int(t))
    if not times:
        # Fallback: index as ms proxy
        return 0, max(0, len(frames) - 1)
    return min(times), max(times)


def _frame_index_at(frames: list[dict[str, Any]], t_ms: int) -> int:
    if not frames:
        return 0
    best_i = 0
    best_d = None
    for i, f in enumerate(frames):
        ft = f.get("timestamp_ms")
        if ft is None:
            ft = i
        d = abs(int(ft) - int(t_ms))
        if best_d is None or d < best_d:
            best_d = d
            best_i = i
    return best_i


def _ordered_stages(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [s for s in stages if isinstance(s, dict) and s.get("code")]
    return sorted(
        rows,
        key=lambda s: (
            int(s.get("sort_order") if s.get("sort_order") is not None else 0),
            str(s.get("code")),
        ),
    )


def _template_anchors_ms(
    stages: list[dict[str, Any]],
    keyframes: Optional[list[dict[str, Any]]],
    *,
    template_total_ms: Optional[int] = None,
) -> tuple[list[Optional[int]], int]:
    """
    Return per-stage start times on the template clock (None = unknown)
    and a template_total_ms used for relative scaling.
    """
    n = len(stages)
    anchors: list[Optional[int]] = [None] * n
    code_to_i = {str(s["code"]): i for i, s in enumerate(stages)}

    kf_times: list[int] = []
    for kf in keyframes or []:
        if not isinstance(kf, dict):
            continue
        t = kf.get("t_ms")
        if t is None:
            continue
        t_i = int(t)
        kf_times.append(t_i)
        sc = kf.get("stage_code")
        if sc and str(sc) in code_to_i:
            i = code_to_i[str(sc)]
            if anchors[i] is None or t_i < anchors[i]:
                anchors[i] = t_i

    # First stage defaults to 0 when any timing exists
    if any(a is not None for a in anchors) and anchors[0] is None:
        anchors[0] = 0

    # Fill missing anchors by linear interpolation between known neighbors
    known = [(i, a) for i, a in enumerate(anchors) if a is not None]
    if not known:
        # Equal splits on a synthetic 1000ms template (relative only)
        total = int(template_total_ms) if template_total_ms and template_total_ms > 0 else 1000
        for i in range(n):
            anchors[i] = int(round(i * total / n))
        return anchors, total

    # Extrapolate ends
    if anchors[0] is None:
        anchors[0] = 0
    if anchors[-1] is None:
        # leave last start; total will extend past last known
        pass

    for k in range(len(known) - 1):
        i0, t0 = known[k]
        i1, t1 = known[k + 1]
        gap = i1 - i0
        if gap <= 1:
            continue
        for j in range(1, gap):
            frac = j / gap
            anchors[i0 + j] = int(round(t0 + (t1 - t0) * frac))

    # Trailing unknowns: spread toward total
    last_known_i = max(i for i, a in enumerate(anchors) if a is not None)
    last_t = int(anchors[last_known_i])  # type: ignore[arg-type]
    inferred_total = max(
        int(template_total_ms) if template_total_ms else 0,
        max(kf_times) if kf_times else 0,
        last_t,
    )
    # Ensure room for remaining stages after last known start
    remaining = n - last_known_i
    if remaining > 1:
        # last stage needs a duration; extend total by last known segment size or 200ms
        pad = max(200, last_t // max(1, last_known_i) if last_known_i else 200)
        inferred_total = max(inferred_total, last_t + pad * (remaining - 1))
        for j in range(1, remaining):
            if anchors[last_known_i + j] is None:
                anchors[last_known_i + j] = int(
                    round(last_t + j * (inferred_total - last_t) / (remaining - 1))
                )
    else:
        inferred_total = max(inferred_total, last_t + 200)

    # Final pass: any still None → equal
    for i in range(n):
        if anchors[i] is None:
            anchors[i] = int(round(i * inferred_total / n))

    return anchors, inferred_total



def _pace_label(delta_ms: Optional[int], stage_name: str, tmpl_seg_ms: int) -> Optional[str]:
    """Human pace hint for amateurs — only when delta is meaningfully large."""
    if delta_ms is None:
        return None
    thr = max(80, int(0.25 * tmpl_seg_ms) if tmpl_seg_ms else 80)
    if abs(int(delta_ms)) < thr:
        return None
    short = (stage_name or "该阶段").strip() or "该阶段"
    # Prefer short stage nouns amateurs know
    return f"{short}偏慢" if int(delta_ms) > 0 else f"{short}偏快"


def build_stage_timeline(
    pose_json: dict[str, Any] | str | Path,
    *,
    stages: list[dict[str, Any]],
    keyframes: Optional[list[dict[str, Any]]] = None,
    template_total_ms: Optional[int] = None,
    benchmark_kind: Optional[str] = None,
    source: str = "heuristic_relative_timing",
) -> dict[str, Any]:
    """
    Segment user pose into benchmark stages via relative timing heuristic.

    Returns:
      {
        segments: [{code,name,t0_ms,t1_ms,frame_i0,frame_i1,
                    template_t0_ms,template_t1_ms,delta_ms}],
        user_t0_ms, user_t1_ms, template_total_ms,
        method, benchmark_kind, notice
      }
    """
    pose = _load_pose(pose_json)
    frames = list(pose.get("frames") or [])
    ordered = _ordered_stages(stages)
    user_t0, user_t1 = _user_span_ms(frames)
    user_dur = max(0, user_t1 - user_t0)

    if not ordered:
        return {
            "segments": [],
            "user_t0_ms": user_t0,
            "user_t1_ms": user_t1,
            "template_total_ms": template_total_ms,
            "method": source,
            "benchmark_kind": benchmark_kind,
            "notice": "无阶段定义，无法切分时间轴",
        }

    anchors, tmpl_total = _template_anchors_ms(
        ordered, keyframes, template_total_ms=template_total_ms
    )
    # Stage i occupies [anchors[i], anchors[i+1]) ; last → tmpl_total
    tmpl_bounds: list[tuple[int, int]] = []
    for i in range(len(ordered)):
        a0 = int(anchors[i] or 0)
        a1 = int(anchors[i + 1]) if i + 1 < len(ordered) else int(tmpl_total)
        if a1 < a0:
            a1 = a0
        tmpl_bounds.append((a0, a1))

    has_template_timing = bool(keyframes) and any(
        isinstance(k, dict) and k.get("t_ms") is not None for k in (keyframes or [])
    )

    segments: list[dict[str, Any]] = []
    for i, st in enumerate(ordered):
        ta0, ta1 = tmpl_bounds[i]
        if tmpl_total > 0:
            f0 = ta0 / tmpl_total
            f1 = ta1 / tmpl_total
        else:
            f0 = i / len(ordered)
            f1 = (i + 1) / len(ordered)
        u0 = int(round(user_t0 + user_dur * f0))
        u1 = int(round(user_t0 + user_dur * f1))
        if i == len(ordered) - 1:
            u1 = user_t1
        fi0 = _frame_index_at(frames, u0) if frames else 0
        fi1 = _frame_index_at(frames, u1) if frames else 0
        user_seg = max(0, u1 - u0)
        tmpl_seg = max(0, ta1 - ta0)
        delta = None
        if has_template_timing:
            # Scale-invariant duration delta on absolute template clock
            delta = int(user_seg - tmpl_seg)
        seg_name = str(st.get("name") or st["code"])
        segments.append(
            {
                "code": str(st["code"]),
                "name": seg_name,
                "sort_order": int(st.get("sort_order") or (i + 1)),
                "t0_ms": u0,
                "t1_ms": u1,
                "frame_i0": fi0,
                "frame_i1": fi1,
                "template_t0_ms": ta0 if has_template_timing else None,
                "template_t1_ms": ta1 if has_template_timing else None,
                "delta_ms": delta,
                "pace_label": _pace_label(delta, seg_name, tmpl_seg),
            }
        )

    notice = "动作阶段示意（引拍→挥拍→击球→随挥），非实验室毫秒标定"
    if benchmark_kind == "synthetic_demo":
        notice += " · synthetic_demo"
    elif benchmark_kind == "literature_cited":
        notice += " · literature_cited"

    return {
        "segments": segments,
        "user_t0_ms": user_t0,
        "user_t1_ms": user_t1,
        "template_total_ms": tmpl_total if has_template_timing else tmpl_total,
        "method": source,
        "benchmark_kind": benchmark_kind,
        "has_template_timing": has_template_timing,
        "notice": notice,
    }


def timeline_from_package(
    pose_json: dict[str, Any] | str | Path,
    package: dict[str, Any],
) -> dict[str, Any]:
    stages = list(package.get("stages") or [])
    keyframes = list(package.get("keyframes") or [])
    tmpl = package.get("synthetic_keypoint_template") or {}
    tmpl_frames = (tmpl.get("frames") if isinstance(tmpl, dict) else None) or []
    template_total = None
    if tmpl_frames:
        times = [int(f["timestamp_ms"]) for f in tmpl_frames if f.get("timestamp_ms") is not None]
        if times:
            template_total = max(times)
    kind = None
    status = str(package.get("verification_status") or "")
    if status == "synthetic_demo":
        kind = "synthetic_demo"
    elif status == "literature_cited":
        kind = "literature_cited"
    elif status == "verified":
        kind = "verified"
    return build_stage_timeline(
        pose_json,
        stages=stages,
        keyframes=keyframes,
        template_total_ms=template_total,
        benchmark_kind=kind,
    )


def segment_at_time(timeline: dict[str, Any], t_ms: int) -> Optional[dict[str, Any]]:
    for seg in timeline.get("segments") or []:
        if int(seg["t0_ms"]) <= t_ms <= int(seg["t1_ms"]):
            return seg
    segs = timeline.get("segments") or []
    return segs[-1] if segs else None


def segment_at_frame(timeline: dict[str, Any], frame: int) -> Optional[dict[str, Any]]:
    for seg in timeline.get("segments") or []:
        if int(seg["frame_i0"]) <= frame <= int(seg["frame_i1"]):
            return seg
    segs = timeline.get("segments") or []
    return segs[-1] if segs else None
