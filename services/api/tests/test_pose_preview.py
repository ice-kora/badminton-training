"""Pose skeleton preview — JSON shape / 404; no scoring."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.pose.landmarks import POSE_CONNECTIONS, POSE_LANDMARK_NAMES, bone_edges
from tests.video_fixtures import write_solid_video


def test_bone_edges_mediapipe_33():
    edges = bone_edges(landmark_count=33)
    assert len(edges) == len(POSE_CONNECTIONS)
    assert edges[0]["from_name"] == POSE_LANDMARK_NAMES[edges[0]["from"]]
    short = bone_edges(landmark_count=12)
    assert all(e["from"] < 12 and e["to"] < 12 for e in short)
    assert len(short) < len(edges)


def _skill_id(client) -> int:
    tree = client.get("/skills/tree").json()
    return next(
        s["id"]
        for c in tree["categories"]
        for s in c["skills"]
        if s["code"] == "forehand_clear"
    )


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


def test_pose_preview_json_when_extracted(client, auth_headers, tmp_path):
    skill_id = _skill_id(client)
    path = write_solid_video(
        tmp_path / "prev.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )
    up = _upload(client, auth_headers, skill_id, path)
    assert up.status_code == 200, up.text
    video_id = up.json()["video"]["id"]
    assert up.json()["analysis_job"]["status"] == "queued"
    ex = client.post(f"/videos/{video_id}/extract-pose", headers=auth_headers)
    assert ex.status_code == 200, ex.text
    assert ex.json()["analysis_job"]["status"] == "pose_extracted"

    r = client.get(
        f"/videos/{video_id}/pose/preview",
        headers=auth_headers,
        params={"frame": 0, "format": "json"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["video_id"] == video_id
    assert body["frame"] == 0
    assert body["frame_count"] > 0
    assert body["normalized"] is True
    assert body["topology"] == "mediapipe_pose_33"
    assert "仅关键点可视化" in body["notice"]
    assert "非评分" in body["notice"]
    assert len(body["landmarks"]) == 33
    assert body["landmarks"][0]["name"] == "NOSE"
    assert "x" in body["landmarks"][0] and "y" in body["landmarks"][0]
    assert len(body["bones"]) == len(POSE_CONNECTIONS)
    assert body["bones"][0]["from"] == POSE_CONNECTIONS[0][0]
    assert body["bones"][0]["to"] == POSE_CONNECTIONS[0][1]
    assert "score" not in body
    dumped = json.dumps(body).lower()
    assert "correctness" not in dumped

    r2 = client.get(
        f"/videos/{video_id}/pose/preview",
        headers=auth_headers,
        params={"frame": 1},
    )
    assert r2.status_code == 200
    assert r2.json()["frame"] == 1

    png = client.get(
        f"/videos/{video_id}/pose/preview",
        headers=auth_headers,
        params={"frame": 0, "format": "png"},
    )
    assert png.status_code == 200
    assert png.headers["content-type"].startswith("image/png")
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"

    bad = client.get(
        f"/videos/{video_id}/pose/preview",
        headers=auth_headers,
        params={"frame": 99999},
    )
    assert bad.status_code == 400


def test_pose_preview_404_when_not_extracted(client, auth_headers, tmp_path):
    skill_id = _skill_id(client)
    path = write_solid_video(
        tmp_path / "nopose.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(180, 180, 180),
    )
    up = _upload(client, auth_headers, skill_id, path)
    assert up.status_code == 200, up.text
    video_id = up.json()["video"]["id"]
    assert up.json()["analysis_job"]["status"] == "queued"

    r = client.get(f"/videos/{video_id}/pose/preview", headers=auth_headers)
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "关键点" in str(detail)

    missing = client.get("/videos/999999/pose/preview", headers=auth_headers)
    assert missing.status_code == 404
