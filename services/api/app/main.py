"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
    me,
    plans,
    recommendations,
    sessions,
    skills,
    samples,
    videos,
)
from app.services.viewer3d.glb import write_stick_figure_glb



def _ensure_drill_demo_assets() -> Path:
    """Stick-figure demo GIFs for drills (示意动图，非真人教练)."""
    static_dir = Path(__file__).resolve().parent / "static" / "drills"
    static_dir.mkdir(parents=True, exist_ok=True)
    return static_dir

def _ensure_viewer3d_assets() -> Path:
    """Write synthetic_demo stick GLB next to static HTML on startup."""
    static_dir = Path(__file__).resolve().parent / "static" / "viewer3d"
    static_dir.mkdir(parents=True, exist_ok=True)
    glb_path = static_dir / "stick_figure.synthetic_demo.glb"
    if not glb_path.exists() or glb_path.stat().st_size < 64:
        write_stick_figure_glb(glb_path)
    return static_dir


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
    _ensure_viewer3d_assets()
    _ensure_drill_demo_assets()
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
        version="0.9.0",
        description=(
            "羽毛球 AI 学习训练助手 API（Phase-2 / V3 3D 标准动作演示壳）。"
            "禁止实时摄像头纠错；synthetic_demo 须展示横幅。"
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
    app.include_router(me.router)
    app.include_router(samples.router)

    static_dir = _ensure_viewer3d_assets()
    app.mount(
        "/static/viewer3d",
        StaticFiles(directory=str(static_dir), html=True),
        name="viewer3d_static",
    )

    drills_dir = _ensure_drill_demo_assets()
    app.mount(
        "/static/drills",
        StaticFiles(directory=str(drills_dir)),
        name="drills_static",
    )


    samples_dir = Path(__file__).resolve().parent / "static" / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static/samples",
        StaticFiles(directory=str(samples_dir)),
        name="samples_static",
    )

    return app


app = create_app()
