"""DB-backed pose extract queue (SQLite solo deploy — no Redis required).

Claim path: status queued → extracting via optimistic UPDATE ... WHERE status='queued'.
Process path: extracting → pose_extracted|scored | failed.
Stale reclaim: extracting older than POSE_EXTRACT_STALE_SECONDS → queued again,
or failed after pose_extract_max_attempts reclaims.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import AnalysisJob, TrainingVideo
from app.services.pose.base import PoseExtractor
from app.services.pose.null_extractor import PoseExtractorUnavailable
from app.services.pose.runner import SCORING_CODE, extract_for_video

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    """Naive UTC for DateTime columns (SQLite / server_default=func.now())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class ProcessStats:
    claimed: int = 0
    processed: int = 0
    failed: int = 0
    requeued: int = 0
    reclaimed: int = 0


def reclaim_stale_extracting_jobs(
    db: Session,
    *,
    stale_seconds: Optional[int] = None,
    max_attempts: Optional[int] = None,
) -> int:
    """
    Requeue jobs stuck in `extracting` longer than stale_seconds.
    Increments attempt_count; after max_attempts marks failed instead of
    infinite requeue.
    Returns number of rows touched (requeued or failed).
    """
    settings = get_settings()
    seconds = (
        int(stale_seconds)
        if stale_seconds is not None
        else int(settings.pose_extract_stale_seconds)
    )
    attempts_limit = (
        int(max_attempts)
        if max_attempts is not None
        else int(settings.pose_extract_max_attempts)
    )
    if seconds <= 0:
        return 0

    cutoff = _utcnow_naive() - timedelta(seconds=seconds)
    now = _utcnow_naive()
    stale_jobs = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.status == "extracting",
            AnalysisJob.updated_at < cutoff,
        )
        .all()
    )
    n = 0
    for job in stale_jobs:
        prev = int(job.attempt_count or 0)
        new_count = prev + 1
        job.attempt_count = new_count
        job.updated_at = now
        if attempts_limit > 0 and new_count >= attempts_limit:
            job.status = "failed"
            job.scoring_status = "blocked"
            job.error_code = SCORING_CODE
            job.message = (
                f"卡死 extracting 已超过 {seconds}s，回收次数 {new_count}/"
                f"{attempts_limit}，已标记 failed；评分未开放（ANALYSIS_NOT_IMPLEMENTED）。"
            )
            logger.warning(
                "stale job %s failed after %s reclaim attempts",
                job.id,
                new_count,
            )
        else:
            job.status = "queued"
            job.scoring_status = "blocked"
            job.error_code = SCORING_CODE
            job.message = (
                f"卡死 extracting 已超过 {seconds}s，已回收为 queued "
                f"(attempt {new_count}/{attempts_limit})；"
                "评分未开放（ANALYSIS_NOT_IMPLEMENTED）。"
            )
        n += 1
    if n:
        db.commit()
        logger.warning(
            "reclaimed/failed %s stale extracting job(s) older than %ss (cutoff=%s)",
            n,
            seconds,
            cutoff.isoformat(sep=" ", timespec="seconds"),
        )
    return n


def claim_next_job(db: Session) -> Optional[AnalysisJob]:
    """
    Claim one queued job with optimistic lock.
    UPDATE ... WHERE id=? AND status='queued' SET status='extracting'.
    Returns None if nothing to claim or race lost.
    """
    candidate_id = (
        db.query(AnalysisJob.id)
        .filter(AnalysisJob.status == "queued")
        .order_by(AnalysisJob.created_at.asc(), AnalysisJob.id.asc())
        .limit(1)
        .scalar()
    )
    if candidate_id is None:
        return None

    now = _utcnow_naive()
    result = db.execute(
        update(AnalysisJob)
        .where(
            AnalysisJob.id == candidate_id,
            AnalysisJob.status == "queued",
        )
        .values(
            status="extracting",
            scoring_status="blocked",
            error_code=SCORING_CODE,
            message="关键点提取中；评分未开放（ANALYSIS_NOT_IMPLEMENTED）。",
            updated_at=now,
        )
    )
    db.commit()
    if result.rowcount != 1:
        return None
    return db.get(AnalysisJob, candidate_id)


def claim_job(db: Session, job_id: int) -> Optional[AnalysisJob]:
    """Optimistic claim of a specific job id (for tests / targeted drain)."""
    now = _utcnow_naive()
    result = db.execute(
        update(AnalysisJob)
        .where(
            AnalysisJob.id == job_id,
            AnalysisJob.status == "queued",
        )
        .values(
            status="extracting",
            scoring_status="blocked",
            error_code=SCORING_CODE,
            message="关键点提取中；评分未开放（ANALYSIS_NOT_IMPLEMENTED）。",
            updated_at=now,
        )
    )
    db.commit()
    if result.rowcount != 1:
        return None
    return db.get(AnalysisJob, job_id)


