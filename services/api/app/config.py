"""Application settings."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default DB under services/api/data/
_API_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = f"sqlite:///{_API_ROOT / 'data' / 'app.db'}"
_DEFAULT_JWT_SECRET = "dev-only-change-me-in-production"
_INSECURE_JWT_SECRETS = frozenset(
    {
        _DEFAULT_JWT_SECRET,
        "test-secret",
        "secret",
        "changeme",
        "change-me",
    }
)


def _env_is_production() -> bool:
    for key in ("APP_ENV", "ENV", "ENVIRONMENT"):
        val = (os.environ.get(key) or "").strip().lower()
        if val in ("production", "prod"):
            return True
    return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "badminton-ai-coach-api"
    # APP_ENV / ENV / ENVIRONMENT=production triggers fail-fast insecure defaults.
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENV", "app_env"),
    )
    debug: bool = True
    database_url: str = _DEFAULT_DB
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    # Short-lived token for <video src>?token= (not the 7d session JWT).
    video_file_token_expire_minutes: int = 10
    allow_dev_login: bool = True
    upload_dir: str = str(_API_ROOT / "data" / "uploads")
    # Cap upload body before unbounded disk fill (UPLOAD_MAX_BYTES).
    upload_max_bytes: int = 200 * 1024 * 1024
    # Comma-separated whitelist. Never combine allow_origins=* with credentials.
    cors_origins: str = ""
    # Local acceptance: set PRECHECK_RELAX_ORIENTATION=true to allow landscape.
    precheck_relax_orientation: bool = False
    # OpenCV mean-luminance gate (0–255). Gyms are often dim; users may override
    # brightness-only failures via force_upload / precheck_override=brightness.
    precheck_min_brightness: float = 40.0
    # Pose extraction (keypoints only — never scoring)
    pose_extractor: str = "auto"  # auto|mediapipe|fake|null
    pose_max_seconds: int = 60
    pose_frame_stride: int = 2
    # Queue mode default: upload leaves status=queued; run worker separately.
    # POSE_EXTRACT_INLINE=true restores sync extract inside upload (tests/debug).
    pose_extract_inline: bool = False
    # Optional in-API daemon thread (POSE_EXTRACT_BACKGROUND=true). Keep false in tests.
    pose_extract_background: bool = False
    # Worker poll interval seconds (POSE_EXTRACT_POLL_INTERVAL, default 2)
    pose_extract_poll_interval: float = 2.0
    # Reclaim extracting jobs stuck longer than this (POSE_EXTRACT_STALE_SECONDS, default 600)
    pose_extract_stale_seconds: int = 600
    # After this many stale reclaims, mark failed instead of infinite requeue.
    pose_extract_max_attempts: int = 3
    # Original video file TTL (days). Keypoints/scores kept; originals purged.
    video_ttl_days: int = 7
    pose_model_path: str = str(_API_ROOT / "data" / "models" / "pose_landmarker_lite.task")

    @property
    def is_production(self) -> bool:
        if _env_is_production():
            return True
        return (self.app_env or "").strip().lower() in ("production", "prod")

    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if not raw:
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]

    @model_validator(mode="after")
    def _reject_insecure_production_defaults(self) -> Settings:
        if not self.is_production:
            return self
        problems: list[str] = []
        secret = (self.jwt_secret or "").strip()
        if not secret or secret in _INSECURE_JWT_SECRETS or secret.startswith("dev-only"):
            problems.append(
                "JWT_SECRET must be set to a strong non-default value in production"
            )
        if self.allow_dev_login:
            problems.append("ALLOW_DEV_LOGIN must be false in production")
        if self.debug:
            problems.append("DEBUG must be false in production")
        if problems:
            raise ValueError(
                "Insecure production settings rejected at startup:\n- "
                + "\n- ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
