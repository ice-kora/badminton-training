"""V2: stage timeline segments + standard/user overlay JSON."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import AnalysisJob, BenchmarkVersion
from app.services.benchmark_pkg import import_package_to_db, load_package
from app.services.pose.fake_extractor import FakePoseExtractor
from app.services.scoring.overlay import (
    OVERLAY_NOTICE,
    STANDARD_COLOR,
    USER_COLOR,
    build_overlay_json,
    generate_synthetic_template_sequence,
    resolve_standard_sequence,
)
from app.services.scoring.stage_timeline import build_stage_timeline, timeline_from_package
from app.worker.pose_queue import claim_job, process_claimed_job
from tests.video_fixtures import write_solid_video

REPO = Path(__file__).resolve().parents[3]
DEMO = REPO / "docs" / "benchmark" / "demo"
SCRIPTS = REPO / "scripts"
CLEAR_DEMO = DEMO / "forehand_clear.synthetic_demo.json"


def _archive_all_published():
    try:
        db = SessionLocal()
    except Exception:
        return
    try:
        rows = db.query(BenchmarkVersion).filter(BenchmarkVersion.status == "published").all()
        for v in rows:
            v.status = "archived"
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@pytest.fixture
def _cleanup_published():
    yield
    _archive_all_published()


def _publish_demo(skill_code: str, version: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "benchmark_publish.py"),
            skill_code,
            "--version",
            version,
            "--allow-synthetic-demo",
        ],
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


def test_build_stage_timeline_relative_and_delta():
    pkg = load_package(CLEAR_DEMO)
    # Fake user pose spanning 0..2000ms (5 frames)
    frames = []
    for i, t in enumerate([0, 500, 1000, 1500, 2000]):
        frames.append(
            {
                "frame_index": i,
                "timestamp_ms": t,
                "landmarks": [{"name": "NOSE", "x": 0.5, "y": 0.2, "z": 0, "visibility": 1}],
            }
        )
    pose = {"frames": frames, "landmark_names": ["NOSE"]}
    tl = timeline_from_package(pose, pkg)
    segs = tl["segments"]
    assert len(segs) == len(pkg["stages"])
    assert segs[0]["code"] == "ready"
    assert segs[0]["t0_ms"] == 0
    assert segs[-1]["t1_ms"] == 2000
    # continuous coverage
    for i in range(len(segs) - 1):
        assert segs[i]["t1_ms"] == segs[i + 1]["t0_ms"]
    assert tl["has_template_timing"] is True
    assert any(s.get("delta_ms") is not None for s in segs)
    assert "启发式" in tl["notice"] or "synthetic_demo" in tl["notice"]


def test_equal_split_without_keyframes():
    pose = {
        "frames": [
            {"timestamp_ms": 0, "landmarks": []},
            {"timestamp_ms": 900, "landmarks": []},
        ]
    }
    stages = [
        {"code": "a", "name": "A", "sort_order": 1},
        {"code": "b", "name": "B", "sort_order": 2},
        {"code": "c", "name": "C", "sort_order": 3},
    ]
    tl = build_stage_timeline(pose, stages=stages, keyframes=[])
    assert len(tl["segments"]) == 3
    assert tl["has_template_timing"] is False
    assert all(s["delta_ms"] is None for s in tl["segments"])
    assert tl["segments"][0]["t0_ms"] == 0
    assert tl["segments"][-1]["t1_ms"] == 900


def test_overlay_prefers_package_template_and_labels():
    pkg = load_package(CLEAR_DEMO)
    user_frames = []
    for i in range(8):
        user_frames.append(
            {
                "frame_index": i,
                "timestamp_ms": i * 100,
                "landmarks": [
                    {"name": n, "x": 0.4, "y": 0.3, "z": 0, "visibility": 1.0}
                    for n in (pkg["synthetic_keypoint_template"]["landmark_names"])
                ],
            }
        )
    pose = {
        "frames": user_frames,
        "landmark_names": pkg["synthetic_keypoint_template"]["landmark_names"],
        "extractor": "fake_pose",
    }
    tmp = Path("/tmp/v2_overlay_user.json")
    tmp.write_text(json.dumps(pose), encoding="utf-8")
    out = build_overlay_json(
        video_id=1,
        keypoint_path=tmp,
        frame=3,
        package=pkg,
    )
    assert out["notice"] == OVERLAY_NOTICE
    assert out["label"] == OVERLAY_NOTICE
    assert out["colors"]["standard"] == STANDARD_COLOR
    assert out["colors"]["user"] == USER_COLOR
    assert out["standard"]["color"] == STANDARD_COLOR
    assert out["user"]["color"] == USER_COLOR
    assert out["standard"]["source"] == "package_template"
    assert out["standard"]["synthetic_demo"] is True
    assert out["benchmark_kind"] == "synthetic_demo"
    assert "工程演示基准" in (out["banner"] or "")
    assert out["stage_timeline"] is not None
    assert out["stage_timeline"]["segments"]
    assert out["frame"] == 3
    assert len(out["user"]["landmarks"]) == 33
    assert len(out["standard"]["landmarks"]) == 33


def test_overlay_generates_synthetic_when_no_template():
    seq, source, syn = resolve_standard_sequence(
        {"verification_status": "synthetic_demo", "stages": []},
        user_frame_count=10,
        user_duration_ms=800,
    )
    assert syn is True
    assert source == "generated_synthetic_demo"
    assert len(seq["frames"]) >= 4
    gen = generate_synthetic_template_sequence(frame_count=5, duration_ms=500)
    assert gen["synthetic_demo"] is True
    assert len(gen["frames"]) == 5


def test_api_stage_timeline_and_overlay(client: TestClient, auth_headers, tmp_path, _cleanup_published):
    data = load_package(CLEAR_DEMO)
    data = json.loads(json.dumps(data))
    data["version"] = "0.2.0-synthetic-v2"
    db = SessionLocal()
    try:
        import_package_to_db(db, data, change_log="v2 pytest")
        db.commit()
    finally:
        db.close()
    assert _publish_demo("forehand_clear", data["version"]).returncode == 0

    clear_id = _skill_id(client, "forehand_clear")
    mp4 = write_solid_video(
        tmp_path / "v2.mp4", width=720, height=1280, duration_sec=6.0, fps=10.0
    )
    body = _upload(client, auth_headers, clear_id, mp4)
    video_id = body["video"]["id"]
    job_id = body["analysis_job"]["id"]

    db = SessionLocal()
    try:
        claimed = claim_job(db, job_id)
        assert claimed is not None
        outcome = process_claimed_job(db, claimed, extractor=FakePoseExtractor())
        assert outcome == "scored"
        job = db.get(AnalysisJob, job_id)
        assert job.status == "scored"
    finally:
        db.close()

    detail = client.get(f"/videos/{video_id}", headers=auth_headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["pose_extracted"] is True
    assert d["overlay_available"] is True
    assert d["stage_timeline"] is not None
    assert len(d["stage_timeline"]["segments"]) >= 2
    assert d["stage_timeline"]["segments"][0]["name"]
    assert "t0_ms" in d["stage_timeline"]["segments"][0]
    assert "t1_ms" in d["stage_timeline"]["segments"][0]

    tl = client.get(f"/videos/{video_id}/stage-timeline", headers=auth_headers)
    assert tl.status_code == 200
    tlj = tl.json()
    assert len(tlj["segments"]) >= 2
    assert tlj["has_template_timing"] is True
    # optional delta vs template
    assert any(s.get("delta_ms") is not None for s in tlj["segments"])

    ov = client.get(
        f"/videos/{video_id}/pose/overlay",
        headers=auth_headers,
        params={"frame": 0},
    )
    assert ov.status_code == 200
    oj = ov.json()
    assert oj["notice"] == "非评分叠加"
    assert oj["label"] == "非评分叠加"
    assert oj["standard"]["color"] == STANDARD_COLOR
    assert oj["user"]["color"] == USER_COLOR
    assert oj["benchmark_kind"] == "synthetic_demo"
    assert "工程演示基准" in (oj["banner"] or "")
    assert oj["standard"]["synthetic_demo"] is True
    assert oj["stage_timeline"] is not None
    assert len(oj["user"]["landmarks"]) > 0
    assert len(oj["standard"]["landmarks"]) > 0
    assert "bones" in oj["user"] and oj["user"]["bones"]
