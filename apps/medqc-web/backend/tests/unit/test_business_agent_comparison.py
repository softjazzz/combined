"""跨期描述只搬正式原值，保持授权范围和两期可回查来源。"""
from copy import deepcopy

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
from pydantic import ValidationError
import pytest

from app.services.qc_agent.business_schemas import BusinessContext
from app.services.qc_agent.business_store import BusinessSessionStore
from app.services.qc_agent.business_tools import BusinessTools, CompareStatistics, tool_specs


USER = {"id": "manager", "roles": ["qc_manager"]}
RULE = "LX0609-01-01-01"
CONTEXT = dict(view="manager", institute_id="H", department="授权科室", care_phase="discharged",
               completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-09-30T23:59:59+08:00")
ARGUMENTS = dict(rule_id=RULE, baseline_completed_from="2026-08-01T00:00:00+08:00", baseline_completed_to="2026-08-31T23:59:59+08:00")


def payload(ready=3, count=2):
    return {"scope": {"rule_id": RULE}, "kpis": {"scoped_record_total": 50, "ready_record_total": ready, "unavailable_result_total": 7},
            "status_distribution": [{"status": "non_compliant", "count": count}],
            "rule_distribution": [{"rule_id": RULE, "rule_name": "合成规则", "evaluated_count": 3,
                                   "non_compliant_count": count, "data_gap_count": 1, "uncertain_count": 0}],
            "record_page": {"items": [{"institute_id": "H", "patient_id": "synthetic-p", "visit_id": "synthetic-v"}]}}


@pytest.mark.parametrize("changes", [
    {"baseline_completed_from": "2026-08-01"}, {"baseline_completed_to": "2026-08-31T23:59:59"},
    {"baseline_completed_from": "上月"}, {"baseline_completed_from": "2026-09-02T00:00:00+08:00"},
    {"baseline_completed_from": "2024-01-01T00:00:00+08:00"}, {"rule_id": "unknown"},
    {"institute_id": "other"}, {"department": "other"}, {"care_phase": "inpatient"},
    {"page": 2}, {"result_status": "non_compliant"},
])
def test_baseline_and_scope_inputs_are_strict(changes):
    with pytest.raises(ValidationError):
        CompareStatistics.model_validate({**ARGUMENTS, **changes})


@pytest.mark.parametrize("field", ["rule_id", "baseline_completed_from", "baseline_completed_to"])
def test_period_and_rule_are_required(field):
    arguments = {key: value for key, value in ARGUMENTS.items() if key != field}
    with pytest.raises(ValidationError):
        CompareStatistics.model_validate(arguments)


@pytest.mark.asyncio
async def test_two_original_periods_fixed_scope_no_record_binding_and_http_readback(tmp_path, monkeypatch):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_store import get_business_store

    store = BusinessSessionStore(tmp_path)
    metadata = store.create(USER, BusinessContext(**CONTEXT))
    responses = {CONTEXT["completed_from"]: payload(), ARGUMENTS["baseline_completed_from"]: payload(ready=2, count=9)}
    calls = []
    def formal(request):
        filters = dict(request.url.params)
        calls.append(filters)
        assert request.method == "GET"
        assert request.url.path == "/api/v1/qc-agent/business/statistics"
        assert {key: filters[key] for key in ("institute_id", "department", "care_phase")} == {key: CONTEXT[key] for key in ("institute_id", "department", "care_phase")}
        assert filters["rule_id"] == RULE
        return httpx.Response(200, json={"data": deepcopy(responses[filters["completed_from"]])})
    def client():
        return httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(formal))
    async with client() as connection:
        result = await BusinessTools(store, connection).execute("compare_statistics", ARGUMENTS, metadata, USER)
    assert len(calls) == 2
    comparison = result["comparison"]
    assert comparison["same_rule_version_verified"] is False
    assert [period["key"] for period in comparison["periods"]] == ["current", "baseline"]
    for period in comparison["periods"]:
        original = responses[period["filters"]["completed_from"]]
        assert period["statistics"] == {key: original[key] for key in ("scope", "kpis", "status_distribution", "rule_distribution")}
        assert not period["data_notes"]
        assert "record_page" not in period["statistics"]
    assert len(result["references"]) == 2
    bindings = store.get(metadata["session_id"], USER)["references"]
    assert all(binding["kind"] == "statistics" for binding in bindings.values())

    monkeypatch.setattr(api, "api_client", lambda _request: client())
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_store] = lambda: store
    access = BusinessAccess({"version": 1, "accounts": {USER["id"]: {"manager_scopes": [{"institute_id": "H", "department": "授权科室"}]}}})
    app.dependency_overrides[get_business_access] = lambda: access
    http = TestClient(app)
    for index, period in enumerate(comparison["periods"]):
        response = http.get(f"/business/sessions/{metadata['session_id']}/references/{period['source_reference']}")
        assert response.status_code == 200
        detail = response.json()
        assert period["label"] in detail["title"]
        assert "机构：H；科室：授权科室；病例范围：出院" in detail["text"]
        assert ("2026年09月" if index == 0 else "2026年08月") in detail["text"]
        assert "UTC+08:00" in detail["text"]
        assert "未按期间过滤" in detail["text"]
        assert "已评价数量包含未执行和不适用" in detail["text"]
        assert ("不合规 2" if index == 0 else "不合规 9") in detail["text"]
        assert calls[-1] == {key: str(value) for key, value in period["filters"].items()}


