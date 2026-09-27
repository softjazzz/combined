"""V3.6 P1-E3 测试病历管理：列表、关联质控点、软移除、编辑替换（SQLite 隔离，不连业务库）。"""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import HTTPException

from app.database.models.cdm import InpatRegistration, PatientInformation
from app.routers import qc_sample_pools
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services.custom_qc_sample_pool_service import (
    CUSTOMER_TEST_POOL_ID,
    CustomerTestRecordConflictError,
    CustomerTestRecordNotFoundError,
    CustomQCSamplePoolService,
)

_T0 = datetime(2026, 9, 27, 8, 0, 0, 123456)
_COUNTER_COLUMNS = (
    "total_items", "llm_intrinsic_items", "programmatic_items", "unsupported_items",
    "matched_items", "ambiguous_items", "unmatched_items", "ready_items",
)


def _build_service(monkeypatch):
    db_engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    pool_table = sa.Table(
        "pools",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String),
        sa.Column("source_file", sa.String),
        sa.Column("source_sheet", sa.String),
        sa.Column("scene", sa.String),
        sa.Column("description", sa.String),
        sa.Column("created_by", sa.String),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("latest_job_id", sa.String),
        sa.Column("latest_job_status", sa.String),
        *[sa.Column(name, sa.Integer, default=0) for name in _COUNTER_COLUMNS],
    )
    item_table = sa.Table(
        "items",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("pool_id", sa.String),
        sa.Column("row_no", sa.Integer),
        sa.Column("department", sa.String),
        sa.Column("patient_name", sa.String),
        sa.Column("mr_no", sa.String),
        sa.Column("manual_issue_text", sa.String),
        sa.Column("normalized_issue_text", sa.String),
        sa.Column("doctor_name", sa.String),
        sa.Column("qc_date", sa.Date),
        sa.Column("qc_user", sa.String),
        sa.Column("coverage_type", sa.String),
        sa.Column("issue_category", sa.String),
        sa.Column("expected_scene", sa.String),
        sa.Column("candidate_rule_ids_json", sa.Text),
        sa.Column("include_in_batch_1", sa.Boolean),
        sa.Column("exclude_reason", sa.String),
        sa.Column("matched_institute_id", sa.String),
        sa.Column("matched_patient_id", sa.String),
        sa.Column("matched_visit_id", sa.String),
        sa.Column("match_status", sa.String),
        sa.Column("sync_status", sa.String),
        sa.Column("bundle_status", sa.String),
        sa.Column("latest_job_id", sa.String),
        sa.Column("latest_match_status", sa.String),
        sa.Column("raw_payload_json", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    metadata.create_all(db_engine)
    InpatRegistration.__table__.create(db_engine)
    PatientInformation.__table__.create(db_engine)
    session_factory = sa.orm.sessionmaker(bind=db_engine)
    monkeypatch.setattr(sample_pool_module, "_session", session_factory)
    service = object.__new__(CustomQCSamplePoolService)
    service._pool_table = pool_table
    service._item_table = item_table
    return service, session_factory, item_table


def _insert_item(session_factory, item_table, **overrides):
    values = {
        "id": "ct-old",
        "pool_id": CUSTOMER_TEST_POOL_ID,
        "row_no": 1,
        "department": "心内科",
        "patient_name": "测试患者",
        "mr_no": "MR-1",
        "manual_issue_text": "说明",
        "normalized_issue_text": "说明",
        "coverage_type": "llm_intrinsic",
        "issue_category": "客户自建测试病历",
        "expected_scene": "running",
        "candidate_rule_ids_json": json.dumps(["LX0609-001"]),
        "include_in_batch_1": True,
        "exclude_reason": "",
        "matched_institute_id": "CUSTOMER_TEST",
        "matched_patient_id": "CUSTOMER_PATIENT_1",
        "matched_visit_id": "CUSTOMER_TEST_1",
        "match_status": "matched",
        "sync_status": "synced",
        "bundle_status": "ready",
        "latest_job_id": "job-1",
        "raw_payload_json": json.dumps(
            {"case_title": "旧病历", "document_count": 3, "selected_rule_ids": ["LX0609-001"]},
            ensure_ascii=False,
        ),
        "created_at": _T0,
        "updated_at": _T0,
    }
    values.update(overrides)
    session = session_factory()
    session.execute(item_table.insert().values(**values))
    session.commit()
    session.close()


def _read_item(session_factory, item_table, item_id):
    session = session_factory()
    try:
        return dict(session.execute(sa.select(item_table).where(item_table.c.id == item_id)).mappings().first())
    finally:
        session.close()


def test_list_hides_removed_and_superseded_unless_requested(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table, id="ct-active")
    _insert_item(
        session_factory, item_table, id="ct-removed",
        include_in_batch_1=False, exclude_reason="test_record_removed",
    )
    _insert_item(
        session_factory, item_table, id="ct-replaced",
        include_in_batch_1=False, exclude_reason="superseded_by:ct-active",
    )
    _insert_item(session_factory, item_table, id="other-pool", pool_id="pool-x")

    default_result = service.list_customer_test_records()
    assert default_result.total == 1
    active = default_result.items[0]
    assert active["id"] == "ct-active"
    assert (active["institute_id"], active["patient_id"], active["visit_id"]) == (
        "CUSTOMER_TEST", "CUSTOMER_PATIENT_1", "CUSTOMER_TEST_1",
    )
    # LX0609-001 不符合旧样本行规则号正则，列表必须直接读取已存关联而非回退推断。
    assert active["rule_ids"] == ["LX0609-001"]
    assert active["rule_count"] == 1
    assert active["document_count"] == 3
    assert active["origin"] == "created"
    assert active["state"] == "active"

    full = {item["id"]: item for item in service.list_customer_test_records(include_removed=True).items}
    assert set(full) == {"ct-active", "ct-removed", "ct-replaced"}
    assert full["ct-removed"]["removed"] is True
    assert full["ct-replaced"]["superseded_by"] == "ct-active"
    assert full["ct-replaced"]["state"] == "superseded"


def test_list_reads_demographics_from_cdm_and_keeps_missing_as_none(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table, id="ct-full")
    _insert_item(
        session_factory, item_table, id="ct-sex-only",
        matched_patient_id="CUSTOMER_PATIENT_2", matched_visit_id="CUSTOMER_TEST_2",
    )
    _insert_item(
        session_factory, item_table, id="ct-missing",
        matched_patient_id="CUSTOMER_PATIENT_3", matched_visit_id="CUSTOMER_TEST_3",
    )
    session = session_factory()
    session.execute(InpatRegistration.__table__.insert().values(
        institute_id="CUSTOMER_TEST", patient_id="CUSTOMER_PATIENT_1", visit_id="CUSTOMER_TEST_1",
        sex="女", age_year="67", age="67岁", admission_datetime=datetime(2026, 9, 1, 8, 30),
    ))
    # 登记行缺性别与年龄：性别取患者主索引，年龄不从出生日期推算。
    session.execute(InpatRegistration.__table__.insert().values(
        institute_id="CUSTOMER_TEST", patient_id="CUSTOMER_PATIENT_2", visit_id="CUSTOMER_TEST_2",
        sex=None, age_year=None, age=None, birthday=datetime(1950, 1, 1).date(), admission_datetime=None,
    ))
    session.execute(PatientInformation.__table__.insert().values(
        institute_id="CUSTOMER_TEST", patient_id="CUSTOMER_PATIENT_2", sex="男",
    ))
    session.commit()
    session.close()

    items = {item["id"]: item for item in service.list_customer_test_records().items}

    assert (items["ct-full"]["sex"], items["ct-full"]["age"]) == ("女", 67)
    assert items["ct-full"]["admission_time"] == "2026-09-01T08:30:00"
    assert (items["ct-sex-only"]["sex"], items["ct-sex-only"]["age"]) == ("男", None)
    assert items["ct-sex-only"]["admission_time"] is None
    assert (items["ct-missing"]["sex"], items["ct-missing"]["age"], items["ct-missing"]["admission_time"]) == (
        None, None, None,
    )


def test_update_rules_writes_both_fields_with_cas(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table)

    item = service.update_customer_test_record_rules(
        item_id="ct-old",
        rule_ids=["lx0609-002", "LX0609-001", "LX0609-002"],
        expected_updated_at=_T0.isoformat(),
        allowed_rule_ids={"LX0609-001", "LX0609-002"},
    )

    assert item["rule_ids"] == ["LX0609-002", "LX0609-001"]
    row = _read_item(session_factory, item_table, "ct-old")
    assert json.loads(row["candidate_rule_ids_json"]) == ["LX0609-002", "LX0609-001"]
    assert json.loads(row["raw_payload_json"])["selected_rule_ids"] == ["LX0609-002", "LX0609-001"]
    assert json.loads(row["raw_payload_json"])["case_title"] == "旧病历"
    assert row["updated_at"] != _T0

    with pytest.raises(CustomerTestRecordConflictError) as stale:
        service.update_customer_test_record_rules(
            item_id="ct-old", rule_ids=[], expected_updated_at=_T0.isoformat(),
            allowed_rule_ids={"LX0609-001"},
        )
    assert stale.value.code == "stale"


def test_update_rules_rejects_rule_outside_current_version_before_write(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table)

    with pytest.raises(ValueError, match="LX0609-999"):
        service.update_customer_test_record_rules(
            item_id="ct-old", rule_ids=["LX0609-999"], expected_updated_at=_T0.isoformat(),
            allowed_rule_ids={"LX0609-001"},
        )
    row = _read_item(session_factory, item_table, "ct-old")
    assert row["updated_at"] == _T0


def test_write_operations_refuse_items_outside_fixed_pool(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table, id="foreign", pool_id="pool-x")

    with pytest.raises(CustomerTestRecordNotFoundError):
        service.remove_customer_test_record(item_id="foreign", expected_updated_at=_T0.isoformat())
    with pytest.raises(CustomerTestRecordNotFoundError):
        service.update_customer_test_record_rules(
            item_id="foreign", rule_ids=[], expected_updated_at=_T0.isoformat(), allowed_rule_ids=set(),
        )
    row = _read_item(session_factory, item_table, "foreign")
    assert row["include_in_batch_1"] is True and row["exclude_reason"] == ""


def test_remove_is_soft_and_refuses_second_remove(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table)

    item = service.remove_customer_test_record(item_id="ct-old", expected_updated_at=_T0.isoformat())

    assert item["removed"] is True
    row = _read_item(session_factory, item_table, "ct-old")
    assert row["include_in_batch_1"] is False
    assert row["exclude_reason"] == "test_record_removed"
    with pytest.raises(CustomerTestRecordConflictError) as inactive:
        service.remove_customer_test_record(item_id="ct-old", expected_updated_at=row["updated_at"].isoformat())
    assert inactive.value.code == "inactive"


def _patch_create_side_effects(monkeypatch, service):
    monkeypatch.setattr(CustomQCSamplePoolService, "_customer_test_bundle_write_lock", staticmethod(nullcontext))
    monkeypatch.setattr(CustomQCSamplePoolService, "_reflect_cdm_table", staticmethod(lambda *_a, **_k: None))
    monkeypatch.setattr(sample_pool_module, "pg_insert", sa.dialects.sqlite.insert)
    monkeypatch.setattr(sample_pool_module, "invalidate_bundle_variants", lambda *_a, **_k: None)
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **_kwargs: None)
    monkeypatch.setattr(sample_pool_module, "engine", object())
    monkeypatch.setattr(service, "_publish_customer_test_bundle", lambda *_a, **_k: None)
    monkeypatch.setattr(service, "_wait_running_bundle_ready", lambda **_k: "pending")
    monkeypatch.setattr(service, "_update_pool_counters", lambda *_a, **_k: None)
    monkeypatch.setattr(service, "get_pool", lambda **_k: {"id": CUSTOMER_TEST_POOL_ID})


def _edit_payload(supersedes_updated_at):
    return {
        "case_title": "编辑后病历",
        "basic_info": {"patient_name": "测试患者", "department": "心内科", "admission_time": "2026-09-01T08:00:00"},
        "documents": [{"document_type": "admission_record", "title": "入院记录", "content": "正文", "enabled": True}],
        "selected_rule_ids": ["LX0609-001"],
        "source": {
            "type": "customer_source_editable_copy",
            "source_pool_id": CUSTOMER_TEST_POOL_ID,
            "source_item_ids": ["ct-old"],
            "supersedes_item_id": "ct-old",
            "supersedes_updated_at": supersedes_updated_at,
        },
    }


def test_edit_creates_copy_and_marks_old_item_superseded_in_same_transaction(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table)
    _patch_create_side_effects(monkeypatch, service)

    result = service.create_customer_test_record(payload=_edit_payload(_T0.isoformat()), created_by="tester")

    new_id = result["item"]["id"]
    old_row = _read_item(session_factory, item_table, "ct-old")
    assert old_row["include_in_batch_1"] is False
    assert old_row["exclude_reason"] == f"superseded_by:{new_id}"
    new_payload = json.loads(_read_item(session_factory, item_table, new_id)["raw_payload_json"])
    assert new_payload["source_record"]["supersedes_item_id"] == "ct-old"
    listed = service.list_customer_test_records().items
    assert [item["id"] for item in listed] == [new_id]
    assert listed[0]["origin"] == "derived"
    assert listed[0]["source_item_id"] == "ct-old"


def test_edit_with_stale_updated_at_writes_nothing(monkeypatch):
    service, session_factory, item_table = _build_service(monkeypatch)
    _insert_item(session_factory, item_table)
    _patch_create_side_effects(monkeypatch, service)

    with pytest.raises(CustomerTestRecordConflictError):
        service.create_customer_test_record(
            payload=_edit_payload("2026-09-27T09:00:00"), created_by="tester",
        )

    session = session_factory()
    assert session.execute(sa.select(item_table.c.id)).scalars().all() == ["ct-old"]
    session.close()


def test_edit_without_updated_at_fails_closed(monkeypatch):
    service, _session_factory, _item_table = _build_service(monkeypatch)
    with pytest.raises(ValueError, match="updated_at"):
        service.create_customer_test_record(payload=_edit_payload(None), created_by="tester")


# ---------------------------------------------------------------------------
# 路由：错误映射与规则全集校验
# ---------------------------------------------------------------------------


def _request():
    return SimpleNamespace(state=SimpleNamespace(trace_id="trace-test"))


class _RouterServiceStub:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def update_customer_test_record_rules(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"id": kwargs["item_id"], "rule_ids": list(kwargs["rule_ids"])}

    def remove_customer_test_record(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"id": kwargs["item_id"], "removed": True}


def _patch_rule_set(monkeypatch):
    monkeypatch.setattr(qc_sample_pools, "_current_rule_set_version", lambda _key: "v-current")
    monkeypatch.setattr(
        qc_sample_pools,
        "resolve_rule_set_version",
        lambda _key, version: {
            "version": version,
            "active_rule_ids": ["LX0609-001"],
            "paused_rule_ids": ["LX0609-002"],
            "excluded_rule_ids": ["LX0609-003"],
        },
    )


@pytest.mark.asyncio
async def test_router_update_rules_uses_full_current_version_rule_set(monkeypatch):
    stub = _RouterServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: stub)
    _patch_rule_set(monkeypatch)

    response = await qc_sample_pools.update_test_record_rules(
        request=_request(),
        item_id="ct-old",
        payload=qc_sample_pools.TestRecordRulesUpdateRequest(rule_ids=["LX0609-003"], updated_at="t"),
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert stub.calls[0]["allowed_rule_ids"] == {"LX0609-001", "LX0609-002", "LX0609-003"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status"),
    [
        (CustomerTestRecordNotFoundError("测试病历不存在"), 404),
        (CustomerTestRecordConflictError("已被修改", code="stale"), 409),
        (ValueError("规则不属于当前规则集版本：X"), 422),
    ],
)
async def test_router_update_rules_maps_errors(monkeypatch, error, status):
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: _RouterServiceStub(error))
    _patch_rule_set(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.update_test_record_rules(
            request=_request(),
            item_id="ct-old",
            payload=qc_sample_pools.TestRecordRulesUpdateRequest(rule_ids=[], updated_at="t"),
            current_user={"id": "tester"},
        )
    assert exc_info.value.status_code == status


@pytest.mark.asyncio
async def test_router_update_rules_fails_closed_when_rule_set_unavailable(monkeypatch):
    stub = _RouterServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: stub)

    def _unavailable(_key):
        raise qc_sample_pools.RuleSetVersionUnavailable("down")

    monkeypatch.setattr(qc_sample_pools, "_current_rule_set_version", _unavailable)
    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.update_test_record_rules(
            request=_request(),
            item_id="ct-old",
            payload=qc_sample_pools.TestRecordRulesUpdateRequest(rule_ids=[], updated_at="t"),
            current_user={"id": "tester"},
        )
    assert exc_info.value.status_code == 503
    assert stub.calls == []


@pytest.mark.asyncio
async def test_router_remove_maps_inactive_conflict(monkeypatch):
    error = CustomerTestRecordConflictError("已移除", code="inactive")
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: _RouterServiceStub(error))

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.remove_test_record(
            request=_request(), item_id="ct-old", updated_at="t", current_user={"id": "tester"},
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "已移除"
