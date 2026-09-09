"""Visual-only retest loop: baseline link + side-by-side pose compare (no scores)."""
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
def other_skill_id(client) -> int:
    tree = client.get("/skills/tree").json()
    return next(
        s["id"]
        for c in tree["categories"]
        for s in c["skills"]
        if s["code"] != "forehand_clear"
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


def _upload(
    client,
    headers,
    skill_id: int,
    video_path: Path,
    *,
    baseline_video_id: int | None = None,
):
    data: dict[str, str] = {
        "skill_id": str(skill_id),
        "client_checklist_json": json.dumps(
            {"full_body": True, "distance_ok": True, "racket_visible": True}
        ),
    }
    if baseline_video_id is not None:
        data["baseline_video_id"] = str(baseline_video_id)
    with video_path.open("rb") as f:
        return client.post(
            "/videos/upload",
            headers=headers,
            data=data,
            files={"file": (video_path.name, f, "video/mp4")},
        )


def _ok_clip(media_dir: Path, name: str) -> Path:
    return write_solid_video(
        media_dir / name,
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )


def test_upload_with_baseline_succeeds(client, auth_headers, skill_id, media_dir):
    base = _upload(client, auth_headers, skill_id, _ok_clip(media_dir, "base.mp4"))
    assert base.status_code == 200, base.text
    base_id = base.json()["video"]["id"]

    retest = _upload(
        client,
        auth_headers,
        skill_id,
        _ok_clip(media_dir, "retest.mp4"),
        baseline_video_id=base_id,
    )
    assert retest.status_code == 200, retest.text
    body = retest.json()
    assert body["video"]["baseline_video_id"] == base_id
    assert "score" not in body
    assert "score" not in body["analysis_job"]
    assert body["analysis_job"]["error_code"] == "ANALYSIS_NOT_IMPLEMENTED"

    detail = client.get(f"/videos/{body['video']['id']}", headers=auth_headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["baseline_video_id"] == base_id
    assert d["baseline"] is not None
    assert d["baseline"]["id"] == base_id
    assert "score" not in d
    assert "score" not in (d.get("baseline") or {})


def test_upload_baseline_wrong_user_rejected(client, skill_id, media_dir):
    headers_a = _login(client, "retest-a", "A")
    headers_b = _login(client, "retest-b", "B")
    base = _upload(client, headers_a, skill_id, _ok_clip(media_dir, "a_base.mp4"))
    assert base.status_code == 200
    base_id = base.json()["video"]["id"]

    bad = _upload(
        client,
        headers_b,
        skill_id,
        _ok_clip(media_dir, "b_retest.mp4"),
        baseline_video_id=base_id,
    )
    assert bad.status_code == 400
    assert "baseline" in str(bad.json()).lower() or "用户" in str(bad.json())


def test_upload_baseline_wrong_skill_rejected(
    client, auth_headers, skill_id, other_skill_id, media_dir
):
    base = _upload(client, auth_headers, skill_id, _ok_clip(media_dir, "sk_base.mp4"))
    assert base.status_code == 200
    base_id = base.json()["video"]["id"]

    bad = _upload(
        client,
        auth_headers,
        other_skill_id,
        _ok_clip(media_dir, "sk_retest.mp4"),
        baseline_video_id=base_id,
    )
    assert bad.status_code == 400
    assert "skill" in str(bad.json()).lower() or "不一致" in str(bad.json())


def test_retest_compare_needs_both_poses(client, auth_headers, skill_id, media_dir):
    base = _upload(client, auth_headers, skill_id, _ok_clip(media_dir, "cmp_base.mp4"))
    assert base.status_code == 200
    base_id = base.json()["video"]["id"]

    retest = _upload(
        client,
        auth_headers,
        skill_id,
        _ok_clip(media_dir, "cmp_retest.mp4"),
        baseline_video_id=base_id,
    )
    assert retest.status_code == 200
    retest_id = retest.json()["video"]["id"]

    # Neither extracted yet (inline extract off) → 404
    missing = client.get(
        f"/videos/{retest_id}/retest-compare",
        headers=auth_headers,
        params={"frame": 0},
    )
    assert missing.status_code == 404

    # Extract baseline only → still 404 (current missing)
    assert (
        client.post(f"/videos/{base_id}/extract-pose", headers=auth_headers).status_code
        == 200
    )
    only_base = client.get(
        f"/videos/{retest_id}/retest-compare",
        headers=auth_headers,
        params={"frame": 0},
    )
    assert only_base.status_code == 404

    # Extract current → 200, dual preview, no scores
    assert (
        client.post(
            f"/videos/{retest_id}/extract-pose", headers=auth_headers
        ).status_code
        == 200
    )
    ok = client.get(
        f"/videos/{retest_id}/retest-compare",
        headers=auth_headers,
        params={"frame": 0},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert "baseline" in body and "current" in body
    assert body["baseline"]["video_id"] == base_id
    assert body["current"]["video_id"] == retest_id
    assert body["baseline"]["frame"] == 0
    assert body["current"]["frame"] == 0
    assert len(body["baseline"]["landmarks"]) == 33
    assert len(body["current"]["landmarks"]) == 33
    assert "仅骨架" in body["notice"] or "非评分" in body["notice"]
    dumped = json.dumps(body).lower()
    assert "score" not in dumped
    assert "correctness" not in dumped
    assert "range_min" not in dumped


def test_retest_compare_without_baseline_link_400(
    client, auth_headers, skill_id, media_dir
):
    up = _upload(client, auth_headers, skill_id, _ok_clip(media_dir, "nolink.mp4"))
    assert up.status_code == 200
    vid = up.json()["video"]["id"]
    assert (
        client.post(f"/videos/{vid}/extract-pose", headers=auth_headers).status_code
        == 200
    )
    r = client.get(
        f"/videos/{vid}/retest-compare",
        headers=auth_headers,
        params={"frame": 0},
    )
    assert r.status_code == 400


def test_list_videos_skill_id_filter(client, auth_headers, skill_id, other_skill_id, media_dir):
    a = _upload(client, auth_headers, skill_id, _ok_clip(media_dir, "filter_a.mp4"))
    b = _upload(
        client, auth_headers, other_skill_id, _ok_clip(media_dir, "filter_b.mp4")
    )
    assert a.status_code == 200 and b.status_code == 200
    a_id = a.json()["video"]["id"]
    b_id = b.json()["video"]["id"]

    filtered = client.get(
        "/videos", headers=auth_headers, params={"skill_id": skill_id}
    )
    assert filtered.status_code == 200
    ids = {v["id"] for v in filtered.json()}
    assert a_id in ids
    assert b_id not in ids
    for v in filtered.json():
        assert v["skill_id"] == skill_id
        assert "score" not in (v.get("latest_job") or {})
