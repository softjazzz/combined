from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.routers import custom_qc
from app.services import custom_qc_service, custom_qc_workspace_service as workspace_module
from app.services import custom_qc_sample_pool_service as pool_module
from app.services.qc_rule_orchestrator import QCRuleOrchestrator
from app.services.draft_test_validation_service import (
    DraftTestValidationConflict,
    DraftTestValidationService,
    fixed_test_validation_state,
    validation_view,
)
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from tests.unit.test_custom_qc_draft_basic_info import (
    _basic_payload,
    _visual_condition,
    workspace,  # noqa: F401 - 复用隔离 SQLite 草稿 fixture。
)


ITEM_UPDATED_AT = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)
RECORD_REF = {"institute_id": "CUSTOMER_TEST", "patient_id": "P1", "visit_id": "TEST-V1"}


def _threadsafe_workspace(monkeypatch, source_drafts):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = sa.MetaData()
    drafts = source_drafts.to_metadata(metadata)
    items = source_drafts.metadata.tables["test_pool_items"].to_metadata(metadata)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(items.insert().values(
            id="item-1", pool_id="customer-created-test-records-v1", include_in_batch_1=True,
            exclude_reason="", updated_at=ITEM_UPDATED_AT.replace(tzinfo=None),
            **{f"matched_{key}": value for key, value in RECORD_REF.items()},
        ))
    monkeypatch.setattr(pool_module, "_sample_pool_items_table", lambda: items)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(workspace_module, "_session", sessions)
    service = object.__new__(CustomQCWorkspaceService)
    service._draft_table = drafts
    return service, sessions, drafts, engine


class SamplePool:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls = []

    def fixed_test_records_current(self, *, selected):
        return self.fail is None

    def load_customer_test_record_transfer_payloads(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise self.fail
        return [{
            "source_item_id": kwargs["item_ids"][0],
            "source_updated_at": ITEM_UPDATED_AT,
            "record_ref": RECORD_REF,
            "documents": [{"title": "入院记录", "content": "服务端测试正文"}],
        }]


def _configured_visual_draft(service):
    created = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    return service.update_visual_condition_draft(
        draft_id=created["id"], created_by="manager-1",
        expected_updated_at=created["updated_at"], visual_condition=_visual_condition(),
    )


@pytest.mark.asyncio
async def test_fixed_pool_validation_uses_server_identity_and_saves_publishable_proof(
    workspace, monkeypatch,  # noqa: F811 - pytest 注入复用 fixture。
):
    service, _sessions, _drafts = workspace
    draft = _configured_visual_draft(service)
    hydrated_inputs = []

    def hydrate(records):
        hydrated_inputs.extend(records)
        return [{
            **records[0],
            "evidence_payload": {"programmatic_timeline": {
                "documents": {"first_course_record": []},
                "source_readiness": {"first_course_record": "complete"},
            }},
        }]

    monkeypatch.setattr(service, "hydrate_records_with_visual_evidence", hydrate)
    monkeypatch.setattr(
        custom_qc_service,
        "evaluate_inline_rule_orchestrated",
        lambda **_kwargs: _async_result({
            "status": "non_compliant",
            "issues": [{"description": "命中缺陷"}],
            "findings": "满足缺陷触发条件",
            "evidence": "条件 condition-1 为 true",
            "metadata": {"visual_condition_trace": [{"conditions": [{
                "condition_id": "condition-1", "truth": "true",
                "document_type": "first_course_record", "actual": False,
            }]}]},
        }),
    )
    sample_pool = SamplePool()
    validator = DraftTestValidationService(
        workspace=service, sample_pool=sample_pool, qc_service=object(),
    )
    view = await validator.run(
        draft_id=draft["id"], created_by="manager-1",
        items=[{"item_id": "item-1", "expected_updated_at": ITEM_UPDATED_AT}],
        expected_updated_at=draft["updated_at"],
    )

    assert sample_pool.calls == [{
        "item_ids": ["item-1"], "expected_updated_at": ITEM_UPDATED_AT,
    }]
    assert hydrated_inputs == [{**RECORD_REF, "record_id": "TEST-V1"}]
    assert view["publish_ready"] is True
    assert view["validation"]["validated_revision"] == draft["updated_at"].replace(
        tzinfo=timezone.utc,
    ).isoformat()
    assert view["validation"]["proof_revision"] == view["draft_updated_at"].replace(
        tzinfo=timezone.utc,
    ).isoformat()
    result = view["validation"]["results"][0]
    assert result["record_ref"] == RECORD_REF
    assert result["finding"] == {
        "description": "满足缺陷触发条件", "evidence": "条件 condition-1 为 true",
    }
    assert result["condition_trace"] and "condition-1" in result["condition_trace"][0]


async def _async_result(value):
    return value


def test_publish_guard_rejects_corrupt_or_foreign_proof_shapes():
    now = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)
    base_item = {
        "item_id": "item-1", "item_updated_at": now.isoformat(), "record_ref": RECORD_REF,
    }
    base = {
        "id": "draft-1", "updated_at": now, "status": "draft", "prompt_template": "规则",
        "last_test_summary": {
            "schema_version": "fixed_test_records_v1", "validation_id": "validation-1",
            "draft_id": "draft-1", "validated_revision": (now - timedelta(seconds=1)).isoformat(),
            "proof_revision": now.isoformat(), "item_count": 2, "success_count": 2,
            "selected_items": [base_item, {**base_item, "item_id": "item-2"}],
            "results": [
                {**base_item, "status": "compliant"},
                {**base_item, "item_id": "foreign-item", "status": "non_compliant"},
            ],
            "failures": [],
        },
    }
    assert fixed_test_validation_state(base) == (False, "validation_incomplete")
    base["last_test_summary"]["results"] = [
        {**base_item, "status": "compliant"}, None,
    ]
    assert fixed_test_validation_state(base) == (False, "validation_incomplete")


