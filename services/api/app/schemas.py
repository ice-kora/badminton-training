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



class UserProfileOut(BaseModel):
    user_id: int
    nickname: str
    handedness: str = "right"
    level: Optional[str] = None


class UserProfileUpdate(BaseModel):
    handedness: Optional[str] = Field(default=None, pattern="^(left|right)$")
    nickname: Optional[str] = Field(default=None, min_length=1, max_length=64)
    level: Optional[str] = None


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
    code: Optional[str] = None
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
    baseline_video_id: Optional[int] = None
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
    score: Optional["TrainingScoreOut"] = None
    benchmark_kind: Optional[str] = None


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
    baseline_video_id: Optional[int] = None
    created_at: datetime
    latest_job: Optional[AnalysisJobSummaryOut] = None


class BaselineVideoSummaryOut(BaseModel):
    """Linked baseline clip for visual retest — no scores."""

    id: int
    skill_id: int
    skill_name: str
    filename: str
    duration_ms: Optional[int] = None
    orientation: Optional[str] = None
    created_at: datetime
    pose_extracted: bool = False
    pose_frame_count: Optional[int] = None


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
    baseline_video_id: Optional[int] = None
    baseline: Optional[BaselineVideoSummaryOut] = None
    created_at: datetime
    jobs: list[AnalysisJobOut] = Field(default_factory=list)
    pose_extracted: bool = False
    pose_frame_count: Optional[int] = None
    score: Optional["TrainingScoreOut"] = None
    problems: list["PoseProblemOut"] = Field(default_factory=list)
    benchmark_kind: Optional[str] = None
    scoring_banner: Optional[str] = None
    stage_timeline: Optional[dict[str, Any]] = None
    overlay_available: bool = False
    notice: str = "关键点可提取；无已发布标准库时评分不开放"


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


class PoseBoneOut(BaseModel):
    """MediaPipe pose bone edge (landmark index pair)."""

    from_: int = Field(alias="from")
    to: int
    from_name: str
    to_name: str

    model_config = {"populate_by_name": True}


class PoseLandmarkOut(BaseModel):
    name: Optional[str] = None
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


class PosePreviewOut(BaseModel):
    """Single-frame skeleton preview for client canvas (no scoring)."""

    video_id: int
    frame: int
    frame_count: int
    source_frame_index: Optional[int] = None
    timestamp_ms: Optional[int] = None
    landmarks: list[dict[str, Any]] = Field(default_factory=list)
    landmark_names: list[str] = Field(default_factory=list)
    landmark_count: int = 33
    bones: list[dict[str, Any]] = Field(default_factory=list)
    normalized: bool = True
    extractor: Optional[str] = None
    topology: str = "mediapipe_pose_33"
    mapping_note: str = (
        "FakePoseExtractor and MediaPipePoseExtractor both store 33 "
        "MediaPipe landmarks 1:1; bone list is full POSE_CONNECTIONS."
    )
    notice: str = "仅关键点可视化，非评分"


class RetestCompareOut(BaseModel):
    """Side-by-side skeleton frames for baseline vs retest; score delta when both scored."""

    baseline: PosePreviewOut
    current: PosePreviewOut
    baseline_score: Optional["TrainingScoreOut"] = None
    current_score: Optional["TrainingScoreOut"] = None
    score_delta: Optional[float] = None
    notice: str = "复测对比（骨架 + 可选分数差）"


# ---- Scoring ----
class PoseProblemOut(BaseModel):
    error_code: str
    title: str
    severity: str
    metric_id: Optional[str] = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    drills: list[dict[str, Any]] = Field(default_factory=list)
    drill_codes: list[str] = Field(default_factory=list)


class TrainingScoreOut(BaseModel):
    overall_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    problems: list[PoseProblemOut] = Field(default_factory=list)
    primary_issue: Optional[PoseProblemOut] = None
    cta_drill: Optional[dict[str, Any]] = None
    benchmark_kind: str = "synthetic_demo"
    verification_status: Optional[str] = None
    source: Optional[str] = None
    banner: Optional[str] = None
    benchmark_version_id: Optional[int] = None
    benchmark_version_label: Optional[str] = None
    explainable: list[dict[str, Any]] = Field(default_factory=list)


# ---- Me / UX comfort ----
class NextFocusSkillOut(BaseModel):
    id: int
    code: str
    name: str


class NextFocusOut(BaseModel):
    """Homepage next-focus: real score issues or beginner filming CTA (no fake scores)."""

    empty: bool = False
    title: str = "今天优先改 1 件事"
    primary_issue: Optional[PoseProblemOut] = None
    issues: list[PoseProblemOut] = Field(default_factory=list)
    cta_drill: Optional[dict[str, Any]] = None
    skill: Optional[NextFocusSkillOut] = None
    last_score: Optional[float] = None
    video_id: Optional[int] = None
    job_id: Optional[int] = None
    benchmark_kind: Optional[str] = None
    banner: Optional[str] = None
    cta_label: str = "去拍摄"
    cta_path: str = "/pages/filming/guide"
    message: Optional[str] = None


