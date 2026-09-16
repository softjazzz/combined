from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.luxian_0916 import batch_worker
from app.services.luxian_0916.contracts import Luxian0916RuleResult
from app.services.luxian_0916.orchestrator import Luxian0916Execution, Luxian0916RuleFailure
from app.services.luxian_0916.rule_catalog import LUXIAN_0916_RULE_CATALOG


class _Workspace:
    def __init__(self, *, job: dict[str, Any], records: list[dict[str, Any]]) -> None:
        self.job = job
        self.records = records
        self.progress: list[dict[str, Any]] = []
        self.completed: dict[str, Any] | None = None
        self.failed: list[dict[str, Any]] = []
        self.marked = False

    def get_batch_job_for_processing(self, *, job_id: str) -> dict[str, Any]:
        assert job_id == self.job["id"]
        return self.job

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        assert job_id == self.job["id"]
        self.marked = True
        return True

    def collect_records(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return list(self.records)

    def hydrate_records_with_medical_text(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return list(records)

    def update_batch_job_progress(self, **kwargs: Any) -> None:
        self.progress.append(kwargs)

    def complete_batch_job(self, **kwargs: Any) -> None:
        self.completed = kwargs

    def fail_batch_job(self, **kwargs: Any) -> None:
        self.failed.append(kwargs)


def _job(*, rule_set_key: str = batch_worker.LUXIAN_0916_RULE_SET_KEY) -> dict[str, Any]:
    return {
        "id": "job-0916",
        "scope": "running",
        "filters": {
            "rule_set_key": rule_set_key,
            "record_refs": [
                {"institute_id": "I-1", "patient_id": "P-1", "visit_id": "V-1"}
            ],
            "date_field": "admission",
        },
    }


def _record(*, patient_id: str = "P-1", visit_id: str = "V-1") -> dict[str, Any]:
    return {
        "institute_id": "I-1",
        "patient_id": patient_id,
        "visit_id": visit_id,
        "record_id": visit_id,
        "patient_name": "测试患者",
        "scope": "running",
        "medical_text": "正文",
    }


def _result(rule_id: str, *, status: str = "compliant") -> Luxian0916RuleResult:
    return Luxian0916RuleResult(
        rule_id=rule_id,
        status=status,
        reason_code="document_complete",
        findings="判定原文",
        evidence=("证据原文",),
        suggestion="整改建议",
        document_anchors=({"document_type": "admission_record", "document_id": "A-1"},),
        diagnostics={"origin": "executor"},
    )


def _patch_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0916_bundle",
        lambda **_kwargs: {"structured_context": {}},
    )
    monkeypatch.setattr(
        batch_worker,
        "build_programmatic_evidence_payload",
        lambda **_kwargs: {"programmatic_timeline": {"documents": {}}},
    )


async def _semantic_generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "semantic_facts": {},
                            "event_facts": {},
                            "document_facts": {},
                            "discharge_facts": {},
                        }
                    )
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_batch_worker_preserves_rule_contract_and_finishes_all_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record(patient_id="P-2", visit_id="V-2"), _record()])
    _patch_loaders(monkeypatch)

    def execute(_context: dict[str, Any], rule_ids: tuple[str, ...]) -> Luxian0916Execution:
        assert rule_ids == tuple(rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)
        return Luxian0916Execution(
            results=tuple(
                _result(rule.rule_id, status="non_compliant" if rule.rule_id == "LX0916-001" else "compliant")
                for rule in LUXIAN_0916_RULE_CATALOG
            )
        )

    monkeypatch.setattr(batch_worker, "execute_luxian_0916", execute)

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916",
        workspace=workspace,
        max_record_concurrency=2,
        semantic_generate=_semantic_generate,
    )

    assert workspace.failed == []
    assert workspace.completed is not None
    assert workspace.completed["persist_record_envelopes"] is False
    summary = workspace.completed["summary"]
    assert summary["status_counts"] == {"non_compliant": 2, "compliant": 62}
    assert summary["display_status_counts"] == summary["status_counts"]
    assert summary["success_count"] == 2
    items = workspace.completed["items"]
    assert len(items) == 64
    first = items[0]
    assert first["rule_id"] == "LX0916-001"
    assert first["status"] == "non_compliant"
    assert first["reason_code"] == "document_complete"
    assert first["findings"] == "判定原文"
    assert first["evidence"] == ["证据原文"]
    assert first["suggestion"] == "整改建议"
    assert first["document_anchors"] == [{"document_type": "admission_record", "document_id": "A-1"}]
    assert first["diagnostics"] == {"origin": "executor"}
    assert [item["visit_id"] for item in items[:32]] == ["V-1"] * 32


@pytest.mark.asyncio
async def test_batch_worker_isolates_one_record_load_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record(visit_id="BROKEN"), _record(visit_id="OK")])

    def load(**kwargs: Any) -> dict[str, Any]:
        if kwargs["visit_id"] == "BROKEN":
            raise LookupError("bundle unavailable")
        return {"structured_context": {}}

    monkeypatch.setattr(batch_worker, "load_luxian_0916_bundle", load)
    monkeypatch.setattr(
        batch_worker,
        "build_programmatic_evidence_payload",
        lambda **_kwargs: {"programmatic_timeline": {"documents": {}}},
    )
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: Luxian0916Execution(results=(_result("LX0916-001"),)),
    )

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.failed == []
    assert workspace.completed is not None
    assert workspace.completed["persist_record_envelopes"] is False
    assert workspace.completed["summary"]["execution_status"] == "completed_with_record_failures"
    assert workspace.completed["summary"]["success_count"] == 1
    assert workspace.completed["summary"]["failed_count"] == 1
    assert workspace.completed["items"][0]["visit_id"] == "OK"
    assert workspace.completed["failed_records"] == [
        {
            "institute_id": "I-1",
            "patient_id": "P-1",
            "visit_id": "BROKEN",
            "record_id": "BROKEN",
            "error_phase": "record_execution",
            "error_type": "LookupError",
        }
    ]


@pytest.mark.asyncio
async def test_rule_failure_is_diagnostic_only_and_never_creates_illegal_customer_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: Luxian0916Execution(
            results=(_result("LX0916-001", status="data_quality_gap"),),
            failures=(Luxian0916RuleFailure("LX0916-002", "TimeoutError"),),
        ),
    )

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.completed is not None
    assert workspace.completed["persist_record_envelopes"] is False
    assert [item["status"] for item in workspace.completed["items"]] == ["data_quality_gap"]
    assert all(
        item["status"] not in {"technical_error", "uncertain"}
        for item in workspace.completed["items"]
    )
    assert workspace.completed["failed_records"] == [
        {
            "institute_id": "I-1",
            "patient_id": "P-1",
            "visit_id": "V-1",
            "record_id": "V-1",
            "error_phase": "rule_execution",
            "rule_id": "LX0916-002",
            "error_type": "TimeoutError",
        }
    ]
    assert workspace.completed["summary"]["diagnostic_rule_failure_count"] == 1


@pytest.mark.asyncio
async def test_batch_worker_rejects_non_exact_rule_set_key() -> None:
    workspace = _Workspace(job=_job(rule_set_key="luxian_0916_qc_v2"), records=[_record()])

    await batch_worker.run_luxian_0916_batch_job("job-0916", workspace=workspace)

    assert workspace.marked is False
    assert workspace.failed == [
        {
            "job_id": "job-0916",
            "error_message": "Luxian0916 任务配置无效: ValueError",
        }
    ]
