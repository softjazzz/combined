"""手术门控客户启用规则经三正式入口到 Canonical 保存的本地验收。"""

from __future__ import annotations

import json
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


REQUESTED_RULE_IDS = (
    "LX0609-003",
    "LX0609-024",
    "LX0609-025",
    "LX0609-028",
    "LX0609-031",
    "LX0609-033",
)
ACTIVE_RULE_IDS = ("LX0609-003", "LX0609-024", "LX0609-031")
PAUSED_RULE_IDS = ("LX0609-025", "LX0609-028")
_USAGE = (90, 10, 100)


@dataclass(frozen=True)
class _Scenario:
    name: str
    expected: dict[str, tuple[str, str]]
    semantic_event: dict[str, object] | None = None
    surgery_error: bool = False
    surgery_overrides: dict[str, object] | None = None
    master_overrides: dict[str, object] | None = None
    consent_overrides: dict[str, object] | None = None
    drug_text: str | None = None


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "event_ref": "EV1",
        "evidence_refs": ["S01-01", "S06-01", "S08-01"],
        "surgery_occurrence": "performed",
        "malignant_relation": "qualifying",
        "lymph_node_documentation": "documented",
        "implant_use": "actual_permanent_implant",
        "implant_name": "present",
        "implant_type": "present",
        "implant_specification": "present",
        "implant_material": "present",
        "implant_quantity": "present",
        "implant_items": [{
            "name": "人工硬脑膜",
            "use_kind": "permanent_implant",
            "evidence_ref": "S01-01",
        }],
        "incision_class": "I",
        "antimicrobial_intent": "prophylactic",
        "start_time_ref": "T004",
        "start_time_role": "actual_administration",
        "end_time_ref": "T005",
        "end_time_role": "actual_stop",
        "interval_scope": "prophylactic_segment",
        "special_extension_reason": "unknown",
        "consent_role": "surgery_informed_consent",
        "consent_linkage": "current_surgery",
        "patient_signature": "present",
        "surgeon_signature": "present",
    }
    event.update(overrides)
    return event


_NA = {
    rule_id: ("not_applicable", "performed_event_absent")
    for rule_id in REQUESTED_RULE_IDS
}
_TE = {
    rule_id: ("technical_error", "source_query_error")
    for rule_id in REQUESTED_RULE_IDS
}

_SCENARIOS = (
    _Scenario("no_performed_surgery", _NA),
    _Scenario(
        "all_compliant",
        {
            "LX0609-003": ("compliant", "requirement_within_threshold"),
            **{
                rule_id: ("compliant", "requirement_satisfied")
                for rule_id in REQUESTED_RULE_IDS[1:]
            },
        },
        semantic_event=_event(),
    ),
    _Scenario(
        "all_non_compliant",
        {
            "LX0609-003": ("non_compliant", "threshold_exceeded"),
            **{
                rule_id: ("non_compliant", "requirement_violated")
                for rule_id in REQUESTED_RULE_IDS[1:]
            },
        },
        semantic_event=_event(
            lymph_node_documentation="not_documented",
            implant_type="missing",
            end_time_ref="T005",
            patient_signature="missing",
        ),
        surgery_overrides={"record_time": "2026-08-21 12:00:00+08:00"},
        master_overrides={"main_surgery_sign": "李医生"},
        consent_overrides={"patient_sign": ""},
        drug_text="2026-08-20 10:00 实际给予预防抗菌药；2026-08-22 12:00 实际停止。",
    ),
    _Scenario(
        "all_data_gap",
        {
            "LX0609-003": ("data_gap", "authoritative_time_missing"),
            **{
                rule_id: ("data_gap", "required_field_missing")
                for rule_id in REQUESTED_RULE_IDS[1:]
            },
        },
        semantic_event=_event(
            malignant_relation="unknown",
            implant_type="unknown",
            end_time_ref=None,
            end_time_role="unknown",
            interval_scope="unknown",
            consent_linkage="unknown",
        ),
        surgery_overrides={"surgery_end_time": "", "surgeon_sign": ""},
        master_overrides={"main_surgery_sign": "已签"},
    ),
    _Scenario("surgery_source_error", _TE, surgery_error=True),
)