def claim_jobs(db: Session, limit: int = 1) -> list[AnalysisJob]:
    """Claim up to `limit` queued jobs one-by-one (each with its own optimistic lock)."""
    claimed: list[AnalysisJob] = []
    for _ in range(max(0, limit)):
        job = claim_next_job(db)
        if job is None:
            break
        claimed.append(job)
    return claimed


def process_claimed_job(
    db: Session,
    job: AnalysisJob,
    *,
    extractor: Optional[PoseExtractor] = None,
) -> str:
    """
    Run extractor on an already-claimed (extracting) job.
    Returns: 'pose_extracted' | 'failed' | 'requeued'
    """
    if not job.video_id:
        job.status = "failed"
        job.scoring_status = "blocked"
        job.error_code = SCORING_CODE
        job.message = "关键点提取失败: 无 video_id。评分仍未开放。"
        db.commit()
        return "failed"

    video = db.get(TrainingVideo, job.video_id)
    if video is None:
        job.status = "failed"
        job.scoring_status = "blocked"
        job.error_code = SCORING_CODE
        job.message = f"关键点提取失败: video {job.video_id} 不存在。评分仍未开放。"
        db.commit()
        return "failed"

    try:
        extract_for_video(db, video, job, extractor=extractor)
        db.refresh(job)
        if job.status == "scored":
            return "scored"
        return "pose_extracted"
    except PoseExtractorUnavailable as exc:
        logger.info("pose extract requeued (unavailable) job=%s: %s", job.id, exc)
        return "requeued"
    except Exception as exc:
        logger.warning("pose extract failed job=%s: %s", job.id, exc)
        return "failed"


def process_batch(
    *,
    limit: int = 1,
    extractor: Optional[PoseExtractor] = None,
    db: Optional[Session] = None,
    stale_seconds: Optional[int] = None,
) -> ProcessStats:
    """Reclaim stale extracting, then claim and process up to `limit` jobs."""
    own = db is None
    session = db if db is not None else SessionLocal()
    stats = ProcessStats()
    try:
        stats.reclaimed = reclaim_stale_extracting_jobs(
            session, stale_seconds=stale_seconds
        )
        jobs = claim_jobs(session, limit=limit)
        stats.claimed = len(jobs)
        for job in jobs:
            outcome = process_claimed_job(session, job, extractor=extractor)
            if outcome in ("pose_extracted", "scored"):
                stats.processed += 1
            elif outcome == "requeued":
                stats.requeued += 1
            else:
                stats.failed += 1
    finally:
        if own:
            session.close()
    return stats


def run_once(
    *,
    limit: int = 1,
    extractor: Optional[PoseExtractor] = None,
) -> ProcessStats:
    """One-shot: reclaim stale + claim + process a batch."""
    return process_batch(limit=limit, extractor=extractor)


def run_loop(
    *,
    poll_interval: Optional[float] = None,
    limit: int = 1,
    extractor: Optional[PoseExtractor] = None,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """Poll forever (or until stop_event). Default interval from settings (2s)."""
    settings = get_settings()
    interval = (
        float(poll_interval)
        if poll_interval is not None
        else float(settings.pose_extract_poll_interval)
    )
    logger.info(
        "pose queue loop started poll=%.2fs limit=%s stale=%ss max_attempts=%s",
        interval,
        limit,
        settings.pose_extract_stale_seconds,
        settings.pose_extract_max_attempts,
    )
    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("pose queue loop stop requested")
            break
        try:
            stats = process_batch(limit=limit, extractor=extractor)
            if stats.claimed or stats.reclaimed:
                logger.info(
                    "pose queue tick claimed=%s ok=%s failed=%s requeued=%s reclaimed=%s",
                    stats.claimed,
                    stats.processed,
                    stats.failed,
                    stats.requeued,
                    stats.reclaimed,
                )
        except Exception:
            logger.exception("pose queue tick error")
        if stop_event is not None:
            if stop_event.wait(timeout=interval):
                break
        else:
            time.sleep(interval)


_bg_stop: Optional[threading.Event] = None
_bg_thread: Optional[threading.Thread] = None


def start_background_worker() -> Optional[threading.Event]:
    """
    Optional in-API daemon thread. Only starts when
    pose_extract_background=True (POSE_EXTRACT_BACKGROUND).
    Tests keep this false so Fake + sync worker --once stays deterministic.
    """
    global _bg_stop, _bg_thread
    settings = get_settings()
    if not settings.pose_extract_background:
        return None
    if _bg_thread is not None and _bg_thread.is_alive():
        return _bg_stop

    stop = threading.Event()
    interval = float(settings.pose_extract_poll_interval)

    def _target() -> None:
        run_loop(poll_interval=interval, limit=1, stop_event=stop)

    thread = threading.Thread(
        target=_target,
        name="pose-extract-bg",
        daemon=True,
    )
    _bg_stop = stop
    _bg_thread = thread
    thread.start()
    logger.info(
        "in-API pose background worker started (poll=%.2fs)",
        interval,
    )
    return stop


def stop_background_worker() -> None:
    global _bg_stop, _bg_thread
    if _bg_stop is not None:
        _bg_stop.set()
    _bg_stop = None
    _bg_thread = None
