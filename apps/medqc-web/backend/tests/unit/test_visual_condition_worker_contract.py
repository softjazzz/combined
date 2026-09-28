from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.routers import custom_qc
from app.services import sample_programmatic_evidence
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.qc_rule_orchestrator import QCRuleOrchestrator


RECORD_REFS = [
    {"institute_id": "HOSP-A", "patient_id": patient, "visit_id": visit}
    for patient, visit in (("PAT-A", "VISIT-A"), ("PAT-B", "VISIT-B"), ("PAT-C", "VISIT-C"))
]


def _visual_condition() -> dict[str, Any]:
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
                "operator": "exists",
            }],
        }],
    }


class _WorkerWorkspace:
    hydrate_records_with_visual_evidence = CustomQCWorkspaceService.hydrate_records_with_visual_evidence

    def __init__(self, *, visual: bool) -> None:
        self.visual = visual
        refs = RECORD_REFS if visual else RECORD_REFS[:1]
        self.job = {
            "id": "job-visual" if visual else "job-legacy",
            "status": "queued",
            "draft_id": "draft-1",
            "draft_ids": ["draft-1"],
            "created_by": "manager-1",
            "scope": "running",
            "filters": {"date_field": "admission", "record_refs": refs},
            "record_ids": ["legacy-must-not-be-used"],
        }
        self.collect_calls: list[dict[str, Any]] = []
        self.medical_hydrate_calls: list[list[dict[str, Any]]] = []
        self.progress_calls: list[dict[str, Any]] = []
        self.completed: dict[str, Any] | None = None
        self.saved_summary: dict[str, Any] | None = None
        self.saved_summaries: list[dict[str, Any]] = []
        self.failure: dict[str, Any] | None = None

    def get_batch_job_for_processing(self, *, job_id: str) -> dict[str, Any]:
        assert job_id == self.job["id"]
        return dict(self.job)

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        assert job_id == self.job["id"]
        self.job["status"] = "running"
        return True

    def get_draft(self, *, draft_id: str, created_by: str) -> dict[str, Any]:
        assert (draft_id, created_by) == ("draft-1", "manager-1")
        check_logic: dict[str, Any] = {}
        if self.visual:
            check_logic["visual_condition"] = _visual_condition()
        return {
            "id": draft_id,
            "rule_code": "CUSTOM-VISUAL" if self.visual else "CUSTOM-LEGACY",
            "name": "首程存在即触发" if self.visual else "旧正文规则",
            "description": "合成worker合同",
            "prompt_template": "请检查：{medical_text}",
            "document_type": "首次病程记录",
            "applicable_documents": ["first_course_record"],
            "severity": "major",
            "scene": "running",
            "status": "published",
            "check_logic": check_logic,
        }

    def collect_records(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.collect_calls.append(kwargs)
        return [{
            **record_ref,
            "record_id": record_ref["visit_id"],
            "patient_name": "合成患者",
            "department": "合成科室",
            "medical_text": "" if self.visual else "旧规则需要的合成正文",
            "evidence_payload": {"client": "must-be-ignored"},
        } for record_ref in kwargs["record_refs"]]

    def hydrate_records_with_medical_text(
        self, records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        copied = [dict(item) for item in records]
        self.medical_hydrate_calls.append(copied)
        return copied

    def update_batch_job_progress(self, **kwargs: Any) -> None:
        self.progress_calls.append(kwargs)

    def complete_batch_job(self, **kwargs: Any) -> None:
        self.completed = kwargs

    def save_last_test_summary(self, **kwargs: Any) -> None:
        self.saved_summary = kwargs
        self.saved_summaries.append(kwargs)

    def fail_batch_job(self, **kwargs: Any) -> None:
        self.failure = kwargs


class _MixedWorkerWorkspace(_WorkerWorkspace):
    def __init__(self) -> None:
        super().__init__(visual=True)
        self.job.update({
            "id": "job-mixed",
            "draft_id": "draft-visual",
            "draft_ids": ["draft-visual", "draft-legacy"],
            "filters": {"date_field": "admission", "record_refs": RECORD_REFS[:1]},
        })

    def get_draft(self, *, draft_id: str, created_by: str) -> dict[str, Any]:
        assert created_by == "manager-1"
        assert draft_id in {"draft-visual", "draft-legacy"}
        visual = draft_id == "draft-visual"
        return {
            "id": draft_id,
            "rule_code": "CUSTOM-VISUAL" if visual else "CUSTOM-LEGACY",
            "name": "首程存在即触发" if visual else "旧正文规则",
            "description": "合成worker合同",
            "prompt_template": "请检查：{medical_text}",
            "document_type": "首次病程记录",
            "applicable_documents": ["first_course_record"],
            "severity": "major",
            "scene": "running",
            "status": "published",
            "check_logic": {"visual_condition": _visual_condition()} if visual else {},
        }

    def collect_records(self, **kwargs: Any) -> list[dict[str, Any]]:
        records = super().collect_records(**kwargs)
        records[0]["medical_text"] = "旧规则需要的合成正文"
        return records


def _qc_service(*, llm_result: dict[str, Any] | None = None) -> SimpleNamespace:
    evaluate = AsyncMock(
        side_effect=AssertionError("visual worker must not call LLM") if llm_result is None else None,
        return_value=llm_result,
    )
    return SimpleNamespace(
        client=SimpleNamespace(model="unit-test"),
        rule_orchestrator=QCRuleOrchestrator(),
        rule_engine=SimpleNamespace(evaluate=evaluate),
        execution_cache=None,
    )


@pytest.mark.asyncio
async def test_worker_visual_rule_runs_real_program_path_and_preserves_unavailable_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _WorkerWorkspace(visual=True)
    qc_service = _qc_service()
    evidence_calls: list[dict[str, Any]] = []

    def build_evidence(**kwargs: Any) -> dict[str, Any]:
        evidence_calls.append(kwargs)
        assert kwargs["bundle"] in RECORD_REFS
        assert kwargs["medical_text"] == ""
        assert kwargs["strict_identity"] is True
        patient_id = kwargs["bundle"]["patient_id"]
        if patient_id == "PAT-C":
            raise RuntimeError("synthetic evidence source failure")
        present = patient_id == "PAT-A"
        return {
            "programmatic_timeline": {
                "documents": {
                    "first_course_record": ([{
                        "visual_record_time": "2026-09-28 09:00:00",
                        "visual_record_time_trusted": True,
                    }] if present else []),
                },
                "source_readiness": {
                    "first_course_record": "complete" if present else "unknown",
                },
            }
        }

    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: workspace)
    monkeypatch.setattr(custom_qc, "create_custom_qc_service", AsyncMock(return_value=qc_service))
    monkeypatch.setattr(sample_programmatic_evidence, "build_programmatic_evidence_payload", build_evidence)

    await custom_qc._run_workspace_batch_job(workspace.job["id"])

    assert workspace.failure is None
    assert workspace.collect_calls[0]["record_refs"] == RECORD_REFS
    assert workspace.collect_calls[0]["record_ids"] is None
    assert len(workspace.medical_hydrate_calls) == 1
    assert len(evidence_calls) == 3
    qc_service.rule_engine.evaluate.assert_not_awaited()
    assert workspace.completed is not None
    statuses = [item["status"] for item in workspace.completed["items"]]
    assert statuses == ["non_compliant", "data_gap", "technical_error"]
    assert all(item["metadata"]["executor_type"] == "program" for item in workspace.completed["items"])
    assert workspace.completed["summary"]["executor_breakdown"] == {"program": 3, "llm": 0}
    assert workspace.completed["summary"]["total_tokens"] == 0
    assert workspace.completed["summary"]["issue_records"] == 1
    assert workspace.completed["summary"]["compliant_records"] == 0
    assert workspace.saved_summary is not None
    assert workspace.saved_summary["draft_id"] == "draft-1"
    assert [item["status"] for item in workspace.saved_summary["summary"]["rule_results"][0]["items"]] == statuses


@pytest.mark.asyncio
async def test_worker_legacy_rule_keeps_medical_text_and_llm_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _WorkerWorkspace(visual=False)
    llm_result = {
        "rule_id": "CUSTOM-LEGACY",
        "rule_name": "旧正文规则",
        "status": "compliant",
        "is_compliant": True,
        "issues": [],
        "findings": "合规",
        "evidence": "旧规则需要的合成正文",
        "suggestion": "",
        "confidence": 0.9,
        "metadata": {"tokens_used": 7},
    }
    qc_service = _qc_service(llm_result=llm_result)
    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: workspace)
    monkeypatch.setattr(custom_qc, "create_custom_qc_service", AsyncMock(return_value=qc_service))

    await custom_qc._run_workspace_batch_job(workspace.job["id"])

    assert workspace.failure is None
    assert len(workspace.medical_hydrate_calls) == 1
    qc_service.rule_engine.evaluate.assert_awaited_once()
    assert workspace.completed is not None
    assert workspace.completed["items"][0]["status"] == "compliant"
    assert workspace.completed["summary"]["executor_breakdown"] == {"program": 0, "llm": 1}


