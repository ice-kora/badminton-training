#!/usr/bin/env python3
"""Repo-root seed entry: delegates to services/api app.seed."""
from __future__ import annotations

import sys
from pathlib import Path

API = Path(__file__).resolve().parent.parent / "services" / "api"
sys.path.insert(0, str(API))

from app.seed import seed  # noqa: E402

if __name__ == "__main__":
    seed()
