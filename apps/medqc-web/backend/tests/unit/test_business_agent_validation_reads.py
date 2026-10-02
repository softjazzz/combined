"""规则验收记录与保存来源缺口经业务工具、来源绑定和回读的整合链路；仅合成数据。"""
import json

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


RULE = "LX0609-01-01-01"
PHI = "患者隐私与原文绝不进入来源"
MANAGER_CONTEXT = {"view": "manager", "institute_id": "H", "department": "科室", "care_phase": "discharged",
                   "completed_from": "2026-09-01T00:00:00+08:00", "completed_to": "2026-09-30T23:59:59+08:00"}
IDENTITY = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}


def build_client(tmp_path, monkeypatch, user, context, saved=None):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_schemas import BusinessContext
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store

    store = BusinessSessionStore(tmp_path)
    session = store.create(user, BusinessContext(**context))
    access = BusinessAccess({"version": 1, "accounts": {user["id"]: {
        "doctor_cases": [IDENTITY], "manager_scopes": [{"institute_id": "H", "department": "科室"}]}}})
    runtime_calls = []

    async def runtime_call(method, path, body=None):
        runtime_calls.append(path)
        return {"id": "runtime"}

    def formal_response(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"data": saved})

    monkeypatch.setattr(api, "runtime_call", runtime_call)
    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(formal_response)))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    return TestClient(app), f"/business/sessions/{session['session_id']}", store, session, runtime_calls


def owner_detail():
    run_id = "7d2b3a3e-3c6f-4f5e-9b38-6a6b2d1c0e11"
    return {"rule": {"rule_id": RULE, "name": "合成规则", "note": PHI}, "stage": "pending_approval",
            "coverage": {"counts": {"compliant": {"synthetic": 2, "real_copy": 0}}, "gaps": ["data_gap"], "acceptance_cases": 2},
            "runs": [{"id": run_id, "rule_id": RULE, "state": "bound", "created_at": "2026-10-02T00:00:00+00:00", "cases": [PHI], "created_by": PHI}],
            "events": [{"rule_id": RULE, "run_id": run_id, "kind": "conclusion", "decision": "accepted", "note": PHI}]}


@pytest.fixture
def owner(monkeypatch):
    """替换只读 owner 读取，统计调用次数；角色与投影仍走真实 reader。"""
    from app.services.qc_agent import business_rule_validation as reader
    from app.services import rule_validation

    state = {"reads": 0, "fail": None}

    class Service:
        def _rule(self, rule_id):
            state["reads"] += 1
            if state["fail"]:
                raise state["fail"]
            if rule_id != RULE:
                raise LookupError("规则不存在")
            return owner_detail()["rule"]

        def list_cases(self, _rule_id):
            return []

        def list_runs(self, _rule_id):
            return owner_detail()["runs"]

        def list_events(self, _rule_id):
            return owner_detail()["events"]

        def summarize(self, _rule_id, *, run=None, rows=None):
            return {"coverage": owner_detail()["coverage"]}

    monkeypatch.setattr(reader, "_readonly_service", Service)
    monkeypatch.setattr(reader, "_latest_rows", lambda _rule_id, _run: [])
    monkeypatch.setattr(rule_validation, "derive_stage", lambda *_args: "pending_approval")
    return state


def test_manager_validation_tool_binds_and_rereads_safe_source(tmp_path, monkeypatch, owner):
    user = {"id": "manager", "roles": ["qc_manager"]}
    client, url, store, session, runtime_calls = build_client(tmp_path, monkeypatch, user, MANAGER_CONTEXT)
    response = client.post(url + "/tools/read_rule_validation", json={"rule_id": RULE})
    assert response.status_code == 200
    reference = response.json()["references"][0]
    assert reference["id"] == f"rule-validation:{RULE}" and reference["kind"] == "rule"
    assert reference["entry_path"] == f"/workstation-v4/rules/validation/{RULE}"
    assert "记录阶段：待审批" in reference["text"] and "保存结论：已接受" in reference["text"]
    assert PHI not in json.dumps(response.json(), ensure_ascii=False)
    binding = store.get(session["session_id"], user)["references"][reference["id"]]
    assert binding == {"kind": "rule_validation", "rule_id": RULE}
    again = client.get(url + f"/references/rule-validation:{RULE}")
    assert again.status_code == 200 and again.json() == reference
    assert owner["reads"] == 2 and runtime_calls == []
    # 角色撤销后回读仍由 reader 重新校验，不沿用旧绑定放行。
    user["roles"] = ["doctor"]
    assert client.get(url + f"/references/rule-validation:{RULE}").status_code == 403
    assert owner["reads"] == 2


