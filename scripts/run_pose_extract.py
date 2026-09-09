#!/usr/bin/env python3
"""Drain queued analysis jobs and extract pose keypoints (no scoring).

Usage (from repo root):
  cd services/api && source .venv/bin/activate
  DATABASE_URL=sqlite:///./data/app.db python ../../scripts/run_pose_extract.py
  # or:
  python -m app.worker extract   # if PYTHONPATH includes services/api

Environment:
  POSE_EXTRACTOR=auto|mediapipe|fake|null
  POSE_MAX_SECONDS=60
  POSE_FRAME_STRIDE=2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "services" / "api"
sys.path.insert(0, str(API_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract pose keypoints for queued jobs")
    parser.add_argument("--limit", type=int, default=20, help="Max jobs to process")
    parser.add_argument(
        "--status",
        default="queued",
        help="Job status to reclaim (default: queued)",
    )
    parser.add_argument("--video-id", type=int, default=None, help="Process one video id")
    args = parser.parse_args()

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
        if args.video_id is not None:
            q = q.filter(AnalysisJob.video_id == args.video_id)
        else:
            q = q.filter(AnalysisJob.status == args.status)
        jobs = (
            q.order_by(AnalysisJob.created_at.asc(), AnalysisJob.id.asc())
            .limit(args.limit)
            .all()
        )
        if not jobs:
            print("No jobs to process.")
            return 0
        for job in jobs:
            if not job.video_id:
                print(f"job {job.id}: skip (no video_id)")
                continue
            video = db.get(TrainingVideo, job.video_id)
            if not video:
                print(f"job {job.id}: skip (video missing)")
                continue
            try:
                pose = extract_for_video(db, video, job)
                print(
                    f"job {job.id} video {video.id}: pose_extracted "
                    f"frames={pose.frame_count} path={pose.keypoint_path}"
                )
                processed += 1
            except PoseExtractorUnavailable as exc:
                print(f"job {job.id}: extractor unavailable — {exc}")
                errors += 1
            except Exception as exc:
                print(f"job {job.id}: FAILED — {exc}")
                errors += 1
    finally:
        db.close()
    print(f"Done. processed={processed} errors={errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
