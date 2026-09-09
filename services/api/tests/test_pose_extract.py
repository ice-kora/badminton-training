"""Pose keypoint extraction — FakePoseExtractor, no scores."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.pose.fake_extractor import FakePoseExtractor
from app.services.pose.landmarks import POSE_LANDMARK_NAMES
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


def _upload(client, auth_headers, skill_id: int, video_path: Path):
    with video_path.open("rb") as f:
        return client.post(
            "/videos/upload",
            headers=auth_headers,
            data={
                "skill_id": str(skill_id),
                "client_checklist_json": json.dumps(
                    {"full_body": True, "distance_ok": True, "racket_visible": True}
                ),
            },
            files={"file": (video_path.name, f, "video/mp4")},
        )


def test_fake_extractor_writes_deterministic_keypoints(media_dir):
    path = write_solid_video(
        media_dir / "fake.mp4",
        width=720,
        height=1280,
        duration_sec=2,
        fps=10.0,
        color_bgr=(200, 200, 200),
    )
    result = FakePoseExtractor().extract(path, max_seconds=60, sample_stride=2)
    assert result.extractor == "fake_pose"
    assert result.frame_count > 0
    assert result.landmark_names == POSE_LANDMARK_NAMES
    assert "score" not in result.to_json_dict(video_id=1)
    assert result.frames[0]["landmarks"][0]["name"] == "NOSE"


def test_upload_queued_then_manual_extract_pose(
    client, auth_headers, skill_id, media_dir
):
    """Default queue mode: upload leaves queued; POST extract-pose runs Fake sync."""
    path = write_solid_video(
        media_dir / "ok_pose.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )
    r = _upload(client, auth_headers, skill_id, path)
    assert r.status_code == 200, r.text
    body = r.json()
    job = body["analysis_job"]
    assert job["status"] == "queued"
    assert job["scoring_status"] == "blocked"
    assert job["error_code"] == "ANALYSIS_NOT_IMPLEMENTED"
    assert "score" not in job

    video_id = body["video"]["id"]
    pose0 = client.get(f"/videos/{video_id}/pose", headers=auth_headers)
    assert pose0.status_code == 200
    assert pose0.json()["extracted"] is False

    ex = client.post(f"/videos/{video_id}/extract-pose", headers=auth_headers)
    assert ex.status_code == 200, ex.text
    assert ex.json()["analysis_job"]["status"] == "pose_extracted"
    assert ex.json()["analysis_job"]["scoring_status"] == "blocked"

    pose = client.get(f"/videos/{video_id}/pose", headers=auth_headers)
    assert pose.status_code == 200
    meta = pose.json()
    assert meta["extracted"] is True
    assert meta["frame_count"] > 0
    assert meta["extractor"] == "fake_pose"
    assert "NOSE" in meta["landmark_names"]
    assert "score" not in meta
    assert "分数" not in meta.get("notice", "") or "不含评分" in meta.get("notice", "")

    detail = client.get(f"/videos/{video_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["pose_extracted"] is True
    assert detail.json()["pose_frame_count"] > 0


def test_extract_pose_endpoint_idempotent(client, auth_headers, skill_id, media_dir):
    path = write_solid_video(
        media_dir / "again.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )
    up = _upload(client, auth_headers, skill_id, path)
    video_id = up.json()["video"]["id"]
    r1 = client.post(f"/videos/{video_id}/extract-pose", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["pose"]["extracted"] is True
    assert r1.json()["analysis_job"]["scoring_status"] == "blocked"
    r2 = client.post(f"/videos/{video_id}/extract-pose", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["pose"]["frame_count"] == r1.json()["pose"]["frame_count"]


def test_mediapipe_import_optional():
    """Heavy path skipped unless RUN_MEDIAPIPE_TEST=1."""
    import os

    if os.environ.get("RUN_MEDIAPIPE_TEST") != "1":
        pytest.skip("set RUN_MEDIAPIPE_TEST=1 to run real mediapipe smoke")
    from app.services.pose.mediapipe_extractor import mediapipe_available

    assert mediapipe_available()