def test_doctor_view_cannot_read_or_bind_validation(tmp_path, monkeypatch, owner):
    user = {"id": "doctor", "roles": ["doctor", "admin"]}
    client, url, store, session, runtime_calls = build_client(tmp_path, monkeypatch, user, {"view": "doctor", **IDENTITY})
    assert client.post(url + "/tools/read_rule_validation", json={"rule_id": RULE}).status_code == 403
    assert owner["reads"] == 0
    assert f"rule-validation:{RULE}" not in store.get(session["session_id"], user)["references"]
    # 未绑定的验收标识只交给运行时按原规则处理，不读取验收库。
    assert client.get(url + f"/references/rule-validation:{RULE}").status_code == 200
    assert runtime_calls and owner["reads"] == 0


@pytest.mark.parametrize("failure,status", [(HTTPException(503, "验收记录存储尚未就绪"), 503), (None, 404)])
def test_validation_failures_do_not_create_success_source(tmp_path, monkeypatch, owner, failure, status):
    user = {"id": "manager", "roles": ["admin"]}
    client, url, store, session, _runtime_calls = build_client(tmp_path, monkeypatch, user, MANAGER_CONTEXT)
    owner["fail"] = failure
    rule_id = RULE if failure else "LX0609-09-09-09"
    response = client.post(url + "/tools/read_rule_validation", json={"rule_id": rule_id})
    assert response.status_code == status
    assert "references" not in response.json()
    assert store.get(session["session_id"], user)["references"] == {}


def saved_payload(items):
    return {"state": "ready", "job_id": "saved-job", "record_ref": "saved-record", "is_complete": True,
            "missing_rule_ids": [], "conflicting_rule_ids": [], "items": items}


def test_saved_source_gaps_project_through_issue_and_reference_without_changing_conclusion(tmp_path, monkeypatch):
    gap = {"rule_id": RULE, "status": "data_gap", "conclusion": "保存结论：资料不足", "suggestion": "保存建议：补充报告",
           "reason_code": "authoritative_report_time_missing", "missing_sources": ["检验结果明细", PHI], "missing_fields": ["report_time"],
           "data_gap_details": {"availability": "unavailable", "patient": {"name": PHI}}}
    compliant = {"rule_id": "LX0609-01-01-02", "status": "compliant", "conclusion": "保存结论：合规"}
    saved = saved_payload([gap, compliant])
    user = {"id": "doctor", "roles": ["doctor"]}
    client, url, *_ = build_client(tmp_path, monkeypatch, user, {"view": "doctor", **IDENTITY}, saved)
    listing = client.post(url + "/tools/read_saved_results", json={"detail": "saved_text"}).json()["references"]
    by_rule = {row["rule_id"]: row for row in listing}
    issue = client.post(url + "/tools/read_saved_issue", json={"result_id": by_rule[RULE]["id"]}).json()
    reference = issue["references"][0]
    assert reference["conclusion"] == gap["conclusion"] and reference["suggestion"] == gap["suggestion"]
    assert issue["reason_code"] == gap["reason_code"]
    assert issue["source_gaps"]["missing_sources"] == ["检验结果明细"]
    assert issue["source_gaps"]["missing_fields"] == ["report_time"]
    assert issue["source_gaps"]["data_gap_details"] == {"availability": "unavailable"}
    assert any("未纳入本次投影" in note for note in issue["source_gaps"]["projection_notes"])
    assert "保存来源缺口信息（本次未重判）" in reference["text"] and "缺口来源：检验结果明细" in reference["text"]
    assert PHI not in json.dumps(issue, ensure_ascii=False)
    again = client.get(url + f"/references/{reference['id']}").json()
    assert again["text"] == reference["text"] and again["conclusion"] == gap["conclusion"]
    other = client.post(url + "/tools/read_saved_issue", json={"result_id": by_rule["LX0609-01-01-02"]["id"]}).json()
    assert "source_gaps" not in other and "来源缺口" not in other["references"][0]["text"]
    # 保存任务变化时不展示旧缺口，也不改用新判定。
    saved["job_id"] = "replacement-job"
    assert client.get(url + f"/references/{reference['id']}").status_code == 409
