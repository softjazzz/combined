"""合成提醒台账验证授权，不访问真实数据库。"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.qc_agent.business_access import BusinessAccess
from app.services.qc_agent.business_schemas import BusinessContext
from app.services.qc_agent import business_followups as service

USER = {"id": "owner", "roles": ["doctor", "qc_manager"]}
IDENTITY = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}


class FakeDB:
    def __init__(self, rows, results):
        self.rows, self.results, self.calls = rows, results, []

    def table(self, table):
        self.calls.append([table])
        db = self
        class Query:
            def __getattr__(self, name):
                def call(*args, **kwargs):
                    db.calls[-1].append((name, args))
                    return self
                return call

            def execute(self):
                # 故意不执行过滤，额外验证适配层不能信任越界返回。
                return SimpleNamespace(data=db.results if table == "qc_results" else db.rows)
        return Query()


def context(view="doctor"):
    if view == "doctor":
        return BusinessContext(view=view, **IDENTITY)
    return BusinessContext(view=view, institute_id="H", department="D", care_phase="discharged",
                           completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-10-01T00:00:00+08:00")


def access():
    return BusinessAccess({"version": 1, "accounts": {"owner": {"doctor_cases": [IDENTITY], "manager_scopes": [{"institute_id": "H", "department": "D"}]}}})


def notification(**changes):
    return {"id": "n", "recipient_id": "owner", "record_id": "record", "related_type": "qc_result", "related_id": "r", "title": "保存提醒", **changes}


def result(**identity):
    return {"id": "r", "record_id": "record", "raw_output": {"metadata": {**IDENTITY, **identity}}}


def read(db, **kwargs):
    return service.read_followups(user=USER, context=context(), access=access(), kind="notifications", db=db, **kwargs)


def test_notification_uses_uid_relation_and_explicit_current_case():
    db = FakeDB([notification()], [result()])
    payload = read(db)
    assert payload["items"][0]["title"] == "保存提醒"
    assert payload["items"][0]["identity"] == IDENTITY
    assert payload["state"] == "ready"
    assert "total" not in payload
    assert ("eq", ("recipient_id", "owner")) in db.calls[0]
    assert ("range", (0, 5)) in db.calls[0]


@pytest.mark.parametrize("row,saved", [
    (notification(recipient_id="other"), result()),
    (notification(related_type="batch"), result()),
    (notification(record_id="other"), result()),
    (notification(), result(institute_id="other")),
    (notification(), result(patient_id="other")),
    (notification(), result(institute_id="")),
    (notification(), {"id": "r", "record_id": "record", "raw_output": "not-json"}),
    (notification(), {"id": "r", "record_id": "record", "raw_output": {**IDENTITY, "metadata": {"institute_id": "other"}}}),
])
def test_unverifiable_or_cross_scope_items_are_excluded(row, saved):
    payload = read(FakeDB([row], [saved]))
    assert payload["items"] == []
    assert payload["state"] == "partial"
    assert "空页不代表" in payload["coverage_note"]


@pytest.mark.parametrize("view,assigned,department,expected", [
    ("doctor", "owner", "D", True), ("doctor", "other", "D", False),
    ("manager", "other", "D", True), ("manager", "owner", "other", False),
])
def test_remediation_requires_assignee_or_authorized_department(monkeypatch, view, assigned, department, expected):
    from app.services.qc_agent import business_reads
    monkeypatch.setattr(business_reads, "scoped_records", lambda **_: [{**IDENTITY, "department": "D"}])
    row = {"id": "task", "record_id": "record", "qc_result_id": "r", "assignee_id": assigned,
           "assignee_department": department, "status": "submitted", "deadline": "2020-01-01"}
    db = FakeDB([row], [result()])
    payload = service.read_followups(user=USER, context=context(view), access=access(), kind="remediations", db=db)
    assert bool(payload["items"]) is expected
    if expected:
        assert payload["items"][0]["status"] == "submitted"
        assert payload["items"][0]["deadline"] == "2020-01-01"
        assert "overdue" not in payload["items"][0]


def test_source_page_is_bounded_and_can_have_next_page_without_visible_items():
    db = FakeDB([notification(recipient_id="other")] * 3, [result()])
    payload = read(db, page_size=2)
    assert payload["has_more"] is True
    assert payload["items"] == []
    assert len(db.calls) == 1
    assert payload["scan_limit_reached"] is False
    assert "不表示当前范围已查完" in payload["coverage_note"]


@pytest.mark.parametrize("page,source_count,has_more,limited", [
    (99, 3, True, False), (100, 3, False, True), (100, 2, False, False),
])
def test_scan_limit_does_not_advertise_an_invalid_next_page(page, source_count, has_more, limited):
    payload = read(FakeDB([notification()] * source_count, [result()]), page=page, page_size=2)
    assert payload["has_more"] is has_more
    assert payload["scan_limit_reached"] is limited
    if limited:
        assert payload["state"] == "partial"
        assert "仍有未扫描条目" in payload["coverage_note"]
        assert "不能继续翻页" in payload["coverage_note"]
    elif not has_more:
        assert "仅核验当前页" in payload["coverage_note"]


def test_revocation_fails_before_any_database_read():
    db = FakeDB([], [])
    with pytest.raises(HTTPException) as error:
        service.read_followups(user=USER, context=context(), access=BusinessAccess({"version": 1, "accounts": {}}), kind="notifications", db=db)
    assert error.value.status_code == 403
    assert db.calls == []


def test_manager_cannot_use_assignee_department_to_prove_current_case_scope(monkeypatch):
    from app.services.qc_agent import business_reads
    monkeypatch.setattr(business_reads, "scoped_records", lambda **_: [])
    db = FakeDB([notification()], [result()])
    payload = service.read_followups(user=USER, context=context("manager"), access=access(), kind="notifications", db=db)
    assert payload["items"] == []
    assert payload["state"] == "partial"


def test_database_failure_is_unavailable_not_empty():
    class BrokenDB:
        def table(self, _):
            raise RuntimeError("synthetic storage failure")
    with pytest.raises(HTTPException) as error:
        read(BrokenDB())
    assert error.value.status_code == 503


def test_another_granted_case_is_not_current_doctor_context():
    other = {**IDENTITY, "patient_id": "P2", "visit_id": "V2"}
    grants = BusinessAccess({"version": 1, "accounts": {"owner": {"doctor_cases": [IDENTITY, other]}}})
    payload = service.read_followups(user=USER, context=context(), access=grants, kind="notifications",
                                     db=FakeDB([notification()], [result(**other)]))
    assert payload["items"] == []
    assert payload["state"] == "partial"


def test_followup_route_uses_owned_session_and_rechecks_revocation(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import get_business_access
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
    store = BusinessSessionStore(tmp_path)
    session = store.create(USER, context())
    calls = []
    def reader(**kwargs):
        calls.append(kwargs)
        return {"items": [], "state": "partial", "coverage_note": "合成覆盖限制"}
    monkeypatch.setattr(api.business_followups, "read_followups", reader)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_access] = access
    app.dependency_overrides[get_business_store] = lambda: store
    client = TestClient(app)
    url = f"/business/sessions/{session['session_id']}/followups?kind=notifications"
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["data"]["state"] == "partial"
    assert calls[0]["context"].model_dump() == context().model_dump()
    assert client.get(url + "&page_size=11").status_code == 422
    app.dependency_overrides[get_current_user] = lambda: {**USER, "id": "other"}
    assert client.get(url).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_access] = lambda: BusinessAccess({"version": 1, "accounts": {}})
    assert client.get(url).status_code == 403
    assert len(calls) == 1


def test_followup_tool_only_reads_own_session_and_keeps_coverage(tmp_path):
    import asyncio
    import httpx
    from pydantic import ValidationError
    from app.services.qc_agent.business_store import BusinessSessionStore
    from app.services.qc_agent.business_tools import BusinessTools
    async def scenario():
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(USER, context())
        payload = {"items": [], "state": "partial", "coverage_note": "本页缺身份", "has_more": True}
        def handle(request):
            assert request.method == "GET"
            assert request.url.path == f"/api/v1/qc-agent/business/sessions/{metadata['session_id']}/followups"
            assert dict(request.url.params) == {"kind": "remediations", "page": "2", "page_size": "5"}
            return httpx.Response(200, json={"data": payload})
        async with httpx.AsyncClient(base_url="http://synthetic", transport=httpx.MockTransport(handle)) as client:
            tools = BusinessTools(store, client)
            actual = await tools.execute("query_followups", {"kind": "remediations", "page": 2}, metadata, USER)
            assert actual == {**payload, "references": []}
            with pytest.raises(ValidationError):
                await tools.execute("query_followups", {"kind": "remediations", "patient_id": "other"}, metadata, USER)
    asyncio.run(scenario())
