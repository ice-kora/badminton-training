"""AI worker — pose extract reclaim + scoring still blocked.

Pose keypoints: use services/api `python -m app.worker extract` or
scripts/run_pose_extract.py. This stub documents status vocabulary and
refuses to invent scores.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol


CODE = "ANALYSIS_NOT_IMPLEMENTED"
MESSAGE = (
    "评分未开放。关键点提取请使用 API worker / scripts/run_pose_extract.py；"
    "本 stub 不产出动作分数或伪报告。"
)

# Job status vocabulary (keep in sync with API models):
# pending | rejected_precheck | queued | pose_extracted | pose_failed |
# not_implemented | failed


class _JobLike(Protocol):
    status: str
    error_code: Optional[str]
    message: Optional[str]
    scoring_status: Optional[str]


def describe() -> dict[str, Any]:
    return {
        "code": CODE,
        "message": MESSAGE,
        "status": "pose_extract_via_api_worker",
        "note": (
            "Upload sets jobs to queued; pose extract → pose_extracted; "
            "scoring_status stays blocked / ANALYSIS_NOT_IMPLEMENTED."
        ),
    }


def analyze(_payload: dict) -> dict[str, Any]:
    """Always refuse scoring — no mock scores."""
    return {"code": CODE, "message": MESSAGE}


def mark_scoring_blocked(job: _JobLike, message: Optional[str] = None) -> _JobLike:
    job.scoring_status = "blocked"
    job.error_code = CODE
    if message:
        job.message = message
    return job


def claim_pending_jobs(jobs: list[_JobLike]) -> list[_JobLike]:
    """
    Legacy helper: pending → queued for pose extract (does NOT score).
    Prefer scripts/run_pose_extract.py for actual keypoint extraction.
    """
    claimed: list[_JobLike] = []
    for job in jobs:
        if getattr(job, "status", None) == "pending":
            job.status = "queued"
            mark_scoring_blocked(job, MESSAGE)
            claimed.append(job)
    return claimed


def process_once(pending_jobs: Optional[list[_JobLike]] = None) -> dict[str, Any]:
    claimed = claim_pending_jobs(pending_jobs or [])
    return {
        "code": CODE,
        "claimed": len(claimed),
        "message": (
            MESSAGE
            if not claimed
            else f"marked {len(claimed)} pending → queued (scoring still blocked)"
        ),
    }
