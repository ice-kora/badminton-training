"""V1 scoring path: synthetic_demo publish → extract → score → problems ≤3."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import (
    AnalysisJob,
    BadmintonSkill,
    BenchmarkVersion,
    MotionBenchmark,
    PoseProblem,
    TrainingScore,
)
from app.services.benchmark_pkg import (
    BenchmarkValidationError,
    import_package_to_db,
    load_package,
    publish_allowed,
    validate_package,
)
from app.services.pose.fake_extractor import FakePoseExtractor
from app.worker.pose_queue import claim_job, process_claimed_job
from tests.video_fixtures import write_solid_video

REPO = Path(__file__).resolve().parents[3]
DEMO = REPO / "docs" / "benchmark" / "demo"
SCRIPTS = REPO / "scripts"
CLEAR_DEMO = DEMO / "forehand_clear.synthetic_demo.json"


def _archive_all_published():
    db = SessionLocal()
    try:
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

ALL_DEMOS = [
    DEMO / "forehand_clear.synthetic_demo.json",
    DEMO / "forehand_smash.synthetic_demo.json",
    DEMO / "net_tumble.synthetic_demo.json",
]


def _publish_demo(skill_code: str, version: str, *, allow: bool) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    cmd = [
        sys.executable,
        str(SCRIPTS / "benchmark_publish.py"),
        skill_code,
        "--version",
        version,
    ]
    if allow:
        cmd.append("--allow-synthetic-demo")
    return subprocess.run(
        cmd,
        cwd=str(REPO / "services" / "api"),
        env=env,
        capture_output=True,
        text=True,
    )


def _skill_id(client: TestClient, code: str) -> int:
    skills = client.get("/skills/tree").json()
    for cat in skills["categories"]:
        for s in cat["skills"]:
            if s["code"] == code:
                return int(s["id"])
    raise AssertionError(f"skill {code} not found")


def _upload(client: TestClient, headers: dict, skill_id: int, path: Path, baseline=None):
    with path.open("rb") as f:
        form = {
            "skill_id": str(skill_id),
            "client_checklist_json": json.dumps(
                {"full_body": True, "distance_ok": True, "racket_visible": True}
            ),
        }
        if baseline is not None:
            form["baseline_video_id"] = str(baseline)
        r = client.post(
            "/videos/upload",
            headers=headers,
            data=form,
            files={"file": (path.name, f, "video/mp4")},
        )
    assert r.status_code == 200, r.text
    return r.json()


def test_synthetic_demo_packages_validate_with_flag():
    for path in ALL_DEMOS:
        data = load_package(path)
        assert data["verification_status"] == "synthetic_demo"
        assert data["source"] == "engineering_synthetic_demo"
        assert "工程演示基准（非教练标定）" in (data.get("banner") or "")
        with pytest.raises(BenchmarkValidationError):
            validate_package(data)
        warnings = validate_package(data, allow_synthetic_demo=True)
        assert any("synthetic_demo" in w for w in warnings)
        assert all(m.get("range_min") is not None for m in data["metrics"])


def test_production_still_blocks_unverified_non_demo_publish(client):
    ok, reason = publish_allowed("draft_unverified")
    assert ok is False
    assert "draft_unverified" in reason

    ok2, reason2 = publish_allowed("synthetic_demo")
    assert ok2 is False
    assert "allow-synthetic-demo" in reason2

    ok3, _ = publish_allowed("synthetic_demo", allow_synthetic_demo=True)
    assert ok3 is True


def test_demo_publish_extract_score_problems(client: TestClient, auth_headers, tmp_path):
    data = load_package(CLEAR_DEMO)
    db = SessionLocal()
    try:
        _, ver = import_package_to_db(db, data, change_log="pytest synthetic")
        db.commit()
        assert ver.verification_status == "synthetic_demo"
        version_label = data["version"]
    finally:
        db.close()

    r_fail = _publish_demo("forehand_clear", version_label, allow=False)
    assert r_fail.returncode != 0
    assert "synthetic_demo" in (r_fail.stderr + r_fail.stdout)

    r_ok = _publish_demo("forehand_clear", version_label, allow=True)
    assert r_ok.returncode == 0, r_ok.stderr

    clear_id = _skill_id(client, "forehand_clear")
    mp4 = write_solid_video(
        tmp_path / "clear.mp4", width=720, height=1280, duration_sec=6.0, fps=10.0
    )
    body = _upload(client, auth_headers, clear_id, mp4)
    video_id = body["video"]["id"]
    job_id = body["analysis_job"]["id"]
    assert body["analysis_job"]["benchmark_version_id"] is not None

    db = SessionLocal()
    try:
        claimed = claim_job(db, job_id)
        assert claimed is not None
        outcome = process_claimed_job(db, claimed, extractor=FakePoseExtractor())
        assert outcome == "scored"
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        assert job.status == "scored"
        assert job.scoring_status == "scored"
        assert job.error_code is None
        score = (
            db.query(TrainingScore).filter(TrainingScore.video_id == video_id).one_or_none()
        )
        assert score is not None
        assert score.benchmark_kind == "synthetic_demo"
        assert "工程演示基准" in (score.banner or "")
        problems = db.query(PoseProblem).filter(PoseProblem.score_id == score.id).all()
        assert len(problems) <= 3
    finally:
        db.close()

    detail = client.get(f"/videos/{video_id}", headers=auth_headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["benchmark_kind"] == "synthetic_demo"
    assert d["scoring_banner"] and "工程演示基准" in d["scoring_banner"]
    assert d["score"] is not None
    assert "overall_score" in d["score"]
    assert len(d["problems"]) <= 3
    job_detail = client.get(f"/analysis/jobs/{job_id}", headers=auth_headers)
    assert job_detail.status_code == 200
    jd = job_detail.json()
    assert jd["status"] == "scored"
    assert jd["score"] is not None
    assert jd["benchmark_kind"] == "synthetic_demo"


def test_without_published_benchmark_stays_blocked(client: TestClient, auth_headers, tmp_path):
    smash_id = _skill_id(client, "forehand_smash")
    db = SessionLocal()
    try:
        skill = db.query(BadmintonSkill).filter(BadmintonSkill.code == "forehand_smash").one()
        bm = (
            db.query(MotionBenchmark)
            .filter(MotionBenchmark.skill_id == skill.id)
            .one_or_none()
        )
        if bm:
            for v in bm.versions:
                if v.status == "published":
                    v.status = "archived"
            db.commit()
    finally:
        db.close()

    mp4 = write_solid_video(
        tmp_path / "smash.mp4", width=720, height=1280, duration_sec=6.0, fps=10.0
    )
    body = _upload(client, auth_headers, smash_id, mp4)
    job_id = body["analysis_job"]["id"]
    video_id = body["video"]["id"]

    db = SessionLocal()
    try:
        claimed = claim_job(db, job_id)
        assert claimed is not None
        outcome = process_claimed_job(db, claimed, extractor=FakePoseExtractor())
        assert outcome == "pose_extracted"
        job = db.get(AnalysisJob, job_id)
        assert job.status == "pose_extracted"
        assert job.scoring_status == "blocked"
        assert job.error_code == "ANALYSIS_NOT_IMPLEMENTED"
        assert "awaiting_published_benchmark" in (job.message or "")
        assert db.query(TrainingScore).filter(TrainingScore.video_id == video_id).count() == 0
    finally:
        db.close()


def test_retest_score_delta_when_both_scored(client: TestClient, auth_headers, tmp_path):
    data = json.loads(json.dumps(load_package(CLEAR_DEMO)))
    data["version"] = "0.2.1-synthetic-retest"
    db = SessionLocal()
    try:
        import_package_to_db(db, data, change_log="retest demo")
        db.commit()
    finally:
        db.close()
    assert _publish_demo("forehand_clear", data["version"], allow=True).returncode == 0

    clear_id = _skill_id(client, "forehand_clear")
    mp4a = write_solid_video(
        tmp_path / "a.mp4", width=720, height=1280, duration_sec=6.0, fps=10.0
    )
    mp4b = write_solid_video(
        tmp_path / "b.mp4", width=720, height=1280, duration_sec=6.0, fps=10.0
    )
    a = _upload(client, auth_headers, clear_id, mp4a)
    b = _upload(client, auth_headers, clear_id, mp4b, baseline=a["video"]["id"])

    db = SessionLocal()
    try:
        for jid in (a["analysis_job"]["id"], b["analysis_job"]["id"]):
            claimed = claim_job(db, jid)
            assert claimed is not None
            assert process_claimed_job(db, claimed, extractor=FakePoseExtractor()) == "scored"
    finally:
        db.close()

    cmp = client.get(
        f"/videos/{b['video']['id']}/retest-compare",
        headers=auth_headers,
        params={"frame": 0},
    )
    assert cmp.status_code == 200
    body = cmp.json()
    assert body["baseline_score"] is not None
    assert body["current_score"] is not None
    assert body["score_delta"] is not None
    assert body["current_score"]["benchmark_kind"] == "synthetic_demo"
