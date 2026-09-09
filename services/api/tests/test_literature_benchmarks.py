"""literature_cited packages: citations required, publish flag, scoring works."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.models import AnalysisJob, TrainingScore
from app.services.benchmark_pkg import (
    LITERATURE_BANNER,
    LITERATURE_SOURCE,
    BenchmarkValidationError,
    import_package_to_db,
    load_package,
    publish_allowed,
    validate_package,
)
from app.services.pose.fake_extractor import FakePoseExtractor
from app.services.scoring.pose_scorer import PoseScorer
from app.worker.pose_queue import claim_job, process_claimed_job
from tests.video_fixtures import write_solid_video

REPO = Path(__file__).resolve().parents[3]
LIT = REPO / "docs" / "benchmark" / "literature"
SCRIPTS = REPO / "scripts"
ALL_LIT = [
    LIT / "forehand_smash.literature_v1.json",
    LIT / "net_tumble.literature_v1.json",
    LIT / "forehand_clear.literature_v1.json",
]


def _archive_all_published():
    from sqlalchemy.exc import OperationalError

    from app.models import BenchmarkVersion

    db = SessionLocal()
    try:
        rows = db.query(BenchmarkVersion).filter(BenchmarkVersion.status == "published").all()
        for v in rows:
            v.status = "archived"
        db.commit()
    except OperationalError:
        db.rollback()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _cleanup_published(request):
    # Only touch DB when a test uses the client fixture (tables exist).
    if "client" in request.fixturenames:
        yield
        _archive_all_published()
    else:
        yield


def test_literature_packages_validate_with_flag():
    for path in ALL_LIT:
        data = load_package(path)
        assert data["verification_status"] == "literature_cited"
        assert data["source"] == LITERATURE_SOURCE
        assert LITERATURE_BANNER in (data.get("banner") or "")
        with pytest.raises(BenchmarkValidationError) as ei:
            validate_package(data)
        assert "allow-literature-cited" in str(ei.value)
        warnings = validate_package(data, allow_literature_cited=True)
        assert any("literature_cited" in w for w in warnings)
        for m in data["metrics"]:
            if m.get("range_min") is not None or m.get("range_max") is not None:
                assert m.get("range_kind") in {
                    "literature_mean_sd",
                    "literature_point_tolerance",
                    "literature_proxy_related_stroke",
                }
                assert m.get("citations") and isinstance(m["citations"], list)
                for c in m["citations"]:
                    assert c.get("title") and c.get("doi_or_url")
                    assert c.get("extracted") and c.get("year") is not None


def test_literature_rejects_missing_citations():
    data = load_package(LIT / "forehand_smash.literature_v1.json")
    data = json.loads(json.dumps(data))
    # strip citations from a numeric metric
    for m in data["metrics"]:
        if m.get("range_min") is not None:
            m["citations"] = []
            break
    with pytest.raises(BenchmarkValidationError) as ei:
        validate_package(data, allow_literature_cited=True)
    assert "citations" in str(ei.value)


def test_literature_rejects_bad_range_kind():
    data = load_package(LIT / "net_tumble.literature_v1.json")
    data = json.loads(json.dumps(data))
    for m in data["metrics"]:
        if m.get("range_min") is not None:
            m["range_kind"] = "synthetic_demo"
            break
    with pytest.raises(BenchmarkValidationError) as ei:
        validate_package(data, allow_literature_cited=True)
    assert "range_kind" in str(ei.value)


def test_publish_allowed_literature_flag():
    ok, reason = publish_allowed("literature_cited")
    assert ok is False
    assert "allow-literature-cited" in reason
    ok2, reason2 = publish_allowed("literature_cited", allow_literature_cited=True)
    assert ok2 is True
    assert "literature_cited" in reason2


def test_literature_publish_and_score(client, auth_headers, tmp_path):
    data = load_package(LIT / "forehand_smash.literature_v1.json")
    db = SessionLocal()
    try:
        _, ver = import_package_to_db(db, data, change_log="pytest lit")
        db.commit()
        assert ver.verification_status == "literature_cited"
        version_label = data["version"]
    finally:
        db.close()

    env = os.environ.copy()
    r_fail = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "benchmark_publish.py"),
            "forehand_smash",
            "--version",
            version_label,
        ],
        cwd=str(REPO / "services" / "api"),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r_fail.returncode != 0
    assert "literature_cited" in (r_fail.stderr + r_fail.stdout)

    r_ok = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "benchmark_publish.py"),
            "forehand_smash",
            "--version",
            version_label,
            "--allow-literature-cited",
        ],
        cwd=str(REPO / "services" / "api"),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r_ok.returncode == 0, r_ok.stderr

    # unit score against package
    fake_pose = {
        "frames": [
            {
                "timestamp_ms": 0,
                "landmarks": [
                    {"name": "LEFT_SHOULDER", "x": 0.40, "y": 0.30, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_SHOULDER", "x": 0.60, "y": 0.28, "z": 0.0, "visibility": 1.0},
                    {"name": "LEFT_ELBOW", "x": 0.36, "y": 0.42, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_ELBOW", "x": 0.72, "y": 0.25, "z": 0.0, "visibility": 1.0},
                    {"name": "LEFT_WRIST", "x": 0.34, "y": 0.52, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_WRIST", "x": 0.78, "y": 0.18, "z": 0.0, "visibility": 1.0},
                    {"name": "LEFT_HIP", "x": 0.44, "y": 0.55, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_HIP", "x": 0.54, "y": 0.55, "z": 0.0, "visibility": 1.0},
                ],
            },
            {
                "timestamp_ms": 200,
                "landmarks": [
                    {"name": "LEFT_SHOULDER", "x": 0.42, "y": 0.30, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_SHOULDER", "x": 0.58, "y": 0.26, "z": 0.0, "visibility": 1.0},
                    {"name": "LEFT_ELBOW", "x": 0.38, "y": 0.40, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_ELBOW", "x": 0.64, "y": 0.20, "z": 0.0, "visibility": 1.0},
                    {"name": "LEFT_WRIST", "x": 0.36, "y": 0.50, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_WRIST", "x": 0.62, "y": 0.08, "z": 0.0, "visibility": 1.0},
                    {"name": "LEFT_HIP", "x": 0.44, "y": 0.54, "z": 0.0, "visibility": 1.0},
                    {"name": "RIGHT_HIP", "x": 0.54, "y": 0.54, "z": 0.0, "visibility": 1.0},
                ],
            },
        ]
    }
    result = PoseScorer().score(fake_pose, data)
    assert result.benchmark_kind == "literature_cited"
    assert LITERATURE_BANNER in result.banner
    assert result.verification_status == "literature_cited"
    assert result.source == LITERATURE_SOURCE
    assert len(result.metrics) >= 3

    # end-to-end extract → score with published lit package
    skills = client.get("/skills/tree").json()
    smash_id = None
    for cat in skills["categories"]:
        for s in cat["skills"]:
            if s["code"] == "forehand_smash":
                smash_id = int(s["id"])
    assert smash_id is not None
    mp4 = write_solid_video(
        tmp_path / "smash_lit.mp4", width=720, height=1280, duration_sec=5.0, fps=10.0
    )
    with mp4.open("rb") as f:
        r = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={
                "skill_id": str(smash_id),
                "client_checklist_json": json.dumps(
                    {"full_body": True, "distance_ok": True, "racket_visible": True}
                ),
            },
            files={"file": (mp4.name, f, "video/mp4")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
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
        assert job is not None and job.status == "scored"
        score = (
            db.query(TrainingScore).filter(TrainingScore.video_id == video_id).one_or_none()
        )
        assert score is not None
        assert score.benchmark_kind == "literature_cited"
        assert LITERATURE_BANNER in (score.banner or "")
    finally:
        db.close()

    detail = client.get(f"/videos/{video_id}", headers=auth_headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["benchmark_kind"] == "literature_cited"
    assert d["scoring_banner"] and "文献抽取" in d["scoring_banner"]
    assert d["score"] is not None


def test_validate_cli_literature():
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "benchmark_validate.py"),
            str(LIT / "forehand_clear.literature_v1.json"),
            "--allow-literature-cited",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "OK:" in r.stdout