class ScoreHistoryItemOut(BaseModel):
    video_id: int
    job_id: Optional[int] = None
    skill_id: int
    skill_code: Optional[str] = None
    skill_name: str
    overall_score: float
    primary_issue_title: Optional[str] = None
    cta_drill: Optional[dict[str, Any]] = None
    benchmark_kind: Optional[str] = None
    banner: Optional[str] = None
    created_at: datetime


# ---- V2 stage timeline + overlay ----
class StageSegmentOut(BaseModel):
    code: str
    name: str
    sort_order: int = 0
    t0_ms: int
    t1_ms: int
    frame_i0: int = 0
    frame_i1: int = 0
    template_t0_ms: Optional[int] = None
    template_t1_ms: Optional[int] = None
    delta_ms: Optional[int] = None


class StageTimelineOut(BaseModel):
    segments: list[StageSegmentOut] = Field(default_factory=list)
    user_t0_ms: Optional[int] = None
    user_t1_ms: Optional[int] = None
    template_total_ms: Optional[int] = None
    method: Optional[str] = None
    benchmark_kind: Optional[str] = None
    has_template_timing: bool = False
    notice: str = "阶段时间轴为相对时序启发式切分，非专家标注"


class OverlaySkeletonOut(BaseModel):
    role: str
    color: str
    frame: int
    frame_count: int
    timestamp_ms: Optional[int] = None
    landmarks: list[dict[str, Any]] = Field(default_factory=list)
    bones: list[dict[str, Any]] = Field(default_factory=list)
    landmark_count: int = 33
    source: Optional[str] = None
    synthetic: Optional[bool] = None
    synthetic_demo: Optional[bool] = None


class PoseOverlayOut(BaseModel):
    """Standard (green) vs user skeleton overlay — 非评分叠加."""

    video_id: int
    frame: int
    frame_count: int
    user: OverlaySkeletonOut
    standard: OverlaySkeletonOut
    colors: dict[str, str] = Field(default_factory=dict)
    stage_timeline: Optional[dict[str, Any]] = None
    current_stage: Optional[dict[str, Any]] = None
    benchmark_kind: str = "synthetic_demo"
    banner: Optional[str] = None
    notice: str = "非评分叠加"
    label: str = "非评分叠加"
    topology: str = "mediapipe_pose_33"
    landmark_names: list[str] = Field(default_factory=list)


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


# ---- V3 3D standard-action viewer ----
class Viewer3DJointOut(BaseModel):
    index: int
    name: str
    x: float
    y: float
    z: float
    visibility: float = 1.0


class Viewer3DFrameOut(BaseModel):
    timestamp_ms: int
    joints: list[Viewer3DJointOut] = Field(default_factory=list)


class Viewer3DStageMarkerOut(BaseModel):
    code: str
    name: str
    sort_order: int = 0
    t_ms: int = 0
    label: Optional[str] = None


class Viewer3DHudAngleOut(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    stage_code: Optional[str] = None
    value: Any = "N/A"
    display: str = "N/A"
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    range_kind: Optional[str] = None
    active: bool = True
    synthetic_demo: bool = False
    note: Optional[str] = None


class Viewer3DAssetsOut(BaseModel):
    glb_url: Optional[str] = None
    glb_note: Optional[str] = None
    web_viewer_url: Optional[str] = None
    renderer: str = "procedural_canvas_primary"
    choice: Optional[str] = None


class Viewer3DManifestOut(BaseModel):
    skill_id: int
    skill_code: str
    skill_name: str
    title: str = "3D 标准动作（演示）"
    version_label: Optional[str] = None
    version_status: Optional[str] = None
    verification_status: str = "synthetic_demo"
    benchmark_kind: str = "synthetic_demo"
    source: Optional[str] = None
    banner: str
    notice: str
    synthetic_demo: bool = True
    realtime: bool = False
    playback_speeds: list[float] = Field(default_factory=lambda: [0.25, 0.5, 1.0])
    default_speed: float = 1.0
    duration_ms: int = 0
    frame_count: int = 0
    topology: str = "mediapipe_pose_33"
    landmark_names: list[str] = Field(default_factory=list)
    bones: list[dict[str, Any]] = Field(default_factory=list)
    bone_index_pairs: list[list[int]] = Field(default_factory=list)
    stages: list[Viewer3DStageMarkerOut] = Field(default_factory=list)
    keyframes: list[dict[str, Any]] = Field(default_factory=list)
    frames: list[Viewer3DFrameOut] = Field(default_factory=list)
    hud_angles: list[Viewer3DHudAngleOut] = Field(default_factory=list)
    sequence_source: str = "generated_synthetic_demo"
    assets: Viewer3DAssetsOut = Field(default_factory=Viewer3DAssetsOut)
    controls: dict[str, Any] = Field(default_factory=dict)
