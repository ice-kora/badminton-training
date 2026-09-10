"""Serialize TrainingScore / PoseProblem rows for API responses."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import PoseProblem, TrainingScore
from app.schemas import PoseProblemOut, TrainingScoreOut
from app.services.benchmark_pkg import LITERATURE_BANNER, SYNTHETIC_BANNER

_SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


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


def _sort_problems(problems: list[PoseProblemOut]) -> list[PoseProblemOut]:
    return sorted(
        problems,
        key=lambda p: (_SEVERITY_RANK.get(p.severity or "P2", 9), p.error_code or ""),
    )


def derive_primary_issue(
    problems: list[PoseProblemOut],
) -> Optional[PoseProblemOut]:
    ordered = _sort_problems(problems)
    return ordered[0] if ordered else None


def derive_cta_drill(
    problems: list[PoseProblemOut],
    primary: Optional[PoseProblemOut] = None,
) -> Optional[dict[str, Any]]:
    """Pick first real drill from primary issue, else any problem drills_json."""
    candidates: list[PoseProblemOut] = []
    if primary is not None:
        candidates.append(primary)
    for p in _sort_problems(problems):
        if primary is None or p.error_code != primary.error_code:
            candidates.append(p)
    for p in candidates:
        drills = p.drills or []
        if drills:
            d0 = drills[0]
            if isinstance(d0, dict):
                media = d0.get("demo_media_url") or d0.get("demo_gif_url")
                return {
                    "id": d0.get("id"),
                    "code": d0.get("code"),
                    "name": d0.get("name") or d0.get("code") or "推荐练习",
                    "demo_media_url": media,
                    "demo_gif_url": d0.get("demo_gif_url") or media,
                }
        codes = p.drill_codes or []
        if codes:
            code = codes[0]
            return {"id": None, "code": code, "name": code}
    return None


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
                drills=p.get("drills") or [],
                drill_codes=p.get("drill_codes") or [],
            )
            for p in result["problems"][:3]
        ]
    problems = _sort_problems(problems)[:3]
    primary = derive_primary_issue(problems)
    cta = derive_cta_drill(problems, primary)
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
        primary_issue=primary,
        cta_drill=cta,
        benchmark_kind=row.benchmark_kind or "synthetic_demo",
        verification_status=row.verification_status,
        source=row.source,
        banner=banner,
        benchmark_version_id=row.benchmark_version_id,
        benchmark_version_label=result.get("benchmark_version_label"),
        explainable=result.get("explainable") or _loads(row.evidence_json, []),
    )