@pytest.mark.asyncio
async def test_worker_mixed_drafts_save_isolated_per_rule_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _MixedWorkerWorkspace()
    llm_result = {
        "rule_id": "CUSTOM-LEGACY",
        "rule_name": "旧正文规则",
        "status": "compliant",
        "is_compliant": True,
        "issues": [],
        "findings": "合规",
        "evidence": "旧规则需要的合成正文",
        "suggestion": "",
        "confidence": 0.9,
        "metadata": {"tokens_used": 7},
    }
    qc_service = _qc_service(llm_result=llm_result)

    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: workspace)
    monkeypatch.setattr(custom_qc, "create_custom_qc_service", AsyncMock(return_value=qc_service))
    monkeypatch.setattr(
        sample_programmatic_evidence,
        "build_programmatic_evidence_payload",
        lambda **_kwargs: {
            "programmatic_timeline": {
                "documents": {"first_course_record": [{
                    "visual_record_time": "2026-09-28 09:00:00",
                    "visual_record_time_trusted": True,
                }]},
                "source_readiness": {"first_course_record": "complete"},
            }
        },
    )

    await custom_qc._run_workspace_batch_job(workspace.job["id"])

    assert workspace.failure is None
    assert workspace.completed is not None
    assert len(workspace.completed["summary"]["rule_results"]) == 2
    summaries = {item["draft_id"]: item["summary"] for item in workspace.saved_summaries}
    assert set(summaries) == {"draft-visual", "draft-legacy"}

    visual = summaries["draft-visual"]
    assert visual["total_tasks"] == 1
    assert visual["success_count"] == 1
    assert visual["executor_breakdown"] == {"program": 1, "llm": 0}
    assert visual["total_tokens"] == 0
    assert len(visual["rule_results"]) == 1
    assert visual["rule_results"][0]["rule_code"] == "CUSTOM-VISUAL"
    assert [item["status"] for item in visual["rule_results"][0]["items"]] == [
        "non_compliant",
    ]

    legacy = summaries["draft-legacy"]
    assert legacy["total_tasks"] == 1
    assert legacy["success_count"] == 1
    assert legacy["executor_breakdown"] == {"program": 0, "llm": 1}
    assert legacy["total_tokens"] == 7
    assert len(legacy["rule_results"]) == 1
    assert legacy["rule_results"][0]["rule_code"] == "CUSTOM-LEGACY"
    assert [item["status"] for item in legacy["rule_results"][0]["items"]] == [
        "compliant",
    ]
