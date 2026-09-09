"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.worker.pose_queue import (
    start_background_worker,
    stop_background_worker,
)
from app.routers import (
    analysis,
    auth,
    benchmarks,
    content,
    filming,
    health,
    plans,
    recommendations,
    sessions,
    skills,
    videos,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        Path("data").mkdir(parents=True, exist_ok=True)
        # Also ensure absolute data dir next to package root
        api_root = Path(__file__).resolve().parent.parent
        (api_root / "data").mkdir(parents=True, exist_ok=True)
        (api_root / "data" / "uploads").mkdir(parents=True, exist_ok=True)
    init_db()
    # Optional lightweight in-API poller (POSE_EXTRACT_BACKGROUND=true)
    start_background_worker()
    try:
        yield
    finally:
        stop_background_worker()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.7.0",
        description=(
            "羽毛球 AI 学习训练助手 API（Phase-2）。"
            "关键点提取支持 DB 队列后台 worker；评分仍返回 ANALYSIS_NOT_IMPLEMENTED。"
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(skills.router)
    app.include_router(filming.router)
    app.include_router(benchmarks.router)
    app.include_router(plans.router)
    app.include_router(sessions.router)
    app.include_router(content.router)
    app.include_router(recommendations.router)
    app.include_router(analysis.router)
    app.include_router(videos.router)
    return app


app = create_app()
