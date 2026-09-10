"""Persist pose extraction results; optionally score when published benchmark exists."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AnalysisJob, PoseAnalysis, TrainingVideo
from app.services.pose.base import PoseExtractor, PoseExtractResult
from app.services.pose.factory import get_pose_extractor
from app.services.pose.null_extractor import PoseExtractorUnavailable

logger = logging.getLogger(__name__)

SCORING_CODE = "ANALYSIS_NOT_IMPLEMENTED"
SCORING_MSG = (
    "关键点已提取（或排队中）；评分需已发布 Motion Benchmark。"
    "无 published 版本时保持 ANALYSIS_NOT_IMPLEMENTED；"
    "synthetic_demo 须展示「工程演示基准（非教练标定）」。"
)


def pose_dir() -> Path:
    settings = get_settings()
    d = Path(settings.upload_dir) / "pose"
    d.mkdir(parents=True, exist_ok=True)
    return d


def keypoint_path_for(video_id: int) -> Path:
    return pose_dir() / f"{video_id}.json"


def write_keypoints(video_id: int, result: PoseExtractResult) -> Path:
    path = keypoint_path_for(video_id)
    path.write_text(
        json.dumps(result.to_json_dict(video_id=video_id), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _scoring_message(job: AnalysisJob) -> str:
    msg = SCORING_MSG
    if job.benchmark_version_id:
        msg += (
            f" benchmark_version_id={job.benchmark_version_id} 已记录；"
            "若该版本已发布将尝试评分。"
        )
    else:
        msg += " awaiting_published_benchmark。"
    return msg


def apply_pose_success(
    db: Session,
    *,
    video: TrainingVideo,
    job: AnalysisJob,
    result: PoseExtractResult,
    path: Path,
) -> PoseAnalysis:
    existing = (
        db.query(PoseAnalysis).filter(PoseAnalysis.video_id == video.id).one_or_none()
    )
    if existing is None:
        existing = PoseAnalysis(video_id=video.id)
        db.add(existing)
    existing.job_id = job.id
    existing.frame_count = result.frame_count
    existing.fps = result.fps
    existing.keypoint_path = str(path)
    existing.extractor = result.extractor
    existing.sample_stride = result.sample_stride
    existing.max_seconds = result.max_seconds
    existing.landmark_count = len(result.landmark_names)

    job.status = "pose_extracted"
    job.scoring_status = "blocked"
    job.error_code = SCORING_CODE
    job.message = (
        f"pose_extracted frames={result.frame_count} extractor={result.extractor}. "
        + _scoring_message(job)
    )
    db.flush()
    return existing


def apply_pose_queued(job: AnalysisJob, reason: str = "") -> None:
    job.status = "queued"
    job.scoring_status = "blocked"
    job.error_code = SCORING_CODE
    base = "关键点提取排队中；评分未开放（ANALYSIS_NOT_IMPLEMENTED）。"
    if reason:
        base += f" {reason}"
    if not job.benchmark_version_id:
        base += " awaiting_published_benchmark。"
    job.message = base


def apply_pose_failed(job: AnalysisJob, err: str) -> None:
    """Mark job failed (keypoints only; scoring stays blocked)."""
    job.status = "failed"
    job.scoring_status = "blocked"
    job.error_code = SCORING_CODE
    job.message = f"关键点提取失败: {err}。评分仍未开放。"


def extract_for_video(
    db: Session,
    video: TrainingVideo,
    job: AnalysisJob,
    *,
    extractor: Optional[PoseExtractor] = None,
) -> PoseAnalysis:
    settings = get_settings()
    backend = extractor or get_pose_extractor()
    video_path = Path(video.storage_path)
    if not video_path.exists():
        apply_pose_failed(job, f"video file missing: {video_path}")
        db.commit()
        raise FileNotFoundError(str(video_path))

    try:
        result = backend.extract(
            video_path,
            max_seconds=float(settings.pose_max_seconds),
            sample_stride=int(settings.pose_frame_stride),
        )
    except PoseExtractorUnavailable as exc:
        apply_pose_queued(job, reason=str(exc))
        db.commit()
        raise
    except Exception as exc:
        logger.exception("pose extract failed for video %s", video.id)
        apply_pose_failed(job, str(exc))
        db.commit()
        raise

    path = write_keypoints(video.id, result)
    pose_row = apply_pose_success(db, video=video, job=job, result=result, path=path)
    db.flush()
    try:
        from app.services.scoring.persist import maybe_score_after_pose, persist_stage_timeline

        maybe_score_after_pose(db, video=video, job=job, pose=pose_row)
        if not pose_row.stage_timeline_json:
            persist_stage_timeline(db, video=video, pose=pose_row)
    except Exception as exc:  # noqa: BLE001 — keep keypoints even if scoring fails
        logger.warning("post-pose scoring skipped video=%s: %s", video.id, exc)
    db.commit()
    db.refresh(pose_row)
    db.refresh(job)
    return pose_row


def try_inline_extract(
    db: Session,
    video: TrainingVideo,
    job: AnalysisJob,
) -> Optional[PoseAnalysis]:
    """Best-effort extract after upload; leave queued on unavailability."""
    settings = get_settings()
    if not settings.pose_extract_inline:
        # Queue mode: upload already left status=queued for the worker.
        return None
    try:
        return extract_for_video(db, video, job)
    except PoseExtractorUnavailable as exc:
        logger.info("inline pose skipped (unavailable): %s", exc)
        return None
    except Exception as exc:
        logger.warning("inline pose failed: %s", exc)
        return None
