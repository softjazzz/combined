import pytest
from fastapi.testclient import TestClient

# 假设主应用在 app.main
from app.main import app
from app.routers import dashboard_api

from app.core.security import get_current_user

app.dependency_overrides[get_current_user] = lambda: {
    "id": "test-uuid",
    "name": "Test User",
    "department": "质控科"
}

client = TestClient(app)

# 模拟获取 trace_id, mock user
def setup_module():
    pass

@pytest.fixture
def auth_headers():
    return {}

def test_dashboard_stats(auth_headers, monkeypatch):
    # P1 Dashboard 待办统计
    async def empty_stats(*_args, **_kwargs):
        return {
            "records": {"total": 0, "by_status": {}, "by_department": {}},
            "qc": {"total": 0, "avg_score": 0, "by_grade": {}},
            "appeals": {"total": 0, "by_status": {}},
            "remediation": {"total": 0, "by_status": {}},
        }

    monkeypatch.setattr(dashboard_api, "_get_db_stats_by_scene", empty_stats)
    response = client.get("/api/v1/dashboard/todo-stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "task_stats" in data["data"]
    assert "defect_stats" in data["data"]

def test_dashboard_performance(auth_headers):
    # P1 Dashboard 工作表现排名
    response = client.get("/api/v1/dashboard/performance?period=this_week", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "defect_ranking" in data["data"]

def test_scoring_rules_crud(auth_headers):
    # P8 评分规则：List -> Create -> Update -> Delete
    # 1. List
    resp = client.get("/api/v1/scoring-rules", headers=auth_headers)
    assert resp.status_code == 200
    # 2. Create
    payload = {
        "name": "自动化测试规则",
        "category": "形式质控",
        "deduction": 5,
        "severity": "warning"
    }
    resp = client.post("/api/v1/scoring-rules", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    rule_id = resp.json()["data"]["id"]
    
    # 3. Update
    resp = client.put(f"/api/v1/scoring-rules/{rule_id}", json={"deduction": 10}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["deduction"] == 10
    
    # 4. Toggle
    resp = client.put(f"/api/v1/scoring-rules/{rule_id}/toggle", headers=auth_headers)
    assert resp.status_code == 200
    
    # 5. Delete
    resp = client.delete(f"/api/v1/scoring-rules/{rule_id}", headers=auth_headers)
    assert resp.status_code == 200

def test_staff_ranking(auth_headers):
    # P7 质控员工作量排名
    resp = client.get("/api/v1/staff-ranking?period=this_month&sort_by=qc_count", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "rankings" in data["data"]
    assert "summary" in data["data"]
    assert len(data["data"]["rankings"]) > 0

def test_notifications_and_rectifications(auth_headers):
    # 1. 消息列表
    resp = client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    notifs = resp.json()
    
    # 2. 整改跟踪列表
    resp = client.get("/api/v1/notifications/rectifications", headers=auth_headers)
    assert resp.status_code == 200
    rects = resp.json()
    assert "items" in rects["data"]
