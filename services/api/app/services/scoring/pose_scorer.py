"""PoseScorer: compare user pose JSON to a published benchmark package.

Synthetic ranges are engineering demo only — never coach-verified truth.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.services.benchmark_pkg import (
    LITERATURE_BANNER,
    SYNTHETIC_BANNER,
    benchmark_kind_for_status,
)
from app.services.scoring.geometry import measure_metric

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


@dataclass
class MetricEvidence:
    metric_id: str
    name: str
    measured: Optional[float]
    range_min: Optional[float]
    range_max: Optional[float]
    in_range: bool
    score: float  # 0-100
    unit: Optional[str] = None
    linked_error_id: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "measured": self.measured,
            "range_min": self.range_min,
            "range_max": self.range_max,
            "in_range": self.in_range,
            "score": round(self.score, 1),
            "unit": self.unit,
            "linked_error_id": self.linked_error_id,
            "notes": self.notes,
        }


@dataclass
class ProblemHit:
    error_code: str
    title: str
    severity: str  # P0|P1|P2
    metric_id: Optional[str] = None
    evidence: dict[str, Any] = field(default_factory=dict)
    drill_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "title": self.title,
            "severity": self.severity,
            "metric_id": self.metric_id,
            "evidence": self.evidence,
            "drill_codes": self.drill_codes,
        }


@dataclass
class ScoreResult:
    overall_score: float
    dimension_scores: dict[str, float]
    metrics: list[MetricEvidence]
    problems: list[ProblemHit]
    benchmark_kind: str
    verification_status: str
    source: str
    banner: str
    benchmark_version_label: Optional[str] = None
    explainable: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 1),
            "dimension_scores": {k: round(v, 1) for k, v in self.dimension_scores.items()},
            "metrics": [m.to_dict() for m in self.metrics],
            "problems": [p.to_dict() for p in self.problems],
            "benchmark_kind": self.benchmark_kind,
            "verification_status": self.verification_status,
            "source": self.source,
            "banner": self.banner,
            "benchmark_version_label": self.benchmark_version_label,
            "explainable": self.explainable,
        }


def _load_pose(pose_json: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(pose_json, (str, Path)):
        return json.loads(Path(pose_json).read_text(encoding="utf-8"))
    return pose_json


def _score_against_range(
    measured: Optional[float], rmin: Optional[float], rmax: Optional[float]
) -> tuple[bool, float, float]:
    """Return (in_range, score_0_100, severity_distance_ratio)."""
    if measured is None or (rmin is None and rmax is None):
        return True, 50.0, 0.0
    lo = rmin if rmin is not None else measured
    hi = rmax if rmax is not None else measured
    if lo > hi:
        lo, hi = hi, lo
    span = max(hi - lo, 1e-6)
    if lo <= measured <= hi:
        # center gets 100, edges ~85
        mid = (lo + hi) / 2.0
        dist = abs(measured - mid) / (span / 2.0)
        score = 100.0 - 15.0 * min(1.0, dist)
        return True, score, 0.0
    if measured < lo:
        over = (lo - measured) / span
    else:
        over = (measured - hi) / span
    score = max(0.0, 70.0 - 70.0 * min(over, 1.5) / 1.5)
    return False, score, over


def _severity_from_distance(over: float) -> str:
    if over >= 1.0:
        return "P0"
    if over >= 0.4:
        return "P1"
    return "P2"


def _parse_linked_error(metric: dict[str, Any]) -> Optional[str]:
    if metric.get("linked_error_id"):
        return str(metric["linked_error_id"])
    notes = str(metric.get("notes") or "")
    marker = "[linked_error_id="
    if marker in notes:
        rest = notes.split(marker, 1)[1]
        return rest.split("]", 1)[0].strip() or None
    return None


class PoseScorer:
    """Score user pose against published benchmark metrics (heuristic)."""

    def score(
        self,
        pose_json: dict[str, Any] | str | Path,
        benchmark_package: dict[str, Any],
        *,
        error_catalog: Optional[dict[str, dict[str, Any]]] = None,
        problem_to_drills: Optional[dict[str, list[str]]] = None,
        max_problems: int = 3,
    ) -> ScoreResult:
        pose = _load_pose(pose_json)
        frames = list(pose.get("frames") or [])
        status = str(benchmark_package.get("verification_status") or "")
        kind = benchmark_kind_for_status(status)
        source = str(benchmark_package.get("source") or "")
        banner = str(benchmark_package.get("banner") or "")
        if kind == "synthetic_demo" and SYNTHETIC_BANNER not in banner:
            banner = SYNTHETIC_BANNER
        if kind == "literature_cited" and LITERATURE_BANNER not in banner:
            banner = LITERATURE_BANNER

        error_catalog = error_catalog or {}
        problem_to_drills = problem_to_drills or {}
        err_title = {
            ref.get("id"): ref.get("title") or ref.get("id")
            for ref in (benchmark_package.get("common_error_refs") or [])
            if isinstance(ref, dict) and ref.get("id")
        }
        for code, meta in error_catalog.items():
            err_title.setdefault(code, meta.get("title") or code)

        metrics_out: list[MetricEvidence] = []
        dim_scores: dict[str, float] = {}
        problem_candidates: list[ProblemHit] = []

        for m in benchmark_package.get("metrics") or []:
            if not isinstance(m, dict) or not m.get("id"):
                continue
            mid = str(m["id"])
            measured = measure_metric(mid, frames)
            rmin = m.get("range_min")
            rmax = m.get("range_max")
            if rmin is not None:
                rmin = float(rmin)
            if rmax is not None:
                rmax = float(rmax)
            in_range, score, over = _score_against_range(measured, rmin, rmax)
            linked = _parse_linked_error(m)
            ev = MetricEvidence(
                metric_id=mid,
                name=str(m.get("name") or mid),
                measured=None if measured is None else round(float(measured), 4),
                range_min=rmin,
                range_max=rmax,
                in_range=in_range,
                score=score,
                unit=m.get("unit"),
                linked_error_id=linked,
                notes=m.get("notes"),
            )
            metrics_out.append(ev)
            dim_scores[mid] = score
            if not in_range and linked:
                sev = _severity_from_distance(over)
                problem_candidates.append(
                    ProblemHit(
                        error_code=linked,
                        title=str(err_title.get(linked) or linked),
                        severity=sev,
                        metric_id=mid,
                        evidence={
                            "metric_id": mid,
                            "measured": ev.measured,
                            "range_min": rmin,
                            "range_max": rmax,
                            "distance_ratio": round(over, 3),
                        },
                        drill_codes=list(problem_to_drills.get(linked) or []),
                    )
                )

        # Deduplicate by error_code keeping worst severity
        by_code: dict[str, ProblemHit] = {}
        for p in problem_candidates:
            prev = by_code.get(p.error_code)
            if prev is None or SEVERITY_ORDER[p.severity] < SEVERITY_ORDER[prev.severity]:
                by_code[p.error_code] = p
        ranked = sorted(
            by_code.values(),
            key=lambda p: (SEVERITY_ORDER[p.severity], -float(p.evidence.get("distance_ratio") or 0)),
        )[: max(0, max_problems)]

        # Fallback: if out-of-range but no linked errors, map from common_error_refs order
        if not ranked:
            failed = [m for m in metrics_out if not m.in_range]
            refs = [
                r.get("id")
                for r in (benchmark_package.get("common_error_refs") or [])
                if isinstance(r, dict) and r.get("id")
            ]
            for i, mid_fail in enumerate(failed[:max_problems]):
                code = refs[i] if i < len(refs) else f"metric_fail_{mid_fail.metric_id}"
                ranked.append(
                    ProblemHit(
                        error_code=str(code),
                        title=str(err_title.get(code) or code),
                        severity="P1",
                        metric_id=mid_fail.metric_id,
                        evidence=mid_fail.to_dict(),
                        drill_codes=list(problem_to_drills.get(str(code)) or []),
                    )
                )

        overall = (
            sum(dim_scores.values()) / len(dim_scores) if dim_scores else 0.0
        )
        explainable = [
            {
                "metric_id": m.metric_id,
                "measured": m.measured,
                "range_min": m.range_min,
                "range_max": m.range_max,
                "in_range": m.in_range,
                "score": round(m.score, 1),
            }
            for m in metrics_out
        ]
        return ScoreResult(
            overall_score=overall,
            dimension_scores=dim_scores,
            metrics=metrics_out,
            problems=ranked,
            benchmark_kind=kind,
            verification_status=status,
            source=source,
            banner=banner,
            benchmark_version_label=str(benchmark_package.get("version") or "") or None,
            explainable=explainable,
        )
