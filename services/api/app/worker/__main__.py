"""python -m app.worker extract"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as module from services/api
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _run_extract(limit: int, status: str, video_id: int | None) -> int:
    from app.config import get_settings
    from app.database import SessionLocal, init_db
    from app.models import AnalysisJob, TrainingVideo
    from app.services.pose.null_extractor import PoseExtractorUnavailable
    from app.services.pose.runner import extract_for_video

    get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    processed = 0
    errors = 0
    try:
        q = db.query(AnalysisJob)
        if video_id is not None:
            q = q.filter(AnalysisJob.video_id == video_id)
        else:
            q = q.filter(AnalysisJob.status == status)
        jobs = q.order_by(AnalysisJob.id.asc()).limit(limit).all()
        for job in jobs:
            video = db.get(TrainingVideo, job.video_id) if job.video_id else None
            if not video:
                continue
            try:
                pose = extract_for_video(db, video, job)
                print(f"ok job={job.id} video={video.id} frames={pose.frame_count}")
                processed += 1
            except PoseExtractorUnavailable as exc:
                print(f"unavailable job={job.id}: {exc}")
                errors += 1
            except Exception as exc:
                print(f"fail job={job.id}: {exc}")
                errors += 1
    finally:
        db.close()
    print(f"processed={processed} errors={errors}")
    return 0 if errors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extract", help="Extract pose keypoints for queued jobs")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--status", default="queued")
    p.add_argument("--video-id", type=int, default=None)
    args = parser.parse_args(argv)
    if args.cmd == "extract":
        return _run_extract(args.limit, args.status, args.video_id)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
