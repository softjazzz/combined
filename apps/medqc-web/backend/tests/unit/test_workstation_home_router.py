def test_workstation_home_router_endpoints(client, monkeypatch):
    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-home"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-home", "roles": ["admin"]},
    )

    payload = {
        "date": "2026-04-01",
        "kpis": {
            "hotspot_total": 1,
            "high_risk_total": 1,
            "my_pending_total": 1,
            "my_in_progress_total": 0,
            "my_overdue_total": 0,
            "batch_summary_total": 1,
        },
        "hotspots": [],
        "my_todo_summary": {
            "pending_total": 1,
            "in_progress_total": 0,
            "overdue_total": 0,
            "high_priority_total": 1,
        },
        "my_todo_items": [],
        "batch_summaries": [],
        "department_options": ["心内科"],
        "team_summary": {
            "department_risk_distribution": [],
            "workflow_status_distribution": [],
        },
    }

    monkeypatch.setattr(
        "app.routers.workstation.default_workstation_aggregation_service.get_home",
        lambda **kwargs: payload,
    )
    monkeypatch.setattr(
        "app.routers.workstation.default_workstation_aggregation_service.get_home_hotspots",
        lambda **kwargs: {"date": "2026-04-01", "items": [], "total": 0},
    )
    monkeypatch.setattr(
        "app.routers.workstation.default_workstation_aggregation_service.get_home_todos",
        lambda **kwargs: {"summary": payload["my_todo_summary"], "items": [], "total": 0},
    )

    headers = {"Authorization": "Bearer test-token"}

    home_resp = client.get("/api/v1/workstation/home?date=2026-04-01", headers=headers)
    assert home_resp.status_code == 200
    assert home_resp.json()["data"]["kpis"]["hotspot_total"] == 1

    hotspots_resp = client.get("/api/v1/workstation/home/hotspots?date=2026-04-01", headers=headers)
    assert hotspots_resp.status_code == 200
    assert hotspots_resp.json()["data"]["total"] == 0

    todos_resp = client.get("/api/v1/workstation/home/todos", headers=headers)
    assert todos_resp.status_code == 200
    assert todos_resp.json()["data"]["summary"]["pending_total"] == 1
