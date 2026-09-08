"""Honest NOT_IMPLEMENTED analysis endpoints — no mock scores."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AnalysisJob, TrainingVideo, User
from app.schemas import AnalysisJobOut, AnalysisJobRequest, AnalysisNotImplemented

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/jobs", response_model=AnalysisNotImplemented)
def create_analysis_job(body: AnalysisJobRequest, response: Response):
    """
    Direct analysis without upload is not supported in V1.
    Prefer POST /videos/upload (precheck → store → analysis_job not_implemented).
    """
    response.status_code = 501
    return AnalysisNotImplemented(
        code="ANALYSIS_NOT_IMPLEMENTED",
        message=(
            "视频姿态分析尚未实现。请先走拍摄引导 → 录制/上传（POST /videos/upload）；"
            "上传成功后会创建 analysis_job，状态为 not_implemented / ANALYSIS_NOT_IMPLEMENTED，"
            "不会返回动作评分。禁止模拟分数或伪 AI 结果。"
        ),
        skill_id=body.skill_id,
    )


@router.get("/jobs/{job_id}", response_model=AnalysisJobOut)
def get_analysis_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.video_id:
        video = db.get(TrainingVideo, job.video_id)
        if video and video.user_id != user.id:
            raise HTTPException(status_code=404, detail="任务不存在")
    return AnalysisJobOut(
        id=job.id,
        video_id=job.video_id,
        skill_id=job.skill_id,
        status=job.status,
        error_code=job.error_code,
        message=job.message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
