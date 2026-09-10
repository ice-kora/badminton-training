"""Pytest fixtures: fresh SQLite DB + TestClient."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Isolate test DB before importing app
_TEST_DB = Path(__file__).resolve().parent / "_test.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except PermissionError:
        pass
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

from app.database import engine, init_db
from app.main import create_app
from app.seed import seed


def _safe_unlink(path: Path, retries: int = 8) -> None:
    """Dispose engine and retry unlink — helps Windows file locks."""
    try:
        engine.dispose()
    except Exception:  # noqa: BLE001
        pass
    for i in range(retries):
        try:
            if path.exists():
                path.unlink()
            return
        except PermissionError:
            time.sleep(0.05 * (i + 1))
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001
                pass


@pytest.fixture(scope="session")
def client():
    _safe_unlink(_TEST_DB)
    if _UPLOAD.exists():
        shutil.rmtree(_UPLOAD, ignore_errors=True)
    _UPLOAD.mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    init_db()
    seed()
    app = create_app()
    with TestClient(app) as c:
        yield c
    _safe_unlink(_TEST_DB)
    if _UPLOAD.exists():
        shutil.rmtree(_UPLOAD, ignore_errors=True)


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Shared default user — prefer unique openids in isolation-sensitive tests."""
    r = client.post(
        "/auth/dev-login",
        json={"openid": "pytest-user", "nickname": "测试球员"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def unique_auth_headers(client: TestClient, request) -> dict[str, str]:
    """Per-test user so /me assertions are not polluted by prior scores."""
    openid = f"pytest-{request.node.nodeid}-{os.getpid()}"
    # keep openid within reasonable length
    if len(openid) > 60:
        openid = f"pytest-{abs(hash(request.node.nodeid)) % 10_000_000}-{os.getpid()}"
    r = client.post(
        "/auth/dev-login",
        json={"openid": openid, "nickname": "隔离测试球员"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
