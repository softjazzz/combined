"""解释入口只提供当前视图可用工具，不把保存覆盖率当任务状态。"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("view", ["doctor", "manager"])
def test_runtime_bridge_limits_tools_on_create_restore_chat_and_reference(tmp_path, monkeypatch, view):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store

    user = {"id": "scope-test", "roles": ["doctor", "qc_manager"]}
    identity = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
    context = {"view": view, **identity} if view == "doctor" else {"view": view, "institute_id": "H", "department": "科室", "care_phase": "discharged", "completed_from": "2026-09-01T00:00:00+08:00", "completed_to": "2026-09-30T23:59:59+08:00"}
    access = BusinessAccess({"version": 1, "accounts": {user["id"]: {"doctor_cases": [identity], "manager_scopes": [{"institute_id": "H", "department": "科室"}]}}})
    calls = []

    async def runtime_call(method, path, body=None):
        calls.append((path, body))
        return {"turns": []}

    monkeypatch.setattr(api, "runtime_call", runtime_call)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: BusinessSessionStore(tmp_path)
    client = TestClient(app)
    created = client.post("/business/sessions", json={"context": context})
    assert created.status_code == 200
    url = f"/business/sessions/{created.json()['session_id']}"
    assert client.get(url).status_code == 200
    assert client.post(url + "/chat", json={"run_id": str(uuid4()), "message": "解释已选问题"}).status_code == 200
    assert client.get(url + "/references/guideline:unknown").status_code == 200
    expected = {"read_saved_results", "read_saved_issue", "read_rule", "search_rules"}
    if view == "manager":
        expected.add("query_statistics")
    bodies = [body for _, body in calls if body is not None]
    assert len(bodies) == 4
    for body in bodies:
        assert {tool["name"] for tool in body["tools"]} == expected


def test_second_saved_issue_opens_its_current_document_and_rechecks_version(tmp_path, monkeypatch):
    import httpx
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_documents import locate_document
    from app.services.qc_agent.business_schemas import BusinessContext
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store

    user = {"id": "doctor-closed-loop", "roles": ["doctor"]}
    identity = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
    store = BusinessSessionStore(tmp_path)
    session = store.create(user, BusinessContext(view="doctor", **identity))
    access = BusinessAccess({"version": 1, "accounts": {user["id"]: {"doctor_cases": [identity]}}})
    evidence = {"source_ref": "source-second", "source_type": "admission_record", "evidence_excerpt": "未发现所述变化"}
    saved = {"state": "ready", "job_id": "saved-job", "record_ref": "saved-record", "is_complete": False, "missing_rule_ids": [], "conflicting_rule_ids": ["LX0609-01-01-03"], "items": [
        {"rule_id": "LX0609-01-01-01", "status": "non_compliant", "conclusion": "第一条保存结论"},
        {"rule_id": "LX0609-01-01-02", "status": "non_compliant", "conclusion": "第二条保存结论", "suggestion": "第二条保存建议", "evidence": [evidence]},
    ]}
    business_reads = []

    def formal_response(request):
        business_reads.append(request)
        assert request.method == "GET"
        assert request.url.params["patient_id"] == "P"
        return httpx.Response(200, json={"data": saved})

    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(formal_response)))
    document_reads = []
    document = {"source_ref": "source-second", "doc_type": "admission_record", "doc_name": "入院记录", "content": "😀当前文书：未发现所述变化。"}

    def read_document(selected_identity, selected_evidence):
        document_reads.append((selected_identity, selected_evidence))
        return locate_document(selected_evidence, {"documents": [document]})

    monkeypatch.setattr(api.business_documents, "read_evidence_document", read_document)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    client = TestClient(app)
    url = f"/business/sessions/{session['session_id']}"
    listing = client.post(url + "/tools/read_saved_results", json={"statuses": ["non_compliant"], "detail": "saved_text"})
    assert listing.status_code == 200
    assert listing.json()["conflicting_rule_ids"] == saved["conflicting_rule_ids"]
    second = listing.json()["references"][1]
    assert second["position"] == 2
    issue = client.post(url + "/tools/read_saved_issue", json={"result_id": second["id"]})
    assert issue.status_code == 200
    assert issue.json()["references"][0]["conclusion"] == second["conclusion"]
    assert issue.json()["evidence"] == [evidence]
    params = {"reference_id": second["id"], "evidence_index": 0}
    current = client.get(url + "/evidence-document", params=params).json()
    assert current["state"] == "located" and current["source_view"] == "current"
    assert current["content"][current["start"]:current["end"]] == evidence["evidence_excerpt"]
    assert document_reads == [(identity, evidence)]
    # 当前文书变化时明确未匹配，不把保存摘录充当当前原文。
    document["content"] = "当前文书已经更新。"
    unmatched = client.get(url + "/evidence-document", params=params).json()
    assert unmatched["state"] == "quote_not_found" and "start" not in unmatched
    assert unmatched["content"] == document["content"]
    # 隐藏统计描述之外，直接调用仍由业务层拒绝，不读取任何统计数据。
    count_before = len(business_reads)
    assert client.post(url + "/tools/query_statistics", json={}).status_code == 422
    assert len(business_reads) == count_before
    saved["job_id"] = "replacement-job"
    assert client.get(url + "/evidence-document", params=params).status_code == 409
    access.config.accounts.clear()
    assert client.get(url + "/evidence-document", params=params).status_code == 403
    assert len(document_reads) == 2