class _SurgeryFactClient:
    def __init__(self, event: dict[str, object] | None) -> None:
        self._event = event
        self.prompts: list[str] = []
        self.options: list[tuple[int | None, bool]] = []
        self.usages: list[tuple[int, int, int]] = []

    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, object]:
        if self._event is None:
            raise AssertionError("非语义场景不得调用模型")
        assert "你是泸县0609手术事实抽取器" in prompt
        assert "本次规则：LX0609-024。" in prompt
        assert prompt.count("材料：") == 1
        self.prompts.append(prompt)
        self.options.append((max_completion_tokens, allow_length_retry))
        self.usages.append(_USAGE)
        # 客户正式入口当前只启用 024 这一条受控语义规则。
        # 验收 Stub 必须与单规则 Prompt 合同一致，不得返回
        # 025/028/033 的额外字段，否则会被严格解析器拒绝。
        semantic_event = {
            "event_ref": self._event["event_ref"],
            "evidence_refs": ["S01-01"],
            "surgery_occurrence": self._event["surgery_occurrence"],
            "malignant_relation": self._event["malignant_relation"],
            "lymph_node_documentation": self._event["lymph_node_documentation"],
        }
        return {
            "choices": [{"message": {"content": json.dumps({
                "schema_version": "lx0609-surgery-text-facts-v2",
                "events": [semantic_event],
            }, ensure_ascii=False)}}],
            "usage": {
                "prompt_tokens": _USAGE[0],
                "completion_tokens": _USAGE[1],
                "total_tokens": _USAGE[2],
            },
            "_api_time": 0.01,
        }


def _rows_for(scenario: _Scenario) -> dict[str, tuple[dict[str, object], ...]]:
    if scenario.semantic_event is None and not scenario.surgery_error:
        return {}
    surgery = {
        "document_id": "SURG-1",
        "surgery_name": "结肠癌根治术",
        "surgery_begin_time": "2026-08-20 08:00:00+08:00",
        "surgery_end_time": "2026-08-20 09:00:00+08:00",
        "record_time": "2026-08-20 10:00:00+08:00",
        "surgeon": "张医生",
        "surgeon_sign": "张医生",
        "surgery_process": "本次手术，术中置入人工硬脑膜。",
    }
    surgery.update(scenario.surgery_overrides or {})
    master = {
        "document_id": "MR-SURG-1",
        "surgery_name": "结肠癌根治术",
        "surgeon": "张医生",
        "main_surgery_sign": "张医生",
    }
    master.update(scenario.master_overrides or {})
    consent = {
        "document_id": "CONSENT-1",
        "record_content": "本次结肠癌根治术手术知情同意书。",
        "patient_sign": "患者签名",
        "surgeon_sign": "张医生",
    }
    consent.update(scenario.consent_overrides or {})
    return {
        "surgery_record": (surgery,),
        "mr_surgery": (master,),
        "admission_record_diagnosis": ({
            "document_id": "ADMISSION-DX-1",
            "diagnosis_code": "C18.9",
            "diagnosis_name": "结肠恶性肿瘤",
        },),
        "diagnosis": ({
            "document_id": "DX-1",
            "diagnosis_code": "C18.9",
            "diagnosis_name": "结肠恶性肿瘤",
        },),
        "pathology_exam_master": ({"document_id": "PATH-MASTER-1", "specimen_name": "结肠标本"},),
        "pathology_exam_report": ({"document_id": "PATH-1", "diagnosis": "恶性肿瘤病理"},),
        "inpat_drug_order": ({
            "document_id": "DRUG-1",
            "record_content": scenario.drug_text
            or "2026-08-20 10:00 实际给予预防抗菌药；2026-08-20 18:00 实际停止。",
        },),
        "daily_course_record": ({"document_id": "COURSE-1", "record_content": "术后病程记录。"},),
        "surgery_inform_consent": (consent,),
    }


def _install_reader(monkeypatch: pytest.MonkeyPatch, scenario: _Scenario) -> None:
    original = luxian_execution.build_luxian_0609_evidence_read_session
    rows_by_source = _rows_for(scenario)

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if scenario.surgery_error and source_key == "surgery_record":
            raise SourceEvidenceQueryError("surgery source failed")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
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
        assert re.fullmatch(r"src_[0-9a-f]{24}", str(entry.get("source_ref") or ""))
        assert "source_document_id" not in entry
    raw_ids = {
        str(entry.get("source_document_id") or "")
        for entry in list(task_item.get("customer_evidence") or [])
        if isinstance(entry, dict) and str(entry.get("source_document_id") or "")
    }
    assert {build_customer_safe_source_ref(item) for item in raw_ids}.issubset(
        {str(item.get("source_ref") or "") for item in list(saved.get("evidence") or [])}
    )
    return saved


