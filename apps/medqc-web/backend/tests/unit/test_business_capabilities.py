"""能力说明：只列已接通操作，未接通事项给原因；回读一致。"""
from app.services.qc_agent import business_capabilities as caps


def test_views_list_only_connected_actions_and_reasons():
    doctor, manager = caps.capabilities("doctor"), caps.capabilities("manager")
    assert "单病例复检预览" in doctor["available"] and "专项质控任务预览" not in doctor["available"]
    assert "专项质控任务预览" in manager["available"] and "参考补充草稿" not in manager["available"]
    names = {row["name"] for row in doctor["unavailable"]}
    assert {"整改分派", "催办", "写回 EMR 或修改病历", "主动订阅与定期推送"} <= names
    text = doctor["references"][0]["text"]
    assert "催办：现有催办接口只更新缺陷状态，未接入真实通知投递" in text
    assert all(row["reason"] for row in doctor["unavailable"])


def test_capability_tool_binds_and_rereads(tmp_path, monkeypatch):
    import httpx
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_schemas import BusinessContext
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
    user = {"id": "u", "roles": ["doctor"]}
    identity = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
    store = BusinessSessionStore(tmp_path)
    session = store.create(user, BusinessContext(view="doctor", **identity))
    access = BusinessAccess({"version": 1, "accounts": {"u": {"doctor_cases": [identity]}}})
    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda _r: httpx.Response(404))))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    client = TestClient(app)
    url = f"/business/sessions/{session['session_id']}"
    card = client.post(url + "/tools/read_action_capabilities", json={}).json()["references"][0]
    assert client.get(url + "/references/" + card["id"]).json() == card