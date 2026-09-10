"""Authenticated /me UX comfort endpoints — real scores only, no mocks."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import AnalysisJob, BadmintonSkill, TrainingScore, TrainingVideo, User
from app.schemas import (
    NextFocusOut,
    NextFocusSkillOut,
    ScoreHistoryItemOut,
    UserProfileOut,
    UserProfileUpdate,
)
from app.services.scoring.serialize import score_out

router = APIRouter(prefix="/me", tags=["me"])

DEFAULT_BEGINNER_SKILL_CODE = "forehand_clear"


def _skill_out(skill: BadmintonSkill) -> NextFocusSkillOut:
    return NextFocusSkillOut(id=skill.id, code=skill.code, name=skill.name)


def _beginner_skill(db: Session) -> Optional[BadmintonSkill]:
    skill = (
        db.query(BadmintonSkill)
        .filter(BadmintonSkill.code == DEFAULT_BEGINNER_SKILL_CODE)
        .one_or_none()
    )
    if skill is not None:
        return skill
    return db.query(BadmintonSkill).order_by(BadmintonSkill.id.asc()).first()


def _empty_next_focus(db: Session) -> NextFocusOut:
    skill = _beginner_skill(db)
    if skill is None:
        return NextFocusOut(
            empty=True,
            title="今天优先改 1 件事",
            cta_label="去学动作",
            cta_path="/pages/skills/tree",
            message="还没有评分记录。先从技术库选一个动作，按拍摄引导录一段。",
        )
    return NextFocusOut(
        empty=True,
        title="今天优先改 1 件事",
        skill=_skill_out(skill),
        cta_label=f"先拍一段{skill.name}",
        cta_path=f"/pages/filming/guide?skill_id={skill.id}",
        message=(
            "还没有评分记录。按拍摄引导录一段，拿到真实问题后再练。"
            "不会伪造分数。"
        ),
    )


@router.get("/next-focus", response_model=NextFocusOut)
def next_focus(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Latest scored job → primary_issue + ≤3 issues + cta_drill; else beginner CTA."""
    row = (
        db.query(TrainingScore, TrainingVideo, AnalysisJob, BadmintonSkill)
        .join(TrainingVideo, TrainingScore.video_id == TrainingVideo.id)
        .outerjoin(AnalysisJob, TrainingScore.job_id == AnalysisJob.id)
        .join(BadmintonSkill, TrainingVideo.skill_id == BadmintonSkill.id)
        .options(joinedload(TrainingScore.problems))
        .filter(TrainingVideo.user_id == user.id)
        .order_by(TrainingScore.created_at.desc(), TrainingScore.id.desc())
        .first()
    )
    if row is None:
        # Fallback: scored job without TrainingScore join miss — still empty
        scored_job = (
            db.query(AnalysisJob)
            .join(TrainingVideo, AnalysisJob.video_id == TrainingVideo.id)
            .filter(TrainingVideo.user_id == user.id, AnalysisJob.status == "scored")
            .order_by(AnalysisJob.updated_at.desc(), AnalysisJob.id.desc())
            .first()
        )
        if scored_job is None:
            return _empty_next_focus(db)
        sc = (
            db.query(TrainingScore)
            .options(joinedload(TrainingScore.problems))
            .filter(TrainingScore.video_id == scored_job.video_id)
            .one_or_none()
        )
        if sc is None:
            return _empty_next_focus(db)
        video = db.get(TrainingVideo, scored_job.video_id)
        skill = db.get(BadmintonSkill, scored_job.skill_id) if scored_job.skill_id else None
        payload = score_out(sc)
        primary = payload.primary_issue
        sentence = (
            f"优先改：{primary.title}"
            if primary and primary.title
            else "已有评分，继续针对问题练习"
        )
        return NextFocusOut(
            empty=False,
            title="今天优先改 1 件事",
            primary_issue=primary,
            issues=list(payload.problems)[:3],
            cta_drill=payload.cta_drill,
            skill=_skill_out(skill) if skill else None,
            last_score=float(payload.overall_score),
            video_id=video.id if video else scored_job.video_id,
            job_id=scored_job.id,
            benchmark_kind=payload.benchmark_kind,
            banner=payload.banner,
            cta_label="去练推荐练习" if payload.cta_drill else "再拍一段对比",
            cta_path=(
                f"/pages/filming/guide?skill_id={skill.id}"
                if skill
                else "/pages/skills/tree"
            ),
            message=sentence,
        )

    sc, video, job, skill = row
    # Ensure problems relationship loaded for score_out
    _ = list(sc.problems or [])
    payload = score_out(sc)
    primary = payload.primary_issue
    sentence = (
        f"优先改：{primary.title}"
        if primary and primary.title
        else "已有评分，继续针对问题练习"
    )
    drill = payload.cta_drill
    if drill and drill.get("name"):
        cta_label = f"去练：{drill['name']}"
    else:
        cta_label = "再拍一段对比"
    return NextFocusOut(
        empty=False,
        title="今天优先改 1 件事",
        primary_issue=primary,
        issues=list(payload.problems)[:3],
        cta_drill=drill,
        skill=_skill_out(skill),
        last_score=float(payload.overall_score),
        video_id=video.id,
        job_id=job.id if job else sc.job_id,
        benchmark_kind=payload.benchmark_kind,
        banner=payload.banner,
        cta_label=cta_label,
        cta_path=f"/pages/filming/guide?skill_id={skill.id}",
        message=sentence,
    )


