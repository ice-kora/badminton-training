"""Honest NOT_IMPLEMENTED analysis endpoints — no mock scores."""
from fastapi import APIRouter, Response

from app.schemas import AnalysisJobRequest, AnalysisNotImplemented

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/jobs", response_model=AnalysisNotImplemented)
def create_analysis_job(body: AnalysisJobRequest, response: Response):
    """
    Pose / video analysis is intentionally not implemented in Phase-2 MVP.
    Returns structured error body; HTTP 501 to signal not implemented.
    """
    response.status_code = 501
    return AnalysisNotImplemented(
        code="ANALYSIS_NOT_IMPLEMENTED",
        message=(
            "视频姿态分析尚未实现。本阶段仅提供内容、计划、拍摄引导与规则推荐；"
            "禁止返回模拟分数或伪 AI 分析结果。"
            "待 Motion Benchmark 经专家标注入库后再接入分析流水线。"
        ),
        skill_id=body.skill_id,
    )
