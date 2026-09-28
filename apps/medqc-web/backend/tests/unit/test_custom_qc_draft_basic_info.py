from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.routers import custom_qc
from app.services import custom_qc_workspace_service as service_module
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    DraftBasicInfoConflict,
    DraftBasicInfoInvalid,
    DraftBasicInfoNotFound,
    DraftVisualConditionConflict,
    DraftVisualConditionNotFound,
    draft_basic_info_document_options,
)
from app.services.visual_condition_service import VisualConditionInvalid


def _request(method: str = "POST") -> Request:
    return Request({"type": "http", "method": method, "path": "/", "headers": []})


@pytest.fixture
def workspace(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    drafts = sa.Table(
        "custom_qc_rule_drafts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_requirement", sa.Text, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("applicable_documents", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("defect_level", sa.String(32), nullable=False),
        sa.Column("complexity", sa.String(32), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False),
        sa.Column("generation_mode", sa.String(32), nullable=False),
        sa.Column("examples", sa.Text, nullable=False),
        sa.Column("check_logic", sa.Text, nullable=False),
        sa.Column("last_test_summary", sa.Text),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("published_rule_id", sa.String(64)),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(service_module, "_session", sessions)
    instance = object.__new__(CustomQCWorkspaceService)
    instance._draft_table = drafts
    yield instance, sessions, drafts
    engine.dispose()


def _basic_payload(**overrides):
    return {
        "name": " 入院记录完整性 ",
        "category": " 病历书写与管理基本规范 ",
        "rule_type": " 完整性 ",
        "document_type": "入院记录",
        **overrides,
    }


def _visual_condition():
    return {
        "schema_version": "visual-condition-v1",
        "root_operator": "all",
        "groups": [{
            "id": "group-1",
            "operator": "all",
            "conditions": [{
                "id": "condition-1",
                "kind": "document_presence",
                "document_type": "first_course_record",
                "operator": "not_exists",
            }],
        }],
    }


def test_visual_condition_get_is_nullable_then_patch_uses_cas_and_clears_test_proof(workspace):
    service, sessions, drafts = workspace
    created = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    assert service.get_visual_condition_draft(
        draft_id=created["id"], created_by="manager-1",
    )["visual_condition"] is None
    with sessions.begin() as session:
        session.execute(
            sa.update(drafts)
            .where(drafts.c.id == created["id"])
            .values(last_test_summary='{"success_count":1}')
        )

    updated = service.update_visual_condition_draft(
        draft_id=created["id"],
        created_by="manager-1",
        visual_condition=_visual_condition(),
        expected_updated_at=created["updated_at"].replace(tzinfo=timezone.utc),
    )
    assert updated["visual_condition"] == _visual_condition()
    with sessions() as session:
        row = session.execute(sa.select(drafts).where(drafts.c.id == created["id"])).mappings().one()
        assert row["last_test_summary"] is None
        assert service_module._safe_json_loads(row["check_logic"], {})["visual_condition"] == _visual_condition()
    with pytest.raises(DraftVisualConditionConflict):
        service.update_visual_condition_draft(
            draft_id=created["id"], created_by="manager-1",
            visual_condition=_visual_condition(), expected_updated_at=created["updated_at"],
        )
    with pytest.raises(DraftVisualConditionNotFound):
        service.get_visual_condition_draft(draft_id=created["id"], created_by="manager-2")


def test_generic_update_validates_visual_config_and_invalidates_old_test(workspace):
    service, sessions, drafts = workspace
    created = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    current = service.get_draft(draft_id=created["id"], created_by="manager-1")
    logic = {**current["check_logic"], "visual_condition": _visual_condition()}
    with sessions.begin() as session:
        session.execute(
            sa.update(drafts).where(drafts.c.id == created["id"])
            .values(last_test_summary='{"success_count":1}')
        )
    service.update_draft(
        draft_id=created["id"], created_by="manager-1", payload={"check_logic": logic},
    )
    with sessions() as session:
        row = session.execute(sa.select(drafts).where(drafts.c.id == created["id"])).mappings().one()
        assert row["last_test_summary"] is None
    broken = {**logic, "visual_condition": {"schema_version": "bad"}}
    with pytest.raises(VisualConditionInvalid):
        service.update_draft(
            draft_id=created["id"], created_by="manager-1", payload={"check_logic": broken},
        )
    with sessions.begin() as session:
        session.execute(
            sa.update(drafts).where(drafts.c.id == created["id"])
            .values(last_test_summary='{"success_count":1}')
        )
    service.update_draft(
        draft_id=created["id"],
        created_by="manager-1",
        payload={"check_logic": {"basic_info": logic["basic_info"]}},
    )
    with sessions() as session:
        row = session.execute(sa.select(drafts).where(drafts.c.id == created["id"])).mappings().one()
        assert row["last_test_summary"] is None


def test_publish_preserves_visual_condition_for_workspace_execution(workspace, monkeypatch):
    service, sessions, drafts = workspace
    qc_rules = sa.Table(
        "qc_rules",
        drafts.metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("check_logic", sa.JSON, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
    )
    qc_rules.create(bind=sessions.kw["bind"])
    monkeypatch.setattr(service_module, "_qc_rules_table", lambda: qc_rules)
    created = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    configured = service.update_visual_condition_draft(
        draft_id=created["id"], created_by="manager-1",
        visual_condition=_visual_condition(), expected_updated_at=created["updated_at"],
    )
    with sessions.begin() as session:
        session.execute(
            sa.update(drafts).where(drafts.c.id == created["id"]).values(
                last_test_summary='{"success_count":1}',
                updated_at=configured["updated_at"],
            )
        )
    published = service.publish_draft(draft_id=created["id"], created_by="manager-1")
    assert published["status"] == "published"
    with sessions() as session:
        row = session.execute(sa.select(qc_rules)).mappings().one()
    assert row["check_logic"]["visual_condition"] == _visual_condition()
    assert row["check_logic"]["source"] == "custom_rule_workspace"


def test_document_options_only_return_real_supported_document_labels():
    options = draft_basic_info_document_options()
    values = [item["value"] for item in options]
    assert options and all(item["value"] == item["label"] for item in options)
    assert "入院记录" in values
    assert "病程记录" not in values
    assert len(values) == len(set(values))


def test_create_persists_basic_info_and_owner_list_reads_top_level_fields(workspace, monkeypatch):
    service, _sessions, _drafts = workspace
    monkeypatch.setattr(
        service,
        "publish_draft",
        lambda **_kwargs: pytest.fail("保存基础信息不得调用发布链"),
    )

    created = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    assert created == {
        "id": created["id"],
        "rule_code": "LXE-0001",
        "status": "draft",
        "updated_at": created["updated_at"],
        "name": "入院记录完整性",
        "category": "病历书写与管理基本规范",
        "rule_type": "完整性",
        "document_type": "入院记录",
    }
    stored = service.get_basic_info_draft(draft_id=created["id"], created_by="manager-1")
    assert stored == created
    listed = service.list_drafts(
        created_by="manager-1", status="draft", query=None, page=1, page_size=20,
    )
    assert listed.total == 1
    assert listed.items[0]["category"] == "病历书写与管理基本规范"
    assert listed.items[0]["rule_type"] == "完整性"
    with pytest.raises(DraftBasicInfoNotFound):
        service.get_basic_info_draft(draft_id=created["id"], created_by="manager-2")


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": " "},
        {"name": "x" * 101},
        {"category": " "},
        {"rule_type": "x" * 101},
        {"document_type": "客户自造未知文书"},
    ],
)
def test_create_rejects_invalid_basic_info_without_writing(workspace, overrides):
    service, sessions, drafts = workspace
    with pytest.raises(DraftBasicInfoInvalid):
        service.create_basic_info_draft(
            created_by="manager-1", payload=_basic_payload(**overrides),
        )
    with sessions() as session:
        assert session.execute(sa.select(sa.func.count()).select_from(drafts)).scalar_one() == 0


def test_patch_uses_cas_rederives_document_domain_and_clears_test_proof(workspace):
    service, sessions, drafts = workspace
    created = service.create_basic_info_draft(
        created_by="manager-1",
        payload=_basic_payload(document_type="手术记录"),
    )
    with sessions.begin() as session:
        session.execute(
            sa.update(drafts)
            .where(drafts.c.id == created["id"])
            .values(
                last_test_summary='{"success_count": 1}',
                check_logic=(
                    '{"basic_info":{"version":1,"category":"病历书写与管理基本规范",'
                    '"rule_type":"完整性"},"execution_domain":"surgery",'
                    '"unrelated":{"keep":true}}'
                ),
            )
        )

    updated = service.update_basic_info_draft(
        draft_id=created["id"],
        created_by="manager-1",
        payload=_basic_payload(
            name="检验结果完整性",
            category="诊疗规范",
            rule_type="规范性",
            document_type="检验报告",
        ),
        expected_updated_at=created["updated_at"].replace(tzinfo=timezone.utc),
    )
    assert updated["updated_at"] > created["updated_at"]
    assert updated["document_type"] == "检验报告"
    with sessions() as session:
        row = session.execute(sa.select(drafts).where(drafts.c.id == created["id"])).mappings().one()
        logic = service_module._safe_json_loads(row["check_logic"], {})
        assert logic["execution_domain"] == "course"
        assert logic["unrelated"] == {"keep": True}
        assert row["last_test_summary"] is None
    with pytest.raises(ValueError, match="至少完成一次成功测试"):
        service.publish_draft(draft_id=created["id"], created_by="manager-1")
    with pytest.raises(DraftBasicInfoConflict):
        service.update_basic_info_draft(
            draft_id=created["id"], created_by="manager-1",
            payload=_basic_payload(), expected_updated_at=created["updated_at"],
        )


def test_basic_info_endpoints_reject_legacy_and_published_drafts(workspace):
    service, sessions, drafts = workspace
    legacy = service.create_draft(
        created_by="manager-1",
        payload={"name": "旧草稿", "description": "旧链", "document_type": "入院记录"},
    )
    with pytest.raises(DraftBasicInfoNotFound):
        service.get_basic_info_draft(draft_id=legacy["id"], created_by="manager-1")

    created = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    with sessions.begin() as session:
        session.execute(
            sa.update(drafts).where(drafts.c.id == created["id"]).values(status="published")
        )
    with pytest.raises(DraftBasicInfoConflict):
        service.get_basic_info_draft(draft_id=created["id"], created_by="manager-1")


@pytest.mark.parametrize("bad_document_type", ["", "客户自造未知文书"])
def test_strict_get_rejects_corrupt_raw_document_without_legacy_default(
    workspace, bad_document_type,
):
    service, sessions, drafts = workspace
    created = service.create_basic_info_draft(created_by="manager-1", payload=_basic_payload())
    with sessions.begin() as session:
        session.execute(
            sa.update(drafts)
            .where(drafts.c.id == created["id"])
            .values(document_type=bad_document_type)
        )
    with pytest.raises(DraftBasicInfoInvalid, match="document_type"):
        service.get_basic_info_draft(draft_id=created["id"], created_by="manager-1")


@pytest.mark.asyncio
async def test_create_readback_invalid_after_commit_returns_unknown_without_success_audit(
    workspace, monkeypatch,
):
    service, _sessions, _drafts = workspace
    monkeypatch.setattr(service, "create_draft", lambda **_kwargs: {"id": "committed-draft"})
    monkeypatch.setattr(
        service,
        "get_basic_info_draft",
        lambda **_kwargs: (_ for _ in ()).throw(
            DraftBasicInfoInvalid("数据库回读的文书类型无效")
        ),
    )

    audits = []
    monkeypatch.setattr(
        custom_qc,
        "audit_event",
        lambda _request, **kwargs: audits.append(kwargs),
    )
    payload = custom_qc.WorkspaceDraftBasicInfoCreateRequest.model_validate(_basic_payload())
    with pytest.raises(HTTPException) as caught:
        await custom_qc.create_workspace_draft_basic_info(
            request=_request(), payload=payload,
            current_user={"id": "manager-1", "roles": ["qc_manager"]},
            workspace=service,
        )
    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "draft_basic_info_result_unknown"
    assert "不要盲目重试" in caught.value.detail["message"]
    assert [item["outcome"] for item in audits] == ["unknown"]


@pytest.mark.asyncio
async def test_patch_forwards_exact_owner_and_expected_version(monkeypatch):
    calls = []

    class Workspace:
        def update_basic_info_draft(self, **kwargs):
            calls.append(kwargs)
            return {
                "id": "draft-1", "rule_code": "LXE-0001", "status": "draft",
                "updated_at": datetime(2026, 9, 28, 8), **kwargs["payload"],
            }

    monkeypatch.setattr(custom_qc, "audit_event", lambda *_args, **_kwargs: None)
    expected = datetime(2026, 9, 28, 7, tzinfo=timezone.utc)
    payload = custom_qc.WorkspaceDraftBasicInfoUpdateRequest.model_validate({
        **_basic_payload(), "expected_updated_at": expected.isoformat(),
    })
    response = await custom_qc.update_workspace_draft_basic_info(
        request=_request("PATCH"), draft_id="draft-1", payload=payload,
        current_user={"id": "manager-1", "roles": ["qc_manager"]},
        workspace=Workspace(),  # type: ignore[arg-type]
    )
    assert response["data"]["updated_at"].endswith("+00:00")
    assert calls == [{
        "draft_id": "draft-1",
        "created_by": "manager-1",
        "payload": {
            "name": "入院记录完整性",
            "category": "病历书写与管理基本规范",
            "rule_type": "完整性",
            "document_type": "入院记录",
        },
        "expected_updated_at": expected,
    }]


def test_actual_router_rejects_wrong_role_and_forbidden_create_fields():
    app = FastAPI()
    app.include_router(custom_qc.router)

    app.dependency_overrides[custom_qc.get_current_user] = lambda: {
        "id": "doctor-1", "roles": ["doctor"],
    }
    with TestClient(app) as client:
        assert client.get("/api/v1/custom-qc/workspace/draft-basic-info/options").status_code == 403

    class Workspace:
        def create_basic_info_draft(self, **_kwargs):
            pytest.fail("非法字段必须在调用服务前由请求模型拒绝")

    app.dependency_overrides[custom_qc.get_current_user] = lambda: {
        "id": "manager-1", "roles": ["qc_manager"],
    }
    app.dependency_overrides[custom_qc.get_workspace_service] = lambda: Workspace()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/custom-qc/workspace/draft-basic-info",
            json={
                **_basic_payload(),
                "status": "published",
                "published_rule_id": "forged-rule",
            },
        )
    assert response.status_code == 422


def test_actual_condition_options_contract_and_patch_forbid_extra_fields():
    app = FastAPI()
    app.include_router(custom_qc.router)
    app.dependency_overrides[custom_qc.get_current_user] = lambda: {
        "id": "manager-1", "roles": ["qc_manager"],
    }

    class Workspace:
        def update_visual_condition_draft(self, **_kwargs):
            pytest.fail("请求模型必须先拒绝额外字段")

    app.dependency_overrides[custom_qc.get_workspace_service] = lambda: Workspace()
    with TestClient(app) as client:
        options = client.get("/api/v1/custom-qc/workspace/draft-condition/options")
        assert options.status_code == 200
        data = options.json()["data"]
        assert all(set(item) == {"value", "label"} for item in data["timeliness"]["start_fields"])
        assert data["timeliness"]["allowed_pairs"]
        assert all(
            set(item) == {"start_fact", "end_fact"}
            for item in data["timeliness"]["allowed_pairs"]
        )
        response = client.patch(
            "/api/v1/custom-qc/workspace/draft-condition/draft-1",
            json={
                "expected_updated_at": "2026-09-28T08:00:00Z",
                "visual_condition": _visual_condition(),
                "status": "published",
            },
        )
    assert response.status_code == 422


def test_visual_evidence_hydration_replaces_client_payload_and_uses_exact_identity(
    workspace, monkeypatch,
):
    service, _sessions, _drafts = workspace
    monkeypatch.setattr(
        service,
        "hydrate_records_with_medical_text",
        lambda _records: [{
            "institute_id": "H2",
            "patient_id": "P2",
            "visit_id": "SAME-VISIT",
            "medical_text": "",
            "evidence_payload": {"forged": True},
            "visual_evidence_error": "forged-error",
        }],
    )
    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        return {"programmatic_timeline": {"documents": {}, "source_readiness": {}}}

    from app.services import sample_programmatic_evidence

    monkeypatch.setattr(sample_programmatic_evidence, "build_programmatic_evidence_payload", build)
    hydrated = service.hydrate_records_with_visual_evidence([{
        "institute_id": "H2", "patient_id": "P2", "visit_id": "SAME-VISIT",
    }])
    assert calls == [{
        "bundle": {"institute_id": "H2", "patient_id": "P2", "visit_id": "SAME-VISIT"},
        "medical_text": "",
        "strict_identity": True,
    }]
    assert hydrated[0]["evidence_payload"] == {
        "programmatic_timeline": {"documents": {}, "source_readiness": {}}
    }
    assert "visual_evidence_error" not in hydrated[0]


def test_visual_evidence_hydration_marks_missing_identity_or_source_failure(
    workspace, monkeypatch,
):
    service, _sessions, _drafts = workspace
    from app.services import sample_programmatic_evidence

    monkeypatch.setattr(
        sample_programmatic_evidence,
        "build_programmatic_evidence_payload",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("source failed")),
    )
    monkeypatch.setattr(
        service,
        "hydrate_records_with_medical_text",
        lambda records: [dict(item) for item in records],
    )
    hydrated = service.hydrate_records_with_visual_evidence([
        {"institute_id": "", "patient_id": "P1", "visit_id": "V1"},
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
    ])
    assert [item["visual_evidence_error"] for item in hydrated] == [
        "record_identity_unavailable",
        "visual_evidence_source_unavailable",
    ]
    assert all("evidence_payload" not in item for item in hydrated)
