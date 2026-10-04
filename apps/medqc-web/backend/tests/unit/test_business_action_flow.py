"""复检/专项任务：预览不写任务、确认只来自按钮、同一预览至多提交一次、未知结果只回查不重发；仅合成数据与内存SQLite。"""
import json

import httpx
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.services.qc_agent import business_action_flow as flow
from app.services.qc_agent import business_actions as actions
from app.services.qc_agent.business_action_store import BusinessActionStore, action_table


IDENTITY = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
OTHER = {"institute_id": "H", "patient_id": "P2", "visit_id": "V2"}
USER = {"id": "u1", "roles": ["doctor", "qc_manager"]}
MANAGER = {"view": "manager", "institute_id": "H", "department": "科室", "care_phase": "discharged",
           "completed_from": "2026-09-01T00:00:00+08:00", "completed_to": "2026-09-30T23:59:59+08:00"}


def active_rule():
    active, _ = actions.partition_luxian_0609_rule_scope(actions.get_luxian_0609_customer_delivery_rule_ids())
    accepted = set(actions.get_luxian_0609_acceptance_only_rule_ids())
    return next(item for item in active if item not in accepted)


RULE = active_rule()


class Formal:
    """模拟正式任务服务：记录创建请求，按脚本返回。"""

    def __init__(self):
        self.posts, self.create = [], lambda body: httpx.Response(200, json={"data": {"id": "job-1", "status": "queued"}})
        self.job = {"id": "job-1", "status": "queued", "total_records": 1, "success_count": 0, "failed_count": 0}
        self.listing = []

    def __call__(self, request):
        if request.method == "POST" and request.url.path == flow.TASK_PATH:
            body = json.loads(request.content)
            self.posts.append(body)
            return self.create(body)
        if request.method == "GET" and request.url.path == flow.TASK_PATH:
            return httpx.Response(200, json={"data": {"items": self.listing}})
        if request.method == "GET" and request.url.path.startswith(flow.TASK_PATH + "/"):
            return httpx.Response(200, json={"data": self.job})
        return httpx.Response(404)


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app.core.security import get_current_user
    from app.routers import business_agent as api
    from app.services.qc_agent.business_access import BusinessAccess, get_business_access
    from app.services.qc_agent.business_action_store import get_action_store
    from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store

    engine = sa.create_engine("sqlite://", poolclass=sa.pool.StaticPool, connect_args={"check_same_thread": False})
    table = action_table()
    table.create(engine)
    action_store = BusinessActionStore(sessionmaker(bind=engine), table)
    store = BusinessSessionStore(tmp_path)
    access = BusinessAccess({"version": 1, "accounts": {USER["id"]: {"doctor_cases": [IDENTITY, OTHER], "manager_scopes": [{"institute_id": "H", "department": "科室"}]}}})
    formal = Formal()
    state = {"saved": {"job_id": "old-job", "items": [{"rule_id": RULE, "status": "non_compliant"}]}, "phase": "discharged",
             "sync": None, "department_records": [IDENTITY, OTHER]}
    monkeypatch.setattr(flow, "record_care_phase", lambda identity: state["phase"])
    monkeypatch.setattr(flow, "material_version", lambda identity: actions.MaterialVersion(
        record_ref=actions.ActionRecordRef(**identity), version=state["sync"] or "未提供病例级同步记录",
        synchronization_verified=state["sync"] == "SYNCED", synchronization_failed=state["sync"] == "FAILED"))
    monkeypatch.setattr(flow.business_reads, "saved_record", lambda identity: state["saved"])
    monkeypatch.setattr(flow.business_reads, "scoped_records", lambda **_: [{**record, "department": "科室"} for record in state["department_records"]])
    monkeypatch.setattr(api, "api_client", lambda _: httpx.AsyncClient(base_url="http://fixture", transport=httpx.MockTransport(formal)))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_business_access] = lambda: access
    app.dependency_overrides[get_business_store] = lambda: store
    app.dependency_overrides[get_action_store] = lambda: action_store
    return {"client": TestClient(app), "store": store, "formal": formal, "state": state, "access": access, "actions": action_store}


def session(env, context):
    from app.services.qc_agent.business_schemas import BusinessContext
    metadata = env["store"].create(USER, BusinessContext(**context))
    return f"/business/sessions/{metadata['session_id']}", metadata


def preview(env, url, rules=None):
    response = env["client"].post(url + "/tools/preview_recheck", json={"rule_ids": rules or [RULE]})
    assert response.status_code == 200, response.text
    return response.json()


