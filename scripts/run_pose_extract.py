#!/usr/bin/env python3
"""Drain queued analysis jobs and extract pose keypoints (no scoring).

Usage (from repo root):
  cd services/api && source .venv/bin/activate
  DATABASE_URL=sqlite:///./data/app.db python ../../scripts/run_pose_extract.py
  # or:
  python -m app.worker extract --once
  python -m app.worker extract --loop

Environment:
  POSE_EXTRACTOR=auto|mediapipe|fake|null
  POSE_MAX_SECONDS=60
  POSE_FRAME_STRIDE=2
  POSE_EXTRACT_POLL_INTERVAL=2
  POSE_EXTRACT_STALE_SECONDS=600
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "services" / "api"
sys.path.insert(0, str(API_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract pose keypoints for queued jobs")
    parser.add_argument("--limit", type=int, default=1, help="Max jobs per batch")
    parser.add_argument("--loop", action="store_true", help="Poll forever")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Loop interval seconds (default env/2)",
    )
    parser.add_argument("--video-id", type=int, default=None, help="Sync one video id")
    args = parser.parse_args()

    from app.worker.__main__ import main as worker_main

    argv = ["extract"]
    if args.video_id is not None:
        argv += ["--video-id", str(args.video_id)]
    elif args.loop:
        argv += ["--loop", "--limit", str(args.limit)]
        if args.poll_interval is not None:
            argv += ["--poll-interval", str(args.poll_interval)]
    else:
        argv += ["--once", "--limit", str(args.limit)]
    return worker_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
