"""python -m app.worker extract [--once|--loop]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as module from services/api
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _run_extract(
    *,
    once: bool,
    loop: bool,
    limit: int,
    poll_interval: float | None,
    video_id: int | None,
) -> int:
    from app.config import get_settings
    from app.database import SessionLocal, init_db
    from app.models import AnalysisJob, TrainingVideo
    from app.services.pose.null_extractor import PoseExtractorUnavailable
    from app.services.pose.runner import apply_pose_queued, extract_for_video
    from app.worker.pose_queue import process_batch, run_loop

    get_settings.cache_clear()
    settings = get_settings()
    init_db()

    # Explicit video: sync extract (manual / debug), no queue claim needed
    if video_id is not None:
        db = SessionLocal()
        try:
            job = (
                db.query(AnalysisJob)
                .filter(AnalysisJob.video_id == video_id)
                .order_by(AnalysisJob.id.desc())
                .first()
            )
            video = db.get(TrainingVideo, video_id)
            if not video:
                print(f"video {video_id} not found")
                return 1
            if job is None:
                job = AnalysisJob(
                    video_id=video.id,
                    skill_id=video.skill_id,
                    status="queued",
                    scoring_status="blocked",
                )
                apply_pose_queued(job)
                db.add(job)
                db.commit()
                db.refresh(job)
            try:
                pose = extract_for_video(db, video, job)
                print(f"ok job={job.id} video={video.id} frames={pose.frame_count}")
                return 0
            except PoseExtractorUnavailable as exc:
                print(f"unavailable job={job.id}: {exc}")
                return 1
            except Exception as exc:
                print(f"fail job={job.id}: {exc}")
                return 1
        finally:
            db.close()

    if loop and not once:
        interval = (
            poll_interval
            if poll_interval is not None
            else float(settings.pose_extract_poll_interval)
        )
        print(f"pose worker loop poll={interval}s limit={limit} (Ctrl+C to stop)")
        try:
            run_loop(poll_interval=interval, limit=limit)
        except KeyboardInterrupt:
            print("stopped")
        return 0

    # Default / --once: one batch via optimistic claim
    stats = process_batch(limit=limit)
    print(
        f"claimed={stats.claimed} processed={stats.processed} "
        f"failed={stats.failed} requeued={stats.requeued} "
        f"reclaimed={stats.reclaimed}"
    )
    return 0 if stats.failed == 0 else 1


def _run_purge(
    *,
    once: bool,
    loop: bool,
    limit: int,
    poll_interval: float | None,
    dry_run: bool,
    ttl_days: int | None,
) -> int:
    import time

    from app.config import get_settings
    from app.database import SessionLocal, init_db
    from app.services.video_purge import run_purge

    get_settings.cache_clear()
    settings = get_settings()
    init_db()
    interval = (
        poll_interval
        if poll_interval is not None
        else max(60.0, float(settings.pose_extract_poll_interval) * 30)
    )

    def _one() -> int:
        db = SessionLocal()
        try:
            stats = run_purge(
                db,
                ttl_days=ttl_days,
                settings=settings,
                limit=limit if limit > 0 else None,
                dry_run=dry_run,
            )
            if not dry_run:
                db.commit()
            print(
                f"purge selected={stats.selected} unlinked={stats.unlinked} "
                f"missing={stats.already_missing} marked={stats.marked} "
                f"errors={stats.errors} dry_run={dry_run}"
            )
            return 0 if stats.errors == 0 else 1
        finally:
            db.close()

    if loop and not once:
        print(f"video purge loop poll={interval}s limit={limit} (Ctrl+C to stop)")
        try:
            while True:
                _one()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("stopped")
        return 0
    return _one()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser(
        "extract",
        help="Claim queued analysis jobs and extract pose keypoints (no scoring)",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Process one batch and exit (default if --loop not set)",
    )
    p.add_argument(
        "--loop",
        action="store_true",
        help="Poll forever (interval: POSE_EXTRACT_POLL_INTERVAL, default 2s)",
    )
    p.add_argument("--limit", type=int, default=1, help="Max jobs per batch")
    p.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Loop sleep seconds (overrides env)",
    )
    p.add_argument(
        "--video-id",
        type=int,
        default=None,
        help="Sync-extract one video id (bypass queue claim)",
    )
    pp = sub.add_parser(
        "purge-videos",
        help="Unlink original video files older than VIDEO_TTL_DAYS (keep pose/scores)",
    )
    pp.add_argument(
        "--once",
        action="store_true",
        help="Run one purge batch and exit (default if --loop not set)",
    )
    pp.add_argument(
        "--loop",
        action="store_true",
        help="Poll forever (default interval ~60s+)",
    )
    pp.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max videos per batch (0 = no limit)",
    )
    pp.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Loop sleep seconds",
    )
    pp.add_argument(
        "--ttl-days",
        type=int,
        default=None,
        help="Override VIDEO_TTL_DAYS",
    )
    pp.add_argument(
        "--dry-run",
        action="store_true",
        help="Select only; do not unlink or stamp file_purged_at",
    )
    args = parser.parse_args(argv)
    if args.cmd == "extract":
        return _run_extract(
            once=args.once or not args.loop,
            loop=args.loop,
            limit=args.limit,
            poll_interval=args.poll_interval,
            video_id=args.video_id,
        )
    if args.cmd == "purge-videos":
        return _run_purge(
            once=args.once or not args.loop,
            loop=args.loop,
            limit=args.limit,
            poll_interval=args.poll_interval,
            dry_run=args.dry_run,
            ttl_days=args.ttl_days,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