def test_published_validation_view_confirms_published_state_without_claiming_ready():
    now = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)
    view = validation_view({
        "id": "draft-1", "status": "published", "published_rule_id": "rule-1",
        "updated_at": now, "prompt_template": "规则", "last_test_summary": {
            "schema_version": "fixed_test_records_v1", "validation_id": "validation-1",
            "draft_id": "draft-1", "validated_revision": (now - timedelta(seconds=2)).isoformat(),
            "proof_revision": (now - timedelta(seconds=1)).isoformat(),
            "item_count": 1, "success_count": 1, "selected_items": [],
            "results": [], "failures": [],
        },
    })
    assert view["draft_status"] == "published"
    assert view["published_rule_id"] == "rule-1"
    assert view["publish_ready"] is False
    assert view["unavailable_reason"] == "draft_changed"


def test_fixed_validation_save_is_cas_and_strictly_advances_revision(workspace):  # noqa: F811
    service, _sessions, _drafts = workspace
    draft = service.create_draft(created_by="manager-1", payload={
        "name": "测试", "description": "", "prompt_template": "执行规则",
        "document_type": "入院记录", "check_logic": {},
    })
    summary = {
        "schema_version": "fixed_test_records_v1", "validation_id": "validation-1",
        "draft_id": draft["id"], "validated_revision": draft["updated_at"].isoformat(),
        "item_count": 1, "success_count": 1, "failed_count": 0,
        "issue_records": 0, "compliant_records": 1,
        "unknown_count": 0, "technical_error_count": 0,
        "selected_items": [{
            "item_id": "item-1", "item_updated_at": ITEM_UPDATED_AT.isoformat(),
            "record_ref": RECORD_REF,
        }],
        "results": [{
            "item_id": "item-1", "item_updated_at": ITEM_UPDATED_AT.isoformat(),
            "record_ref": RECORD_REF, "status": "compliant",
        }],
        "failures": [],
    }
    confirmed = service.save_fixed_test_validation_summary(
        draft_id=draft["id"], created_by="manager-1",
        expected_updated_at=draft["updated_at"], summary=summary,
    )
    assert confirmed["updated_at"] > draft["updated_at"]
    assert fixed_test_validation_state(confirmed) == (True, None)
    for field, bad_value in (
        ("success_count", True),
        ("failed_count", 1),
        ("issue_records", 1),
        ("compliant_records", 0),
        ("unknown_count", -1),
        ("technical_error_count", "0"),
    ):
        corrupted = deepcopy(confirmed)
        corrupted["last_test_summary"][field] = bad_value
        assert fixed_test_validation_state(corrupted) == (False, "validation_incomplete")
    with pytest.raises(DraftTestValidationConflict):
        service.save_fixed_test_validation_summary(
            draft_id=draft["id"], created_by="manager-1",
            expected_updated_at=draft["updated_at"], summary=summary,
        )


