#!/usr/bin/env python3
"""Import a benchmark package into DB as a draft version (not published)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
API = REPO / "services" / "api"
sys.path.insert(0, str(API))
os.chdir(API)

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.benchmark_pkg import (  # noqa: E402
    BenchmarkValidationError,
    import_package_to_db,
    load_package,
    validate_package,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package", type=Path, help="Path to benchmark package JSON")
    ap.add_argument(
        "--allow-unverified-numbers",
        action="store_true",
        help="Forwarded to validator",
    )
    ap.add_argument("--change-log", default=None)
    args = ap.parse_args()

    # Resolve package path before chdir side effects (already chdir'd)
    pkg_path = args.package if args.package.is_absolute() else (REPO / args.package)
    if not pkg_path.exists():
        # try relative to cwd (API) as well
        alt = Path(args.package)
        if alt.exists():
            pkg_path = alt.resolve()
        else:
            print(f"FAIL: package not found: {args.package}", file=sys.stderr)
            return 1

    try:
        data = load_package(pkg_path)
        warnings = validate_package(
            data, allow_unverified_numbers=args.allow_unverified_numbers
        )
        init_db()
        db = SessionLocal()
        try:
            bm, ver = import_package_to_db(db, data, change_log=args.change_log)
            db.commit()
            print(
                f"OK: imported draft skill={data['skill_code']} "
                f"benchmark_id={bm.id} version_id={ver.id} "
                f"label={ver.version_label} status={ver.status} "
                f"verification_status={ver.verification_status}"
            )
        finally:
            db.close()
    except (OSError, ValueError, BenchmarkValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"WARN: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
