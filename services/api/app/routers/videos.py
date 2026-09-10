"""Video precheck + upload + pose extract + gated scoring against published benchmarks."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session, joinedload

from app.auth import decode_token, get_current_user, get_optional_user
from app.config import get_settings
from app.database import get_db
from app.models import (
    AnalysisJob,
    BadmintonSkill,
    FilmingGuide,
    PoseAnalysis,
    TrainingVideo,
    User,
)
from app.schemas import (
    AnalysisJobOut,
    AnalysisJobSummaryOut,
    BaselineVideoSummaryOut,
    PoseExtractOut,
    PoseMetaOut,
    PoseOverlayOut,
    PosePreviewOut,
    PrecheckReportOut,
    RetestCompareOut,
    StageTimelineOut,
    TrainingVideoOut,
    VideoDetailOut,
    VideoListItemOut,
    VideoUploadOut,
)
from app.services.benchmark_pkg import (
    LITERATURE_BANNER,
    SYNTHETIC_BANNER,
    find_published_version,
    package_dict_from_version,
)
from app.services.scoring.overlay import build_overlay_json
from app.services.scoring.persist import persist_stage_timeline
from app.services.scoring.serialize import score_for_video, score_out
from app.services.scoring.stage_timeline import timeline_from_package
from app.services.pose.landmarks import POSE_LANDMARK_NAMES
from app.services.pose.null_extractor import PoseExtractorUnavailable
from app.services.pose.preview import (
    FrameOutOfRange,
    PoseNotExtracted,
    PosePreviewError,
    build_preview_json,
    render_preview_png,
)
from app.services.pose.runner import (
    SCORING_CODE,
    apply_pose_queued,
    extract_for_video,
    try_inline_extract,
)
from app.services.precheck import run_precheck

router = APIRouter(tags=["videos"])

DETAIL_NOTICE = "关键点可提取；有已发布标准库时返回评分（合成演示须展示横幅）"


def _parse_precheck(row: TrainingVideo) -> Optional[dict[str, Any]]:
    if not row.precheck_json:
        return None
    try:
        return json.loads(row.precheck_json)
    except json.JSONDecodeError:
        return None


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
        precheck=_parse_precheck(row),
        baseline_video_id=row.baseline_video_id,
        created_at=row.created_at,
    )


def _baseline_summary(db: Session, baseline: TrainingVideo) -> BaselineVideoSummaryOut:
    pose = _pose_for_video(db, baseline.id)
    return BaselineVideoSummaryOut(
        id=baseline.id,
        skill_id=baseline.skill_id,
        skill_name=_skill_name(db, baseline.skill_id),
        filename=baseline.filename,
        duration_ms=baseline.duration_ms,
        orientation=baseline.orientation,
        created_at=baseline.created_at,
        pose_extracted=pose is not None,
        pose_frame_count=pose.frame_count if pose else None,
    )


def _validate_baseline(
    db: Session, *, user: User, skill_id: int, baseline_video_id: int
) -> TrainingVideo:
    """Baseline must exist, belong to same user, and share skill_id."""
    baseline = db.get(TrainingVideo, baseline_video_id)
    if baseline is None or baseline.user_id != user.id:
        raise HTTPException(status_code=400, detail="baseline_video_id 无效或不属于当前用户")
    if baseline.skill_id != skill_id:
        raise HTTPException(
            status_code=400,
            detail="baseline_video_id 与当前 skill_id 不一致",
        )
    return baseline


def _preview_for_pose(video: TrainingVideo, pose: PoseAnalysis, frame: int) -> dict:
    return build_preview_json(
        video_id=video.id,
        keypoint_path=pose.keypoint_path,
        frame=frame,
        landmark_count=pose.landmark_count,
        extractor=pose.extractor,
    )


def _job_summary(row: AnalysisJob) -> AnalysisJobSummaryOut:
    return AnalysisJobSummaryOut(
        id=row.id,
        status=row.status,
        scoring_status=row.scoring_status,
        error_code=row.error_code,
        message=row.message,
        benchmark_version_id=row.benchmark_version_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _latest_job(jobs: list[AnalysisJob]) -> Optional[AnalysisJob]:
    if not jobs:
        return None
    return max(jobs, key=lambda j: (j.created_at, j.id))


def _skill_name(db: Session, skill_id: int) -> str:
    skill = db.get(BadmintonSkill, skill_id)
    return skill.name if skill else f"技能#{skill_id}"


def _job_out(row: AnalysisJob, db: Optional[Session] = None) -> AnalysisJobOut:
    score = None
    kind = None
    if db is not None and row.video_id:
        sc = score_for_video(db, row.video_id)
        if sc is not None:
            score = score_out(sc)
            kind = sc.benchmark_kind
    return AnalysisJobOut(
        id=row.id,
        video_id=row.video_id,
        skill_id=row.skill_id,
        benchmark_version_id=row.benchmark_version_id,
        status=row.status,
        scoring_status=row.scoring_status,
        error_code=row.error_code,
        message=row.message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        score=score,
        benchmark_kind=kind,
    )



def _loads_timeline(pose: Optional[PoseAnalysis]) -> Optional[dict]:
    if pose is None or not pose.stage_timeline_json:
        return None
    try:
        data = json.loads(pose.stage_timeline_json)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _ensure_timeline(
    db: Session, video: TrainingVideo, pose: PoseAnalysis
) -> Optional[dict]:
    existing = _loads_timeline(pose)
    if existing and existing.get("segments"):
        return existing
    return persist_stage_timeline(db, video=video, pose=pose)


def _published_package(db: Session, video: TrainingVideo, job: Optional[AnalysisJob]):
    published = None
    if job and job.benchmark_version_id:
        from app.models import BenchmarkVersion

        published = db.get(BenchmarkVersion, job.benchmark_version_id)
        if published is not None and published.status != "published":
            published = None
    if published is None:
        published = find_published_version(db, video.skill_id)
    if published is None:
        return None, None
    return published, package_dict_from_version(published)

def _pose_for_video(db: Session, video_id: int) -> Optional[PoseAnalysis]:
    return (
        db.query(PoseAnalysis).filter(PoseAnalysis.video_id == video_id).one_or_none()
    )


def _pose_meta(
    video_id: int,
    pose: Optional[PoseAnalysis],
    job: Optional[AnalysisJob] = None,
) -> PoseMetaOut:
    if pose is None:
        return PoseMetaOut(
            video_id=video_id,
            extracted=False,
            landmark_names=[],
            job_status=job.status if job else None,
            scoring_status=job.scoring_status if job else "blocked",
            notice="关键点尚未提取；评分未开放",
        )
    return PoseMetaOut(
        video_id=video_id,
        extracted=True,
        frame_count=pose.frame_count,
        fps=pose.fps,
        extractor=pose.extractor,
        keypoint_path=pose.keypoint_path,
        landmark_names=list(POSE_LANDMARK_NAMES)[: pose.landmark_count or 33],
        sample_stride=pose.sample_stride,
        max_seconds=pose.max_seconds,
        landmark_count=pose.landmark_count,
        job_status=job.status if job else "pose_extracted",
        scoring_status=job.scoring_status if job else "blocked",
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


def _owned_video(db: Session, video_id: int, user: User) -> TrainingVideo:
    row = (
        db.query(TrainingVideo)
        .options(joinedload(TrainingVideo.analysis_jobs))
        .filter(TrainingVideo.id == video_id)
        .first()
    )
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="视频不存在")
    return row


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
        settings = get_settings()
        report = run_precheck(
            tmp,
            guide=guide,
            client_checklist=checklist,
            client_hints=hints,
            relax_orientation=settings.precheck_relax_orientation,
        )
    finally:
        tmp.unlink(missing_ok=True)
    return PrecheckReportOut(**report)


@router.post("/videos/upload", response_model=VideoUploadOut)
async def upload_video(
    file: UploadFile = File(...),
    skill_id: int = Form(...),
    baseline_video_id: Optional[int] = Form(None),
    client_checklist_json: Optional[str] = Form(None),
    frame_coverage_hints_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Precheck → store file + training_video + analysis_job(status=queued).
    Optional baseline_video_id links a visual retest (same user + skill).
    Default: leave queued for background worker (POSE_EXTRACT_INLINE=false).
    Scoring always blocked (ANALYSIS_NOT_IMPLEMENTED).
    """
    skill = db.get(BadmintonSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    resolved_baseline_id: Optional[int] = None
    if baseline_video_id is not None:
        _validate_baseline(
            db, user=user, skill_id=skill_id, baseline_video_id=baseline_video_id
        )
        resolved_baseline_id = baseline_video_id
    guide = _guide_for_skill(db, skill_id)
    checklist = _parse_json_form(client_checklist_json, "client_checklist_json")
    hints = _parse_json_form(frame_coverage_hints_json, "frame_coverage_hints_json")

    original_name = file.filename or "clip.mp4"
    suffix = Path(original_name).suffix or ".mp4"
    tmp = _save_upload_temp(file, suffix=suffix)
    try:
        settings = get_settings()
        report = run_precheck(
            tmp,
            guide=guide,
            client_checklist=checklist,
            client_hints=hints,
            relax_orientation=settings.precheck_relax_orientation,
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
        tmp = final_path

        video = TrainingVideo(
            user_id=user.id,
            skill_id=skill_id,
            baseline_video_id=resolved_baseline_id,
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

        published = find_published_version(db, skill_id)
        bv_id = published.id if published else None
        job = AnalysisJob(
            video_id=video.id,
            skill_id=skill_id,
            benchmark_version_id=bv_id,
            status="queued",
            scoring_status="blocked",
            error_code=SCORING_CODE,
            message="",
        )
        apply_pose_queued(job)
        if bv_id:
            job.message = (
                (job.message or "")
                + f" benchmark_version_id={bv_id} 已记录；提取后将尝试评分。"
            )
        db.add(job)
        db.commit()
        db.refresh(video)
        db.refresh(job)
        tmp = None

        # Optional sync extract (POSE_EXTRACT_INLINE=true). Default queue mode leaves queued.
        try_inline_extract(db, video, job)
        db.refresh(job)

        return VideoUploadOut(
            video=_video_out(video),
            analysis_job=_job_out(job, db),
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


@router.get("/videos", response_model=list[VideoListItemOut])
def list_videos(
    skill_id: Optional[int] = Query(None, description="Filter history by skill"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List current user's uploaded videos (newest first) with latest job summary."""
    q = (
        db.query(TrainingVideo)
        .options(joinedload(TrainingVideo.analysis_jobs))
        .filter(TrainingVideo.user_id == user.id)
    )
    if skill_id is not None:
        q = q.filter(TrainingVideo.skill_id == skill_id)
    rows = q.order_by(TrainingVideo.created_at.desc(), TrainingVideo.id.desc()).all()
    items: list[VideoListItemOut] = []
    for row in rows:
        latest = _latest_job(list(row.analysis_jobs or []))
        items.append(
            VideoListItemOut(
                id=row.id,
                skill_id=row.skill_id,
                skill_name=_skill_name(db, row.skill_id),
                duration_ms=row.duration_ms,
                orientation=row.orientation,
                baseline_video_id=row.baseline_video_id,
                created_at=row.created_at,
                latest_job=_job_summary(latest) if latest else None,
            )
        )
    return items


@router.get("/videos/{video_id}", response_model=VideoDetailOut)
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Video detail + precheck summary + linked analysis jobs (owner only)."""
    row = _owned_video(db, video_id, user)
    jobs = sorted(
        list(row.analysis_jobs or []),
        key=lambda j: (j.created_at, j.id),
        reverse=True,
    )
    pose = _pose_for_video(db, row.id)
    baseline_out: Optional[BaselineVideoSummaryOut] = None
    if row.baseline_video_id:
        baseline = db.get(TrainingVideo, row.baseline_video_id)
        if baseline is not None and baseline.user_id == user.id:
            baseline_out = _baseline_summary(db, baseline)
    sc = score_for_video(db, row.id)
    score_payload = score_out(sc) if sc is not None else None
    problems = list(score_payload.problems) if score_payload else []
    kind = sc.benchmark_kind if sc is not None else None
    banner = None
    if kind == "synthetic_demo":
        banner = (sc.banner if sc is not None else None) or SYNTHETIC_BANNER
    elif kind == "literature_cited":
        banner = (sc.banner if sc is not None else None) or LITERATURE_BANNER
    notice = DETAIL_NOTICE
    if score_payload is None:
        notice = "关键点可提取；无已发布标准库时评分不开放（ANALYSIS_NOT_IMPLEMENTED / awaiting_published_benchmark）"
    elif kind == "synthetic_demo":
        notice = SYNTHETIC_BANNER
    elif kind == "literature_cited":
        notice = LITERATURE_BANNER
    stage_timeline = None
    overlay_available = False
    if pose is not None:
        overlay_available = True
        stage_timeline = _ensure_timeline(db, row, pose)
        if stage_timeline:
            db.commit()
        if kind is None and stage_timeline:
            kind = stage_timeline.get("benchmark_kind") or kind
            if kind == "synthetic_demo" and not banner:
                banner = SYNTHETIC_BANNER
            if kind == "literature_cited" and not banner:
                banner = LITERATURE_BANNER
    return VideoDetailOut(
        id=row.id,
        user_id=row.user_id,
        skill_id=row.skill_id,
        skill_name=_skill_name(db, row.skill_id),
        filename=row.filename,
        duration_ms=row.duration_ms,
        width=row.width,
        height=row.height,
        orientation=row.orientation,
        size_bytes=row.size_bytes,
        precheck=_parse_precheck(row),
        baseline_video_id=row.baseline_video_id,
        baseline=baseline_out,
        created_at=row.created_at,
        jobs=[_job_out(j, db) for j in jobs],
        pose_extracted=pose is not None,
        pose_frame_count=pose.frame_count if pose else None,
        score=score_payload,
        problems=problems,
        benchmark_kind=kind,
        scoring_banner=banner,
        stage_timeline=stage_timeline,
        overlay_available=overlay_available,
        notice=notice,
    )


@router.get("/videos/{video_id}/pose", response_model=PoseMetaOut)
def get_video_pose(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Keypoint extraction metadata — never scores."""
    row = _owned_video(db, video_id, user)
    job = _latest_job(list(row.analysis_jobs or []))
    pose = _pose_for_video(db, row.id)
    return _pose_meta(row.id, pose, job)


@router.post("/videos/{video_id}/extract-pose", response_model=PoseExtractOut)
def extract_video_pose(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run (or re-run) offline pose keypoint extraction for an owned video."""
    row = _owned_video(db, video_id, user)
    job = _latest_job(list(row.analysis_jobs or []))
    if job is None:
        published = find_published_version(db, row.skill_id)
        job = AnalysisJob(
            video_id=row.id,
            skill_id=row.skill_id,
            benchmark_version_id=published.id if published else None,
            status="queued",
            scoring_status="blocked",
            error_code=SCORING_CODE,
        )
        apply_pose_queued(job)
        db.add(job)
        db.commit()
        db.refresh(job)

    try:
        extract_for_video(db, row, job)
    except PoseExtractorUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "POSE_EXTRACTOR_UNAVAILABLE",
                "message": str(exc),
                "hint": "安装 mediapipe 或设置 POSE_EXTRACTOR=fake 后重试；"
                "也可运行 scripts/run_pose_extract.py",
            },
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "POSE_EXTRACT_FAILED", "message": str(exc)},
        ) from exc

    db.refresh(job)
    pose = _pose_for_video(db, row.id)
    return PoseExtractOut(
        video_id=row.id,
        analysis_job=_job_out(job, db),
        pose=_pose_meta(row.id, pose, job),
    )

@router.get("/videos/{video_id}/pose/preview")
def get_video_pose_preview(
    video_id: int,
    frame: int = Query(0, ge=0, description="Scrub index into stored frames (0-based)"),
    format: str = Query("json", pattern="^(json|png)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    2D skeleton preview for one stored pose frame — visualization only.

    Default JSON: normalized landmarks + MediaPipe bone edges for mini-program canvas.
    Optional `?format=png&frame=0` returns a debug PNG (no score overlay).
    """
    row = _owned_video(db, video_id, user)
    pose = _pose_for_video(db, row.id)
    if pose is None or not pose.keypoint_path:
        raise HTTPException(status_code=404, detail="关键点尚未提取")

    try:
        if format == "png":
            png = render_preview_png(
                video_id=row.id,
                keypoint_path=pose.keypoint_path,
                frame=frame,
                landmark_count=pose.landmark_count,
            )
            return Response(
                content=png,
                media_type="image/png",
                headers={"X-Pose-Preview-Notice": "keypoints_only_no_scoring"},
            )
        data = build_preview_json(
            video_id=row.id,
            keypoint_path=pose.keypoint_path,
            frame=frame,
            landmark_count=pose.landmark_count,
            extractor=pose.extractor,
        )
        return PosePreviewOut(**data)
    except FrameOutOfRange as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PoseNotExtracted as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PosePreviewError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/videos/{video_id}/retest-compare", response_model=RetestCompareOut)
def retest_compare(
    video_id: int,
    frame: int = Query(0, ge=0, description="Scrub index into stored frames (0-based)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Side-by-side skeleton preview for baseline vs current retest video.
    Visualization only — no scores / correctness / angle judgment.
    """
    current = _owned_video(db, video_id, user)
    if not current.baseline_video_id:
        raise HTTPException(status_code=400, detail="该视频未关联复测基准（baseline_video_id）")
    baseline = db.get(TrainingVideo, current.baseline_video_id)
    if baseline is None or baseline.user_id != user.id:
        raise HTTPException(status_code=404, detail="基准视频不存在")

    current_pose = _pose_for_video(db, current.id)
    baseline_pose = _pose_for_video(db, baseline.id)
    if current_pose is None or not current_pose.keypoint_path:
        raise HTTPException(status_code=404, detail="当前视频关键点尚未提取")
    if baseline_pose is None or not baseline_pose.keypoint_path:
        raise HTTPException(status_code=404, detail="基准视频关键点尚未提取")

    try:
        baseline_preview = _preview_for_pose(baseline, baseline_pose, frame)
        current_preview = _preview_for_pose(current, current_pose, frame)
        base_sc = score_for_video(db, baseline.id)
        cur_sc = score_for_video(db, current.id)
        base_out = score_out(base_sc) if base_sc is not None else None
        cur_out = score_out(cur_sc) if cur_sc is not None else None
        delta = None
        notice = "复测对比（仅骨架，非评分）"
        if base_out is not None and cur_out is not None:
            delta = round(cur_out.overall_score - base_out.overall_score, 1)
            notice = f"复测对比：分数差 {delta:+.1f}"
            if cur_out.benchmark_kind == "synthetic_demo" or (
                base_out.benchmark_kind == "synthetic_demo"
            ):
                notice += f" · {SYNTHETIC_BANNER}"
            if cur_out.benchmark_kind == "literature_cited" or (
                base_out.benchmark_kind == "literature_cited"
            ):
                notice += f" · {LITERATURE_BANNER}"
        return RetestCompareOut(
            baseline=PosePreviewOut(**baseline_preview),
            current=PosePreviewOut(**current_preview),
            baseline_score=base_out,
            current_score=cur_out,
            score_delta=delta,
            notice=notice,
        )
    except FrameOutOfRange as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PoseNotExtracted as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PosePreviewError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/videos/{video_id}/stage-timeline", response_model=StageTimelineOut)
def get_stage_timeline(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Heuristic stage segments for the user pose sequence (not coach cuts)."""
    row = _owned_video(db, video_id, user)
    pose = _pose_for_video(db, row.id)
    if pose is None or not pose.keypoint_path:
        raise HTTPException(status_code=404, detail="关键点尚未提取")
    timeline = _ensure_timeline(db, row, pose)
    if timeline is None:
        # Try skill stages without published package — still honest heuristic
        skill = db.get(BadmintonSkill, row.skill_id)
        stages = [
            {"code": f"stage_{i}", "name": s.name, "sort_order": s.sort_order}
            for i, s in enumerate(getattr(skill, "stages", None) or [], start=1)
        ]
        if stages:
            timeline = timeline_from_package(
                pose.keypoint_path,
                {
                    "stages": stages,
                    "keyframes": [],
                    "verification_status": "draft_unverified",
                },
            )
            pose.stage_timeline_json = json.dumps(timeline, ensure_ascii=False)
            db.commit()
    if timeline is None:
        raise HTTPException(status_code=404, detail="无可用阶段定义")
    db.commit()
    return StageTimelineOut(
        segments=timeline.get("segments") or [],
        user_t0_ms=timeline.get("user_t0_ms"),
        user_t1_ms=timeline.get("user_t1_ms"),
        template_total_ms=timeline.get("template_total_ms"),
        method=timeline.get("method"),
        benchmark_kind=timeline.get("benchmark_kind"),
        has_template_timing=bool(timeline.get("has_template_timing")),
        notice=timeline.get("notice")
        or "阶段时间轴为相对时序启发式切分，非专家标注",
    )


@router.get("/videos/{video_id}/pose/overlay", response_model=PoseOverlayOut)
def get_pose_overlay(
    video_id: int,
    frame: int = Query(0, ge=0, description="Scrub index into user frames (0-based)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Standard (green) vs user skeleton overlay with synced scrub.

    Label: 非评分叠加. Template from package synthetic_keypoint_template when
    present; otherwise a generated synthetic_demo sequence.
    """
    row = _owned_video(db, video_id, user)
    pose = _pose_for_video(db, row.id)
    if pose is None or not pose.keypoint_path:
        raise HTTPException(status_code=404, detail="关键点尚未提取")
    job = _latest_job(list(row.analysis_jobs or []))
    _published, pkg = _published_package(db, row, job)
    timeline = _ensure_timeline(db, row, pose)
    if timeline:
        db.commit()
    try:
        data = build_overlay_json(
            video_id=row.id,
            keypoint_path=pose.keypoint_path,
            frame=frame,
            package=pkg,
            timeline=timeline,
            landmark_count=pose.landmark_count,
            extractor=pose.extractor,
        )
        return PoseOverlayOut(**data)
    except FrameOutOfRange as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PoseNotExtracted as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PosePreviewError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/videos/{video_id}/file")
def get_video_file(
    video_id: int,
    token: Optional[str] = Query(
        None, description="JWT for <video> tag when Bearer header unavailable"
    ),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Stream owned training video for player UX (Bearer or ?token=)."""
    owner = user
    if owner is None and token:
        try:
            payload = decode_token(token)
            owner = db.get(User, int(payload.get("sub", 0)))
        except Exception:
            owner = None
    if owner is None:
        raise HTTPException(status_code=401, detail="需要登录")
    row = _owned_video(db, video_id, owner)
    path = Path(row.storage_path)
    if not path.is_file():
        alt = _uploads_root() / row.storage_path
        if alt.is_file():
            path = alt
    if not path.is_file():
        # relative filename under uploads
        alt2 = _uploads_root() / Path(row.storage_path).name
        if alt2.is_file():
            path = alt2
    if not path.is_file():
        raise HTTPException(status_code=404, detail="视频文件不存在")
    media = "video/mp4"
    suffix = path.suffix.lower()
    if suffix in {".mov", ".qt"}:
        media = "video/quicktime"
    elif suffix == ".webm":
        media = "video/webm"
    return FileResponse(
        path,
        media_type=media,
        filename=row.filename or path.name,
        content_disposition_type="inline",
    )
