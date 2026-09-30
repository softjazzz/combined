"""未上线自定义质控点管理：CAS 删除、批量上线全批回滚、编码占用与越权。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import custom_qc
from app.services import custom_qc_workspace_service as workspace_module
from tests.unit.test_custom_qc_draft_basic_info import workspace  # noqa: F401 - 复用隔离 SQLite 草稿 fixture。
from tests.unit.test_draft_test_validation_service import (
    ITEM_UPDATED_AT,
    RECORD_REF,
    _threadsafe_workspace,
)


def _iso(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).isoformat()


def _publishable_draft(service, *, owner: str = "manager-1", name: str = "测试规则"):
    draft = service.create_draft(created_by=owner, payload={
        "name": name, "description": "", "prompt_template": "执行规则",
        "document_type": "入院记录", "check_logic": {},
    })
    item = {"item_id": "item-1", "item_updated_at": ITEM_UPDATED_AT.isoformat(), "record_ref": RECORD_REF}
    return service.save_fixed_test_validation_summary(
        draft_id=draft["id"], created_by=owner, expected_updated_at=draft["updated_at"],
        summary={
            "schema_version": "fixed_test_records_v1", "validation_id": f"validation-{draft['id']}",
            "draft_id": draft["id"], "validated_revision": draft["updated_at"].isoformat(),
            "item_count": 1, "success_count": 1, "failed_count": 0,
            "issue_records": 0, "compliant_records": 1,
            "unknown_count": 0, "technical_error_count": 0,
            "selected_items": [item], "results": [{**item, "status": "compliant"}], "failures": [],
        },
    )


def _publish_item(draft):
    return {
        "draft_id": draft["id"],
        "expected_updated_at": _iso(draft["updated_at"]),
        "validation_id": draft["last_test_summary"]["validation_id"],
    }


@pytest.fixture
def api(workspace, monkeypatch):  # noqa: F811 - pytest 注入复用 fixture。
    _old_service, _old_sessions, source_drafts = workspace
    service, sessions, drafts, engine = _threadsafe_workspace(monkeypatch, source_drafts)
    rules = sa.Table(
        "qc_rules", drafts.metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("rule_code", sa.String, unique=True),
        sa.Column("check_logic", sa.JSON),
        sa.Column("status", sa.String),
    )
    rules.create(engine)
    monkeypatch.setattr(workspace_module, "_qc_rules_table", lambda: rules)
    user = {"id": "manager-1", "roles": ["qc_manager"]}
    app = FastAPI()
    app.include_router(custom_qc.router)
    app.dependency_overrides[custom_qc.get_current_user] = lambda: user
    app.dependency_overrides[custom_qc.get_workspace_service] = lambda: service
    with TestClient(app) as client:
        yield client, service, sessions, drafts, rules, user
    engine.dispose()


def _statuses(sessions, drafts):
    with sessions() as session:
        return dict(session.execute(sa.select(drafts.c.id, drafts.c.status)).all())


def _rule_count(sessions, rules):
    with sessions() as session:
        return session.execute(sa.select(sa.func.count()).select_from(rules)).scalar()


def test_list_exposes_server_publish_readiness(api):
    client, service, *_ = api
    ready = _publishable_draft(service, name="已测")
    untested = service.create_draft(created_by="manager-1", payload={
        "name": "未测", "description": "", "prompt_template": "执行规则",
        "document_type": "入院记录", "check_logic": {},
    })
    items = client.get("/api/v1/custom-qc/workspace/drafts?status=draft").json()["data"]["items"]
    by_id = {item["id"]: item for item in items}
    assert by_id[ready["id"]]["publish_ready"] is True
    assert by_id[ready["id"]]["publish_blocked_reason"] is None
    assert by_id[untested["id"]]["publish_ready"] is False
    assert by_id[untested["id"]]["publish_blocked_reason"] == "not_tested"


def test_batch_publish_publishes_all_in_one_transaction(api):
    client, service, sessions, drafts, rules, _user = api
    first, second = _publishable_draft(service, name="一"), _publishable_draft(service, name="二")
    response = client.post(
        "/api/v1/custom-qc/workspace/drafts/publish-batch",
        json={"items": [_publish_item(second), _publish_item(first)]},
    )
    assert response.status_code == 200
    published = response.json()["data"]["items"]
    assert sorted(item["draft_id"] for item in published) == sorted([first["id"], second["id"]])
    assert all(item["status"] == "published" and item["published_rule_id"] for item in published)
    assert set(_statuses(sessions, drafts).values()) == {"published"}
    assert _rule_count(sessions, rules) == 2


@pytest.mark.parametrize("breaker", ["stale_revision", "stale_proof", "untested", "foreign_owner"])
def test_batch_publish_rolls_back_whole_batch_on_any_failure(api, breaker):
    client, service, sessions, drafts, rules, _user = api
    good = _publishable_draft(service, name="好")
    if breaker == "foreign_owner":
        bad = _publishable_draft(service, owner="manager-2", name="他人")
        bad_item = _publish_item(bad)
    elif breaker == "untested":
        bad = service.create_draft(created_by="manager-1", payload={
            "name": "未测", "description": "", "prompt_template": "执行规则",
            "document_type": "入院记录", "check_logic": {},
        })
        bad_item = {"draft_id": bad["id"], "expected_updated_at": _iso(bad["updated_at"]), "validation_id": "x"}
    else:
        bad = _publishable_draft(service, name="坏")
        bad_item = _publish_item(bad)
        if breaker == "stale_revision":
            bad_item["expected_updated_at"] = "2026-01-01T00:00:00Z"
        else:
            bad_item["validation_id"] = "validation-old"
    response = client.post(
        "/api/v1/custom-qc/workspace/drafts/publish-batch",
        json={"items": [_publish_item(good), bad_item]},
    )
    # 未测草稿没有匹配的证明ID，按证明过期拒绝；他人草稿不暴露存在性。
    expected_status = 422 if breaker == "foreign_owner" else 409
    assert response.status_code == expected_status
    assert bad["id"] in response.json()["detail"]
    statuses = _statuses(sessions, drafts)
    assert statuses[good["id"]] == "draft"
    assert statuses[bad["id"]] == "draft"
    assert _rule_count(sessions, rules) == 0


def test_batch_publish_rejects_duplicates_missing_proof_and_empty(api):
    client, service, sessions, drafts, rules, _user = api
    draft = _publishable_draft(service)
    url = "/api/v1/custom-qc/workspace/drafts/publish-batch"
    duplicate = client.post(url, json={"items": [_publish_item(draft), _publish_item(draft)]})
    assert duplicate.status_code == 422
    missing = {k: v for k, v in _publish_item(draft).items() if k != "validation_id"}
    assert client.post(url, json={"items": [missing]}).status_code == 422
    assert client.post(url, json={"items": []}).status_code == 422
    assert _statuses(sessions, drafts)[draft["id"]] == "draft"
    assert _rule_count(sessions, rules) == 0


def test_publish_refuses_to_overwrite_rule_code_owned_by_another_rule(api):
    client, service, sessions, drafts, rules, _user = api
    draft = _publishable_draft(service)
    with sessions() as session:
        session.execute(rules.insert().values(
            id="builtin-1", rule_code=draft["rule_code"], check_logic={"source": "other"}, status="published",
        ))
        session.commit()
    response = client.post(
        "/api/v1/custom-qc/workspace/drafts/publish-batch", json={"items": [_publish_item(draft)]},
    )
    assert response.status_code == 409
    assert _statuses(sessions, drafts)[draft["id"]] == "draft"
    with sessions() as session:
        row = session.execute(sa.select(rules).where(rules.c.id == "builtin-1")).mappings().one()
    assert row["check_logic"] == {"source": "other"}


def test_delete_only_removes_owned_unpublished_draft_with_current_revision(api):
    client, service, sessions, drafts, _rules, user = api
    draft = _publishable_draft(service)
    url = f"/api/v1/custom-qc/workspace/drafts/{draft['id']}"
    stale = client.delete(url, params={"expected_updated_at": "2026-01-01T00:00:00Z"})
    assert stale.status_code == 409
    user["id"] = "manager-2"
    assert client.delete(url, params={"expected_updated_at": _iso(draft["updated_at"])}).status_code == 404
    user["id"] = "manager-1"
    assert draft["id"] in _statuses(sessions, drafts)
    assert client.delete(url, params={"expected_updated_at": _iso(draft["updated_at"])}).status_code == 200
    assert draft["id"] not in _statuses(sessions, drafts)


def test_delete_rejects_published_draft_even_on_legacy_path(api):
    client, service, sessions, drafts, _rules, _user = api
    draft = _publishable_draft(service)
    assert client.post(
        "/api/v1/custom-qc/workspace/drafts/publish-batch", json={"items": [_publish_item(draft)]},
    ).status_code == 200
    response = client.delete(f"/api/v1/custom-qc/workspace/drafts/{draft['id']}")
    assert response.status_code == 409
    assert _statuses(sessions, drafts)[draft["id"]] == "published"
    legacy = service.create_draft(created_by="manager-1", payload={
        "name": "旧入口", "description": "", "prompt_template": "执行规则",
        "document_type": "入院记录", "check_logic": {},
    })
    assert client.delete(f"/api/v1/custom-qc/workspace/drafts/{legacy['id']}").status_code == 200
