"""030/032 经三入口到 Canonical 保存的本地验收。

仅通过正式 evidence-session 的 row_reader 提供脱敏外部资料；route、worker、
prepare、统一引擎、Binding 与保存/回读均为生产实现。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.routers import qc_sample_pools, qc_sichuan
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services import custom_qc_workspace_service as workspace_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.case_identity import CaseRef
from app.services.custom_qc_workspace_service import build_customer_safe_source_ref
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
)
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from tests.integration.test_luxian_0609_consultation_api_entry_flow import (
    _api_app,
    _install_sample_pool_sqlite,
    _wait_for_terminal_job,
)
from tests.integration.test_luxian_0609_exam_lab_family_convergence import (
    _install_isolated_sqlite,
)
from tests.integration.test_luxian_0609_transfusion_family_convergence import (
    _ActivationStub,
    _RECORD_A,
    _RECORD_B,
    _bundle_for_record,
    _create_ready_sample_pool,
    _formal_settings,
    _item,
    _seed_registration_projection,
)


RULE_IDS = ("LX0609-030", "LX0609-032")
EXECUTOR_KEY = "surgery_presence"


@dataclass(frozen=True)
class _Scenario:
    name: str
    surgery_rows: tuple[dict[str, Any], ...]
    safecheck_rows: tuple[dict[str, Any], ...]
    expected: dict[str, tuple[str, str]]
    safecheck_error: bool = False


_SCENARIOS = (
    _Scenario(
        "no_performed_surgery",
        (),
        (),
        {
            "LX0609-030": ("not_applicable", "trigger_absent_complete"),
            "LX0609-032": ("not_applicable", "trigger_absent_complete"),
        },
    ),
    _Scenario(
        "single_complete",
        ({"document_id": "SURG-1", "surgery_begin_time": "2026-08-20 08:00:00+08"},),
        ({"document_id": "CHECK-1", "record_content": "手术时间：2026-08-20 08:00:00"},),
        {
            "LX0609-030": ("compliant", "requirement_satisfied"),
            "LX0609-032": ("compliant", "requirement_satisfied"),
        },
    ),
    _Scenario(
        "safecheck_missing",
        ({"document_id": "SURG-1", "surgery_begin_time": "2026-08-20 08:00:00+08"},),
        (),
        {
            "LX0609-030": ("compliant", "requirement_satisfied"),
            "LX0609-032": ("non_compliant", "required_document_missing"),
        },
    ),
    _Scenario(
        "two_unique_pairs",
        (
            {"document_id": "SURG-1", "surgery_begin_time": "2026-08-20 08:00:00+08"},
            {"document_id": "SURG-2", "surgery_begin_time": "2026-08-20 10:00:00+08"},
        ),
        (
            {"document_id": "CHECK-1", "record_content": "手术时间：2026-08-20 08:00:00"},
            {"document_id": "CHECK-2", "record_content": "手术时间：2026-08-20 10:00:00"},
        ),
        {
            "LX0609-030": ("compliant", "requirement_satisfied"),
            "LX0609-032": ("compliant", "requirement_satisfied"),
        },
    ),
    _Scenario(
        "two_ambiguous_safecheck",
        (
            {"document_id": "SURG-1", "surgery_begin_time": "2026-08-20 08:00:00+08"},
            {"document_id": "SURG-2", "surgery_begin_time": "2026-08-20 10:00:00+08"},
        ),
        (
            {"document_id": "CHECK-1", "record_content": "手术时间：2026-08-20 08:00:00"},
            {"document_id": "CHECK-2", "record_content": "手术时间：2026-08-20 08:00:00"},
        ),
        {
            "LX0609-030": ("compliant", "requirement_satisfied"),
            "LX0609-032": ("data_gap", "association_failed"),
        },
    ),
    _Scenario(
        "safecheck_source_error",
        ({"document_id": "SURG-1", "surgery_begin_time": "2026-08-20 08:00:00+08"},),
        (),
        {
            "LX0609-030": ("compliant", "requirement_satisfied"),
            "LX0609-032": ("technical_error", "executor_exception"),
        },
        safecheck_error=True,
    ),
)


class _NoLlmClient:
    def __init__(self) -> None:
        self.call_count = 0
        self.usages: list[tuple[int, int, int]] = []

    async def generate(self, prompt: str) -> dict[str, Any]:
        self.call_count += 1
        raise AssertionError(f"030/032 must not call LLM: {prompt[:80]}")


def _rows(*, source_key: str, visit_id: str, scenario: _Scenario) -> list[dict[str, Any]]:
    record = _RECORD_B if visit_id == _RECORD_B["visit_id"] else _RECORD_A
    common = {**record, "record_time": "2026-08-20 12:00:00"}
    if source_key == "surgery_record":
        return [{**common, **row} for row in scenario.surgery_rows]
    if source_key == "surgery_safecheck_record":
        return [{**common, **row} for row in scenario.safecheck_rows]
    return []


def _install_reader(monkeypatch: pytest.MonkeyPatch, scenario: _Scenario) -> None:
    original = luxian_execution.build_luxian_0609_evidence_read_session

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if source_key == "surgery_safecheck_record" and scenario.safecheck_error:
            raise SourceEvidenceQueryError("safecheck external source failure")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=_rows(
                source_key=source_key,
                visit_id=str(kwargs["visit_id"]),
                scenario=scenario,
            ),
            truncated=False,
            limit_rows=50,
        )

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **kwargs: original(**kwargs, row_reader=reader),
    )


def _projection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("status", "reason_code", "customer_display_facts", "criterion_results")
    }


def _coordinates(item: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    return {
        (
            str(entry.get("source_type") or ""),
            str(entry.get("source_document_id") or entry.get("source_ref") or ""),
            str(entry.get("field_path") or ""),
            str(entry.get("record_time") or ""),
        )
        for entry in list(item.get("customer_evidence") or item.get("evidence") or [])
        if isinstance(entry, dict)
    }


def _read_saved_item(*, app: Any, job_id: str, task_item: dict[str, Any], record: dict[str, str], rule_id: str) -> dict[str, Any]:
    with TestClient(app) as api:
        response = api.get(
            f"/api/v1/qc/sichuan/workspace/records/{record['visit_id']}/latest-result",
            params={"institute_id": record["institute_id"], "patient_id": record["patient_id"]},
        )
    assert response.status_code == 200, response.text
    latest = response.json()["data"]
    assert latest["state"] == "ready" and latest["job_id"] == job_id
    matches = [item for item in latest["items"] if item.get("rule_id") == rule_id]
    assert len(matches) == 1
    saved = matches[0]
    assert _projection(saved) == _projection(task_item)
    for entry in list(saved.get("evidence") or []):
        source_ref = str(entry.get("source_ref") or "")
        assert re.fullmatch(r"src_[0-9a-f]{24}", source_ref)
        assert "source_document_id" not in entry
    raw_ids = {
        str(entry.get("source_document_id") or "")
        for entry in list(task_item.get("customer_evidence") or [])
        if isinstance(entry, dict) and str(entry.get("source_document_id") or "")
    }
    assert {
        build_customer_safe_source_ref(document_id) for document_id in raw_ids
    }.issubset({str(item.get("source_ref") or "") for item in list(saved.get("evidence") or [])})
    return saved


@pytest.mark.integration
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda item: item.name)
def test_030_032_entries_preserve_canonical_state_and_coordinates(
    monkeypatch: pytest.MonkeyPatch, tmp_path, scenario: _Scenario
) -> None:
    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    engine = workspace_module.engine
    _seed_registration_projection(engine=engine)
    sample_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _install_reader(monkeypatch, scenario)
    settings = _formal_settings()
    for module in (batch_worker, sichuan_qc_service, qc_sichuan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
    monkeypatch.setattr(sichuan_qc_service, "build_adjudicator_runtime_config", lambda config: dict(config or {}))
    monkeypatch.setattr(batch_worker, "load_running_final_bundle", lambda *, institute_id, patient_id, visit_id, **_: _bundle_for_record(visit_id=str(visit_id), patient_id=str(patient_id)))
    monkeypatch.setattr(sample_pool_module, "get_settings", lambda: SimpleNamespace(JWT_SECRET="030-032-entry"))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated-030-032", "allow_mock_when_unconfigured": True})
    no_llm = _NoLlmClient()
    service.adjudicator_client = no_llm

    async def provide_service() -> Any:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_service)
    app = _api_app(service=service)
    pool_id, sample_item_id = _create_ready_sample_pool(engine=engine, service=sample_service)

    def create_workspace_job(records: list[dict[str, str]]) -> str:
        with TestClient(app) as api:
            response = api.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={"rule_set_key": LUXIAN_0609_RULE_SET_KEY, "rule_ids": list(RULE_IDS), "scope": "final", "record_refs": records, "run_mode": "serial"},
            )
        assert response.status_code == 200, response.text
        return str(response.json()["data"]["id"])

    single_job = _wait_for_terminal_job(
        workspace=workspace, job_id=create_workspace_job([_RECORD_A])
    )
    single_saved = {
        rule_id: _read_saved_item(
            app=app,
            job_id=str(single_job["id"]),
            task_item=_item(single_job, rule_id=rule_id),
            record=_RECORD_A,
            rule_id=rule_id,
        )
        for rule_id in RULE_IDS
    }
    batch_job = _wait_for_terminal_job(
        workspace=workspace,
        job_id=create_workspace_job([_RECORD_A, _RECORD_B]),
    )
    batch_saved = {
        rule_id: _read_saved_item(
            app=app,
            job_id=str(batch_job["id"]),
            task_item=_item(batch_job, rule_id=rule_id),
            record=_RECORD_A,
            rule_id=rule_id,
        )
        for rule_id in RULE_IDS
    }
    with TestClient(app) as api:
        response = api.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={"validation_mode": "customer", "rule_set_key": LUXIAN_0609_RULE_SET_KEY, "selected_rule_ids": list(RULE_IDS), "sample_item_ids": [sample_item_id], "record_refs": [_RECORD_A], "group_by_luxian_family": False},
        )
    assert response.status_code == 200, response.text
    sample_job = _wait_for_terminal_job(
        workspace=workspace, job_id=str(response.json()["data"]["job_id"])
    )
    sample_saved = {
        rule_id: _read_saved_item(
            app=app,
            job_id=str(sample_job["id"]),
            task_item=_item(sample_job, rule_id=rule_id),
            record=_RECORD_A,
            rule_id=rule_id,
        )
        for rule_id in RULE_IDS
    }

    for job in (single_job, batch_job, sample_job):
        assert job["status"] == "completed", job.get("error_message")
        assert not list(job.get("failed_records") or [])
    for rule_id in RULE_IDS:
        single_item = _item(single_job, rule_id=rule_id)
        batch_item = _item(batch_job, rule_id=rule_id)
        sample_item = _item(sample_job, rule_id=rule_id)
        assert (single_item["status"], single_item["reason_code"]) == scenario.expected[rule_id]
        for item in (single_item, batch_item, sample_item):
            assert (item.get("metadata") or {}).get("executor_key") == EXECUTOR_KEY
            assert not item.get("llm_fallback") and not item.get("pack_fallback")
            assert "legacy" not in str(item.get("metadata") or {}).lower()
        assert _projection(single_item) == _projection(batch_item) == _projection(sample_item)
        assert _coordinates(single_item) == _coordinates(batch_item) == _coordinates(sample_item)
        assert _projection(single_saved[rule_id]) == _projection(batch_saved[rule_id]) == _projection(sample_saved[rule_id])
        assert _coordinates(single_saved[rule_id]) == _coordinates(batch_saved[rule_id]) == _coordinates(sample_saved[rule_id])
    assert no_llm.call_count == 0 and no_llm.usages == []
