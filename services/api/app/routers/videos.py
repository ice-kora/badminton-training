"""Video precheck + upload pipeline (local storage, no pose scoring)."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import AnalysisJob, BadmintonSkill, FilmingGuide, TrainingVideo, User
from app.schemas import (
    AnalysisJobOut,
    PrecheckReportOut,
    TrainingVideoOut,
    VideoUploadOut,
)
from app.services.precheck import run_precheck

router = APIRouter(tags=["videos"])

ANALYSIS_MSG = (
    "视频姿态分析尚未实现。上传仅完成质量预检与元数据入库；"
    "禁止返回模拟分数或伪 AI 分析结果。"
)


def _uploads_root() -> Path:
    settings = get_settings()
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _parse_json_form(raw: Optional[str], field: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"{field} 不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail=f"{field} 须为 JSON 对象")
    return data


def _guide_for_skill(db: Session, skill_id: int) -> Optional[FilmingGuide]:
    return (
        db.query(FilmingGuide)
        .filter(FilmingGuide.skill_id == skill_id)
        .order_by(FilmingGuide.id.asc())
        .first()
    )


def _video_out(row: TrainingVideo) -> TrainingVideoOut:
    precheck = None
    if row.precheck_json:
        try:
            precheck = json.loads(row.precheck_json)
        except json.JSONDecodeError:
            precheck = None
    return TrainingVideoOut(
        id=row.id,
        user_id=row.user_id,
        skill_id=row.skill_id,
        filename=row.filename,
        duration_ms=row.duration_ms,
        width=row.width,
        height=row.height,
        orientation=row.orientation,
        size_bytes=row.size_bytes,
        precheck=precheck,
        created_at=row.created_at,
    )


def _job_out(row: AnalysisJob) -> AnalysisJobOut:
    return AnalysisJobOut(
        id=row.id,
        video_id=row.video_id,
        skill_id=row.skill_id,
        status=row.status,
        error_code=row.error_code,
        message=row.message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _save_upload_temp(file: UploadFile, suffix: str = ".mp4") -> Path:
    uploads = _uploads_root()
    tmp_dir = uploads / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    dest = tmp_dir / name
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return dest


@router.post("/videos/precheck", response_model=PrecheckReportOut)
async def precheck_video(
    file: UploadFile = File(...),
    skill_id: int = Form(...),
    client_checklist_json: Optional[str] = Form(None),
    frame_coverage_hints_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run server precheck without persisting (auth required)."""
    _ = user
    skill = db.get(BadmintonSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    guide = _guide_for_skill(db, skill_id)
    checklist = _parse_json_form(client_checklist_json, "client_checklist_json")
    hints = _parse_json_form(frame_coverage_hints_json, "frame_coverage_hints_json")

    suffix = Path(file.filename or "clip.mp4").suffix or ".mp4"
    tmp = _save_upload_temp(file, suffix=suffix)
    try:
        report = run_precheck(
            tmp, guide=guide, client_checklist=checklist, client_hints=hints
        )
    finally:
        tmp.unlink(missing_ok=True)
    return PrecheckReportOut(**report)


@router.post("/videos/upload", response_model=VideoUploadOut)
async def upload_video(
    file: UploadFile = File(...),
    skill_id: int = Form(...),
    client_checklist_json: Optional[str] = Form(None),
    frame_coverage_hints_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Precheck → on fail 400 with checks; on pass store file + training_video
    + analysis_job(status=not_implemented, error_code=ANALYSIS_NOT_IMPLEMENTED).
    """
    skill = db.get(BadmintonSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    guide = _guide_for_skill(db, skill_id)
    checklist = _parse_json_form(client_checklist_json, "client_checklist_json")
    hints = _parse_json_form(frame_coverage_hints_json, "frame_coverage_hints_json")

    original_name = file.filename or "clip.mp4"
    suffix = Path(original_name).suffix or ".mp4"
    tmp = _save_upload_temp(file, suffix=suffix)
    try:
        report = run_precheck(
            tmp, guide=guide, client_checklist=checklist, client_hints=hints
        )
        if not report["passed"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "PRECHECK_FAILED",
                    "message": "拍摄质量预检未通过，请按提示重拍",
                    "precheck": report,
                },
            )

        probe = report.get("probe") or {}
        video_uuid = uuid.uuid4().hex
        rel_name = f"{user.id}_{skill_id}_{video_uuid}{suffix}"
        final_path = _uploads_root() / rel_name
        shutil.move(str(tmp), str(final_path))
        tmp = final_path  # for cleanup on later failure

        video = TrainingVideo(
            user_id=user.id,
            skill_id=skill_id,
            storage_path=str(final_path),
            filename=original_name,
            duration_ms=probe.get("duration_ms"),
            width=probe.get("width"),
            height=probe.get("height"),
            orientation=probe.get("orientation"),
            size_bytes=probe.get("size_bytes"),
            precheck_json=json.dumps(report, ensure_ascii=False),
        )
        db.add(video)
        db.flush()

        job = AnalysisJob(
            video_id=video.id,
            skill_id=skill_id,
            status="not_implemented",
            error_code="ANALYSIS_NOT_IMPLEMENTED",
            message=ANALYSIS_MSG,
        )
        db.add(job)
        db.commit()
        db.refresh(video)
        db.refresh(job)
        tmp = None  # owned by storage now

        return VideoUploadOut(
            video=_video_out(video),
            analysis_job=_job_out(job),
            precheck=PrecheckReportOut(**report),
        )
    except HTTPException:
        if tmp is not None and tmp.exists() and "_tmp" in str(tmp):
            tmp.unlink(missing_ok=True)
        raise
    except Exception:
        if tmp is not None and tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    finally:
        if tmp is not None and tmp.exists() and "_tmp" in str(tmp):
            tmp.unlink(missing_ok=True)


@router.get("/videos/{video_id}", response_model=TrainingVideoOut)
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(TrainingVideo, video_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="视频不存在")
    return _video_out(row)
