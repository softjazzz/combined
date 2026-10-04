"""编码字典检索：只搬字典候选，限10条，卡片声明非编码建议，可回读；仅合成数据。"""
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest


def test_code_search_projects_candidates_and_rereads(tmp_path, monkeypatch):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_schemas import BusinessContext
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
    user = {"id": "u", "roles": ["doctor"]}
    identity = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
    store = BusinessSessionStore(tmp_path)
    session = store.create(user, BusinessContext(view="doctor", **identity))
    calls = []

    def formal(request):
        calls.append(dict(request.url.params))
        assert request.url.path == "/api/v1/icd/search"
        return httpx.Response(200, json={"success": True, "data": {"total": 37, "items": [
            {"code": "J18.900", "name": "肺炎", "type_label": "诊断", "version_label": "医保版", "mapped_code": "J18.900x001", "mapped_name": "肺炎", "mapped_version": "国临版", "is_diff": True, "confidence": 0.9}]}})

    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(formal)))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_access] = lambda: BusinessAccess({"version": 1, "accounts": {"u": {"doctor_cases": [identity]}}})
    app.dependency_overrides[get_business_store] = lambda: store
    client = TestClient(app)
    url = f"/business/sessions/{session['session_id']}"
    result = client.post(url + "/tools/search_icd_codes", json={"q": "肺炎", "type": "icd10"}).json()
    assert calls[0] == {"q": "肺炎", "type": "icd10", "version": "insurance", "limit": "10"}
    assert result["codes"]["items"][0] == {"code": "J18.900", "name": "肺炎", "type_label": "诊断", "version_label": "医保版",
                                           "mapped_code": "J18.900x001", "mapped_name": "肺炎", "mapped_version": "国临版", "is_diff": True}
    card = result["references"][0]
    assert "J18.900 肺炎（医保版）；国临版对应 J18.900x001 肺炎" in card["text"] and "不是针对本病例的编码建议" in card["text"]
    bindings = len(store.get(session["session_id"], user)["references"])
    assert client.get(url + "/references/" + card["id"]).json() == card
    assert len(store.get(session["session_id"], user)["references"]) == bindings


@pytest.mark.parametrize("args", [{"q": ""}, {"q": "肺炎", "limit": 11}, {"q": "肺炎", "type": "other"}, {"q": "肺炎", "extra": 1}])
def test_code_search_input_is_strict(args):
    from pydantic import ValidationError
    from app.services.qc_agent.business_tools import SearchCodes
    with pytest.raises(ValidationError):
        SearchCodes.model_validate(args)