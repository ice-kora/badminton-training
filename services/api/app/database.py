"""SQLAlchemy engine and session."""
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Lightweight SQLite column adds for evolving MVP schema."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(analysis_jobs)")).fetchall()
        if rows:
            names = {r[1] for r in rows}
            if "scoring_status" not in names:
                conn.execute(
                    text(
                        "ALTER TABLE analysis_jobs ADD COLUMN scoring_status VARCHAR(64)"
                    )
                )
        tv_rows = conn.execute(text("PRAGMA table_info(training_videos)")).fetchall()
        if tv_rows:
            tv_names = {r[1] for r in tv_rows}
            if "baseline_video_id" not in tv_names:
                conn.execute(
                    text(
                        "ALTER TABLE training_videos "
                        "ADD COLUMN baseline_video_id INTEGER"
                    )
                )
        pose_rows = conn.execute(text("PRAGMA table_info(pose_analyses)")).fetchall()
        if pose_rows:
            pose_names = {r[1] for r in pose_rows}
            if "stage_timeline_json" not in pose_names:
                conn.execute(
                    text(
                        "ALTER TABLE pose_analyses "
                        "ADD COLUMN stage_timeline_json TEXT"
                    )
                )

        user_rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        if user_rows:
            user_names = {r[1] for r in user_rows}
            if "handedness" not in user_names:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN handedness VARCHAR(16) DEFAULT 'right'"
                    )
                )
            if "subscribe_opt_in" not in user_names:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN subscribe_opt_in INTEGER DEFAULT 0"
                    )
                )


def init_db() -> None:
    """Create all tables (MVP: create_all; Alembic optional later)."""
    # Import models so metadata is populated
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema()