def test_generic_update_dto_rejects_client_proof_and_publish_fields():
    for forbidden in ("last_test_summary", "status", "published_rule_id"):
        with pytest.raises(Exception):
            custom_qc.WorkspaceDraftUpdateRequest.model_validate({forbidden: "forged"})


@pytest.mark.parametrize("case_changed", [False, True])
def test_actual_http_runs_visual_validation_publishes_and_reads_published_state(
    workspace, monkeypatch, case_changed,  # noqa: F811 - pytest 注入复用 fixture。
):
    _old_service, _old_sessions, source_drafts = workspace
    service, sessions, drafts, engine = _threadsafe_workspace(monkeypatch, source_drafts)
    rules = sa.Table(
        "qc_rules", drafts.metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("rule_code", sa.String, unique=True),
        sa.Column("check_logic", sa.JSON),
        sa.Column("status", sa.String),
    )
    rules.create(sessions.kw["bind"])
    monkeypatch.setattr(workspace_module, "_qc_rules_table", lambda: rules)
    draft = _configured_visual_draft(service)
    monkeypatch.setattr(
        service,
        "hydrate_records_with_visual_evidence",
        lambda records: [{
            **records[0],
            "evidence_payload": {"programmatic_timeline": {
                "documents": {"first_course_record": []},
                "source_readiness": {"first_course_record": "complete"},
            }},
        }],
    )
    sample_pool = SamplePool()
    monkeypatch.setattr(custom_qc, "CustomQCSamplePoolService", lambda: sample_pool)
    llm = AsyncMock(side_effect=AssertionError("visual validation must not call llm"))
    qc_service = SimpleNamespace(
        client=SimpleNamespace(model="test"),
        rule_orchestrator=QCRuleOrchestrator(),
        rule_engine=SimpleNamespace(evaluate=llm),
        execution_cache=None,
    )
    app = FastAPI()
    app.include_router(custom_qc.router)
    app.dependency_overrides[custom_qc.get_current_user] = lambda: {
        "id": "manager-1", "roles": ["qc_manager"],
    }
    app.dependency_overrides[custom_qc.get_workspace_service] = lambda: service
    app.dependency_overrides[custom_qc.get_custom_qc_service] = lambda: qc_service
    with TestClient(app) as client:
        post_response = client.post(
            f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/test-validations",
            json={
                "items": [{
                    "item_id": "item-1", "expected_updated_at": ITEM_UPDATED_AT.isoformat(),
                }],
                "expected_updated_at": draft["updated_at"].replace(tzinfo=timezone.utc).isoformat(),
            },
        )
        assert post_response.status_code == 200
        validation_view_data = post_response.json()["data"]
        assert validation_view_data["publish_ready"] is True
        proof = validation_view_data["validation"]
        if case_changed:
            items = drafts.metadata.tables["test_pool_items"]
            with engine.begin() as connection:
                connection.execute(items.update().values(
                    include_in_batch_1=False, exclude_reason="superseded:new-item",
                ))
            actual_pool = object.__new__(pool_module.CustomQCSamplePoolService)
            actual_pool._item_table = items
            monkeypatch.setattr(pool_module, "_session", sessions)
            sample_pool.fixed_test_records_current = actual_pool.fixed_test_records_current
            stale_view = client.get(
                f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/test-validations"
            ).json()["data"]
            assert stale_view["publish_ready"] is False
            assert stale_view["unavailable_reason"] == "test_records_changed"
        publish_response = client.post(
            f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/publish",
            json={
                "expected_updated_at": validation_view_data["draft_updated_at"],
                "validation_id": proof["validation_id"],
            },
        )
        if case_changed:
            assert publish_response.status_code == 409
            with sessions() as session:
                assert session.execute(sa.select(sa.func.count()).select_from(rules)).scalar() == 0
            with pytest.raises(DraftTestValidationConflict, match="测试病例已修改"):
                service.publish_draft(draft_id=draft["id"], created_by="manager-1")
            engine.dispose()
            return
        assert publish_response.status_code == 200
        get_response = client.get(
            f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/test-validations"
        )
        assert get_response.status_code == 200
        published_view = get_response.json()["data"]
        assert published_view["draft_status"] == "published"
        assert published_view["published_rule_id"]
        assert published_view["publish_ready"] is False
        app.dependency_overrides[custom_qc.get_current_user] = lambda: {
            "id": "manager-2", "roles": ["qc_manager"],
        }
        assert client.get(
            f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/test-validations"
        ).status_code == 404
    llm.assert_not_awaited()
    engine.dispose()