@pytest.mark.asyncio
async def test_missing_period_values_stay_missing_not_zero(tmp_path):
    store = BusinessSessionStore(tmp_path)
    metadata = store.create(USER, BusinessContext(**CONTEXT))
    missing = {"kpis": {"ready_record_total": 0}, "rule_distribution": []}
    async with httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"data": missing}))) as client:
        result = await BusinessTools(store, client).execute("compare_statistics", ARGUMENTS, metadata, USER)
    for period in result["comparison"]["periods"]:
        assert period["statistics"] == missing
        assert len(period["data_notes"]) == 2
        assert "不能补零" in period["data_notes"][1]
    assert any("未执行和不适用" in note for note in result["comparison"]["limitations"])
    assert any("不是期间历史快照" in note for note in result["comparison"]["limitations"])


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [
    {}, {"kpis": None, "rule_distribution": None, "scope": None, "status_distribution": None},
    {"kpis": {"ready_record_total": None}, "rule_distribution": [None]},
    {"kpis": {"ready_record_total": 2}, "rule_distribution": [{"rule_id": RULE, "evaluated_count": None}]},
])
async def test_null_or_incomplete_structure_is_insufficient_without_replacing_source(tmp_path, missing):
    store = BusinessSessionStore(tmp_path)
    metadata = store.create(USER, BusinessContext(**CONTEXT))
    async with httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"data": missing}))) as client:
        result = await BusinessTools(store, client).execute("compare_statistics", ARGUMENTS, metadata, USER)
    for period in result["comparison"]["periods"]:
        assert period["statistics"] == missing
        assert period["data_notes"]
    assert all("范围病例 未提供" in reference["text"] for reference in result["references"])
    assert all("None" not in reference["text"] for reference in result["references"])


@pytest.mark.asyncio
async def test_doctor_and_invalid_current_period_cannot_read(tmp_path):
    assert "compare_statistics" not in {tool["name"] for tool in tool_specs("doctor")}
    assert "compare_statistics" in {tool["name"] for tool in tool_specs("manager")}
    calls = []
    async with httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(lambda request: calls.append(request))) as client:
        for context in ({"view": "doctor"}, {**CONTEXT, "completed_from": "2026-09-01"}, {**CONTEXT, "completed_from": "2024-01-01T00:00:00+08:00"}, {**CONTEXT, "department": ""}):
            with pytest.raises(HTTPException) as exc:
                await BusinessTools(BusinessSessionStore(tmp_path), client).execute("compare_statistics", ARGUMENTS, {"context": context}, USER)
            assert exc.value.status_code == 422
    assert calls == []


@pytest.mark.asyncio
async def test_second_read_failure_leaves_no_half_group_or_scope_change(tmp_path):
    store = BusinessSessionStore(tmp_path)
    metadata = store.create(USER, BusinessContext(**CONTEXT))
    def formal(request):
        return httpx.Response(200, json={"data": payload()}) if request.url.params["completed_from"] == CONTEXT["completed_from"] else httpx.Response(503)
    async with httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(formal)) as client:
        with pytest.raises(HTTPException) as exc:
            await BusinessTools(store, client).execute("compare_statistics", ARGUMENTS, metadata, USER)
        assert exc.value.status_code == 503
    restored = store.get(metadata["session_id"], USER)
    assert restored["references"] == {}
    assert restored["context"] == CONTEXT
