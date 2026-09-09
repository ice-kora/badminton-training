"""Serialize TrainingScore / PoseProblem rows for API responses."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import PoseProblem, TrainingScore
from app.schemas import PoseProblemOut, TrainingScoreOut
from app.services.benchmark_pkg import LITERATURE_BANNER, SYNTHETIC_BANNER


def _loads(raw: Optional[str], default: Any):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def score_for_video(db: Session, video_id: int) -> Optional[TrainingScore]:
    return (
        db.query(TrainingScore)
        .filter(TrainingScore.video_id == video_id)
        .one_or_none()
    )


def problem_out(row: PoseProblem) -> PoseProblemOut:
    return PoseProblemOut(
        error_code=row.error_code,
        title=row.title,
        severity=row.severity,
        metric_id=row.metric_id,
        evidence=_loads(row.evidence_json, {}),
        drills=_loads(row.drills_json, []),
        drill_codes=_loads(row.drill_codes_json, []),
    )


def score_out(row: TrainingScore) -> TrainingScoreOut:
    result = _loads(row.result_json, {})
    problems = [problem_out(p) for p in (row.problems or [])][:3]
    if not problems and result.get("problems"):
        problems = [
            PoseProblemOut(
                error_code=p.get("error_code") or "unknown",
                title=p.get("title") or "",
                severity=p.get("severity") or "P1",
                metric_id=p.get("metric_id"),
                evidence=p.get("evidence") or {},
                drills=[],
                drill_codes=p.get("drill_codes") or [],
            )
            for p in result["problems"][:3]
        ]
    banner = row.banner
    if row.benchmark_kind == "synthetic_demo" and not banner:
        banner = SYNTHETIC_BANNER
    if row.benchmark_kind == "literature_cited" and not banner:
        banner = LITERATURE_BANNER
    return TrainingScoreOut(
        overall_score=float(row.overall_score or 0.0),
        dimension_scores=_loads(row.dimension_scores_json, {})
        or result.get("dimension_scores")
        or {},
        metrics=result.get("metrics") or _loads(row.evidence_json, []),
        problems=problems,
        benchmark_kind=row.benchmark_kind or "synthetic_demo",
        verification_status=row.verification_status,
        source=row.source,
        banner=banner,
        benchmark_version_id=row.benchmark_version_id,
        benchmark_version_label=result.get("benchmark_version_label"),
        explainable=result.get("explainable") or _loads(row.evidence_json, []),
    )
