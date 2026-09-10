"""Amateur UX follow-ups: drill demo media + human pace labels."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.scoring.stage_timeline import build_stage_timeline, _pace_label


STATIC_GIF = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "static"
    / "drills"
    / "clear_stance_hold.gif"
)


def test_pace_label_only_when_meaningful():
    assert _pace_label(None, "引拍", 200) is None
    assert _pace_label(20, "引拍", 200) is None  # below threshold
    assert _pace_label(120, "引拍", 200) == "引拍偏慢"
    assert _pace_label(-120, "挥拍", 200) == "挥拍偏快"


def test_timeline_includes_pace_label_field():
    frames = [{"timestamp_ms": i * 50, "landmarks": []} for i in range(20)]
    stages = [
        {"code": "prep", "name": "引拍", "sort_order": 1},
        {"code": "swing", "name": "挥拍", "sort_order": 2},
        {"code": "hit", "name": "击球", "sort_order": 3},
        {"code": "follow", "name": "随挥", "sort_order": 4},
    ]
    keyframes = [
        {"stage_code": "prep", "t_ms": 0},
        {"stage_code": "swing", "t_ms": 200},
        {"stage_code": "hit", "t_ms": 400},
        {"stage_code": "follow", "t_ms": 600},
    ]
    tl = build_stage_timeline(
        {"frames": frames},
        stages=stages,
        keyframes=keyframes,
        template_total_ms=800,
    )
    assert tl["segments"]
    assert "pace_label" in tl["segments"][0]
    # notice should be amateur-friendly (no lab Δt branding)
    assert "Δt" not in (tl.get("notice") or "")
    assert "引拍" in tl["notice"] or "阶段" in tl["notice"]


def test_drills_expose_demo_media(client: TestClient):
    assert STATIC_GIF.exists()
    rows = client.get("/drills").json()
    assert len(rows) >= 1
    with_media = [d for d in rows if d.get("demo_media_url") or d.get("demo_gif_url")]
    assert len(with_media) >= 1
    d0 = with_media[0]
    code = d0["code"]
    one = client.get(f"/drills/{code}")
    assert one.status_code == 200
    body = one.json()
    media = body.get("demo_media_url") or body.get("demo_gif_url")
    assert media
    # static asset reachable
    rel = media if media.startswith("/") else "/" + media
    st = client.get(rel)
    assert st.status_code == 200
    assert st.headers.get("content-type", "").startswith("image/") or len(st.content) > 100
