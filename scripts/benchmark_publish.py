#!/usr/bin/env python3
"""Publish a draft benchmark version.

Default policy: draft_unverified cannot be published.
verified publishes cleanly.
synthetic_demo publishes only with --allow-synthetic-demo.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
API = REPO / "services" / "api"
sys.path.insert(0, str(API))
os.chdir(API)

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import BadmintonSkill, BenchmarkVersion, MotionBenchmark  # noqa: E402
from app.services.benchmark_pkg import publish_allowed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("skill_code", help="e.g. forehand_clear")
    ap.add_argument(
        "--version",
        required=True,
        help="version_label to publish (e.g. 0.1.0)",
    )
    ap.add_argument(
        "--force-draft-forbidden",
        action="store_true",
        help="Explicit no-op asserting default policy (draft_unverified cannot publish)",
    )
    ap.add_argument(
        "--force-allow-draft",
        action="store_true",
        help="DANGEROUS: allow publishing draft_unverified",
    )
    ap.add_argument(
        "--force-expert-pending",
        action="store_true",
        help="Allow publishing expert_pending (still not verified)",
    )
    ap.add_argument(
        "--allow-synthetic-demo",
        action="store_true",
        help="Allow publishing synthetic_demo packages (pipeline demo only)",
    )
    args = ap.parse_args()

    if args.force_draft_forbidden and args.force_allow_draft:
        print(
            "FAIL: conflicting flags --force-draft-forbidden and --force-allow-draft",
            file=sys.stderr,
        )
        return 1
    force_draft_forbidden = not args.force_allow_draft

    init_db()
    db = SessionLocal()
    try:
        skill = (
            db.query(BadmintonSkill)
            .filter(BadmintonSkill.code == args.skill_code)
            .one_or_none()
        )
        if not skill:
            print(f"FAIL: unknown skill_code {args.skill_code}", file=sys.stderr)
            return 1
        bm = (
            db.query(MotionBenchmark)
            .filter(MotionBenchmark.skill_id == skill.id)
            .one_or_none()
        )
        if not bm:
            print(f"FAIL: no motion_benchmark for {args.skill_code}", file=sys.stderr)
            return 1
        ver = (
            db.query(BenchmarkVersion)
            .filter(
                BenchmarkVersion.benchmark_id == bm.id,
                BenchmarkVersion.version_label == args.version,
            )
            .one_or_none()
        )
        if not ver:
            print(
                f"FAIL: version {args.version} not found for {args.skill_code}",
                file=sys.stderr,
            )
            return 1

        ok, reason = publish_allowed(
            ver.verification_status,
            force_allow_draft=args.force_allow_draft,
            force_allow_expert_pending=args.force_expert_pending,
            allow_synthetic_demo=args.allow_synthetic_demo,
        )
        if not ok:
            print(f"FAIL: {reason}", file=sys.stderr)
            if force_draft_forbidden and ver.verification_status == "draft_unverified":
                print(
                    "hint: keep draft unpublished until experts fill ranges and set verified",
                    file=sys.stderr,
                )
            if ver.verification_status == "synthetic_demo" and not args.allow_synthetic_demo:
                print(
                    "hint: pass --allow-synthetic-demo for pipeline demo publish",
                    file=sys.stderr,
                )
            return 1

        others = (
            db.query(BenchmarkVersion)
            .filter(
                BenchmarkVersion.benchmark_id == bm.id,
                BenchmarkVersion.status == "published",
                BenchmarkVersion.id != ver.id,
            )
            .all()
        )
        for o in others:
            o.status = "archived"

        ver.status = "published"
        ver.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
        bm.verification_status = ver.verification_status
        bm.source = ver.source
        db.commit()
        print(
            f"OK: published {args.skill_code}@{args.version} "
            f"version_id={ver.id} ({reason})"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
