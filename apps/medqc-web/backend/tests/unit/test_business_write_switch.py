"""助手写入开关：正式入口默认关闭，关闭时不触达任何写存储；仅合成数据。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.qc_agent import business_capabilities as caps
from app.services.qc_agent import business_write_switch as switch

SESSION = "11111111-1111-1111-1111-111111111111"
ACTION = "22222222-2222-2222-2222-222222222222"
USER = {"id": "u1", "roles": ["doctor"]}


class Untouchable:
    """任何访问都视为越过了开关。"""

    def __getattr__(self, name):
        raise AssertionError(f"开关关闭时不应访问写存储：{name}")


@pytest.fixture
def client():
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent import business_feedback
    from app.services.qc_agent.business_access import get_business_access
    from app.services.qc_agent.business_action_store import get_action_store
    from app.services.qc_agent.business_store import get_business_store

    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1/qc-agent")
    for dependency in (get_business_store, get_business_access, get_action_store, business_feedback.get_feedback_store):
        app.dependency_overrides[dependency] = lambda: Untouchable()
    app.dependency_overrides[get_current_user] = lambda: USER
    return TestClient(app)


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    monkeypatch.delenv(switch.FEEDBACK_SWITCH, raising=False)
    monkeypatch.delenv(switch.TASK_SWITCH, raising=False)


def test_switches_default_to_off_and_only_one_enables(monkeypatch):
    assert not switch.enabled(switch.TASK_SWITCH) and not switch.enabled(switch.FEEDBACK_SWITCH)
    for value in ("0", "", "true", "yes", "2"):
        monkeypatch.setenv(switch.TASK_SWITCH, value)
        assert not switch.enabled(switch.TASK_SWITCH)
    monkeypatch.setenv(switch.TASK_SWITCH, "1")
    assert switch.enabled(switch.TASK_SWITCH)


def test_feedback_submit_is_refused_without_touching_stores(client):
    response = client.post(f"/api/v1/qc-agent/business/sessions/{SESSION}/feedback",
                           json={"reference_id": "result:a:b:c", "comment": "理由", "request_id": ACTION})
    assert response.status_code == 423
    assert "未启用" in response.json()["detail"]


def test_action_confirm_is_refused_without_touching_stores(client):
    response = client.post(f"/api/v1/qc-agent/business/sessions/{SESSION}/actions/{ACTION}/confirm",
                           json={"confirmed": True, "confirmation_hash": "a" * 64})
    assert response.status_code == 423
    assert "未启用" in response.json()["detail"]


def test_preview_is_refused_before_any_row_is_written():
    import asyncio

    from app.services.qc_agent import business_action_flow

    with pytest.raises(Exception) as caught:
        asyncio.run(business_action_flow.create_preview(Untouchable(), Untouchable(), {}, USER, Untouchable(), "single_recheck", ["R"]))
    assert getattr(caught.value, "status_code", None) == 423


def test_capabilities_move_switched_items_to_unavailable_when_off():
    doctor = caps.capabilities("doctor")
    assert "单病例复检预览" not in doctor["available"] and "异议反馈" not in doctor["available"]
    assert {item["name"] for item in doctor["unavailable"]} >= {"单病例复检预览", "异议反馈"}
    manager = caps.capabilities("manager")
    assert "专项质控任务预览" not in manager["available"]


def test_capabilities_list_switched_items_as_available_when_on(monkeypatch):
    monkeypatch.setenv(switch.TASK_SWITCH, "1")
    monkeypatch.setenv(switch.FEEDBACK_SWITCH, "1")
    assert {"单病例复检预览", "异议反馈"} <= set(caps.capabilities("doctor")["available"])
    assert "专项质控任务预览" in caps.capabilities("manager")["available"]
