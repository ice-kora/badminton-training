"""U1/U6 /me next-focus + score-history — real TrainingScore only."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import AnalysisJob, TrainingScore
from app.services.benchmark_pkg import import_package_to_db, load_package
from app.services.pose.fake_extractor import FakePoseExtractor
from app.services.scoring.serialize import derive_cta_drill, derive_primary_issue, score_out
from app.worker.pose_queue import claim_job, process_claimed_job
from tests.video_fixtures import write_solid_video

REPO = Path(__file__).resolve().parents[3]
DEMO = REPO / "docs" / "benchmark" / "demo"
CLEAR_DEMO = DEMO / "forehand_clear.synthetic_demo.json"
SCRIPTS = REPO / "scripts"


def _archive_all_published():
    db = SessionLocal()
    try:
        from app.models import BenchmarkVersion

        rows = db.query(BenchmarkVersion).filter(BenchmarkVersion.status == "published").all()
        for v in rows:
            v.status = "archived"
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _cleanup_published():
    yield
    _archive_all_published()


def _publish_demo(skill_code: str, version: str) -> None:
    env = os.environ.copy()
    cmd = [
        sys.executable,
        str(SCRIPTS / "benchmark_publish.py"),
        skill_code,
        "--version",
        version,
        "--allow-synthetic-demo",
    ]
    r = subprocess.run(
        cmd,
        cwd=str(REPO / "services" / "api"),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout


def _skill_id(client: TestClient, code: str) -> int:
    skills = client.get("/skills/tree").json()
    for cat in skills["categories"]:
        for s in cat["skills"]:
            if s["code"] == code:
                return int(s["id"])
    raise AssertionError(f"skill {code} not found")


def _upload(client: TestClient, headers: dict, skill_id: int, path: Path):
    with path.open("rb") as f:
        r = client.post(
            "/videos/upload",
            headers=headers,
            data={
                "skill_id": str(skill_id),
                "client_checklist_json": json.dumps(
                    {"full_body": True, "distance_ok": True, "racket_visible": True}
                ),
            },
            files={"file": (path.name, f, "video/mp4")},
        )
    assert r.status_code == 200, r.text
    return r.json()


def test_next_focus_empty_beginner_cta(client: TestClient, auth_headers):
    r = client.get("/me/next-focus", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["empty"] is True
    assert body["last_score"] is None
    assert body["primary_issue"] is None
    assert body["issues"] == []
    assert "随机" not in (body.get("message") or "")
    assert "fake" not in (body.get("message") or "").lower()
    assert body["skill"] is not None
    assert body["skill"]["code"] == "forehand_clear"
    assert "filming/guide" in body["cta_path"]
    assert str(body["skill"]["id"]) in body["cta_path"]


def test_score_history_empty(client: TestClient, auth_headers):
    r = client.get("/me/score-history", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_next_focus_and_history_after_score(client: TestClient, auth_headers, tmp_path):
    data = load_package(CLEAR_DEMO)
    db = SessionLocal()
    try:
        _, ver = import_package_to_db(db, data, change_log="ux comfort")
        db.commit()
        version_label = data["version"]
    finally:
        db.close()
    _publish_demo("forehand_clear", version_label)

    clear_id = _skill_id(client, "forehand_clear")
    mp4 = write_solid_video(
        tmp_path / "ux.mp4", width=720, height=1280, duration_sec=6.0, fps=10.0
    )
    body = _upload(client, auth_headers, clear_id, mp4)
    video_id = body["video"]["id"]
    job_id = body["analysis_job"]["id"]

    db = SessionLocal()
    try:
        claimed = claim_job(db, job_id)
        assert claimed is not None
        assert process_claimed_job(db, claimed, extractor=FakePoseExtractor()) == "scored"
        sc = db.query(TrainingScore).filter(TrainingScore.video_id == video_id).one()
        payload = score_out(sc)
        assert payload.primary_issue is not None or len(payload.problems) == 0
        if payload.problems:
            assert payload.primary_issue is not None
            assert derive_primary_issue(payload.problems).error_code == payload.primary_issue.error_code
    finally:
        db.close()

    focus = client.get("/me/next-focus", headers=auth_headers)
    assert focus.status_code == 200, focus.text
    f = focus.json()
    assert f["empty"] is False
    assert f["last_score"] is not None
    assert f["video_id"] == video_id
    assert f["skill"]["code"] == "forehand_clear"
    assert len(f["issues"]) <= 3
    if f["primary_issue"]:
        assert f["primary_issue"]["title"]
        assert f["message"] and "优先改" in f["message"]
    # score serialize fields on analysis job
    job = client.get(f"/analysis/jobs/{job_id}", headers=auth_headers).json()
    assert job["score"] is not None
    assert "primary_issue" in job["score"]
    assert "cta_drill" in job["score"]

    hist = client.get("/me/score-history", headers=auth_headers, params={"limit": 10})
    assert hist.status_code == 200
    items = hist.json()
    assert len(items) >= 1
    assert items[0]["video_id"] == video_id
    assert items[0]["overall_score"] == f["last_score"]
    assert items[0]["benchmark_kind"] == "synthetic_demo"

    filtered = client.get(
        "/me/score-history",
        headers=auth_headers,
        params={"skill": clear_id, "limit": 5},
    )
    assert filtered.status_code == 200
    assert all(i["skill_id"] == clear_id for i in filtered.json())

    # video file stream
    file_r = client.get(f"/videos/{video_id}/file", headers=auth_headers)
    assert file_r.status_code == 200
    assert file_r.headers["content-type"].startswith("video/")
    assert len(file_r.content) > 100


def test_me_requires_auth(client: TestClient):
    assert client.get("/me/next-focus").status_code == 401
    assert client.get("/me/score-history").status_code == 401
