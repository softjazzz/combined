from __future__ import annotations

import io
import json
from copy import deepcopy
from datetime import datetime

import pytest
import sqlalchemy as sa
from openpyxl import load_workbook

from app.database.models.cdm import AdmissionRecord, InpatRegistration, PatientInformation
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services.custom_qc_sample_pool_service import (
    CUSTOMER_TEST_POOL_ID,
    CustomerTestRecordConflictError,
    CustomerTestRecordNotFoundError,
    CustomQCSamplePoolService,
)
from app.services.test_record_import_service import parse_test_record_import
from app.services import test_record_transfer_service as service


def _payload(*, content: str = "=需要按原文保留\n+第二行") -> dict:
    return {
        "source_item_id": "ct-source",
        "source_updated_at": datetime(2026, 9, 28, 8),
        "case_title": "测试病例",
        "basic_info": {
            "patient_name": "测试患者",
            "sex": "女",
            "age": 45,
            "mr_no": "SYN-1",
            "department": "心内科",
            "admission_time": datetime(2026, 9, 1, 8),
            "discharge_time": None,
            "main_diagnosis": "测试诊断",
            "other_diagnoses": ["诊断乙"],
            "doctor_name": "测试医师",
        },
        "documents": [{
            "document_type": "admission_record",
            "title": "=入院记录",
            "record_time": datetime(2026, 9, 1, 9),
            "submit_time": datetime(2026, 9, 1, 9, 30),
            "content": content,
            "doctor_name": "测试医师",
            "doctor_code": "SYN-DOC",
            "enabled": True,
        }],
        "selected_rule_ids": ["LX0609-001"],
        "manual_issue_text": "合成说明",
    }


class _Stub:
    def __init__(self, payload=None):
        self.payload = deepcopy(payload or _payload())
        self.loads = []
        self.created = []

    def load_customer_test_record_transfer_payloads(self, **kwargs):
        self.loads.append(kwargs)
        return [deepcopy(self.payload)]

    def create_customer_test_record(self, **kwargs):
        self.created.append(kwargs)
        return {
            "item": {"id": "ct-copy", "latest_job_id": ""},
            "patient_id": "CUSTOMER_PATIENT_NEW",
            "visit_id": "CUSTOMER_TEST_NEW",
            "bundle_status": "ready",
        }


def test_export_round_trips_through_existing_parser_and_preserves_formula_like_text():
    stub = _Stub()
    content, count = service.export_customer_test_records(
        item_ids=["ct-source"],
        allowed_rule_ids={"LX0609-001"},
        sample_service_factory=lambda: stub,
    )
    parsed = parse_test_record_import(
        content, allowed_rule_ids={"LX0609-001"}, file_sha256="a" * 64,
    )
    assert count == 1
    assert len(parsed) == 1
    assert parsed[0].payload["documents"][0]["title"] == "=入院记录"
    assert parsed[0].payload["documents"][0]["content"] == "=需要按原文保留\n+第二行"
    workbook = load_workbook(io.BytesIO(content), data_only=False)
    assert workbook["文书"]["C2"].data_type == "s"
    assert workbook["文书"]["F2"].data_type == "s"


def test_export_rejects_over_limit_and_excel_cell_overflow_without_truncating():
    stub = _Stub(_payload(content="正文" * 20_000))
    with pytest.raises(ValueError, match="Excel 单元格上限"):
        service.export_customer_test_records(
            item_ids=["ct-source"], allowed_rule_ids={"LX0609-001"},
            sample_service_factory=lambda: stub,
        )
    with pytest.raises(ValueError, match="最多导出 20"):
        service.export_customer_test_records(
            item_ids=[f"ct-{index}" for index in range(21)],
            allowed_rule_ids={"LX0609-001"}, sample_service_factory=lambda: stub,
        )


