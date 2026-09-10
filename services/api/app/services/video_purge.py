"""Purge original training video files older than VIDEO_TTL_DAYS.

Keeps pose keypoints, analysis jobs, and score rows. Only unlinks the
original media under storage_path and stamps file_purged_at.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import TrainingVideo


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def purge_cutoff(
    *,
    now: datetime | None = None,
    ttl_days: int | None = None,
    settings: Settings | None = None,
) -> datetime:
    """Return created_at threshold: videos strictly older than this are eligible."""
    cfg = settings or get_settings()
    days = int(ttl_days if ttl_days is not None else cfg.video_ttl_days)
    if days < 0:
        days = 0
    ref = now if now is not None else _utc_now()
    return ref - timedelta(days=days)


def select_videos_for_purge(
    db: Session,
    *,
    now: datetime | None = None,
    ttl_days: int | None = None,
    settings: Settings | None = None,
    limit: int | None = None,
) -> list[TrainingVideo]:
    """
    Select rows whose original file should be purged:
    - file_purged_at IS NULL
    - created_at < now - VIDEO_TTL_DAYS
    Does not require the file to exist (orphan paths still get stamped).
    """
    cutoff = purge_cutoff(now=now, ttl_days=ttl_days, settings=settings)
    q = (
        db.query(TrainingVideo)
        .filter(TrainingVideo.file_purged_at.is_(None))
        .filter(TrainingVideo.created_at < cutoff)
        .order_by(TrainingVideo.created_at.asc(), TrainingVideo.id.asc())
    )
    if limit is not None:
        q = q.limit(int(limit))
    return list(q.all())


def resolve_video_file(video: TrainingVideo, upload_dir: str | Path | None = None) -> Path | None:
    """Best-effort resolve of original media path (mirrors /videos/{id}/file)."""
    raw = Path(video.storage_path) if video.storage_path else None
    candidates: list[Path] = []
    if raw is not None:
        candidates.append(raw)
    root = Path(upload_dir) if upload_dir is not None else Path(get_settings().upload_dir)
    if raw is not None:
        candidates.append(root / raw)
        candidates.append(root / raw.name)
    for p in candidates:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


@dataclass
class PurgeStats:
    selected: int = 0
    unlinked: int = 0
    already_missing: int = 0
    marked: int = 0
    errors: int = 0


def purge_video_file(
    db: Session,
    video: TrainingVideo,
    *,
    now: datetime | None = None,
    upload_dir: str | Path | None = None,
    dry_run: bool = False,
) -> bool:
    """
    Unlink original file (if present) and set file_purged_at.
    Returns True if the row was marked purged (or would be in dry_run).
    Does NOT delete pose/score/job rows.
    """
    if video.file_purged_at is not None:
        return False
    path = resolve_video_file(video, upload_dir=upload_dir)
    unlinked = False
    missing = path is None
    if path is not None and not dry_run:
        try:
            path.unlink(missing_ok=True)
            unlinked = True
        except OSError:
            raise
    if dry_run:
        return True
    video.file_purged_at = now if now is not None else _utc_now()
    db.add(video)
    return True


def run_purge(
    db: Session,
    *,
    now: datetime | None = None,
    ttl_days: int | None = None,
    settings: Settings | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> PurgeStats:
    """Select + purge a batch. Caller commits."""
    cfg = settings or get_settings()
    stats = PurgeStats()
    rows = select_videos_for_purge(
        db, now=now, ttl_days=ttl_days, settings=cfg, limit=limit
    )
    stats.selected = len(rows)
    stamp = now if now is not None else _utc_now()
    for video in rows:
        try:
            path = resolve_video_file(video, upload_dir=cfg.upload_dir)
            if path is None:
                stats.already_missing += 1
            elif not dry_run:
                path.unlink(missing_ok=True)
                stats.unlinked += 1
            else:
                stats.unlinked += 1  # would unlink
            if not dry_run:
                video.file_purged_at = stamp
                db.add(video)
                stats.marked += 1
            else:
                stats.marked += 1
        except OSError:
            stats.errors += 1
    return stats
