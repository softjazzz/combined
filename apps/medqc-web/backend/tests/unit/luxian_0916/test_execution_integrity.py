"""0916 任务交付完整性：规则结果与执行失败必须精确覆盖计划。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace_module
from app.services.luxian_0916.execution_integrity import (
    validate_luxian_0916_task_delivery,
)
from app.services.luxian_0916.rule_catalog import LUXIAN_0916_RULE_CATALOG


_RULE_IDS = tuple(rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)
_IDENTITY = {
    "institute_id": "I-1",
    "patient_id": "P-1",
    "visit_id": "V-1",
}


def _item(rule_id: str) -> dict[str, Any]:
    return {
        **_IDENTITY,
        "record_id": "V-1",
        "rule_id": rule_id,
        "rule_code": rule_id,
        "customer_rule_id": rule_id,
        "qc_point_id": rule_id,
        "status": "compliant",
        "reason_code": "document_complete",
        "findings": "记录完整。",
        "evidence": [],
        "suggestion": "",
        "document_anchors": [],
        "diagnostics": {},
        "decision_facts": {},
    }


def _failure(rule_id: str) -> dict[str, Any]:
    return {
        **_IDENTITY,
        "record_id": "V-1",
        "rule_id": rule_id,
        "error_phase": "rule_execution",
        "error_type": "TimeoutError",
    }


def _summary(*, completed: int, failed: int) -> dict[str, Any]:
    return {
        "rule_set_key": "luxian_0916_qc_v1",
        "rule_count": len(_RULE_IDS),
        "total_records": 1,
        "success_count": 0 if failed else 1,
        "failed_count": 1 if failed else 0,
        "failed_record_count": 1 if failed else 0,
        "completed_rule_count": completed,
        "failed_rule_count": failed,
        "execution_status": (
            "failed"
            if failed and not completed
            else "partial_failed"
            if failed
            else "completed"
        ),
    }


def test_full_32_rule_delivery_is_complete() -> None:
    validate_luxian_0916_task_delivery(
        summary=_summary(completed=32, failed=0),
        items=[_item(rule_id) for rule_id in _RULE_IDS],
        failures=[],
        expected_rule_ids=_RULE_IDS,
        expected_record_refs=[_IDENTITY],
    )


@pytest.mark.parametrize("all_failed", [False, True])
def test_rule_failures_are_preserved_without_fabricating_clinical_results(
    all_failed: bool,
) -> None:
    failed_rule_ids = _RULE_IDS if all_failed else (_RULE_IDS[-1],)
    completed_rule_ids = () if all_failed else _RULE_IDS[:-1]

    validate_luxian_0916_task_delivery(
        summary=_summary(
            completed=len(completed_rule_ids), failed=len(failed_rule_ids)
        ),
        items=[_item(rule_id) for rule_id in completed_rule_ids],
        failures=[_failure(rule_id) for rule_id in failed_rule_ids],
        expected_rule_ids=_RULE_IDS,
        expected_record_refs=[_IDENTITY],
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_result", "重复"),
        ("unknown_rule", "计划外"),
        ("missing_rule", "缺失"),
        ("result_failure_overlap", "同时"),
    ],
)
def test_inconsistent_delivery_is_rejected(mutation: str, message: str) -> None:
    items = [_item(rule_id) for rule_id in _RULE_IDS]
    failures: list[dict[str, Any]] = []
    summary = _summary(completed=32, failed=0)
    if mutation == "duplicate_result":
        items.append(_item(_RULE_IDS[0]))
        summary["completed_rule_count"] += 1
    elif mutation == "unknown_rule":
        items[-1] = {**items[-1], "rule_id": "LX0916-999"}
    elif mutation == "missing_rule":
        items.pop()
        summary["completed_rule_count"] -= 1
    else:
        failures.append(_failure(_RULE_IDS[-1]))
        summary = _summary(completed=32, failed=1)

    with pytest.raises(ValueError, match=message):
        validate_luxian_0916_task_delivery(
            summary=summary,
            items=items,
            failures=failures,
            expected_rule_ids=_RULE_IDS,
            expected_record_refs=[_IDENTITY],
        )


def test_native_result_rejects_string_instead_of_evidence_list() -> None:
    items = [_item(rule_id) for rule_id in _RULE_IDS]
    items[0]["evidence"] = "不能把字符串拆成字符证据"

    with pytest.raises(ValueError, match="原生交付合同"):
        validate_luxian_0916_task_delivery(
            summary=_summary(completed=32, failed=0),
            items=items,
            failures=[],
            expected_rule_ids=_RULE_IDS,
            expected_record_refs=[_IDENTITY],
        )


@pytest.fixture
def persistence_storage(monkeypatch: pytest.MonkeyPatch):
    service = object.__new__(workspace_module.CustomQCWorkspaceService)
    metadata = sa.MetaData()
    table = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("summary_json", sa.Text),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("total_records", sa.Integer, nullable=False, default=0),
        sa.Column("success_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("issue_records", sa.Integer, nullable=False, default=0),
        sa.Column("compliant_records", sa.Integer, nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("total_processing_time", sa.Float, nullable=False, default=0.0),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    service._batch_job_table = table
    monkeypatch.setattr(workspace_module, "_session", factory)
    with engine.begin() as connection:
        connection.execute(
            table.insert().values(
                id="job-0916",
                status="running",
                total_records=1,
                filters_json=json.dumps(
                    {
                        "rule_set_key": "luxian_0916_qc_v1",
                        "rule_ids": list(_RULE_IDS),
                        "record_refs": [_IDENTITY],
                    }
                ),
                updated_at=datetime(2026, 9, 21),
            )
        )
    monkeypatch.setattr(service, "refresh_parent_batch_job", lambda **_kwargs: None)
    yield service, engine, table
    engine.dispose()


@pytest.mark.parametrize("all_failed", [False, True])
def test_complete_batch_job_accepts_native_0916_partial_and_failed_delivery(
    persistence_storage: tuple[Any, Any, Any],
    all_failed: bool,
) -> None:
    service, engine, table = persistence_storage
    failed_rule_ids = _RULE_IDS if all_failed else (_RULE_IDS[-1],)
    completed_rule_ids = () if all_failed else _RULE_IDS[:-1]
    summary = _summary(
        completed=len(completed_rule_ids), failed=len(failed_rule_ids)
    )

    service.complete_batch_job(
        job_id="job-0916",
        summary=summary,
        items=[_item(rule_id) for rule_id in completed_rule_ids],
        failed_records=[_failure(rule_id) for rule_id in failed_rule_ids],
        persist_record_envelopes=False,
    )

    with engine.connect() as connection:
        row = connection.execute(sa.select(table)).mappings().one()
    assert row["status"] == "failed"
    assert json.loads(row["summary_json"])["execution_status"] == summary[
        "execution_status"
    ]
    assert len(json.loads(row["items_json"])) == len(completed_rule_ids)
    assert len(json.loads(row["failed_records_json"])) == len(failed_rule_ids)


def test_complete_batch_job_rejects_incomplete_0916_delivery(
    persistence_storage: tuple[Any, Any, Any],
) -> None:
    service, _engine, _table = persistence_storage
    items = [_item(rule_id) for rule_id in _RULE_IDS[:-1]]

    with pytest.raises(ValueError, match="缺失"):
        service.complete_batch_job(
            job_id="job-0916",
            summary=_summary(completed=31, failed=0),
            items=items,
            failed_records=[],
            persist_record_envelopes=False,
        )