def test_copy_reuses_create_chain_without_superseding_source_or_copying_results():
    stub = _Stub()
    result = service.copy_customer_test_record(
        item_id="ct-source",
        expected_updated_at="2026-09-28T08:00:00",
        case_title="复制病历",
        created_by="manager-1",
        sample_service_factory=lambda: stub,
    )
    assert stub.loads == [{
        "item_ids": ["ct-source"], "expected_updated_at": "2026-09-28T08:00:00",
    }]
    create_call = stub.created[0]
    assert create_call["created_by"] == "manager-1"
    payload = create_call["payload"]
    assert payload["case_title"] == "复制病历"
    assert payload["documents"] == _payload()["documents"]
    assert payload["selected_rule_ids"] == ["LX0609-001"]
    assert payload["golden_answers"] == []
    assert payload["source"] == {
        "type": "customer_test_record_copy",
        "source_pool_id": "customer-created-test-records-v1",
        "source_record_id": "ct-source",
        "source_item_ids": ["ct-source"],
        "created_from": "test_record_management_copy",
    }
    assert "supersedes_item_id" not in payload["source"]
    assert "latest_job_id" not in payload
    assert result["source_item_id"] == "ct-source"
    assert result["source_updated_at"] == "2026-09-28T08:00:00"
    assert result["item"]["id"] == "ct-copy"


def test_copy_propagates_stale_or_inactive_source_without_calling_create():
    stub = _Stub()

    def fail(**_kwargs):
        raise CustomerTestRecordConflictError("已修改", code="stale")

    stub.load_customer_test_record_transfer_payloads = fail
    with pytest.raises(CustomerTestRecordConflictError) as caught:
        service.copy_customer_test_record(
            item_id="ct-source", expected_updated_at="old", case_title=None,
            created_by="manager-1", sample_service_factory=lambda: stub,
        )
    assert caught.value.code == "stale"
    assert stub.created == []


def test_copy_wraps_any_create_chain_exception_as_unknown_result():
    stub = _Stub()

    def fail(**_kwargs):
        raise RuntimeError("synthetic post-commit readback failure")

    stub.create_customer_test_record = fail
    with pytest.raises(service.CustomerTestRecordCopyResultUnknown, match="可能已复制"):
        service.copy_customer_test_record(
            item_id="ct-source", expected_updated_at="2026-09-28T08:00:00",
            case_title=None, created_by="manager-1", sample_service_factory=lambda: stub,
        )


def _build_real_transfer_service(monkeypatch):
    db_engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    item_table = sa.Table(
        "transfer_items",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("pool_id", sa.String),
        sa.Column("department", sa.String),
        sa.Column("patient_name", sa.String),
        sa.Column("mr_no", sa.String),
        sa.Column("manual_issue_text", sa.String),
        sa.Column("doctor_name", sa.String),
        sa.Column("candidate_rule_ids_json", sa.Text),
        sa.Column("include_in_batch_1", sa.Boolean),
        sa.Column("exclude_reason", sa.String),
        sa.Column("matched_institute_id", sa.String),
        sa.Column("matched_patient_id", sa.String),
        sa.Column("matched_visit_id", sa.String),
        sa.Column("raw_payload_json", sa.Text),
        sa.Column("updated_at", sa.DateTime),
    )
    metadata.create_all(db_engine)
    for table in (
        InpatRegistration.__table__, PatientInformation.__table__, AdmissionRecord.__table__,
    ):
        table.create(db_engine)
    session_factory = sa.orm.sessionmaker(bind=db_engine)
    monkeypatch.setattr(sample_pool_module, "_session", session_factory)
    monkeypatch.setattr(sample_pool_module, "engine", db_engine)
    sample_service = object.__new__(CustomQCSamplePoolService)
    sample_service._item_table = item_table
    return sample_service, session_factory, item_table


def _insert_real_transfer_source(session_factory, item_table, **overrides):
    values = {
        "id": "ct-source",
        "pool_id": CUSTOMER_TEST_POOL_ID,
        "department": "心内科",
        "patient_name": "合成患者",
        "mr_no": "SYN-001",
        "manual_issue_text": "合成问题",
        "doctor_name": "测试医师",
        "candidate_rule_ids_json": json.dumps(["LX0609-001"]),
        "include_in_batch_1": True,
        "exclude_reason": "",
        "matched_institute_id": "CUSTOMER_TEST",
        "matched_patient_id": "CUSTOMER_PATIENT_1",
        "matched_visit_id": "CUSTOMER_TEST_1",
        "raw_payload_json": json.dumps({"case_title": "合成病历", "document_count": 1}),
        "updated_at": datetime(2026, 9, 28, 8),
    }
    values.update(overrides)
    with session_factory.begin() as session:
        session.execute(item_table.insert().values(**values))


