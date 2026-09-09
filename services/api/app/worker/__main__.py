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
    args = parser.parse_args(argv)
    if args.cmd == "extract":
        return _run_extract(
            once=args.once or not args.loop,
            loop=args.loop,
            limit=args.limit,
            poll_interval=args.poll_interval,
            video_id=args.video_id,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
