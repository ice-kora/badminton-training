#!/usr/bin/env python3
"""CLI wrapper: purge original training videos older than VIDEO_TTL_DAYS."""
from __future__ import annotations

import sys
from pathlib import Path

_API = Path(__file__).resolve().parents[1] / "services" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from app.worker.__main__ import main  # noqa: E402


if __name__ == "__main__":
    # Default subcommand
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["purge-videos", *argv]
    elif argv[0] != "purge-videos":
        argv = ["purge-videos", *argv]
    raise SystemExit(main(argv))
