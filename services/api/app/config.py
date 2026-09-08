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


@lru_cache
def get_settings() -> Settings:
    return Settings()
