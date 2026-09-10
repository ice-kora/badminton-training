"""Persist scoring results after pose extraction when a published benchmark exists."""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    AnalysisJob,
    CommonError,
    Drill,
    PoseAnalysis,
    PoseProblem,
    ProblemToDrill,
    TrainingScore,
    TrainingVideo,
    User,
)
from app.services.benchmark_pkg import (
    LITERATURE_BANNER,
    SYNTHETIC_BANNER,
    find_published_version,
    package_dict_from_version,
)
from app.services.pose.runner import SCORING_CODE
from app.services.scoring.pose_scorer import PoseScorer
from app.services.scoring.stage_timeline import timeline_from_package

logger = logging.getLogger(__name__)


def persist_stage_timeline(
    db: Session,
    *,
    video: TrainingVideo,
    pose: PoseAnalysis,
    package: Optional[dict] = None,
) -> Optional[dict]:
    """Compute heuristic stage timeline and store on PoseAnalysis."""
    pkg = package
    if pkg is None:
        published = None
        if pose.job_id:
            job = db.get(AnalysisJob, pose.job_id)
            if job and job.benchmark_version_id:
                from app.models import BenchmarkVersion

                published = db.get(BenchmarkVersion, job.benchmark_version_id)
        if published is None:
            published = find_published_version(db, video.skill_id)
        if published is None:
            return None
        pkg = package_dict_from_version(published)
    if not pose.keypoint_path or not (pkg.get("stages") or []):
        return None
    try:
        timeline = timeline_from_package(pose.keypoint_path, pkg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("stage timeline failed video=%s: %s", video.id, exc)
        return None
    pose.stage_timeline_json = json.dumps(timeline, ensure_ascii=False)
    db.flush()
    return timeline


def _error_catalog(db: Session) -> dict[str, dict]:
    rows = db.query(CommonError).filter(CommonError.code.isnot(None)).all()
    return {e.code: {"title": e.title, "id": e.id, "description": e.description} for e in rows if e.code}


def _problem_to_drills(db: Session) -> dict[str, list[str]]:
    rows = (
        db.query(CommonError.code, Drill.code)
        .join(ProblemToDrill, ProblemToDrill.error_id == CommonError.id)
        .join(Drill, Drill.id == ProblemToDrill.drill_id)
        .filter(CommonError.code.isnot(None), Drill.code.isnot(None))
        .all()
    )
    out: dict[str, list[str]] = {}
    for err_code, drill_code in rows:
        out.setdefault(str(err_code), []).append(str(drill_code))
    return out


def _drill_rows_by_code(db: Session, codes: list[str]) -> list[Drill]:
    if not codes:
        return []
    return db.query(Drill).filter(Drill.code.in_(codes)).all()


def maybe_score_after_pose(
    db: Session,
    *,
    video: TrainingVideo,
    job: AnalysisJob,
    pose: PoseAnalysis,
) -> Optional[TrainingScore]:
    """
    If a published benchmark exists for the skill, run PoseScorer and persist.
    Sets job.status=scored. Otherwise leaves ANALYSIS_NOT_IMPLEMENTED / awaiting gate.
    """
    published = None
    if job.benchmark_version_id:
        from app.models import BenchmarkVersion

        published = db.get(BenchmarkVersion, job.benchmark_version_id)
        if published is not None and published.status != "published":
            published = None
    if published is None:
        published = find_published_version(db, video.skill_id)
        if published is not None:
            job.benchmark_version_id = published.id

    if published is None:
        # Keep blocked + ANALYSIS_NOT_IMPLEMENTED; message flags awaiting gate
        job.scoring_status = "blocked"
        job.error_code = SCORING_CODE
        if "awaiting_published_benchmark" not in (job.message or ""):
            job.message = (job.message or "") + " awaiting_published_benchmark。"
        db.flush()
        return None

    pkg = package_dict_from_version(published)
    if not pose.keypoint_path:
        job.scoring_status = "blocked"
        job.error_code = SCORING_CODE
        job.message = "关键点路径缺失，无法评分。"
        db.flush()
        return None

    # Stage timeline can land even if scoring later fails
    persist_stage_timeline(db, video=video, pose=pose, package=pkg)

    user = db.get(User, video.user_id) if video.user_id else None
    handedness = getattr(user, "handedness", None) if user is not None else None

    try:
        scorer = PoseScorer()
        result = scorer.score(
            pose.keypoint_path,
            pkg,
            error_catalog=_error_catalog(db),
            problem_to_drills=_problem_to_drills(db),
            max_problems=3,
            handedness=handedness,
        )
    except Exception as exc:
        logger.exception("scoring failed video=%s job=%s", video.id, job.id)
        job.scoring_status = "blocked"
        job.error_code = SCORING_CODE
        job.message = f"评分失败: {exc}。关键点已保留。"
        db.flush()
        return None

    # Upsert training_score
    existing = (
        db.query(TrainingScore).filter(TrainingScore.video_id == video.id).one_or_none()
    )
    if existing is None:
        existing = TrainingScore(video_id=video.id)
        db.add(existing)
    existing.job_id = job.id
    existing.pose_analysis_id = pose.id
    existing.benchmark_version_id = published.id
    existing.overall_score = result.overall_score
    existing.dimension_scores_json = json.dumps(result.dimension_scores, ensure_ascii=False)
    existing.evidence_json = json.dumps(result.explainable, ensure_ascii=False)
    existing.benchmark_kind = result.benchmark_kind
    existing.verification_status = result.verification_status
    existing.source = result.source
    if result.banner:
        existing.banner = result.banner
    elif result.benchmark_kind == "synthetic_demo":
        existing.banner = SYNTHETIC_BANNER
    elif result.benchmark_kind == "literature_cited":
        existing.banner = LITERATURE_BANNER
    else:
        existing.banner = None
    existing.result_json = json.dumps(result.to_dict(), ensure_ascii=False)
    db.flush()

    # V2: stage timeline boundaries on pose analysis
    persist_stage_timeline(db, video=video, pose=pose, package=pkg)

    # Replace problems
    for old in list(existing.problems or []):
        db.delete(old)
    db.flush()

    for p in result.problems:
        drills = _drill_rows_by_code(db, p.drill_codes)
        drill_payload = [
            {"id": d.id, "code": d.code, "name": d.name} for d in drills
        ]
        err = (
            db.query(CommonError)
            .filter(CommonError.code == p.error_code)
            .one_or_none()
        )
        db.add(
            PoseProblem(
                score_id=existing.id,
                error_id=err.id if err else None,
                error_code=p.error_code,
                title=p.title,
                severity=p.severity,
                metric_id=p.metric_id,
                evidence_json=json.dumps(p.evidence, ensure_ascii=False),
                drill_codes_json=json.dumps(p.drill_codes, ensure_ascii=False),
                drills_json=json.dumps(drill_payload, ensure_ascii=False),
            )
        )

    job.status = "scored"
    job.scoring_status = "scored"
    job.error_code = None
    banner_note = ""
    if result.benchmark_kind == "synthetic_demo":
        banner_note = f" 【{SYNTHETIC_BANNER}】"
    elif result.benchmark_kind == "literature_cited":
        banner_note = f" 【{LITERATURE_BANNER}】"
    job.message = (
        f"scored overall={result.overall_score:.1f} "
        f"problems={len(result.problems)} "
        f"benchmark={published.version_label} kind={result.benchmark_kind}."
        + banner_note
    )
    db.flush()
    return existing
