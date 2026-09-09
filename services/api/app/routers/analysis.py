"""Honest NOT_IMPLEMENTED analysis endpoints — no mock scores."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AnalysisJob, BadmintonSkill, TrainingVideo, User
from app.services.benchmark_pkg import find_published_version
from app.schemas import AnalysisJobOut, AnalysisJobRequest, AnalysisNotImplemented

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _job_out(job: AnalysisJob) -> AnalysisJobOut:
    return AnalysisJobOut(
        id=job.id,
        video_id=job.video_id,
        skill_id=job.skill_id,
        benchmark_version_id=job.benchmark_version_id,
        status=job.status,
        scoring_status=job.scoring_status,
        error_code=job.error_code,
        message=job.message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _user_owns_job(db: Session, job: AnalysisJob, user: User) -> bool:
    """Jobs are scoped via linked TrainingVideo owner."""
    if not job.video_id:
        return False
    video = db.get(TrainingVideo, job.video_id)
    return bool(video and video.user_id == user.id)


@router.post("/jobs", response_model=AnalysisNotImplemented)
def create_analysis_job(
    body: AnalysisJobRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Direct analysis without upload is not supported in V1.
    Prefer POST /videos/upload (precheck → store → analysis_job not_implemented).
    """
    response.status_code = 501
    extra = ""
    skill = db.get(BadmintonSkill, body.skill_id)
    if skill and find_published_version(db, skill.id) is None:
        extra = " awaiting_published_benchmark。"
    return AnalysisNotImplemented(
        code="ANALYSIS_NOT_IMPLEMENTED",
        message=(
            "视频姿态分析尚未实现。请先走拍摄引导 → 录制/上传（POST /videos/upload）；"
            "上传成功后会创建 analysis_job，状态为 not_implemented / ANALYSIS_NOT_IMPLEMENTED，"
            "不会返回动作评分。禁止模拟分数或伪 AI 结果。"
            + extra
        ),
        skill_id=body.skill_id,
    )


@router.get("/jobs", response_model=list[AnalysisJobOut])
def list_analysis_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List current user's analysis jobs (newest first). No scores."""
    rows = (
        db.query(AnalysisJob)
        .join(TrainingVideo, AnalysisJob.video_id == TrainingVideo.id)
        .filter(TrainingVideo.user_id == user.id)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        .all()
    )
    return [_job_out(j) for j in rows]


@router.get("/jobs/{job_id}", response_model=AnalysisJobOut)
def get_analysis_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.get(AnalysisJob, job_id)
    if not job or not _user_owns_job(db, job, user):
        raise HTTPException(status_code=404, detail="任务不存在")
    return _job_out(job)
