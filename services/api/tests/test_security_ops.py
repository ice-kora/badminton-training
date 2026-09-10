"""P0/P1 security & ops review coverage."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token, create_video_file_token
from app.config import get_settings
from app.database import SessionLocal
from app.models import AnalysisJob
from app.worker.pose_queue import reclaim_stale_extracting_jobs
from tests.video_fixtures import write_solid_video


@pytest.fixture
def skill_id(client) -> int:
    tree = client.get("/skills/tree").json()
    return next(
        s["id"]
        for c in tree["categories"]
        for s in c["skills"]
        if s["code"] == "forehand_clear"
    )


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    d = tmp_path / "media"
    d.mkdir()
    return d


def test_production_rejects_insecure_defaults(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "dev-only-change-me-in-production")
    monkeypatch.setenv("ALLOW_DEV_LOGIN", "true")
    monkeypatch.setenv("DEBUG", "true")
    with pytest.raises(Exception) as ei:
        get_settings()
    msg = str(ei.value).lower()
    assert "jwt_secret" in msg or "insecure" in msg or "production" in msg
    get_settings.cache_clear()
    monkeypatch.delenv("APP_ENV", raising=False)
    # restore test defaults used by conftest
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("ALLOW_DEV_LOGIN", "true")
    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()
    s = get_settings()
    assert s.is_production is False


def test_production_accepts_hardened_settings(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "prod-strong-secret-value-32chars!!")
    monkeypatch.setenv("ALLOW_DEV_LOGIN", "false")
    monkeypatch.setenv("DEBUG", "false")
    s = get_settings()
    assert s.is_production is True
    assert s.allow_dev_login is False
    assert s.debug is False
    get_settings.cache_clear()
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("ALLOW_DEV_LOGIN", "true")
    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()


def test_upload_over_limit_returns_413(
    client: TestClient, auth_headers, skill_id, media_dir, monkeypatch
):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "2048")
    get_settings.cache_clear()
    assert get_settings().upload_max_bytes == 2048

    path = write_solid_video(
        media_dir / "bigish.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )
    # Ensure file larger than 2KiB
    assert path.stat().st_size > 2048

    with path.open("rb") as f:
        r = client.post(
            "/videos/upload",
            headers={
                **auth_headers,
                # Content-Length will be set by httpx; also exercise stream path
            },
            data={
                "skill_id": str(skill_id),
                "client_checklist_json": json.dumps(
                    {"full_body": True, "distance_ok": True, "racket_visible": True}
                ),
            },
            files={"file": (path.name, f, "video/mp4")},
        )
    assert r.status_code == 413, r.text
    detail = r.json().get("detail")
    assert detail is not None

    monkeypatch.setenv("UPLOAD_MAX_BYTES", str(200 * 1024 * 1024))
    get_settings.cache_clear()


def test_video_file_rejects_session_jwt_query(
    client: TestClient, auth_headers, skill_id, media_dir
):
    path = write_solid_video(
        media_dir / "tok.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(180, 180, 180),
    )
    with path.open("rb") as f:
        up = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={
                "skill_id": str(skill_id),
                "client_checklist_json": json.dumps(
                    {"full_body": True, "distance_ok": True, "racket_visible": True}
                ),
            },
            files={"file": (path.name, f, "video/mp4")},
        )
    assert up.status_code == 200, up.text
    vid = up.json()["video"]["id"]
    session_jwt = auth_headers["Authorization"].split(" ", 1)[1]

    bad = client.get(f"/videos/{vid}/file?token={session_jwt}")
    assert bad.status_code == 401

    mint = client.get(f"/videos/{vid}/file-token", headers=auth_headers)
    assert mint.status_code == 200, mint.text
    body = mint.json()
    assert body["token"]
    assert body["expires_in"] <= 15 * 60
    ok = client.get(f"/videos/{vid}/file?token={body['token']}")
    assert ok.status_code == 200
    # Bearer still works without query token
    ok2 = client.get(f"/videos/{vid}/file", headers=auth_headers)
    assert ok2.status_code == 200


def test_reclaim_fails_after_max_attempts(client, auth_headers, skill_id, media_dir):
    path = write_solid_video(
        media_dir / "stale_fail.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(160, 160, 160),
    )
    with path.open("rb") as f:
        up = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={
                "skill_id": str(skill_id),
                "client_checklist_json": json.dumps(
                    {"full_body": True, "distance_ok": True, "racket_visible": True}
                ),
            },
            files={"file": (path.name, f, "video/mp4")},
        )
    assert up.status_code == 200, up.text
    job_id = up.json()["analysis_job"]["id"]

    db = SessionLocal()
    try:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        job.status = "extracting"
        job.attempt_count = 2
        job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            seconds=900
        )
        db.commit()

        n = reclaim_stale_extracting_jobs(db, stale_seconds=600, max_attempts=3)
        assert n == 1
        db.refresh(job)
        assert job.status == "failed"
        assert job.attempt_count == 3
    finally:
        db.close()
