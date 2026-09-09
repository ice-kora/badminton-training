"""Motion Benchmark package pipeline tests — no fabricated verified angles."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.models import BenchmarkVersion, MotionBenchmark
from app.services.benchmark_pkg import (
    BenchmarkValidationError,
    import_package_to_db,
    load_package,
    publish_allowed,
    validate_package,
)

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "docs" / "benchmark" / "templates"
SCRIPTS = REPO / "scripts"
CLEAR_PKG = TEMPLATES / "forehand_clear.v0.json"


def test_good_template_passes_validation():
    data = load_package(CLEAR_PKG)
    warnings = validate_package(data)
    assert data["verification_status"] == "draft_unverified"
    assert all(m.get("range_min") is None and m.get("range_max") is None for m in data["metrics"])
    assert warnings == []


def test_numeric_ranges_with_draft_unverified_fail():
    data = load_package(CLEAR_PKG)
    data = json.loads(json.dumps(data))
    data["metrics"][0]["range_min"] = 90.0
    data["metrics"][0]["range_max"] = 120.0
    with pytest.raises(BenchmarkValidationError) as ei:
        validate_package(data)
    assert "draft_unverified" in str(ei.value)


def test_numeric_ranges_allowed_with_explicit_flag():
    data = load_package(CLEAR_PKG)
    data = json.loads(json.dumps(data))
    data["metrics"][0]["range_min"] = 90.0
    warnings = validate_package(data, allow_unverified_numbers=True)
    assert warnings
    assert "allowing unverified" in warnings[0]


def test_import_creates_db_rows(client):
    # client fixture seeds DB
    data = load_package(CLEAR_PKG)
    db = SessionLocal()
    try:
        bm, ver = import_package_to_db(db, data, change_log="pytest import")
        db.commit()
        assert bm.id
        assert ver.status == "draft"
        assert ver.verification_status == "draft_unverified"
        assert ver.package_json
        assert len(ver.stages) == 4
        assert len(ver.metrics) >= 3
        assert all(m.range_min is None and m.range_max is None for m in ver.metrics)
    finally:
        db.close()


def test_publish_blocked_for_unverified(client):
    data = load_package(CLEAR_PKG)
    db = SessionLocal()
    try:
        bm, ver = import_package_to_db(db, data)
        db.commit()
        ok, reason = publish_allowed(ver.verification_status)
        assert ok is False
        assert "draft_unverified" in reason

        # CLI should also fail
        env = os.environ.copy()
        # Use same test DB
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "benchmark_publish.py"),
                "forehand_clear",
                "--version",
                data["version"],
                "--force-draft-forbidden",
            ],
            cwd=str(REPO / "services" / "api"),
            env=env,
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0
        assert "draft_unverified" in (r.stderr + r.stdout)
    finally:
        db.close()


def test_get_benchmark_endpoints(client):
    # Ensure template imported so stages/metrics appear on a version
    data = load_package(CLEAR_PKG)
    db = SessionLocal()
    try:
        import_package_to_db(db, data)
        db.commit()
    finally:
        db.close()

    r = client.get("/benchmarks")
    assert r.status_code == 200
    items = r.json()
    codes = {x["skill_code"] for x in items}
    assert {"forehand_clear", "forehand_smash", "net_tumble"} <= codes
    clear = next(x for x in items if x["skill_code"] == "forehand_clear")
    assert clear["has_published_version"] is False

    r2 = client.get("/benchmarks/forehand_clear")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["skill_code"] == "forehand_clear"
    assert detail["has_published_version"] is False
    assert detail["current"] is not None
    assert detail["current"]["status"] == "draft"
    # ranges null
    for m in detail["current"]["metrics"]:
        assert m["range_min"] is None
        assert m["range_max"] is None

    r3 = client.get("/benchmarks/forehand_clear/versions")
    assert r3.status_code == 200
    versions = r3.json()
    assert len(versions) >= 1
    labels = {v["version_label"] for v in versions}
    assert "0.1.0" in labels or "v0-shell" in labels


def test_analysis_mentions_awaiting_when_no_published(client):
    r = client.post("/analysis/jobs", json={"skill_id": 1})
    assert r.status_code == 501
    body = r.json()
    assert body["code"] == "ANALYSIS_NOT_IMPLEMENTED"
    assert "awaiting_published_benchmark" in body["message"]


def test_validate_script_cli_good_template():
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "benchmark_validate.py"), str(CLEAR_PKG)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "OK:" in r.stdout
