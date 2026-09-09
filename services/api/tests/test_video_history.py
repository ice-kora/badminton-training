"""Video / analysis_job history APIs — auth scoping, no scores."""
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


def _login(client, openid: str, nickname: str) -> dict[str, str]:
    r = client.post(
        "/auth/dev-login",
        json={"openid": openid, "nickname": nickname},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(client, headers, skill_id: int, video_path: Path):
    with video_path.open("rb") as f:
        return client.post(
            "/videos/upload",
            headers=headers,
            data={
                "skill_id": str(skill_id),
                "client_checklist_json": json.dumps(
                    {"full_body": True, "distance_ok": True, "racket_visible": True}
                ),
            },
            files={"file": (video_path.name, f, "video/mp4")},
        )


def test_upload_appears_in_list_and_detail(
    client, auth_headers, skill_id, media_dir
):
    path = write_solid_video(
        media_dir / "hist.mp4",
        width=720,
        height=1280,
        duration_sec=8,
        color_bgr=(200, 200, 200),
    )
    up = _upload(client, auth_headers, skill_id, path)
    assert up.status_code == 200, up.text
    video_id = up.json()["video"]["id"]
    job_id = up.json()["analysis_job"]["id"]

    listed = client.get("/videos", headers=auth_headers)
    assert listed.status_code == 200
    items = listed.json()
    assert any(v["id"] == video_id for v in items)
    mine = next(v for v in items if v["id"] == video_id)
    assert mine["skill_name"]
    assert mine["orientation"] == "portrait"
    assert mine["latest_job"] is not None
    assert mine["latest_job"]["status"] in ("pose_extracted", "queued")
    assert mine["latest_job"]["error_code"] == "ANALYSIS_NOT_IMPLEMENTED"
    assert mine["latest_job"].get("scoring_status") == "blocked"
    assert mine["latest_job"].get("score") in (None,)

    detail = client.get(f"/videos/{video_id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == video_id
    assert body["skill_name"]
    assert body["precheck"] and body["precheck"]["passed"] is True
    assert any(j["id"] == job_id for j in body["jobs"])
    assert "评分" in body["notice"] or "关键点" in body["notice"]
    assert body.get("pose_extracted") in (True, False)
    assert body.get("score") in (None,)

    jobs = client.get("/analysis/jobs", headers=auth_headers)
    assert jobs.status_code == 200
    assert any(j["id"] == job_id for j in jobs.json())
    this_job = next(j for j in jobs.json() if j["id"] == job_id)
    # Unscored jobs must not invent scores; previously scored jobs in shared DB may exist
    if this_job.get("status") != "scored":
        assert this_job.get("score") in (None,)


def test_user_cannot_see_other_users_videos_or_jobs(
    client, skill_id, media_dir
):
    headers_a = _login(client, "hist-user-a", "用户A")
    headers_b = _login(client, "hist-user-b", "用户B")

    path = write_solid_video(
        media_dir / "scope.mp4",
        width=720,
        height=1280,
        duration_sec=8,
        color_bgr=(200, 200, 200),
    )
    up = _upload(client, headers_a, skill_id, path)
    assert up.status_code == 200, up.text
    video_id = up.json()["video"]["id"]
    job_id = up.json()["analysis_job"]["id"]

    # A sees own
    assert any(
        v["id"] == video_id
        for v in client.get("/videos", headers=headers_a).json()
    )

    # B list does not include A's video
    b_list = client.get("/videos", headers=headers_b)
    assert b_list.status_code == 200
    assert all(v["id"] != video_id for v in b_list.json())

    # B detail/job 404
    assert client.get(f"/videos/{video_id}", headers=headers_b).status_code == 404
    assert client.get(f"/analysis/jobs/{job_id}", headers=headers_b).status_code == 404

    b_jobs = client.get("/analysis/jobs", headers=headers_b)
    assert b_jobs.status_code == 200
    assert all(j["id"] != job_id for j in b_jobs.json())


def test_videos_list_requires_auth(client):
    assert client.get("/videos").status_code in (401, 403)
    assert client.get("/analysis/jobs").status_code in (401, 403)
