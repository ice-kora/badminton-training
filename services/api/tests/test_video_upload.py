"""V1 filming precheck + upload pipeline tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _upload(client, auth_headers, skill_id: int, video_path: Path, checklist=None):
    data = {"skill_id": str(skill_id)}
    if checklist is not None:
        data["client_checklist_json"] = json.dumps(checklist)
    with video_path.open("rb") as f:
        return client.post(
            "/videos/upload",
            headers=auth_headers,
            data=data,
            files={"file": (video_path.name, f, "video/mp4")},
        )


def test_filming_guide_includes_precheck_policy(client, skill_id):
    r = client.get(f"/filming-guides/{skill_id}")
    assert r.status_code == 200
    g = r.json()[0]
    assert g["duration_range_sec"] == [5, 60]
    assert g["min_resolution"]["min_short_side"] == 720
    assert g["brightness_policy"]["min_mean_luminance"] == 40
    assert "duration" in g["required_checks"]
    assert "full_body" in g["deferred_checks"]


def test_upload_success_creates_video_and_job(
    client, auth_headers, skill_id, media_dir
):
    # Portrait 720x1280, bright, ~8s
    path = write_solid_video(
        media_dir / "ok.mp4",
        width=720,
        height=1280,
        duration_sec=8,
        color_bgr=(200, 200, 200),
    )
    r = _upload(
        client,
        auth_headers,
        skill_id,
        path,
        checklist={"full_body": True, "distance_ok": True, "racket_visible": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["precheck"]["passed"] is True
    assert body["video"]["id"] > 0
    assert body["video"]["width"] == 720
    assert body["video"]["height"] == 1280
    assert body["video"]["orientation"] == "portrait"
    job = body["analysis_job"]
    assert job["status"] == "not_implemented"
    assert job["error_code"] == "ANALYSIS_NOT_IMPLEMENTED"
    assert job.get("benchmark_version_id") is None
    assert "awaiting_published_benchmark" in (job.get("message") or "")
    assert "score" not in job
    assert "scores" not in body
    assert "分析" in body["notice"] or "尚未" in body["notice"]

    vid = client.get(f"/videos/{body['video']['id']}", headers=auth_headers)
    assert vid.status_code == 200
    job_r = client.get(f"/analysis/jobs/{job['id']}", headers=auth_headers)
    assert job_r.status_code == 200
    assert job_r.json()["error_code"] == "ANALYSIS_NOT_IMPLEMENTED"
    assert "score" not in job_r.json()


def test_fail_duration_too_short(client, auth_headers, skill_id, media_dir):
    path = write_solid_video(
        media_dir / "short.mp4",
        width=720,
        height=1280,
        duration_sec=2,
        color_bgr=(200, 200, 200),
    )
    r = _upload(client, auth_headers, skill_id, path)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == "PRECHECK_FAILED"
    checks = {c["id"]: c for c in detail["precheck"]["checks"]}
    assert checks["duration"]["status"] == "fail"


def test_fail_duration_too_long(client, auth_headers, skill_id, media_dir):
    path = write_solid_video(
        media_dir / "long.mp4",
        width=720,
        height=1280,
        duration_sec=70,
        color_bgr=(200, 200, 200),
    )
    r = _upload(client, auth_headers, skill_id, path)
    assert r.status_code == 400
    checks = {c["id"]: c for c in r.json()["detail"]["precheck"]["checks"]}
    assert checks["duration"]["status"] == "fail"


def test_fail_wrong_orientation(client, auth_headers, skill_id, media_dir):
    # Landscape 1280x720
    path = write_solid_video(
        media_dir / "land.mp4",
        width=1280,
        height=720,
        duration_sec=8,
        color_bgr=(200, 200, 200),
    )
    r = _upload(client, auth_headers, skill_id, path)
    assert r.status_code == 400
    checks = {c["id"]: c for c in r.json()["detail"]["precheck"]["checks"]}
    assert checks["orientation"]["status"] == "fail"


def test_fail_low_brightness(client, auth_headers, skill_id, media_dir):
    path = write_solid_video(
        media_dir / "dark.mp4",
        width=720,
        height=1280,
        duration_sec=8,
        color_bgr=(5, 5, 5),
    )
    r = _upload(client, auth_headers, skill_id, path)
    assert r.status_code == 400
    checks = {c["id"]: c for c in r.json()["detail"]["precheck"]["checks"]}
    assert checks["brightness"]["status"] == "fail"


def test_fail_low_resolution(client, auth_headers, skill_id, media_dir):
    path = write_solid_video(
        media_dir / "tiny.mp4",
        width=320,
        height=480,
        duration_sec=8,
        color_bgr=(200, 200, 200),
    )
    r = _upload(client, auth_headers, skill_id, path)
    assert r.status_code == 400
    checks = {c["id"]: c for c in r.json()["detail"]["precheck"]["checks"]}
    assert checks["resolution"]["status"] == "fail"


def test_analysis_still_no_scores(client):
    r = client.post("/analysis/jobs", json={"skill_id": 1})
    assert r.status_code == 501
    body = r.json()
    assert body["code"] == "ANALYSIS_NOT_IMPLEMENTED"
    assert "score" not in body
