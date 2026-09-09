"""Application settings."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default DB under services/api/data/
_API_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = f"sqlite:///{_API_ROOT / 'data' / 'app.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "badminton-ai-coach-api"
    debug: bool = True
    database_url: str = _DEFAULT_DB
    jwt_secret: str = "dev-only-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    allow_dev_login: bool = True
    upload_dir: str = str(_API_ROOT / "data" / "uploads")
    # Local acceptance: set PRECHECK_RELAX_ORIENTATION=true to allow landscape.
    precheck_relax_orientation: bool = False
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
    pose_model_path: str = str(_API_ROOT / "data" / "models" / "pose_landmarker_lite.task")


@lru_cache
def get_settings() -> Settings:
    return Settings()
