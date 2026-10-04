"""科室趋势：各期只搬正式原值，范围固定，期间严格，可回读；仅合成数据。"""
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.services.qc_agent.business_schemas import BusinessContext
from app.services.qc_agent.business_store import BusinessSessionStore
from app.services.qc_agent.business_tools import TrendStatistics, tool_specs


USER = {"id": "manager", "roles": ["doctor", "qc_manager"]}
RULE = "LX0609-01-01-01"
CONTEXT = dict(view="manager", institute_id="H", department="授权科室", care_phase="discharged",
               completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-09-30T23:59:59+08:00")
MONTHS = [{"completed_from": f"2026-0{m}-01T00:00:00+08:00", "completed_to": f"2026-0{m}-{d}T23:59:59+08:00"} for m, d in ((7, 31), (8, 31), (9, 30))]


def payload(ready, counts):
    return {"scope": {}, "kpis": {"scoped_record_total": 50, "ready_record_total": ready, "unavailable_result_total": 7},
            "status_distribution": [],
            "rule_distribution": [{"rule_id": rule, "rule_name": f"规则{rule[-2:]}", "evaluated_count": 9,
                                   "non_compliant_count": count, "data_gap_count": 1, "uncertain_count": 0} for rule, count in counts.items()]}


@pytest.mark.parametrize("periods", [
    MONTHS[:1], MONTHS * 3, [MONTHS[1], MONTHS[0]], [MONTHS[0], MONTHS[0]],
    [{"completed_from": "2026-07-01", "completed_to": "2026-07-31"}, MONTHS[1]],
])
def test_periods_must_be_2_to_6_ascending_non_overlapping_with_timezone(periods):
    with pytest.raises(ValidationError):
        TrendStatistics.model_validate({"periods": periods})


def build(tmp_path, monkeypatch, responses, context=CONTEXT):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_store import get_business_store

    store = BusinessSessionStore(tmp_path)
    metadata = store.create(USER, BusinessContext(**context))
    calls = []

    def formal(request):
        calls.append(dict(request.url.params))
        response = responses.get(request.url.params["completed_from"])
        return httpx.Response(503) if response is None else httpx.Response(200, json={"data": response})

    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(formal)))
    access = BusinessAccess({"version": 1, "accounts": {USER["id"]: {"doctor_cases": [{"institute_id": "H", "patient_id": "P", "visit_id": "V"}],
                                                                      "manager_scopes": [{"institute_id": "H", "department": "授权科室"}]}}})
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    return TestClient(app), f"/business/sessions/{metadata['session_id']}", store, metadata, calls


def test_each_period_reads_formal_values_with_fixed_scope_and_rereads(tmp_path, monkeypatch):
    responses = {MONTHS[0]["completed_from"]: payload(4, {RULE: 3}), MONTHS[1]["completed_from"]: payload(0, {}),
                 MONTHS[2]["completed_from"]: payload(6, {RULE: 1})}
    client, url, store, metadata, calls = build(tmp_path, monkeypatch, responses)
    response = client.post(url + "/tools/trend_statistics", json={"rule_id": RULE, "periods": MONTHS})
    assert response.status_code == 200
    assert [call["completed_from"] for call in calls] == [month["completed_from"] for month in MONTHS]
    assert all(call["institute_id"] == "H" and call["department"] == "授权科室" and call["care_phase"] == "discharged"
               and call["rule_id"] == RULE for call in calls)
    card = response.json()["references"][0]
    assert card["kind"] == "statistics" and card["id"].startswith("trend:")
    text = card["text"]
    assert "第1期 2026年07月01日 00:00:00（UTC+08:00）" in text and "规则01：不合规 3；资料不足 1；已评价 9" in text
    assert "该期没有期间内有效保存结果，不能将缺结果解释为零问题或改善" in text
    assert "该期未返回所选规则统计，不能补零" in text
    assert "%" not in text and "增长" not in text.split("只列各期原值")[0]
    before = len(calls)
    again = client.get(url + "/references/" + card["id"])
    assert again.status_code == 200 and again.json() == card and len(calls) == before + 3


def test_without_rule_lists_top5_by_non_compliant(tmp_path, monkeypatch):
    counts = {f"LX0609-01-01-0{i}": i for i in range(1, 8)}
    responses = {month["completed_from"]: payload(5, counts) for month in MONTHS[:2]}
    client, url, *_ = build(tmp_path, monkeypatch, responses)
    text = client.post(url + "/tools/trend_statistics", json={"periods": MONTHS[:2]}).json()["references"][0]["text"]
    first = text.split("第2期")[0]
    assert "不合规次数前5条规则" in first and "规则07：不合规 7" in first and "规则02：" not in first


def test_failed_period_saves_no_partial_trend(tmp_path, monkeypatch):
    responses = {MONTHS[0]["completed_from"]: payload(4, {RULE: 3})}
    client, url, store, metadata, _ = build(tmp_path, monkeypatch, responses)
    assert client.post(url + "/tools/trend_statistics", json={"rule_id": RULE, "periods": MONTHS[:2]}).status_code == 503
    assert not any(binding["kind"] == "trend" for binding in store.get(metadata["session_id"], USER)["references"].values())


def test_trend_is_manager_only(tmp_path, monkeypatch):
    client, url, *_ = build(tmp_path, monkeypatch, {}, {"view": "doctor", "institute_id": "H", "patient_id": "P", "visit_id": "V"})
    assert client.post(url + "/tools/trend_statistics", json={"periods": MONTHS[:2]}).status_code == 422
    assert "trend_statistics" in {spec["name"] for spec in tool_specs("manager")}
    assert "trend_statistics" not in {spec["name"] for spec in tool_specs("doctor")}