@router.get("/score-history", response_model=list[ScoreHistoryItemOut])
def score_history(
    skill: Optional[int] = Query(None, alias="skill", description="skill_id filter"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recent real TrainingScore rows for growth tab — no mock values."""
    q = (
        db.query(TrainingScore, TrainingVideo, BadmintonSkill)
        .join(TrainingVideo, TrainingScore.video_id == TrainingVideo.id)
        .join(BadmintonSkill, TrainingVideo.skill_id == BadmintonSkill.id)
        .options(joinedload(TrainingScore.problems))
        .filter(TrainingVideo.user_id == user.id)
    )
    if skill is not None:
        q = q.filter(TrainingVideo.skill_id == skill)
    rows = q.order_by(TrainingScore.created_at.desc(), TrainingScore.id.desc()).limit(limit).all()
    out: list[ScoreHistoryItemOut] = []
    for sc, video, sk in rows:
        _ = list(sc.problems or [])
        payload = score_out(sc)
        primary = payload.primary_issue
        out.append(
            ScoreHistoryItemOut(
                video_id=video.id,
                job_id=sc.job_id,
                skill_id=sk.id,
                skill_code=sk.code,
                skill_name=sk.name,
                overall_score=float(payload.overall_score),
                primary_issue_title=primary.title if primary else None,
                cta_drill=payload.cta_drill,
                benchmark_kind=payload.benchmark_kind,
                banner=payload.banner,
                created_at=sc.created_at,
            )
        )
    return out


def _normalize_handedness(value: str | None) -> str:
    return "left" if value == "left" else "right"


def _subscribe_opt_in(user: User) -> bool:
    return bool(getattr(user, "subscribe_opt_in", 0) or 0)


@router.get("/profile", response_model=UserProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    hand = getattr(user, "handedness", None) or "right"
    return UserProfileOut(
        user_id=user.id,
        nickname=user.nickname,
        handedness=_normalize_handedness(hand),
        level=user.level,
        subscribe_opt_in=_subscribe_opt_in(user),
    )


@router.patch("/profile", response_model=UserProfileOut)
def patch_profile(
    body: UserProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.handedness is not None:
        user.handedness = _normalize_handedness(body.handedness)
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.level is not None:
        user.level = body.level
    if body.subscribe_opt_in is not None:
        # Preference scaffold only — does not claim WeChat push works.
        user.subscribe_opt_in = 1 if body.subscribe_opt_in else 0
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserProfileOut(
        user_id=user.id,
        nickname=user.nickname,
        handedness=_normalize_handedness(getattr(user, "handedness", None)),
        level=user.level,
        subscribe_opt_in=_subscribe_opt_in(user),
    )
