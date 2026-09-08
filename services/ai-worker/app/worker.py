"""Minimal stub documenting NOT_IMPLEMENTED for analyze."""

CODE = "ANALYSIS_NOT_IMPLEMENTED"
MESSAGE = (
    "视频姿态分析尚未实现。本 Worker 不产出动作分数或伪报告；"
    "待标准动作库专家标注完成后接入离线分析流水线。"
)


def describe() -> dict:
    return {"code": CODE, "message": MESSAGE, "status": "stub"}


def analyze(_payload: dict) -> dict:
    """Always refuse — no mock scores."""
    return {"code": CODE, "message": MESSAGE}
