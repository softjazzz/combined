"""合成正式 DTO 验证，不接共享业务库、不调用模型。"""
import asyncio
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.services.qc_agent.business_schemas import BusinessContext
from app.services.qc_agent.business_store import BusinessSessionStore
from app.services.qc_agent.business_tools import BusinessTools


USER = {"id": "synthetic-a"}
RULE = "LX0609-01-01-01"


def test_owner_isolation_and_metadata_has_no_evidence(tmp_path):
    store = BusinessSessionStore(tmp_path)
    session = store.create(USER, BusinessContext(view="doctor", institute_id="S", patient_id="A", visit_id="A1"))
    store.bind(session["session_id"], USER, "result:1", {"kind": "saved_result", "job_id": "job-synthetic"})
    assert "turns" not in store.get(session["session_id"], USER)
    with pytest.raises(HTTPException) as denied:
        store.get(session["session_id"], {"id": "synthetic-b"})
    assert denied.value.status_code == 404
    with pytest.raises(ValidationError):
        BusinessContext(view="doctor", patient_id="A")


def test_saved_issue_keeps_formal_facts_and_rejects_replaced_job(tmp_path):
    async def scenario():
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(USER, BusinessContext(view="doctor", institute_id="S", patient_id="A", visit_id="A1"))
        payload = {"state": "ready", "job_id": "job-a", "record_ref": "rec-synthetic", "rule_set_version": "synthetic-v1", "is_complete": True,
                   "items": [{"rule_id": RULE, "qc_point": "合成质控点", "status": "non_compliant", "conclusion": "原保存结论", "suggestion": "原保存建议", "evidence": [{"source_type": "admission_record", "source_ref": "src_synthetic", "field_path": "name", "evidence_excerpt": "合成原文摘录"}]}]}
        calls = []
        def handler(request):
            calls.append(request)
            assert request.method == "GET"
            assert request.url.params["patient_id"] == "A"
            return httpx.Response(200, json={"data": payload})
        async with httpx.AsyncClient(base_url="http://synthetic", transport=httpx.MockTransport(handler)) as client:
            tools = BusinessTools(store, client)
            results = await tools.execute("read_saved_results", {}, metadata, USER)
            result_id = results["references"][0]["id"]
            metadata = store.get(metadata["session_id"], USER)
            issue = await tools.execute("read_saved_issue", {"result_id": result_id}, metadata, USER)
            assert issue["references"][0]["status"] == "non_compliant"
            assert issue["references"][0]["suggestion"] == "原保存建议"
            assert "合成原文摘录" in issue["references"][0]["text"]
            payload["job_id"] = "job-b"
            with pytest.raises(HTTPException) as replaced:
                await tools.issue(metadata, result_id)
            assert replaced.value.status_code == 409
            with pytest.raises(ValidationError):
                await tools.execute("read_saved_results", {"patient_id": "B"}, metadata, USER)
            with pytest.raises(HTTPException):
                await tools.execute("query_statistics", {}, metadata, USER)
            assert len(calls) == 3
    asyncio.run(scenario())


def test_statistics_preserves_filters_and_api_metrics(tmp_path):
    async def scenario():
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(USER, BusinessContext(view="manager", department="合成科室", care_phase="discharged", completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-09-30T23:59:59+08:00"))
        payload = {"kpis": {"scoped_record_total": 13, "ready_record_total": 10, "unavailable_result_total": 3},
                   "rule_distribution": [{"rule_id": RULE, "rule_name": "合成质控点", "non_compliant_count": 4, "data_gap_count": 2, "evaluated_count": 10}],
                   "record_page": {"items": [{"institute_id": "S", "patient_id": "A", "visit_id": "A1"}]}}
        def handler(request):
            assert request.url.params["department"] == "合成科室"
            assert request.url.params["completed_from"] == metadata["context"]["completed_from"]
            return httpx.Response(200, json={"data": payload})
        async with httpx.AsyncClient(base_url="http://synthetic", transport=httpx.MockTransport(handler)) as client:
            result = await BusinessTools(store, client).execute("query_statistics", {}, metadata, USER)
            assert result["statistics"] == payload
            assert "不合规 4；资料不足 2；已评价 10" in result["references"][0]["text"]
            saved = store.get(metadata["session_id"], USER)
            assert BusinessTools(store, client).identity(saved, result["references"][1]["id"]) == {"institute_id": "S", "patient_id": "A", "visit_id": "A1"}
            with pytest.raises(ValidationError):
                await BusinessTools(store, client).execute("query_statistics", {"department": "其他科室"}, metadata, USER)
        async with httpx.AsyncClient(base_url="http://synthetic", transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
            with pytest.raises(HTTPException) as failure:
                await BusinessTools(store, client).execute("query_statistics", {}, metadata, USER)
            assert failure.value.status_code == 503
    asyncio.run(scenario())


def test_current_catalog_is_not_misrepresented_as_historical_evidence(tmp_path):
    async def scenario():
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(USER, BusinessContext(view="manager"))
        async with httpx.AsyncClient(base_url="http://synthetic", transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"success": False}))) as client:
            tools = BusinessTools(store, client)
            result = await tools.execute("read_rule", {"rule_id": RULE}, metadata, USER)
            assert result["rule"]["rule_id"] == RULE
            assert "空数组不表示医学判据缺失" in result["scope_note"]
            assert "不是历史执行版本或规范原文" in result["references"][0]["locator"]
            with pytest.raises(HTTPException) as invalid:
                await tools.read_api("/invalid")
            assert invalid.value.status_code == 502
    asyncio.run(scenario())


def test_selected_reference_and_restore_must_belong_to_current_account(tmp_path, monkeypatch):
    from app.core.security import get_current_user
    from app.routers import business_agent
    from app.services.qc_agent.business_store import get_business_store
    store = BusinessSessionStore(tmp_path)
    metadata = store.create(USER, BusinessContext(view="manager"))
    selected = "record:synthetic"
    store.bind(metadata["session_id"], USER, selected, {"kind": "record", "identity": {"institute_id": "S", "patient_id": "A", "visit_id": "A1"}})
    calls = []
    async def runtime_call(method, path, body=None):
        calls.append(body)
        return {"status": "completed"}
    monkeypatch.setattr(business_agent, "runtime_call", runtime_call)
    app = FastAPI()
    app.include_router(business_agent.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_store] = lambda: store
    client = TestClient(app)
    url = f"/business/sessions/{metadata['session_id']}"
    body = {"run_id": str(uuid4()), "message": "查看这份病例", "reference_id": "record:foreign"}
    assert client.post(url + "/chat", json=body).status_code == 404
    assert calls == []
    body["reference_id"] = selected
    assert client.post(url + "/chat", json=body).status_code == 200
    assert calls[0]["reference_id"] == selected
    app.dependency_overrides[get_current_user] = lambda: {"id": "synthetic-b"}
    assert client.get(url).status_code == 404
    assert len(calls) == 1
