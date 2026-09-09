"""V3: 3D standard-action viewer manifest + stages + synthetic_demo HUD."""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import BenchmarkVersion
from app.services.benchmark_pkg import import_package_to_db, load_package
from app.services.viewer3d.glb import build_stick_figure_glb
from app.services.viewer3d.manifest import (
    PLAYBACK_SPEEDS,
    VIEWER3D_NOTICE,
    build_viewer3d_manifest,
)

REPO = Path(__file__).resolve().parents[3]
DEMO = REPO / "docs" / "benchmark" / "demo"
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


def test_build_manifest_from_demo_package():
    pkg = load_package(CLEAR_DEMO)
    m = build_viewer3d_manifest(
        skill_id=1,
        skill_code="forehand_clear",
        skill_name="正手高远球",
        package=pkg,
        version_label=pkg.get("version"),
        version_status="draft",
    )
    assert m["synthetic_demo"] is True
    assert m["realtime"] is False
    assert m["playback_speeds"] == PLAYBACK_SPEEDS
    assert m["frame_count"] >= 4
    assert m["stages"]
    assert all("t_ms" in s for s in m["stages"])
    assert m["bones"]
    assert m["bone_index_pairs"]
    assert m["hud_angles"]
    # synthetic metrics should expose demo mid values, not pretend expert
    demo_hud = [h for h in m["hud_angles"] if h.get("synthetic_demo")]
    assert demo_hud
    assert any(h["display"] != "N/A" for h in demo_hud)
    assert "非专家" in m["banner"] or "演示" in m["banner"]
    assert VIEWER3D_NOTICE in m["notice"]
    j0 = m["frames"][0]["joints"][0]
    assert {"x", "y", "z"} <= set(j0.keys())


def test_build_manifest_without_template_generates_demo():
    m = build_viewer3d_manifest(
        skill_id=2,
        skill_code="forehand_smash",
        skill_name="正手杀球",
        package={"verification_status": "synthetic_demo", "stages": [], "metrics": []},
    )
    assert m["sequence_source"] == "generated_synthetic_demo"
    assert m["frame_count"] >= 4
    assert any(h["display"] == "N/A" for h in m["hud_angles"])


def test_glb_is_valid_minimal_container():
    raw = build_stick_figure_glb()
    assert raw[:4] == b"glTF"
    version, total = struct.unpack_from("<II", raw, 4)
    assert version == 2
    assert total == len(raw)
    # JSON chunk header
    chunk_len, chunk_type = struct.unpack_from("<I4s", raw, 12)
    assert chunk_type == b"JSON"
    gltf = json.loads(raw[20 : 20 + chunk_len].decode("utf-8"))
    assert gltf["asset"]["extras"]["synthetic_demo"] is True


def test_viewer3d_endpoint_with_imported_demo(client: TestClient, _cleanup_published):
    pkg = load_package(CLEAR_DEMO)
    db = SessionLocal()
    try:
        import_package_to_db(db, pkg)
        db.commit()
    finally:
        db.close()

    res = client.get("/benchmarks/forehand_clear/viewer3d")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["skill_code"] == "forehand_clear"
    assert body["frame_count"] >= 1
    assert body["stages"]
    assert body["controls"]["orbit"] is True
    assert 0.25 in body["playback_speeds"]
    assert body["assets"]["glb_url"].endswith(".glb")
    assert "procedural_canvas" in body["assets"]["renderer"]
    # HUD must not claim expert truth
    for h in body["hud_angles"]:
        assert "专家" not in (h.get("note") or "") or "非专家" in (h.get("note") or "")


def test_viewer3d_404_unknown_skill(client: TestClient):
    res = client.get("/benchmarks/not_a_real_skill/viewer3d")
    assert res.status_code == 404


def test_static_glb_and_html_served(client: TestClient):
    glb = client.get("/static/viewer3d/stick_figure.synthetic_demo.glb")
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"
    html = client.get("/static/viewer3d/index.html")
    assert html.status_code == 200
    assert "synthetic_demo" in html.text or "非专家" in html.text