def _insert_real_cdm_source(session_factory):
    with session_factory.begin() as session:
        session.execute(InpatRegistration.__table__.insert(), [
            {
                "institute_id": "CUSTOMER_TEST", "patient_id": "CUSTOMER_PATIENT_1",
                "visit_id": "CUSTOMER_TEST_1", "sex": "女", "age_year": "45",
                "admission_datetime": datetime(2026, 9, 1, 8),
            },
            {
                "institute_id": "OTHER_HOSPITAL", "patient_id": "CUSTOMER_PATIENT_1",
                "visit_id": "CUSTOMER_TEST_1", "sex": "男", "age_year": "99",
                "admission_datetime": datetime(2020, 1, 1, 8),
            },
        ])
        session.execute(AdmissionRecord.__table__.insert(), [
            {
                "institute_id": "CUSTOMER_TEST", "patient_id": "CUSTOMER_PATIENT_1",
                "visit_id": "CUSTOMER_TEST_1", "document_id": "DOC-1",
                "document_title": "入院记录", "record_datetime": datetime(2026, 9, 1, 9),
                "record_content": "本院合成正文", "submitter": "测试医师",
            },
            {
                "institute_id": "OTHER_HOSPITAL", "patient_id": "CUSTOMER_PATIENT_1",
                "visit_id": "CUSTOMER_TEST_1", "document_id": "OTHER-DOC",
                "document_title": "外院记录", "record_datetime": datetime(2020, 1, 1, 9),
                "record_content": "外院同号正文", "submitter": None,
            },
        ])


def test_real_loader_reads_exact_triple_and_complete_document_count(monkeypatch):
    sample_service, session_factory, item_table = _build_real_transfer_service(monkeypatch)
    _insert_real_transfer_source(session_factory, item_table)
    _insert_real_cdm_source(session_factory)

    result = sample_service.load_customer_test_record_transfer_payloads(
        item_ids=["ct-source"], expected_updated_at="2026-09-28T08:00:00",
    )[0]

    assert result["basic_info"]["sex"] == "女"
    assert result["basic_info"]["age"] == 45
    assert [item["content"] for item in result["documents"]] == ["本院合成正文"]
    assert result["selected_rule_ids"] == ["LX0609-001"]


def test_real_loader_rejects_foreign_pool_removed_and_stale_sources(monkeypatch):
    sample_service, session_factory, item_table = _build_real_transfer_service(monkeypatch)
    _insert_real_transfer_source(session_factory, item_table, id="foreign", pool_id="another-pool")
    _insert_real_transfer_source(
        session_factory, item_table, id="removed", include_in_batch_1=False,
        exclude_reason="test_record_removed",
    )
    _insert_real_transfer_source(session_factory, item_table, id="stale")

    with pytest.raises(CustomerTestRecordNotFoundError):
        sample_service.load_customer_test_record_transfer_payloads(item_ids=["foreign"])
    with pytest.raises(CustomerTestRecordConflictError) as removed:
        sample_service.load_customer_test_record_transfer_payloads(item_ids=["removed"])
    assert removed.value.code == "inactive"
    with pytest.raises(CustomerTestRecordConflictError) as stale:
        sample_service.load_customer_test_record_transfer_payloads(
            item_ids=["stale"], expected_updated_at="2026-09-28T09:00:00",
        )
    assert stale.value.code == "stale"


def test_real_loader_rejects_missing_basics_and_document_count_mismatch(monkeypatch):
    sample_service, session_factory, item_table = _build_real_transfer_service(monkeypatch)
    _insert_real_transfer_source(session_factory, item_table, patient_name="")
    _insert_real_cdm_source(session_factory)

    with pytest.raises(CustomerTestRecordConflictError) as invalid:
        sample_service.load_customer_test_record_transfer_payloads(item_ids=["ct-source"])
    assert invalid.value.code == "invalid_source"

    with session_factory.begin() as session:
        session.execute(
            item_table.update().where(item_table.c.id == "ct-source").values(
                patient_name="合成患者",
                raw_payload_json=json.dumps({"case_title": "合成病历", "document_count": 2}),
            )
        )
    with pytest.raises(CustomerTestRecordConflictError) as documents:
        sample_service.load_customer_test_record_transfer_payloads(item_ids=["ct-source"])
    assert documents.value.code == "documents_unavailable"
