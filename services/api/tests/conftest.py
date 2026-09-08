"""Pytest fixtures: fresh SQLite DB + TestClient."""
from __future__ import annotations

import os
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

from app.config import get_settings

get_settings.cache_clear()

from app.database import SessionLocal, init_db
from app.main import create_app
from app.seed import seed


@pytest.fixture(scope="session")
def client():
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    get_settings.cache_clear()
    init_db()
    seed()
    app = create_app()
    with TestClient(app) as c:
        yield c
    if _TEST_DB.exists():
        _TEST_DB.unlink()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    r = client.post(
        "/auth/dev-login",
        json={"openid": "pytest-user", "nickname": "测试球员"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
