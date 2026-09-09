#!/usr/bin/env python3
"""Validate a Motion Benchmark package against schema + anti-fabrication policy."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
API = REPO / "services" / "api"
sys.path.insert(0, str(API))

from app.services.benchmark_pkg import (  # noqa: E402
    BenchmarkValidationError,
    load_package,
    validate_package,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package", type=Path, help="Path to benchmark package JSON")
    ap.add_argument(
        "--allow-unverified-numbers",
        action="store_true",
        help="Allow numeric ranges while verification_status=draft_unverified",
    )
    args = ap.parse_args()
    try:
        data = load_package(args.package)
        warnings = validate_package(
            data, allow_unverified_numbers=args.allow_unverified_numbers
        )
    except (OSError, ValueError, BenchmarkValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: {data['skill_code']}@{data['version']} "
        f"status={data['verification_status']} metrics={len(data.get('metrics') or [])}"
    )
    for w in warnings:
        print(f"WARN: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
