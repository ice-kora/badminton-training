"""Pytest fixtures: fresh SQLite DB + TestClient."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Isolate test DB before importing app
_TEST_DB = Path(__file__).resolve().parent / "_test.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ALLOW_DEV_LOGIN"] = "true"
os.environ["JWT_SECRET"] = "test-secret"
_UPLOAD = Path(__file__).resolve().parent / "_test_uploads"
_UPLOAD.mkdir(parents=True, exist_ok=True)
os.environ["UPLOAD_DIR"] = str(_UPLOAD)
os.environ["POSE_EXTRACTOR"] = "fake"
os.environ["POSE_EXTRACT_INLINE"] = "false"
os.environ["POSE_EXTRACT_BACKGROUND"] = "false"

from app.config import get_settings

get_settings.cache_clear()

from app.database import init_db
from app.main import create_app
from app.seed import seed


@pytest.fixture(scope="session")
def client():
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    if _UPLOAD.exists():
        shutil.rmtree(_UPLOAD, ignore_errors=True)
    _UPLOAD.mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    init_db()
    seed()
    app = create_app()
    with TestClient(app) as c:
        yield c
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    if _UPLOAD.exists():
        shutil.rmtree(_UPLOAD, ignore_errors=True)


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    r = client.post(
        "/auth/dev-login",
        json={"openid": "pytest-user", "nickname": "测试球员"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
