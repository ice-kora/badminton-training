"""SQLAlchemy models for badminton coach MVP."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="球员")
    level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # beginner/intermediate/advanced
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plans: Mapped[list[TrainingPlan]] = relationship(back_populates="user")
    sessions: Mapped[list[TrainingSession]] = relationship(back_populates="user")


class SkillCategory(Base):
    __tablename__ = "skill_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    skills: Mapped[list[BadmintonSkill]] = relationship(back_populates="category")


class BadmintonSkill(Base):
    __tablename__ = "badminton_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("skill_categories.id"))
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(32), default="beginner")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(128), default="editorial_draft")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )  # draft_unverified|expert_pending|verified

    category: Mapped[SkillCategory] = relationship(back_populates="skills")
    stages: Mapped[list[SkillStage]] = relationship(
        back_populates="skill", order_by="SkillStage.sort_order"
    )
    content_blocks: Mapped[list[SkillContentBlock]] = relationship(
        back_populates="skill", order_by="SkillContentBlock.sort_order"
    )
    common_errors: Mapped[list[CommonError]] = relationship(back_populates="skill")
    drills: Mapped[list[Drill]] = relationship(back_populates="skill")
    filming_guides: Mapped[list[FilmingGuide]] = relationship(back_populates="skill")
    motion_benchmarks: Mapped[list[MotionBenchmark]] = relationship(
        back_populates="skill"
    )


class SkillStage(Base):
    __tablename__ = "skill_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("badminton_skills.id"))
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(128), default="editorial_draft")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )

    skill: Mapped[BadmintonSkill] = relationship(back_populates="stages")


class SkillContentBlock(Base):
    __tablename__ = "skill_content_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("badminton_skills.id"))
    block_type: Mapped[str] = mapped_column(String(32))  # overview|key_points|cues|notes
    title: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(128), default="editorial_draft")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )

    skill: Mapped[BadmintonSkill] = relationship(back_populates="content_blocks")


class CommonError(Base):
    __tablename__ = "common_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("badminton_skills.id"), nullable=True
    )
    code: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    how_to_fix: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(128), default="editorial_draft")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )

    skill: Mapped[Optional[BadmintonSkill]] = relationship(back_populates="common_errors")
    problem_links: Mapped[list[ProblemToDrill]] = relationship(back_populates="error")


class TipArticle(Base):
    __tablename__ = "tip_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    tags: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    source: Mapped[str] = mapped_column(String(128), default="editorial_draft")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Drill(Base):
    __tablename__ = "drills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("badminton_skills.id"), nullable=True
    )
    code: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps: Mapped[str] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=10)
    intensity: Mapped[str] = mapped_column(String(32), default="medium")
    source: Mapped[str] = mapped_column(String(128), default="editorial_draft")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )

    skill: Mapped[Optional[BadmintonSkill]] = relationship(back_populates="drills")
    problem_links: Mapped[list[ProblemToDrill]] = relationship(back_populates="drill")


class ProblemToDrill(Base):
    """Maps a common error (problem) to a corrective drill."""

    __tablename__ = "problem_to_drill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    error_id: Mapped[int] = mapped_column(ForeignKey("common_errors.id"))
    drill_id: Mapped[int] = mapped_column(ForeignKey("drills.id"))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    error: Mapped[CommonError] = relationship(back_populates="problem_links")
    drill: Mapped[Drill] = relationship(back_populates="problem_links")


class FilmingGuide(Base):
    """Product UX filming guidelines — NOT numerical joint-angle standards."""

    __tablename__ = "filming_guides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("badminton_skills.id"))
    camera_angle: Mapped[str] = mapped_column(String(128))
    distance_hint: Mapped[str] = mapped_column(String(128))
    height_hint: Mapped[str] = mapped_column(String(128))
    orientation: Mapped[str] = mapped_column(String(32), default="portrait")
    full_body_required: Mapped[int] = mapped_column(Integer, default=1)
    racket_visible: Mapped[int] = mapped_column(Integer, default=1)
    lighting_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checklist_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # V1 precheck policy (engineering checks — not pose standards)
    duration_min_sec: Mapped[int] = mapped_column(Integer, default=5)
    duration_max_sec: Mapped[int] = mapped_column(Integer, default=60)
    min_short_side: Mapped[int] = mapped_column(Integer, default=720)
    min_brightness: Mapped[int] = mapped_column(Integer, default=40)
    precheck_policy_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(128), default="product_ux_guideline")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )

    skill: Mapped[BadmintonSkill] = relationship(back_populates="filming_guides")


class MotionBenchmark(Base):
    """
    Motion benchmark shell per skill. Packages live in BenchmarkVersion rows.
    Do NOT invent joint-angle standards; metric ranges stay null until verified.
    """

    __tablename__ = "motion_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("badminton_skills.id"))
    name: Mapped[str] = mapped_column(String(128))
    handedness: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    camera_view: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Legacy shell field — prefer version.package_json / metrics rows
    metric_table_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # NULL = expert annotation required
    source: Mapped[str] = mapped_column(String(128), default="placeholder_shell")
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )

    skill: Mapped[BadmintonSkill] = relationship(back_populates="motion_benchmarks")
    versions: Mapped[list[BenchmarkVersion]] = relationship(
        back_populates="benchmark", order_by="BenchmarkVersion.id"
    )


class BenchmarkVersion(Base):
    """Imported / published package version. status: draft|published|archived."""

    __tablename__ = "benchmark_versions"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "version_label", name="uq_bm_version_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    benchmark_id: Mapped[int] = mapped_column(ForeignKey("motion_benchmarks.id"))
    version_label: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|published|archived
    verification_status: Mapped[str] = mapped_column(
        String(32), default="draft_unverified"
    )
    source: Mapped[str] = mapped_column(String(128), default="placeholder_shell")
    # Full package JSON as imported (authoritative asset snapshot)
    package_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Denormalized metrics array (may mirror package); null ranges OK
    metrics_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    benchmark: Mapped[MotionBenchmark] = relationship(back_populates="versions")
    stages: Mapped[list[BenchmarkStage]] = relationship(
        back_populates="version", order_by="BenchmarkStage.sort_order"
    )
    metrics: Mapped[list[BenchmarkMetric]] = relationship(back_populates="version")


class BenchmarkStage(Base):
    """Stage names from a benchmark package (no numerical standards)."""

    __tablename__ = "benchmark_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("benchmark_versions.id"))
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    version: Mapped[BenchmarkVersion] = relationship(back_populates="stages")


class BenchmarkMetric(Base):
    """
    Metric shell rows. range_min / range_max MUST be null until expert verification.
    """

    __tablename__ = "benchmark_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("benchmark_versions.id"))
    metric_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    stage_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    range_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    range_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    version: Mapped[BenchmarkVersion] = relationship(back_populates="metrics")


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(128))
    level: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active")
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="plans")
    days: Mapped[list[TrainingPlanDay]] = relationship(
        back_populates="plan", order_by="TrainingPlanDay.day_index"
    )


class TrainingPlanDay(Base):
    __tablename__ = "training_plan_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"))
    day_index: Mapped[int] = mapped_column(Integer)
    focus: Mapped[str] = mapped_column(String(128))
    drill_ids_csv: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    skill_ids_csv: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)

    plan: Mapped[TrainingPlan] = relationship(back_populates="days")


class TrainingSession(Base):
    """Check-in / training log entry."""

    __tablename__ = "training_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "session_date", "plan_day_id", name="uq_session_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_plans.id"), nullable=True
    )
    plan_day_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_plan_days.id"), nullable=True
    )
    session_date: Mapped[date] = mapped_column(Date)
    completed: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5 self rating
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="sessions")


class TrainingVideo(Base):
    """Uploaded training clip metadata (local filesystem storage for MVP)."""

    __tablename__ = "training_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("badminton_skills.id"), index=True)
    storage_path: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(256))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    orientation: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    precheck_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="video")


class AnalysisJob(Base):
    """
    Analysis job shell. V1 does NOT run pose; status stays not_implemented / pending.
    Never store fake scores here.
    """

    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_videos.id"), nullable=True, index=True
    )
    skill_id: Mapped[int] = mapped_column(ForeignKey("badminton_skills.id"), index=True)
    benchmark_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("benchmark_versions.id"), nullable=True, index=True
    )
    # pending|rejected_precheck|queued|not_implemented|failed
    status: Mapped[str] = mapped_column(String(32), default="not_implemented")
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    video: Mapped[Optional[TrainingVideo]] = relationship(back_populates="analysis_jobs")
