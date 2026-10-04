"""M1隔离合同验收：合成非空台账与双版本；不连接业务库或模型。"""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import business_agent as api
from app.services.qc_agent import business_followups, business_reads
from app.services.qc_agent.business_access import BusinessAccess, get_business_access
from app.services.qc_agent.business_schemas import BusinessContext
from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store
from app.services.qc_agent.business_tools import BusinessTools

USER = {"id": "synthetic-m1", "roles": ["doctor", "qc_manager"]}
CASE = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}


class ReadOnlyRows:
    """仅允许生产读链使用的查询方法；任何写方法立即失败。"""

    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def table(self, name):
        db = self
        db.calls.append(name)

        class Query:
            def select(self, *_):
                self.rows = list(db.tables[name])
                return self

            def eq(self, key, value):
                self.rows = [row for row in self.rows if row.get(key) == value]
                return self

            def order(self, *_, **__):
                return self

            def range(self, start, end):
                self.rows = self.rows[start:end + 1]
                return self

            def limit(self, count):
                self.rows = self.rows[:count]
                return self

            def execute(self):
                return SimpleNamespace(data=self.rows)

        return Query()


@pytest.mark.parametrize("view,kind", [("doctor", "notifications"), ("doctor", "remediations"), ("manager", "remediations")])
def test_nonempty_followups_http_runs_real_authorization_then_revocation(tmp_path, monkeypatch, view, kind):
    context = BusinessContext(view=view, **CASE) if view == "doctor" else BusinessContext(view=view, institute_id="H", department="D", care_phase="discharged", completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-10-01T00:00:00+08:00")
    access = BusinessAccess({"version": 1, "accounts": {USER["id"]: {
        "doctor_cases": [CASE], "manager_scopes": [{"institute_id": "H", "department": "D"}],
    }}})
    store = BusinessSessionStore(tmp_path)
    session = store.create(USER, context)
    db = ReadOnlyRows({
        "notifications": [{"id": "notice", "recipient_id": USER["id"], "record_id": "record", "related_type": "qc_result", "related_id": "result", "title": "合成待办", "is_read": False}],
        "qc_remediation_tasks": [{"id": "task", "record_id": "record", "qc_result_id": "result", "assignee_id": USER["id"], "assignee_department": "D", "status": "submitted", "deadline": "2026-01-01"}],
        "qc_results": [{"id": "result", "record_id": "record", "raw_output": {"metadata": CASE}}],
    })
    scope_calls = []

    def scope(**kwargs):
        scope_calls.append(kwargs)
        return [{**CASE, "department": "D"}]

    monkeypatch.setattr(business_reads, "scoped_records", scope)
    original = business_followups.read_followups
    monkeypatch.setattr(business_followups, "read_followups", lambda **kwargs: original(**kwargs, db=db))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    with TestClient(app) as client:
        url = f"/business/sessions/{session['session_id']}/followups?kind={kind}"
        response = client.get(url)
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["state"] == "ready"
        assert len(payload["items"]) == 1
        assert payload["items"][0]["identity"] == CASE
        assert payload["items"][0]["id"] == ("notice" if kind == "notifications" else "task")
        if kind == "remediations":
            assert payload["items"][0]["status"] == "submitted"
        assert bool(scope_calls) is (view == "manager")
        opened = []

        def saved_record(identity):
            opened.append(identity)
            return {"state": "ready", "job_id": "saved-job", "record_ref": "record", "items": []}

        monkeypatch.setattr(business_reads, "saved_record", saved_record)

        async def open_link():
            mounted = FastAPI()
            mounted.mount("/api/v1/qc-agent", app)
            async with httpx.AsyncClient(base_url="http://isolated", transport=httpx.ASGITransport(app=mounted)) as transport:
                tools = BusinessTools(store, transport)
                result = await tools.execute("query_followups", {"kind": kind}, session, USER)
                reference = result["items"][0]["record_reference"]
                assert result["references"][0]["id"] == reference
                assert result["references"][0]["kind"] == "record"
                assert "关联病例" in result["references"][0]["title"]
                assert "V" in result["references"][0]["title"]
                bound = store.get(session["session_id"], USER)
                await tools.execute("read_saved_results", {"record_reference": reference}, bound, USER)
                assert opened == [CASE]
                with pytest.raises(HTTPException):
                    await tools.execute("read_saved_results", {"record_reference": "record:forged"}, bound, USER)
                if view == "doctor":
                    store.bind(session["session_id"], USER, "record:other", {"kind": "record", "identity": {**CASE, "patient_id": "other"}})
                    with pytest.raises(HTTPException) as denied:
                        await tools.execute("read_saved_results", {"record_reference": "record:other"}, store.get(session["session_id"], USER), USER)
                    assert denied.value.status_code == 422
                assert opened == [CASE]

        asyncio.run(open_link())
        reads_before = list(db.calls)
        app.dependency_overrides[get_current_user] = lambda: {**USER, "id": "other"}
        assert client.get(url).status_code == 404
        app.dependency_overrides[get_current_user] = lambda: USER
        app.dependency_overrides[get_business_access] = lambda: BusinessAccess({"version": 1, "accounts": {}})
        assert client.get(url).status_code == 403
        assert db.calls == reads_before


def test_saved_version_survives_reading_different_current_catalog(tmp_path, monkeypatch):
    """同一会话先读旧结果、再读新目录、再回读旧问题，不用新口径覆盖旧事实。"""
    from app.services import luxian_0609_rule_master as master

    rule = master.load_luxian_0609_rule_master()[0]
    monkeypatch.setattr(master, "LUXIAN_0609_RULE_MASTER_VERSION", "synthetic-current-v2")
    monkeypatch.setattr(master, "load_luxian_0609_rule_master", lambda: (rule,))

    async def scenario():
        store = BusinessSessionStore(tmp_path)
        metadata = store.create(USER, BusinessContext(view="doctor", **CASE))
        saved = {"state": "ready", "job_id": "old-job", "record_ref": "record", "rule_set_version": "synthetic-saved-v1", "is_complete": True,
                 "items": [{"rule_id": rule.rule_id, "qc_point": "合成旧问题", "status": "non_compliant", "conclusion": "旧保存结论", "suggestion": "旧保存建议", "evidence": []}]}
        with_calls = []

        def handler(request):
            assert request.method == "GET"
            assert request.url.path.endswith("/latest-result")
            with_calls.append(request)
            return httpx.Response(200, json={"data": saved})

        async with httpx.AsyncClient(base_url="http://isolated", transport=httpx.MockTransport(handler)) as client:
            tools = BusinessTools(store, client)
            listed = await tools.execute("read_saved_results", {}, metadata, USER)
            result_id = listed["references"][0]["id"]
            metadata = store.get(metadata["session_id"], USER)
            before = await tools.execute("read_saved_issue", {"result_id": result_id}, metadata, USER)
            current = await tools.execute("read_rule", {"rule_id": rule.rule_id}, metadata, USER)
            after = await tools.execute("read_saved_issue", {"result_id": result_id}, store.get(metadata["session_id"], USER), USER)
            assert current["catalog_version"] == "synthetic-current-v2"
            assert current["historical_definition_available"] is False
            assert "历史" in current["scope_note"]
            assert before == after
            assert after["rule_set_version"] == "synthetic-saved-v1"
            assert after["references"][0]["conclusion"] == "旧保存结论"
            assert after["references"][0]["suggestion"] == "旧保存建议"
            assert len(with_calls) == 3

    asyncio.run(scenario())


@pytest.mark.parametrize("view", ["doctor", "manager"])
def test_feedback_http_isolated_submit_replay_and_denial(tmp_path, monkeypatch, view):
    """真实路由和SQL事务写临时SQLite，业务结果仅合成只读对象。"""
    from copy import deepcopy
    from uuid import uuid4

    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.services.qc_agent import business_feedback as feedback

    context = BusinessContext(view=view, **CASE) if view == "doctor" else BusinessContext(view=view, institute_id="H", department="D", care_phase="discharged", completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-10-01T00:00:00+08:00")
    access = BusinessAccess({"version": 1, "accounts": {USER["id"]: {"doctor_cases": [CASE], "manager_scopes": [{"institute_id": "H", "department": "D"}]}}})
    store = BusinessSessionStore(tmp_path / "sessions")
    metadata = store.create(USER, context)
    binding = {"kind": "saved_result", "identity": CASE, "job_id": "old-job", "record_ref": "record", "rule_id": "synthetic-rule"}
    store.bind(metadata["session_id"], USER, "result:one", binding)
    saved = {"job_id": "old-job", "record_ref": "record", "items": [{"rule_id": "synthetic-rule", "status": "non_compliant", "qc_point": "合成问题"}]}
    original = deepcopy(saved)
    monkeypatch.setattr(business_reads, "saved_record", lambda _: saved)
    monkeypatch.setattr(business_reads, "scoped_records", lambda **_: [{**CASE, "department": "D"}])
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'isolated-feedback.sqlite'}", connect_args={"check_same_thread": False})
    table = feedback.feedback_table()
    table.metadata.create_all(engine)
    feedback_store = feedback.BusinessFeedbackStore(sessionmaker(bind=engine), table)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    app.dependency_overrides[feedback.get_feedback_store] = lambda: feedback_store
    try:
        with TestClient(app) as client:
            url = f"/business/sessions/{metadata['session_id']}/feedback"
            params = {"reference_id": "result:one"}
            before = client.get(url, params=params)
            assert before.status_code == 200
            assert before.json()["data"] is None
            assert all(before.json()["target"][key] == value for key, value in CASE.items())
            payload = {**params, "comment": "合成异议理由", "request_id": str(uuid4())}
            response = client.post(url, json=payload)
            assert response.status_code == 200
            posted = response.json()["data"]
            assert posted["status"] == "submitted"
            assert client.post(url, json=payload).json()["data"] == posted
            assert client.get(url, params=params).json()["data"] == posted
            assert saved == original
            assert client.post(url, json={**payload, "comment": ""}).status_code == 422
            assert client.post(url, json={**payload, "reference_id": "forged"}).status_code == 404
            app.dependency_overrides[get_current_user] = lambda: {**USER, "id": "other"}
            assert client.get(url, params=params).status_code == 404
            assert client.post(url, json=payload).status_code == 404
            app.dependency_overrides[get_current_user] = lambda: USER
            app.dependency_overrides[get_business_access] = lambda: BusinessAccess({"version": 1, "accounts": {}})
            assert client.get(url, params=params).status_code == 403
            assert client.post(url, json=payload).status_code == 403
            app.dependency_overrides[get_business_access] = lambda: access
            saved["job_id"] = "new-job"
            assert client.post(url, json=payload).status_code == 409
            saved["job_id"] = "old-job"
            with engine.connect() as connection:
                assert connection.scalar(sa.select(sa.func.count()).select_from(table)) == 1
            # 独立空SQLite模拟迁移未就绪；不得回退到共享库或报告成功。
            missing_engine = sa.create_engine(f"sqlite:///{tmp_path / 'missing-schema.sqlite'}")
            app.dependency_overrides[feedback.get_feedback_store] = lambda: feedback.BusinessFeedbackStore(sessionmaker(bind=missing_engine), feedback.feedback_table())
            try:
                assert client.get(url, params=params).status_code == 503
                assert client.post(url, json=payload).status_code == 503
            finally:
                missing_engine.dispose()
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _writes_enabled(monkeypatch):
    # 这些用例验证写入逻辑本身；开关默认关闭的行为见 test_business_write_switch.py。
    monkeypatch.setenv("MEDQC_AGENT_TASK_WRITE_ENABLED", "1")
    monkeypatch.setenv("MEDQC_AGENT_FEEDBACK_WRITE_ENABLED", "1")
