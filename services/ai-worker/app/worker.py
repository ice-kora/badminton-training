"""AI worker stub — honest ANALYSIS_NOT_IMPLEMENTED, no scores.

V1 upload already creates analysis_job with status=not_implemented and
error_code=ANALYSIS_NOT_IMPLEMENTED. This worker is a no-op for the common
path, and optionally drains any legacy/pending rows the same honest way.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol


CODE = "ANALYSIS_NOT_IMPLEMENTED"
MESSAGE = (
    "视频姿态分析尚未实现。本 Worker 不产出动作分数或伪报告；"
    "待标准动作库专家标注完成后接入离线分析流水线。"
)

# Job status vocabulary (keep in sync with API models):
# pending | rejected_precheck | queued | not_implemented | failed


class _JobLike(Protocol):
    status: str
    error_code: Optional[str]
    message: Optional[str]


def describe() -> dict[str, Any]:
    return {
        "code": CODE,
        "message": MESSAGE,
        "status": "stub",
        "note": (
            "Upload path already marks jobs not_implemented; "
            "claim_pending_jobs only handles residual pending rows."
        ),
    }


def analyze(_payload: dict) -> dict[str, Any]:
    """Always refuse — no mock scores."""
    return {"code": CODE, "message": MESSAGE}


def mark_not_implemented(job: _JobLike, message: Optional[str] = None) -> _JobLike:
    """Mutate a job-like object to the honest terminal state."""
    job.status = "not_implemented"
    job.error_code = CODE
    job.message = message or MESSAGE
    return job


def claim_pending_jobs(jobs: list[_JobLike]) -> list[_JobLike]:
    """
    Mark given pending jobs as not_implemented (honest, no scores).

    Callers that talk to the API DB should query status=pending themselves
    and pass rows in. Upload already writes not_implemented, so this is
    usually a no-op.
    """
    claimed: list[_JobLike] = []
    for job in jobs:
        if getattr(job, "status", None) == "pending":
            mark_not_implemented(job)
            claimed.append(job)
    return claimed


def process_once(pending_jobs: Optional[list[_JobLike]] = None) -> dict[str, Any]:
    """Single tick for future schedulers — drains provided pending jobs."""
    claimed = claim_pending_jobs(pending_jobs or [])
    return {
        "code": CODE,
        "claimed": len(claimed),
        "message": (
            MESSAGE
            if not claimed
            else f"marked {len(claimed)} pending → not_implemented"
        ),
    }
