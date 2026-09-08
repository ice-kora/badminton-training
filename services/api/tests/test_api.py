"""API acceptance tests for Phase-2 MVP."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_skill_tree(client):
    r = client.get("/skills/tree")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert len(data["categories"]) >= 2
    skill_names = [
        s["name"] for c in data["categories"] for s in c["skills"]
    ]
    for name in ("正手高远球", "正手杀球", "网前搓球"):
        assert name in skill_names
    # provenance on skills
    sample = data["categories"][0]["skills"][0]
    assert "source" in sample
    assert sample["verification_status"] in (
        "draft_unverified",
        "expert_pending",
        "verified",
    )


def test_skill_detail(client):
    tree = client.get("/skills/tree").json()
    skill_id = tree["categories"][0]["skills"][0]["id"]
    r = client.get(f"/skills/{skill_id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == skill_id
    assert len(detail["stages"]) >= 1
    assert len(detail["content_blocks"]) >= 1
    assert detail["content_blocks"][0]["verification_status"] == "draft_unverified"


def test_filming_guide(client):
    tree = client.get("/skills/tree").json()
    skill_id = next(
        s["id"]
        for c in tree["categories"]
        for s in c["skills"]
        if s["code"] == "forehand_clear"
    )
    r = client.get(f"/filming-guides/{skill_id}")
    assert r.status_code == 200
    guides = r.json()
    assert len(guides) >= 1
    g = guides[0]
    assert g["camera_angle"]
    assert "source" in g
    assert isinstance(g["checklist"], list)


def test_level_test_plan(client, auth_headers):
    r = client.post(
        "/plans/level-test",
        json={"level": "beginner"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    plan = r.json()
    assert plan["level"] == "beginner"
    assert len(plan["days"]) == 7
    assert "规则" in (plan["rationale"] or "")

    cur = client.get("/plans/current", headers=auth_headers)
    assert cur.status_code == 200
    assert cur.json()["id"] == plan["id"]


def test_recommendations(client, auth_headers):
    # Ensure plan exists
    client.post(
        "/plans/level-test",
        json={"level": "intermediate"},
        headers=auth_headers,
    )
    r = client.get("/recommendations/what-to-practice-now", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["method"] == "rule_based_from_plan_and_checkins"
    assert "姿态" in data["disclaimer"] or "不是" in data["disclaimer"]
    assert data["title"]


def test_analysis_not_implemented(client):
    r = client.post("/analysis/jobs", json={"skill_id": 1, "video_uri": "file://x"})
    assert r.status_code == 501
    body = r.json()
    assert body["code"] == "ANALYSIS_NOT_IMPLEMENTED"
    assert "尚未实现" in body["message"] or "未实现" in body["message"]


def test_drills_errors_tips(client):
    assert client.get("/drills").status_code == 200
    assert len(client.get("/drills").json()) >= 1
    assert client.get("/errors").status_code == 200
    assert client.get("/tips").status_code == 200


def test_check_in_and_sessions(client, auth_headers):
    plan = client.post(
        "/plans/level-test",
        json={"level": "beginner"},
        headers=auth_headers,
    ).json()
    day_id = plan["days"][0]["id"]
    r = client.post(
        "/sessions/check-in",
        json={"plan_id": plan["id"], "plan_day_id": day_id, "rating": 4, "notes": "完成"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    sessions = client.get("/sessions", headers=auth_headers)
    assert sessions.status_code == 200
    assert len(sessions.json()) >= 1
