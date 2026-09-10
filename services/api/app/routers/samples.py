"""Cold-start sample analysis reports (literature/demo data, not user video)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/samples", tags=["samples"])

_SAMPLES_DIR = Path(__file__).resolve().parent.parent / "static" / "samples"

# Allowed sample codes (filename stem). Extend carefully — honesty only.
_KNOWN = frozenset({"forehand_clear"})


def _load_sample(code: str) -> dict:
    path = _SAMPLES_DIR / f"{code}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"sample not found: {code}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    data["is_sample"] = True
    if not data.get("sample_banner"):
        data["sample_banner"] = "【样例】文献/演示数据，非你的真实视频评分"
    return data


@router.get("/{code}")
def get_sample(code: str):
    """Return a static sample analysis payload for cold-start UX.

    Honesty: literature/demo data marked as sample — never a user video score.
    """
    key = (code or "").strip().lower()
    if key not in _KNOWN:
        raise HTTPException(status_code=404, detail=f"unknown sample code: {code}")
    payload = _load_sample(key)
    return JSONResponse(payload)
