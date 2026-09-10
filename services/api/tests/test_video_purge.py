"""VIDEO_TTL_DAYS purge: selection logic + unlink originals, keep pose/scores."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal
from app.models import AnalysisJob, PoseAnalysis, TrainingScore, TrainingVideo, User
from app.services.video_purge import (
    purge_cutoff,
    run_purge,
    select_videos_for_purge,
)


def _ensure_user(db, openid: str = "purge-test-user") -> User:
    u = db.query(User).filter(User.openid == openid).first()
    if u:
        return u
    u = User(openid=openid, nickname="purge")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _skill_id(client) -> int:
    tree = client.get("/skills/tree").json()
    return next(
        s["id"]
        for c in tree["categories"]
        for s in c["skills"]
        if s["code"] == "forehand_clear"
    )


def test_purge_cutoff_uses_ttl_days():
    now = datetime(2026, 9, 10, 12, 0, 0)
    assert purge_cutoff(now=now, ttl_days=7) == datetime(2026, 9, 3, 12, 0, 0)
    assert purge_cutoff(now=now, ttl_days=0) == now


def test_select_videos_for_purge_age_and_not_already_purged(client):
    """Only rows older than TTL and without file_purged_at are selected."""
    get_settings.cache_clear()
    settings = get_settings()
    upload = Path(settings.upload_dir)
    upload.mkdir(parents=True, exist_ok=True)
    skill_id = _skill_id(client)

    now = datetime(2026, 9, 10, 12, 0, 0)
    cutoff = purge_cutoff(now=now, ttl_days=7)

    db = SessionLocal()
    try:
        user = _ensure_user(db)
        fresh_path = upload / "fresh.mp4"
        fresh_path.write_bytes(b"fresh")
        fresh = TrainingVideo(
            user_id=user.id,
            skill_id=skill_id,
            storage_path=str(fresh_path),
            filename="fresh.mp4",
            created_at=now - timedelta(days=1),
        )
        old_path = upload / "old.mp4"
        old_path.write_bytes(b"old-bytes")
        old = TrainingVideo(
            user_id=user.id,
            skill_id=skill_id,
            storage_path=str(old_path),
            filename="old.mp4",
            created_at=cutoff - timedelta(hours=1),
        )
        purged_path = upload / "purged.mp4"
        purged_path.write_bytes(b"purged")
        already = TrainingVideo(
            user_id=user.id,
            skill_id=skill_id,
            storage_path=str(purged_path),
            filename="purged.mp4",
            created_at=cutoff - timedelta(days=2),
            file_purged_at=now - timedelta(days=1),
        )
        edge_path = upload / "edge.mp4"
        edge_path.write_bytes(b"edge")
        edge = TrainingVideo(
            user_id=user.id,
            skill_id=skill_id,
            storage_path=str(edge_path),
            filename="edge.mp4",
            created_at=cutoff,
        )
        db.add_all([fresh, old, already, edge])
        db.commit()
        db.refresh(old)
        db.refresh(fresh)
        db.refresh(already)
        db.refresh(edge)
        old_id, fresh_id, already_id, edge_id = old.id, fresh.id, already.id, edge.id

        selected = select_videos_for_purge(db, now=now, ttl_days=7)
        ids = {v.id for v in selected}
        assert old_id in ids
        assert fresh_id not in ids
        assert already_id not in ids
        assert edge_id not in ids
    finally:
        db.close()


def test_run_purge_unlinks_file_keeps_pose_and_score(client, auth_headers):
    """Purge deletes media bytes but leaves pose/score/job rows; file API → 410."""
    get_settings.cache_clear()
    settings = get_settings()
    upload = Path(settings.upload_dir)
    upload.mkdir(parents=True, exist_ok=True)
    skill_id = _skill_id(client)

    # Resolve auth user id
    me = client.get("/me", headers=auth_headers)
    # /me may or may not exist — fall back to JWT user via videos list empty
    db = SessionLocal()
    try:
        # auth_headers uses openid pytest-user
        user = db.query(User).filter(User.openid == "pytest-user").first()
        if user is None:
            user = _ensure_user(db, "pytest-user")
        user_id = user.id
    finally:
        db.close()

    now = datetime(2026, 9, 10, 12, 0, 0)
    media = upload / "ttl_clip.mp4"
    media.write_bytes(b"video-bytes-to-purge")

    db = SessionLocal()
    try:
        video = TrainingVideo(
            user_id=user_id,
            skill_id=skill_id,
            storage_path=str(media),
            filename="ttl_clip.mp4",
            created_at=now - timedelta(days=10),
        )
        db.add(video)
        db.flush()
        job = AnalysisJob(
            video_id=video.id,
            skill_id=skill_id,
            status="scored",
            scoring_status="scored",
        )
        db.add(job)
        db.flush()
        pose_dir = upload / "pose"
        pose_dir.mkdir(parents=True, exist_ok=True)
        kp = pose_dir / f"{video.id}.json"
        kp.write_text("{}", encoding="utf-8")
        pose = PoseAnalysis(
            video_id=video.id,
            job_id=job.id,
            frame_count=3,
            keypoint_path=str(kp),
            extractor="fake",
        )
        db.add(pose)
        db.flush()
        score = TrainingScore(
            video_id=video.id,
            job_id=job.id,
            pose_analysis_id=pose.id,
            overall_score=72.5,
            benchmark_kind="synthetic_demo",
        )
        db.add(score)
        db.commit()
        vid = video.id
        pose_id = pose.id
        score_id = score.id
        job_id = job.id
        kp_path = str(kp)
    finally:
        db.close()

    assert media.is_file()

    db = SessionLocal()
    try:
        stats = run_purge(db, now=now, ttl_days=7, limit=10, dry_run=False)
        db.commit()
        assert stats.selected >= 1
        assert stats.marked >= 1
        row = db.get(TrainingVideo, vid)
        assert row is not None
        assert row.file_purged_at is not None
        assert db.get(PoseAnalysis, pose_id) is not None
        assert db.get(TrainingScore, score_id) is not None
        assert db.get(AnalysisJob, job_id) is not None
        assert float(db.get(TrainingScore, score_id).overall_score) == 72.5
        assert Path(kp_path).exists()
    finally:
        db.close()

    assert not media.exists()

    r = client.get(f"/videos/{vid}/file", headers=auth_headers)
    assert r.status_code == 410
    assert "清理" in (r.json().get("detail") or "")


def test_select_respects_custom_ttl(client):
    get_settings.cache_clear()
    settings = get_settings()
    upload = Path(settings.upload_dir)
    upload.mkdir(parents=True, exist_ok=True)
    skill_id = _skill_id(client)
    now = datetime(2026, 9, 10, 12, 0, 0)
    path = upload / "mid.mp4"
    path.write_bytes(b"x")
    db = SessionLocal()
    try:
        user = _ensure_user(db)
        mid = TrainingVideo(
            user_id=user.id,
            skill_id=skill_id,
            storage_path=str(path),
            filename="mid.mp4",
            created_at=now - timedelta(days=3),
        )
        db.add(mid)
        db.commit()
        db.refresh(mid)
        assert mid.id not in {v.id for v in select_videos_for_purge(db, now=now, ttl_days=7)}
        assert mid.id in {v.id for v in select_videos_for_purge(db, now=now, ttl_days=2)}
    finally:
        db.close()