@pytest.mark.integration
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda item: item.name)
def test_surgery_gate_entries_preserve_canonical_state_prompt_and_coordinates(
    monkeypatch: pytest.MonkeyPatch, tmp_path, scenario: _Scenario
) -> None:
    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    engine = workspace_module.engine
    _seed_registration_projection(engine=engine)
    sample_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _install_reader(monkeypatch, scenario)
    settings = _formal_settings()
    settings.LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED = True
    settings.LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED = True
    settings.LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED = True
    for module in (batch_worker, sichuan_qc_service, qc_sichuan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
    monkeypatch.setattr(sichuan_qc_service, "build_adjudicator_runtime_config", lambda config: dict(config or {}))
    monkeypatch.setattr(batch_worker, "load_running_final_bundle", lambda *, institute_id, patient_id, visit_id, **_: _bundle_for_record(visit_id=str(visit_id), patient_id=str(patient_id)))
    monkeypatch.setattr(sample_pool_module, "get_settings", lambda: SimpleNamespace(JWT_SECRET="surgery-gate-entry"))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    service = sichuan_qc_service.SichuanQCService({"provider_code": "surgery-gate-entry", "allow_mock_when_unconfigured": True})
    client = _SurgeryFactClient(scenario.semantic_event)
    service.adjudicator_client = client

    async def provide_service() -> Any:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_service)
    app = _api_app(service=service)
    pool_id, sample_item_id = _create_ready_sample_pool(engine=engine, service=sample_service)

    def create_workspace_job(records: list[dict[str, str]]) -> str:
        with TestClient(app) as api:
            response = api.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={"rule_set_key": LUXIAN_0609_RULE_SET_KEY, "rule_ids": list(REQUESTED_RULE_IDS), "scope": "final", "record_refs": records, "run_mode": "serial"},
            )
        assert response.status_code == 200, response.text
        return str(response.json()["data"]["id"])

    single_job = _wait_for_terminal_job(workspace=workspace, job_id=create_workspace_job([_RECORD_A]))
    assert {
        str(item.get("rule_id") or "")
        for item in list(single_job.get("items") or [])
    } == set((*ACTIVE_RULE_IDS, *PAUSED_RULE_IDS))
    assert set(single_job["filters"]["paused_customer_rule_ids"]) == set(PAUSED_RULE_IDS)
    assert "LX0609-033" not in single_job["filters"]["scoped_customer_rule_ids"]
    single_saved = {
        rule_id: _read_saved_item(app=app, job_id=str(single_job["id"]), task_item=_item(single_job, rule_id=rule_id), record=_RECORD_A, rule_id=rule_id)
        for rule_id in ACTIVE_RULE_IDS
    }
    batch_job = _wait_for_terminal_job(workspace=workspace, job_id=create_workspace_job([_RECORD_A, _RECORD_B]))
    batch_saved = {
        rule_id: _read_saved_item(app=app, job_id=str(batch_job["id"]), task_item=_item(batch_job, rule_id=rule_id), record=_RECORD_A, rule_id=rule_id)
        for rule_id in ACTIVE_RULE_IDS
    }
    with TestClient(app) as api:
        response = api.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={"validation_mode": "customer", "rule_set_key": LUXIAN_0609_RULE_SET_KEY, "selected_rule_ids": list(ACTIVE_RULE_IDS), "sample_item_ids": [sample_item_id], "record_refs": [_RECORD_A], "group_by_luxian_family": False},
        )
    assert response.status_code == 200, response.text
    sample_job = _wait_for_terminal_job(workspace=workspace, job_id=str(response.json()["data"]["job_id"]))
    sample_saved = {
        rule_id: _read_saved_item(app=app, job_id=str(sample_job["id"]), task_item=_item(sample_job, rule_id=rule_id), record=_RECORD_A, rule_id=rule_id)
        for rule_id in ACTIVE_RULE_IDS
    }

    for job in (single_job, batch_job, sample_job):
        assert job["status"] == "completed", job.get("error_message")
        assert not list(job.get("failed_records") or [])
    for rule_id in ACTIVE_RULE_IDS:
        single_item = _item(single_job, rule_id=rule_id)
        batch_item = _item(batch_job, rule_id=rule_id)
        sample_item = _item(sample_job, rule_id=rule_id)
        assert (single_item["status"], single_item["reason_code"]) == scenario.expected[rule_id]
        for item in (single_item, batch_item, sample_item):
            metadata = dict(item.get("metadata") or {})
            assert metadata.get("executor_key") == "surgery_gate"
            assert not item.get("llm_fallback") and not item.get("pack_fallback")
            assert "legacy" not in str(metadata).lower()
        assert _projection(single_item) == _projection(batch_item) == _projection(sample_item)
        assert _coordinates(single_item) == _coordinates(batch_item) == _coordinates(sample_item)
        assert _projection(single_saved[rule_id]) == _projection(batch_saved[rule_id]) == _projection(sample_saved[rule_id])
        assert _coordinates(single_saved[rule_id]) == _coordinates(batch_saved[rule_id]) == _coordinates(sample_saved[rule_id])
        if scenario.semantic_event is not None and rule_id in {"LX0609-003", "LX0609-024"}:
            assert any(source_type == "surgery_record" for source_type, *_ in _coordinates(single_item))

    expected_calls = 4 if scenario.semantic_event is not None else 0
    assert len(client.prompts) == expected_calls
    assert client.options == [(512, False)] * expected_calls
    assert client.usages == [_USAGE] * expected_calls
    if expected_calls:
        assert len(set(client.prompts)) == 1
