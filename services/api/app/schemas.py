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
    duration_range_sec: list[int] = Field(default_factory=lambda: [5, 60])
    min_resolution: dict[str, int] = Field(
        default_factory=lambda: {"min_short_side": 720}
    )
    brightness_policy: dict[str, float] = Field(
        default_factory=lambda: {"min_mean_luminance": 40.0}
    )
    required_checks: list[str] = Field(
        default_factory=lambda: [
            "duration",
            "resolution",
            "brightness",
            "orientation",
        ]
    )
    deferred_checks: list[str] = Field(
        default_factory=lambda: ["full_body", "distance"]
    )
    client_checklist_items: list[str] = Field(
        default_factory=lambda: ["full_body", "distance_ok", "racket_visible"]
    )


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
    code: Optional[str] = None
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


# ---- Video precheck / upload ----
class PrecheckCheckOut(BaseModel):
    id: str
    status: str  # pass|fail|skipped|deferred_to_pose|client_checklist_only
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class PrecheckReportOut(BaseModel):
    passed: bool
    checks: list[PrecheckCheckOut]
    probe: Optional[dict[str, Any]] = None
    policy: Optional[dict[str, Any]] = None


class TrainingVideoOut(OrmModel):
    id: int
    user_id: int
    skill_id: int
    filename: str
    duration_ms: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: Optional[str] = None
    size_bytes: Optional[int] = None
    precheck: Optional[dict[str, Any]] = None
    created_at: datetime


class AnalysisJobOut(OrmModel):
    id: int
    video_id: Optional[int] = None
    skill_id: int
    benchmark_version_id: Optional[int] = None
    status: str
    scoring_status: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Explicit: no scores field — scoring blocked


class VideoUploadOut(BaseModel):
    video: TrainingVideoOut
    analysis_job: AnalysisJobOut
    precheck: PrecheckReportOut
    notice: str = (
        "关键点提取可异步执行；评分未开放（ANALYSIS_NOT_IMPLEMENTED）。"
        "已保存视频与任务元数据，不会返回动作评分。"
    )


# ---- Video / analysis history ----
class AnalysisJobSummaryOut(BaseModel):
    """Lightweight job summary for list views — no scores."""

    id: int
    status: str
    scoring_status: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    benchmark_version_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class VideoListItemOut(BaseModel):
    id: int
    skill_id: int
    skill_name: str
    duration_ms: Optional[int] = None
    orientation: Optional[str] = None
    created_at: datetime
    latest_job: Optional[AnalysisJobSummaryOut] = None


class VideoDetailOut(BaseModel):
    id: int
    user_id: int
    skill_id: int
    skill_name: str
    filename: str
    duration_ms: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: Optional[str] = None
    size_bytes: Optional[int] = None
    precheck: Optional[dict[str, Any]] = None
    created_at: datetime
    jobs: list[AnalysisJobOut] = Field(default_factory=list)
    pose_extracted: bool = False
    pose_frame_count: Optional[int] = None
    notice: str = "关键点可提取；评分尚未开放，不返回分数"


# ---- Pose keypoints (no scoring) ----
class PoseMetaOut(BaseModel):
    video_id: int
    extracted: bool
    frame_count: Optional[int] = None
    fps: Optional[float] = None
    extractor: Optional[str] = None
    keypoint_path: Optional[str] = None
    landmark_names: list[str] = Field(default_factory=list)
    sample_stride: Optional[int] = None
    max_seconds: Optional[float] = None
    landmark_count: Optional[int] = None
    job_status: Optional[str] = None
    scoring_status: Optional[str] = None
    notice: str = "仅关键点序列，不含评分或动作正确性判断"


class PoseExtractOut(BaseModel):
    video_id: int
    analysis_job: AnalysisJobOut
    pose: PoseMetaOut
    notice: str = "关键点提取完成或已排队；评分未开放"


# ---- Motion Benchmark (read-only) ----
class BenchmarkStageOut(BaseModel):
    code: str
    name: str
    sort_order: int = 0


class BenchmarkMetricOut(BaseModel):
    id: str
    name: str
    unit: Optional[str] = None
    stage_code: Optional[str] = None
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    notes: Optional[str] = None


class BenchmarkVersionOut(BaseModel):
    id: int
    version_label: str
    status: str
    verification_status: str
    source: str
    change_log: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    stages: list[BenchmarkStageOut] = Field(default_factory=list)
    metrics: list[BenchmarkMetricOut] = Field(default_factory=list)
    package: Optional[dict[str, Any]] = None


class BenchmarkListItemOut(BaseModel):
    skill_id: int
    skill_code: str
    skill_name: str
    benchmark_id: int
    name: str
    handedness: Optional[str] = None
    camera_view: Optional[str] = None
    verification_status: str
    source: str
    has_published_version: bool = False
    published_version_label: Optional[str] = None
    latest_version_label: Optional[str] = None
    latest_version_status: Optional[str] = None


class BenchmarkDetailOut(BaseModel):
    skill_id: int
    skill_code: str
    skill_name: str
    benchmark_id: int
    name: str
    handedness: Optional[str] = None
    camera_view: Optional[str] = None
    notes: Optional[str] = None
    verification_status: str
    source: str
    has_published_version: bool = False
    current: Optional[BenchmarkVersionOut] = None
    notice: str = "姿态分析尚未开放，不返回分数"
