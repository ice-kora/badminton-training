"""Pydantic v2 schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth ----
class DevLoginRequest(BaseModel):
    openid: str = Field(default="dev-user-001", min_length=1)
    nickname: str = Field(default="本地测试球员")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    nickname: str


# ---- Content provenance ----
class ProvenanceMixin(BaseModel):
    source: str
    verification_status: str


# ---- Skills ----
class SkillStageOut(OrmModel, ProvenanceMixin):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: int


class SkillContentBlockOut(OrmModel, ProvenanceMixin):
    id: int
    block_type: str
    title: str
    body: str
    sort_order: int


class SkillBriefOut(OrmModel, ProvenanceMixin):
    id: int
    code: str
    name: str
    summary: Optional[str] = None
    difficulty: str
    sort_order: int


class SkillDetailOut(SkillBriefOut):
    stages: list[SkillStageOut] = []
    content_blocks: list[SkillContentBlockOut] = []


class CategoryTreeOut(OrmModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    skills: list[SkillBriefOut] = []


class SkillTreeOut(BaseModel):
    categories: list[CategoryTreeOut]


# ---- Filming ----
class FilmingGuideOut(OrmModel, ProvenanceMixin):
    id: int
    skill_id: int
    camera_angle: str
    distance_hint: str
    height_hint: str
    orientation: str
    full_body_required: bool
    racket_visible: bool
    lighting_notes: Optional[str] = None
    checklist: list[str] = []


# ---- Drills / errors / tips ----
class DrillOut(OrmModel, ProvenanceMixin):
    id: int
    skill_id: Optional[int] = None
    name: str
    goal: Optional[str] = None
    steps: str
    duration_minutes: int
    intensity: str


class CommonErrorOut(OrmModel, ProvenanceMixin):
    id: int
    skill_id: Optional[int] = None
    title: str
    description: str
    how_to_fix: Optional[str] = None


class TipArticleOut(OrmModel, ProvenanceMixin):
    id: int
    title: str
    summary: Optional[str] = None
    body: str
    tags: Optional[str] = None


# ---- Plans / sessions ----
class LevelTestRequest(BaseModel):
    level: str = Field(description="beginner | intermediate | advanced")
    preferred_skill_codes: list[str] = Field(default_factory=list)


class PlanDayOut(OrmModel):
    id: int
    day_index: int
    focus: str
    drill_ids: list[int] = []
    skill_ids: list[int] = []
    notes: Optional[str] = None
    duration_minutes: int


class PlanOut(OrmModel):
    id: int
    title: str
    level: str
    start_date: date
    end_date: date
    status: str
    rationale: Optional[str] = None
    days: list[PlanDayOut] = []


class CheckInRequest(BaseModel):
    session_date: Optional[date] = None
    plan_id: Optional[int] = None
    plan_day_id: Optional[int] = None
    notes: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class SessionOut(OrmModel):
    id: int
    session_date: date
    plan_id: Optional[int] = None
    plan_day_id: Optional[int] = None
    completed: bool
    notes: Optional[str] = None
    rating: Optional[int] = None
    created_at: datetime


# ---- Recommendations ----
class RecommendationOut(BaseModel):
    title: str
    reason: str
    method: str = "rule_based_from_plan_and_checkins"
    disclaimer: str = (
        "本推荐基于训练计划与打卡记录的规则引擎，不是姿态/AI 动作评分结果。"
    )
    skill_ids: list[int] = []
    drill_ids: list[int] = []
    focus_today: Optional[str] = None
    extras: dict[str, Any] = Field(default_factory=dict)


# ---- Analysis (honest NOT_IMPLEMENTED) ----
class AnalysisJobRequest(BaseModel):
    skill_id: int
    video_uri: Optional[str] = None
    note: Optional[str] = None


class AnalysisNotImplemented(BaseModel):
    code: str = "ANALYSIS_NOT_IMPLEMENTED"
    message: str = (
        "视频姿态分析尚未实现。本阶段仅提供内容、计划与拍摄引导；"
        "分析流水线将在标准动作库经专家标注后接入，禁止返回模拟分数。"
    )
    skill_id: Optional[int] = None
