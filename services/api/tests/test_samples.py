"""Cold-start sample analysis endpoint (O1)."""
from __future__ import annotations


def test_get_sample_forehand_clear(client):
    res = client.get("/samples/forehand_clear")
    assert res.status_code == 200
    body = res.json()
    assert body["is_sample"] is True
    assert "样例" in body["sample_banner"]
    assert body["code"] == "forehand_clear"
    assert body["skill"]["code"] == "forehand_clear"
    score = body["score"]
    assert score["overall_score"] == 62
    assert score["primary_issue"]["title"]
    assert 1 <= len(score["problems"]) <= 3
    assert body["honesty"]
    # Must not pretend to be a user job
    assert "job_id" not in body
    assert body.get("benchmark_kind") in ("literature_cited", "synthetic_demo")


def test_get_sample_unknown_404(client):
    res = client.get("/samples/not_a_real_skill")
    assert res.status_code == 404


def test_sample_static_json_mounted(client):
    res = client.get("/static/samples/forehand_clear.json")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == "forehand_clear"
