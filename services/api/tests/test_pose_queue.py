"""DB-backed pose queue: claim → extract; concurrent claim safety."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.models import AnalysisJob, PoseAnalysis
from app.services.pose.fake_extractor import FakePoseExtractor
from app.worker.pose_queue import (
    claim_job,
    claim_next_job,
    process_batch,
    process_claimed_job,
    reclaim_stale_extracting_jobs,
)
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


def test_upload_stays_queued_then_worker_once(
    client, auth_headers, skill_id, media_dir
):
    path = write_solid_video(
        media_dir / "queue_ok.mp4",
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
    assert job.get("score") in (None,)

    video_id = body["video"]["id"]
    pose_before = client.get(f"/videos/{video_id}/pose", headers=auth_headers)
    assert pose_before.status_code == 200
    assert pose_before.json()["extracted"] is False

    db = SessionLocal()
    try:
        claimed = claim_job(db, job["id"])
        assert claimed is not None
        assert claimed.status == "extracting"
        outcome = process_claimed_job(
            db, claimed, extractor=FakePoseExtractor()
        )
        assert outcome in ("pose_extracted", "scored")

        row = db.get(AnalysisJob, job["id"])
        db.refresh(row)
        assert row.status in ("pose_extracted", "scored")
        assert row.scoring_status in ("blocked", "scored")
        assert row.error_code == "ANALYSIS_NOT_IMPLEMENTED"
        pose = (
            db.query(PoseAnalysis)
            .filter(PoseAnalysis.video_id == video_id)
            .one_or_none()
        )
        assert pose is not None
        assert pose.frame_count > 0
        assert pose.extractor == "fake_pose"
    finally:
        db.close()

    pose_after = client.get(f"/videos/{video_id}/pose", headers=auth_headers)
    assert pose_after.status_code == 200
    meta = pose_after.json()
    assert meta["extracted"] is True
    assert meta["frame_count"] > 0
    assert "score" not in meta


def test_concurrent_claim_does_not_double_process(
    client, auth_headers, skill_id, media_dir
):
    path = write_solid_video(
        media_dir / "claim_race.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )
    up = _upload(client, auth_headers, skill_id, path)
    assert up.status_code == 200, up.text
    job_id = up.json()["analysis_job"]["id"]
    assert up.json()["analysis_job"]["status"] == "queued"

    db_a = SessionLocal()
    db_b = SessionLocal()
    try:
        claimed_a = claim_job(db_a, job_id)
        claimed_b = claim_job(db_b, job_id)
        winners = [j for j in (claimed_a, claimed_b) if j is not None]
        assert len(winners) == 1
        assert winners[0].id == job_id
        assert winners[0].status == "extracting"
        assert claimed_a is None or claimed_b is None

        owner = db_a if claimed_a is not None else db_b
        outcome = process_claimed_job(
            owner, winners[0], extractor=FakePoseExtractor()
        )
        assert outcome in ("pose_extracted", "scored")

        # Third claim must lose
        assert claim_job(db_a, job_id) is None
        assert claim_job(db_b, job_id) is None

        row = owner.get(AnalysisJob, job_id)
        owner.refresh(row)
        assert row.status in ("pose_extracted", "scored")
    finally:
        db_a.close()
        db_b.close()


def test_claim_next_skips_non_queued(client, auth_headers, skill_id, media_dir):
    path = write_solid_video(
        media_dir / "skip.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )
    up = _upload(client, auth_headers, skill_id, path)
    job_id = up.json()["analysis_job"]["id"]

    db = SessionLocal()
    try:
        claimed = claim_job(db, job_id)
        assert claimed is not None
        # Now status=extracting; claim_next should not return this id as queued
        nxt = claim_next_job(db)
        if nxt is not None:
            assert nxt.id != job_id
            # leave it extracting for cleanliness? requeue
            nxt.status = "queued"
            db.commit()
        # finish our job
        process_claimed_job(db, claimed, extractor=FakePoseExtractor())
    finally:
        db.close()


def test_process_batch_api_stable():
    stats = process_batch(limit=1, extractor=FakePoseExtractor())
    assert stats.claimed >= 0
    assert stats.processed + stats.failed + stats.requeued == stats.claimed


def test_stale_extracting_reclaimed_to_queued(
    client, auth_headers, skill_id, media_dir
):
    path = write_solid_video(
        media_dir / "stale.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(200, 200, 200),
    )
    up = _upload(client, auth_headers, skill_id, path)
    assert up.status_code == 200, up.text
    job_id = up.json()["analysis_job"]["id"]

    db = SessionLocal()
    try:
        claimed = claim_job(db, job_id)
        assert claimed is not None
        assert claimed.status == "extracting"

        # Simulate worker crash: backdate updated_at
        stale_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            seconds=900
        )
        claimed.updated_at = stale_at
        db.commit()

        n = reclaim_stale_extracting_jobs(db, stale_seconds=600)
        assert n == 1

        row = db.get(AnalysisJob, job_id)
        db.refresh(row)
        assert row.status == "queued"
        assert row.scoring_status in ("blocked", "scored")
        assert row.error_code == "ANALYSIS_NOT_IMPLEMENTED"
        assert "回收" in (row.message or "")

        # Fresh extracting must NOT be reclaimed
        claimed2 = claim_job(db, job_id)
        assert claimed2 is not None
        assert claimed2.status == "extracting"
        n2 = reclaim_stale_extracting_jobs(db, stale_seconds=600)
        assert n2 == 0
        db.refresh(claimed2)
        assert claimed2.status == "extracting"
    finally:
        db.close()


def test_process_batch_reclaims_then_processes(
    client, auth_headers, skill_id, media_dir
):
    path = write_solid_video(
        media_dir / "stale_batch.mp4",
        width=720,
        height=1280,
        duration_sec=6,
        color_bgr=(180, 180, 180),
    )
    up = _upload(client, auth_headers, skill_id, path)
    job_id = up.json()["analysis_job"]["id"]

    db = SessionLocal()
    try:
        claimed = claim_job(db, job_id)
        assert claimed is not None
        claimed.updated_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            seconds=1200
        )
        db.commit()

        stats = process_batch(
            limit=1, extractor=FakePoseExtractor(), db=db, stale_seconds=600
        )
        assert stats.reclaimed == 1
        assert stats.claimed == 1
        assert stats.processed == 1

        row = db.get(AnalysisJob, job_id)
        db.refresh(row)
        assert row.status in ("pose_extracted", "scored", "queued")
        # After reclaim+process should leave extract/score terminal; allow queued only if reclaim raced
        if row.status == "queued":
            # retry once
            claimed2 = claim_job(db, job_id)
            if claimed2 is not None:
                process_claimed_job(db, claimed2, extractor=FakePoseExtractor())
                db.refresh(row)
            assert row.status in ("pose_extracted", "scored")
        assert row.scoring_status in ("blocked", "scored")
    finally:
        db.close()