def test_doctor_preview_writes_no_task_and_warns_unverified_material(env):
    url, metadata = session(env, {"view": "doctor", **IDENTITY})
    result = preview(env, url)
    card = result["references"][0]
    assert card["kind"] == "action" and card["status"] == "previewed" and card["allowed"] is True
    assert "未能证实最新修改的文书已同步" in card["text"] and "需点击“确认执行”" in card["text"]
    assert result["preview"]["warnings"] and env["formal"].posts == []
    reread = env["client"].get(url + "/references/" + card["id"])
    assert reread.status_code == 200 and reread.json()["text"] == card["text"]


def test_confirm_requires_matching_hash_then_submits_once(env):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    card = preview(env, url)["references"][0]
    confirm = f"{url}/actions/{card['action_id']}/confirm"
    bad = env["client"].post(confirm, json={"confirmed": True, "confirmation_hash": "0" * 64})
    assert bad.status_code == 409 and env["formal"].posts == []
    ok = env["client"].post(confirm, json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert ok.status_code == 200 and ok.json()["status"] == "submitted" and ok.json()["job_id"] == "job-1"
    from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
    assert env["formal"].posts == [{"rule_set_key": LUXIAN_0609_RULE_SET_KEY, "rule_ids": [RULE], "scope": "final", "record_refs": [IDENTITY]}]
    again = env["client"].post(confirm, json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert again.status_code == 200 and again.json()["job_id"] == "job-1" and len(env["formal"].posts) == 1
    assert "正式任务 job-1：queued" in again.json()["text"]


def test_claim_is_atomic(env):
    url, metadata = session(env, {"view": "doctor", **IDENTITY})
    card = preview(env, url)["references"][0]
    claims = [env["actions"].claim(action_id=card["action_id"], owner_id=USER["id"], session_id=metadata["session_id"]) for _ in range(3)]
    assert claims == [True, False, False]


@pytest.mark.parametrize("change", ["revoke", "expire", "phase"])
def test_changed_scope_requires_new_preview(env, monkeypatch, change):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    card = preview(env, url)["references"][0]
    if change == "revoke":
        env["access"].config.accounts[USER["id"]].doctor_cases.clear()
    elif change == "expire":
        monkeypatch.setattr(flow, "datetime", type("Later", (), {"now": staticmethod(lambda tz=None: __import__("datetime").datetime(2999, 1, 1, tzinfo=tz))}))
    else:
        env["state"]["phase"] = "inpatient"
    response = env["client"].post(f"{url}/actions/{card['action_id']}/confirm", json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert response.status_code in {403, 409} and env["formal"].posts == []


def test_sync_failure_and_paused_or_unknown_rules_block(env):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    env["state"]["sync"] = "FAILED"
    card = preview(env, url)["references"][0]
    assert card["allowed"] is False and "同步失败" in card["text"] and card["confirmation_hash"]
    blocked = env["client"].post(f"{url}/actions/{card['action_id']}/confirm", json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert blocked.status_code == 409 and env["formal"].posts == []
    env["state"]["sync"] = None
    unknown = preview(env, url, ["LX0609-99-99-99"])["references"][0]
    assert unknown["allowed"] is False and "未知、排除或仅待验收规则" in unknown["text"]


def test_formal_rejection_is_recorded_and_not_resubmitted(env):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    env["formal"].create = lambda body: httpx.Response(422, json={"detail": "所选规则不在当前客户运行范围"})
    card = preview(env, url)["references"][0]
    confirm = f"{url}/actions/{card['action_id']}/confirm"
    first = env["client"].post(confirm, json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]}).json()
    assert first["status"] == "rejected" and "所选规则不在当前客户运行范围" in first["text"]
    env["client"].post(confirm, json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert len(env["formal"].posts) == 1


def test_unknown_result_never_claims_unproven_unique_match_or_resubmits(env):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    env["formal"].create = lambda body: httpx.Response(502)
    card = preview(env, url)["references"][0]
    first = env["client"].post(f"{url}/actions/{card['action_id']}/confirm", json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]}).json()
    assert first["status"] == "unknown" and "未自动重试" in first["text"]
    # 与真实列表投影一致：无 filters/病例三坐标，只有规则与病例数。
    matching = {"id": "job-9", "created_at": "2999-01-01T00:00:00", "draft_ids": [RULE], "total_records": 1, "filters": {}}
    env["formal"].listing = [{**matching, "id": "job-old", "created_at": "2000-01-01T00:00:00"}, {**matching, "id": "job-other", "draft_ids": ["LX0609-99-99-99"]}]
    assert env["client"].get(f"{url}/actions/{card['action_id']}").json()["status"] == "unknown"
    env["formal"].listing = [matching, {**matching, "id": "job-10"}]
    assert env["client"].get(f"{url}/actions/{card['action_id']}").json()["status"] == "unknown"
    env["formal"].listing = [matching]
    view = env["client"].get(f"{url}/actions/{card['action_id']}").json()
    assert view["status"] == "unknown" and view["job_id"] is None and len(env["formal"].posts) == 1


def test_completed_job_shows_saved_before_and_after_without_rejudging(env):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    card = preview(env, url)["references"][0]
    env["client"].post(f"{url}/actions/{card['action_id']}/confirm", json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    env["formal"].job = {**env["formal"].job, "status": "completed", "success_count": 1}
    pending = env["client"].get(f"{url}/actions/{card['action_id']}").json()
    assert "新任务结果尚未成为最新保存结果" in pending["text"]
    env["state"]["saved"] = {"job_id": "job-1", "items": [{"rule_id": RULE, "status": "compliant"}]}
    done = env["client"].get(f"{url}/actions/{card['action_id']}").json()
    assert f"{RULE}：复检前 不合规 → 复检后 合规" in done["text"] and "助手未重新判定" in done["text"]


def test_specialist_task_uses_only_bound_records_and_view_rules(env):
    url, metadata = session(env, MANAGER)
    assert env["client"].post(url + "/tools/preview_specialist_task", json={"record_references": ["record:unbound"], "rule_ids": [RULE]}).status_code == 422
    for identity, reference in ((IDENTITY, "record:a"), (OTHER, "record:b")):
        env["store"].bind(metadata["session_id"], USER, reference, {"kind": "record", "identity": identity})
    card = env["client"].post(url + "/tools/preview_specialist_task", json={"record_references": ["record:a", "record:b"], "rule_ids": [RULE]}).json()["references"][0]
    assert card["allowed"] is True and "病例（2份）：V、V2" in card["text"]
    env["client"].post(f"{url}/actions/{card['action_id']}/confirm", json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert env["formal"].posts[0]["record_refs"] == [IDENTITY, OTHER]
    # 管理视图不能单病例复检；医生视图不能专项任务。
    assert env["client"].post(url + "/tools/preview_recheck", json={"rule_ids": [RULE]}).status_code == 422
    doctor_url, _ = session(env, {"view": "doctor", **IDENTITY})
    assert env["client"].post(doctor_url + "/tools/preview_specialist_task", json={"record_references": ["record:a"], "rule_ids": [RULE]}).status_code == 422
    assert len(env["client"].post(url + "/tools/preview_specialist_task", json={"record_references": [f"r{i}" for i in range(21)], "rule_ids": [RULE]}).json()["detail"])


def test_tool_specs_split_preview_by_view():
    from app.services.qc_agent.business_tools import tool_specs
    assert "preview_recheck" in {s["name"] for s in tool_specs("doctor")} and "preview_recheck" not in {s["name"] for s in tool_specs("manager")}
    assert "preview_specialist_task" in {s["name"] for s in tool_specs("manager")} and "preview_specialist_task" not in {s["name"] for s in tool_specs("doctor")}


@pytest.fixture(autouse=True)
def _writes_enabled(monkeypatch):
    # 这些用例验证写入逻辑本身；开关默认关闭的行为见 test_business_write_switch.py。
    monkeypatch.setenv("MEDQC_AGENT_TASK_WRITE_ENABLED", "1")
    monkeypatch.setenv("MEDQC_AGENT_FEEDBACK_WRITE_ENABLED", "1")


@pytest.mark.parametrize("response", [httpx.Response(200, text="not-json"), httpx.Response(200, json=[1]),
    httpx.Response(200, json={"data": []}), httpx.Response(200, json=None)])
def test_invalid_creation_receipt_is_unknown_and_never_resubmitted(env, response):
    url, metadata = session(env, {"view": "doctor", **IDENTITY})
    env["formal"].create = lambda body: response
    card = preview(env, url)["references"][0]
    endpoint = f"{url}/actions/{card['action_id']}"
    payload = {"confirmed": True, "confirmation_hash": card["confirmation_hash"]}
    first = env["client"].post(endpoint + "/confirm", json=payload)
    assert first.status_code == 200 and first.json()["status"] == "unknown"
    for result in (env["client"].get(endpoint), env["client"].post(endpoint + "/confirm", json=payload)):
        assert result.status_code == 200 and result.json()["status"] == "unknown"
    row = env["actions"].get(action_id=card["action_id"], owner_id=USER["id"], session_id=metadata["session_id"])
    assert row["status"] == "unknown" and row["job_id"] is None
    assert len(env["formal"].posts) == 1


@pytest.mark.parametrize("age,expected", [(0, "submitting"), (61, "unknown")])
def test_interrupted_claim_expires_to_unknown_without_resubmission(env, age, expected):
    from datetime import datetime, timedelta, timezone
    url, metadata = session(env, {"view": "doctor", **IDENTITY})
    card = preview(env, url)["references"][0]
    store = env["actions"]
    assert store.claim(action_id=card["action_id"], owner_id=USER["id"], session_id=metadata["session_id"])
    with store.session_factory() as db:
        db.execute(store.table.update().where(store.table.c.id == card["action_id"]).values(
            claimed_at=datetime.now(timezone.utc) - timedelta(seconds=age)))
        db.commit()
    endpoint = f"{url}/actions/{card['action_id']}"
    assert env["client"].get(endpoint).json()["status"] == expected
    response = env["client"].post(endpoint + "/confirm", json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert response.json()["status"] == expected and env["formal"].posts == []


def test_late_valid_receipt_can_resolve_expired_claim(env):
    url, metadata = session(env, {"view": "doctor", **IDENTITY})
    card = preview(env, url)["references"][0]
    def expire_then_reply(body):
        assert env["actions"].finish(action_id=card["action_id"], status="unknown", message="回执尚未确认")
        return httpx.Response(200, json={"data": {"id": "job-1"}})
    env["formal"].create = expire_then_reply
    result = env["client"].post(f"{url}/actions/{card['action_id']}/confirm",
        json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert result.json()["status"] == "submitted" and result.json()["job_id"] == "job-1"
    assert len(env["formal"].posts) == 1


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_all_server_errors_are_unknown_not_rejected(env, code):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    env["formal"].create = lambda body: httpx.Response(code, json=["unexpected"])
    card = preview(env, url)["references"][0]
    result = env["client"].post(f"{url}/actions/{card['action_id']}/confirm",
        json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert result.status_code == 200 and result.json()["status"] == "unknown"


@pytest.mark.parametrize("candidate", [
    {"record_refs": [OTHER]},
    {"record_refs": [IDENTITY], "scope": "running"},
    {"record_refs": [IDENTITY], "task_runtime": "another-version"},
    {"record_refs": [IDENTITY]},
])
def test_unknown_never_uses_similar_scope_as_request_identity(env, candidate):
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    env["formal"].create = lambda body: httpx.Response(502)
    env["formal"].listing = [{"id": "another-request", "draft_ids": [RULE], "total_records": 1,
                               "created_at": "2999-01-01T00:00:00", **candidate}]
    card = preview(env, url)["references"][0]
    response = env["client"].post(f"{url}/actions/{card['action_id']}/confirm",
        json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
    assert response.json()["status"] == "unknown" and response.json()["job_id"] is None
    assert len(env["formal"].posts) == 1


def test_commit_failure_after_formal_success_does_not_claim_no_submission(env):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.exc import OperationalError
    url, metadata = session(env, {"view": "doctor", **IDENTITY})
    card = preview(env, url)["references"][0]
    store = env["actions"]
    engine = store.session_factory.kw["bind"]
    def fail_finish(_conn, _cursor, statement, parameters, _context, _many):
        if statement.startswith("UPDATE") and "submitted" in parameters:
            raise OperationalError(statement, parameters, RuntimeError("synthetic write failure"))
    sa.event.listen(engine, "before_cursor_execute", fail_finish)
    try:
        response = env["client"].post(f"{url}/actions/{card['action_id']}/confirm",
            json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
        assert response.status_code == 503 and "未提交任务" not in response.text
    finally:
        sa.event.remove(engine, "before_cursor_execute", fail_finish)
    with store.session_factory() as db:
        db.execute(store.table.update().where(store.table.c.id == card["action_id"]).values(
            claimed_at=datetime.now(timezone.utc) - timedelta(seconds=61)))
        db.commit()
    result = env["client"].get(f"{url}/actions/{card['action_id']}")
    assert result.json()["status"] == "unknown" and len(env["formal"].posts) == 1