def test_actual_http_rejects_stale_draft_and_nondeterminate_publish(workspace, monkeypatch):  # noqa: F811
    _old_service, _old_sessions, source_drafts = workspace
    service, _sessions, _drafts, engine = _threadsafe_workspace(monkeypatch, source_drafts)
    draft = _configured_visual_draft(service)
    monkeypatch.setattr(
        service,
        "hydrate_records_with_visual_evidence",
        lambda records: [{
            **records[0],
            "evidence_payload": {"programmatic_timeline": {
                "documents": {"first_course_record": []},
                "source_readiness": {"first_course_record": "partial"},
            }},
        }],
    )
    monkeypatch.setattr(custom_qc, "CustomQCSamplePoolService", SamplePool)
    qc_service = SimpleNamespace(
        client=SimpleNamespace(model="test"),
        rule_orchestrator=QCRuleOrchestrator(),
        rule_engine=SimpleNamespace(evaluate=AsyncMock(side_effect=AssertionError("no llm"))),
        execution_cache=None,
    )
    app = FastAPI()
    app.include_router(custom_qc.router)
    app.dependency_overrides[custom_qc.get_current_user] = lambda: {
        "id": "manager-1", "roles": ["qc_manager"],
    }
    app.dependency_overrides[custom_qc.get_workspace_service] = lambda: service
    app.dependency_overrides[custom_qc.get_custom_qc_service] = lambda: qc_service
    request_body = {
        "items": [{"item_id": "item-1", "expected_updated_at": ITEM_UPDATED_AT.isoformat()}],
        "expected_updated_at": draft["updated_at"].replace(tzinfo=timezone.utc).isoformat(),
    }
    with TestClient(app) as client:
        stale = client.post(
            f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/test-validations",
            json={**request_body, "expected_updated_at": "2026-01-01T00:00:00Z"},
        )
        assert stale.status_code == 409
        tested = client.post(
            f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/test-validations",
            json=request_body,
        )
        assert tested.status_code == 200
        data = tested.json()["data"]
        assert data["validation"]["results"][0]["status"] == "data_gap"
        assert data["publish_ready"] is False
        publish = client.post(
            f"/api/v1/custom-qc/workspace/drafts/{draft['id']}/publish",
            json={
                "expected_updated_at": data["draft_updated_at"],
                "validation_id": data["validation"]["validation_id"],
            },
        )
        assert publish.status_code == 422
    engine.dispose()
