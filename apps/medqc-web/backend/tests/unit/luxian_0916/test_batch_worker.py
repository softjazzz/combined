from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.luxian_0916 import batch_worker
from app.services.luxian_0916.contracts import Luxian0916RuleResult
from app.services.luxian_0916.orchestrator import (
    Luxian0916Execution,
    Luxian0916RuleFailure,
)
from app.services.luxian_0916.rule_catalog import LUXIAN_0916_RULE_CATALOG


_REAL_BUILD_CRITICAL_VALUE_018_FACTS = batch_worker.build_critical_value_018_facts
_REAL_EXTRACT_CRITICAL_VALUE_018_STAGE2_FACTS = (
    batch_worker.extract_critical_value_018_stage2_facts
)
_REAL_EXECUTE_LUXIAN_0916 = batch_worker.execute_luxian_0916
_FORMAL_COURSE_SOURCES = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "postsurg_firstcourse_record",
    "rescue_record",
)


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


def _complete_execution(
    *, statuses: dict[str, str] | None = None
) -> Luxian0916Execution:
    statuses = statuses or {}
    return Luxian0916Execution(
        results=tuple(
            _result(rule.rule_id, status=statuses.get(rule.rule_id, "compliant"))
            for rule in LUXIAN_0916_RULE_CATALOG
        )
    )


@pytest.fixture(autouse=True)
def _isolate_structured_disease_change_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """批处理单测不连接真实 CDM；结构化来源由专属单测覆盖。"""

    monkeypatch.setattr(
        batch_worker,
        "build_critical_value_018_facts",
        lambda **_kwargs: {
            "event_facts": {"critical_values": []},
            "event_source_state_by_rule": {
                "LX0916-018": "critical_value_source_complete"
            },
            "diagnostic": {
                "code": "critical_value_018_stage1_ready",
                "event_count": 0,
                "llm_call_count": 0,
            },
        },
    )

    monkeypatch.setattr(
        batch_worker,
        "load_disease_change_015016_facts",
        lambda **_kwargs: {
            "event_facts": {"disease_changes": []},
            "event_source_state_by_rule": {
                "LX0916-015": "structured_complete",
                "LX0916-016": "structured_complete",
            },
            "diagnostic": {
                "code": "structured_disease_change_trigger_ready",
                "event_count": 0,
                "llm_call_count": 0,
            },
        },
    )

    async def extract_stage2(**kwargs: Any) -> dict[str, Any]:
        result = dict(kwargs["structured_facts"])
        result["diagnostic"] = {
            "code": "disease_change_stage2_not_triggered",
            "event_count": 0,
            "llm_call_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model_elapsed_ms": 0,
            "failure_count": 0,
        }
        return result

    monkeypatch.setattr(
        batch_worker,
        "extract_disease_change_stage2_facts",
        extract_stage2,
    )


def _patch_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0916_bundle",
        lambda **_kwargs: {"structured_context": {}},
    )
    def build_evidence(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["strict_structured_source_limits"] == {
            "labtest_master": 100,
            "labtest_item_report": 400,
        }
        return {"programmatic_timeline": {"documents": {}}}

    monkeypatch.setattr(
        batch_worker,
        "build_programmatic_evidence_payload",
        build_evidence,
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


async def _invalid_semantic_generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"content": "not-json"}}]}


def _critical_value_018_worker_evidence() -> dict[str, Any]:
    documents = {source: [] for source in _FORMAL_COURSE_SOURCES}
    documents["daily_course_record"] = [
        {
            "document_id": "COURSE-1",
            "authored_at": "2026-09-16 08:30:00",
            "content": "接获血钾危急值6.8 mmol/L报告并立即停用补钾、复查电解质。",
        }
    ]
    return {
        "programmatic_timeline": {
            "documents": documents,
            "source_readiness": {
                source: "complete" for source in _FORMAL_COURSE_SOURCES
            },
            "structured_source_readiness": {
                "labtest_master": "complete",
                "labtest_item_report": "complete",
            },
            "structured_source_rows": {
                "labtest_master": [
                    {
                        "test_id": "TEST-1",
                        "test_no": "REPORT-1",
                        "labtest_result_status": "已审核",
                        "report_datetime": "2026-09-16 08:00:00",
                    }
                ],
                "labtest_item_report": [
                    {
                        "test_id": "TEST-1",
                        "test_no": "REPORT-1",
                        "item_id": "ITEM-1",
                        "item_name": "血钾",
                        "result": "6.8",
                        "unit": "mmol/L",
                        "abnormal_indicator": "PH",
                        "report_time": "2026-09-16 08:00:00",
                    }
                ],
            },
        }
    }


def _critical_value_018_model_response(*, disposition_state: str) -> dict[str, Any]:
    present_coordinate = {
        "source_type": "daily_course_record",
        "document_id": "COURSE-1",
        "clause_id": "COURSE-1:1",
    }
    disposition_coordinate = (
        present_coordinate
        if disposition_state == "present"
        else {"source_type": None, "document_id": None, "clause_id": None}
    )
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "events": [
                                {
                                    "event_id": "critical-value:REPORT-1",
                                    "facts": [
                                        {
                                            "fact_kind": "report_recorded",
                                            "state": "present",
                                            "event_id": "critical-value:REPORT-1",
                                            **present_coordinate,
                                        },
                                        {
                                            "fact_kind": "disposition_recorded",
                                            "state": disposition_state,
                                            "event_id": "critical-value:REPORT-1",
                                            **disposition_coordinate,
                                        },
                                    ],
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
        "_api_time": 0.01,
    }


async def _run_real_critical_value_018_worker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    generate,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = _critical_value_018_worker_evidence()
    scenes: list[str] = []

    def load_bundle(**kwargs: Any) -> dict[str, Any]:
        scenes.append(kwargs["scene"])
        return {"structured_context": {}}

    def build_evidence(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["strict_structured_source_limits"] == {
            "labtest_master": 100,
            "labtest_item_report": 400,
        }
        return evidence

    async def extract_shared_semantic(**_kwargs: Any) -> dict[str, Any]:
        return {
            "semantic_facts": {},
            "event_facts": {},
            "document_facts": {},
            "discharge_facts": {},
            "event_source_state_by_rule": {},
            "diagnostic": {"code": "semantic_extraction_ready", "llm_call_count": 0},
        }

    monkeypatch.setattr(
        batch_worker,
        "build_critical_value_018_facts",
        _REAL_BUILD_CRITICAL_VALUE_018_FACTS,
    )
    monkeypatch.setattr(
        batch_worker,
        "extract_critical_value_018_stage2_facts",
        _REAL_EXTRACT_CRITICAL_VALUE_018_STAGE2_FACTS,
    )
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        _REAL_EXECUTE_LUXIAN_0916,
    )
    monkeypatch.setattr(batch_worker, "load_luxian_0916_bundle", load_bundle)
    monkeypatch.setattr(
        batch_worker, "build_programmatic_evidence_payload", build_evidence
    )
    monkeypatch.setattr(
        batch_worker, "extract_luxian_0916_facts", extract_shared_semantic
    )
    workspace = _Workspace(job=_job(), records=[_record()])

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=generate
    )

    assert scenes == ["running"]
    assert workspace.failed == []
    assert workspace.completed is not None
    item = next(
        item
        for item in workspace.completed["items"]
        if item["rule_id"] == "LX0916-018"
    )
    return item, workspace.completed["summary"]


@pytest.mark.asyncio
async def test_semantic_generate_forces_deterministic_sampling_without_losing_model_or_token_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_configs: list[dict[str, Any]] = []

    async def load_config(**_kwargs: Any) -> dict[str, Any]:
        return {
            "model": "saved-model",
            "custom_parameters": {
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 512,
                "preserved_setting": "value",
            },
        }

    class Client:
        def __init__(self, config: dict[str, Any]) -> None:
            captured_configs.append(config)

        async def generate(self, _prompt: str, **_kwargs: Any) -> dict[str, Any]:
            return {}

    monkeypatch.setattr(batch_worker.LLMConfigLoader, "load_config", load_config)
    monkeypatch.setattr(batch_worker, "SichuanQCLLMClient", Client)

    generate = await batch_worker._build_semantic_generate(
        {
            "temperature": 0.8,
            "top_p": 0.2,
            "max_tokens": 4096,
            "model_code": "task-model",
        }
    )

    assert callable(generate)
    assert captured_configs == [
        {
            "model": "task-model",
            "custom_parameters": {
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 4096,
                "preserved_setting": "value",
            },
        }
    ]


@pytest.mark.asyncio
async def test_batch_worker_preserves_rule_contract_and_finishes_all_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record(patient_id="P-2", visit_id="V-2"), _record()])
    _patch_loaders(monkeypatch)
    captured_semantic_rule_ids: list[tuple[str, ...]] = []

    async def extract(**kwargs: Any) -> dict[str, Any]:
        captured_semantic_rule_ids.append(tuple(kwargs["rule_ids"]))
        return {
            "semantic_facts": {},
            "event_facts": {},
            "document_facts": {},
            "discharge_facts": {},
            "event_source_state_by_rule": {},
            "diagnostic": {
                "code": "semantic_extraction_ready",
                "document_count": 0,
                "llm_call_count": 0,
            },
        }

    monkeypatch.setattr(batch_worker, "extract_luxian_0916_facts", extract)

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
    expected_shared_rule_ids = tuple(
        rule.rule_id
        for rule in LUXIAN_0916_RULE_CATALOG
        if rule.rule_id
        not in {
            "LX0916-015",
            "LX0916-016",
            "LX0916-018",
        }
    )
    assert captured_semantic_rule_ids == [expected_shared_rule_ids, expected_shared_rule_ids]
    summary = workspace.completed["summary"]
    assert summary["status_counts"] == {"non_compliant": 2, "compliant": 62}
    assert summary["display_status_counts"] == summary["status_counts"]
    assert summary["success_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["completed_rule_count"] == 64
    assert summary["failed_rule_count"] == 0
    assert summary["execution_status"] == "completed"
    assert summary["max_parallel_records"] == 2
    assert summary["progress"]["max_parallel_records"] == 2
    assert summary["disease_change_stage2_llm_call_count"] == 0
    assert summary["disease_change_stage2_total_tokens"] == 0
    assert summary["critical_value_018_stage2_llm_call_count"] == 0
    assert summary["critical_value_018_stage2_total_tokens"] == 0
    assert summary["critical_value_018_stage2_model_parameters"] == [
        {
            "enable_thinking": False,
            "max_completion_tokens": 2048,
            "allow_length_retry": False,
            "response_format": "json_object",
        }
    ]
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
async def test_batch_worker_runs_018_family_and_summarizes_actual_model_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    event = {
        "event_type": "critical_values",
        "event_id": "critical-value:REPORT-1",
        "trigger_confirmed": True,
        "evaluation_window_mature": None,
        "event_source_type": "labtest_item_report",
        "event_source_id": "REPORT-1",
        "event_time": "2026-09-16 08:00:00",
        "event_kind": "critical_lab_report",
        "related_source_type": "labtest_item_report",
        "related_source_ids": ["ITEM-1"],
        "critical_flags": ["PH"],
        "critical_items": [
            {
                "item_id": "ITEM-1",
                "item_name": "血钾",
                "result": "6.8",
                "unit": "mmol/L",
                "critical_flag": "PH",
            }
        ],
    }
    monkeypatch.setattr(
        batch_worker,
        "build_critical_value_018_facts",
        lambda **_kwargs: {
            "event_facts": {"critical_values": [event]},
            "event_source_state_by_rule": {
                "LX0916-018": "critical_value_source_complete"
            },
            "diagnostic": {"llm_call_count": 0},
        },
    )
    captured: list[dict[str, Any]] = []

    async def extract_018(**kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs)
        enriched = {
            **event,
            "evaluation_window_mature": True,
            "stage2_state_by_rule": {"LX0916-018": "ready"},
            "stage2_facts": [],
        }
        return {
            "event_facts": {"critical_values": [enriched]},
            "event_source_state_by_rule": {
                "LX0916-018": "critical_value_source_complete"
            },
            "diagnostic": {
                "code": "critical_value_018_stage2_ready",
                "llm_call_count": 1,
                "prompt_tokens": 90,
                "completion_tokens": 18,
                "total_tokens": 108,
                "model_elapsed_ms": 140,
                "failure_count": 0,
                "usage_incomplete": False,
                "model_parameters": {
                    "provider_code": "aliyun_bailian",
                    "model": "qwen3.8-flash",
                    "temperature": 0,
                    "top_p": 1,
                    "enable_thinking": False,
                    "max_completion_tokens": 2048,
                    "allow_length_retry": False,
                    "response_format": "json_object",
                },
            },
        }

    monkeypatch.setattr(
        batch_worker,
        "extract_critical_value_018_stage2_facts",
        extract_018,
    )
    observed_contexts: list[dict[str, Any]] = []

    def execute(
        context: dict[str, Any], _rule_ids: tuple[str, ...]
    ) -> Luxian0916Execution:
        observed_contexts.append(context)
        return _complete_execution()

    monkeypatch.setattr(batch_worker, "execute_luxian_0916", execute)

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert len(captured) == 1
    assert captured[0]["scene"] == "running"
    assert callable(captured[0]["generate"])
    assert observed_contexts[0]["event_facts"]["critical_values"][0][
        "stage2_state_by_rule"
    ] == {"LX0916-018": "ready"}
    assert workspace.completed is not None
    summary = workspace.completed["summary"]
    assert summary["critical_value_018_stage2_llm_call_count"] == 1
    assert summary["critical_value_018_stage2_prompt_tokens"] == 90
    assert summary["critical_value_018_stage2_completion_tokens"] == 18
    assert summary["critical_value_018_stage2_total_tokens"] == 108
    assert summary["critical_value_018_stage2_model_elapsed_ms"] == 140
    assert summary["critical_value_018_stage2_failure_count"] == 0
    assert summary["critical_value_018_stage2_usage_incomplete_count"] == 0
    assert summary["critical_value_018_stage2_model_parameters"] == [
        {
            "provider_code": "aliyun_bailian",
            "model": "qwen3.8-flash",
            "temperature": 0,
            "top_p": 1,
            "enable_thinking": False,
            "max_completion_tokens": 2048,
            "allow_length_retry": False,
            "response_format": "json_object",
        }
    ]


@pytest.mark.asyncio
async def test_batch_worker_contains_invalid_018_stage2_output_to_018(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    event = {
        "event_type": "critical_values",
        "event_id": "critical-value:REPORT-1",
        "trigger_confirmed": True,
        "event_time": "2026-09-16 08:00:00",
    }
    monkeypatch.setattr(
        batch_worker,
        "build_critical_value_018_facts",
        lambda **_kwargs: {
            "event_facts": {"critical_values": [event]},
            "event_source_state_by_rule": {
                "LX0916-018": "critical_value_source_complete"
            },
        },
    )

    async def invalid_stage2(**_kwargs: Any) -> object:
        return None

    monkeypatch.setattr(
        batch_worker,
        "extract_critical_value_018_stage2_facts",
        invalid_stage2,
    )
    observed: list[dict[str, Any]] = []

    def execute(
        context: dict[str, Any], _rule_ids: tuple[str, ...]
    ) -> Luxian0916Execution:
        observed.append(context)
        return _complete_execution()

    monkeypatch.setattr(batch_worker, "execute_luxian_0916", execute)

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.completed is not None
    protected = observed[0]["event_facts"]["critical_values"][0]
    assert protected["event_id"] == "critical-value:REPORT-1"
    assert protected["stage2_state_by_rule"] == {
        "LX0916-018": "internal_failure"
    }
    assert protected["evaluation_window_mature"] is True
    assert workspace.completed["summary"][
        "critical_value_018_stage2_failure_count"
    ] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("disposition_state", "expected_status", "expected_reason"),
    (
        (
            "absent",
            "non_compliant",
            "critical_value_documentation_incomplete",
        ),
        ("present", "compliant", "critical_value_documentation_complete"),
    ),
)
async def test_running_worker_delivers_real_018_pipeline_result(
    monkeypatch: pytest.MonkeyPatch,
    disposition_state: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    calls: list[dict[str, Any]] = []

    async def generate(_prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _critical_value_018_model_response(
            disposition_state=disposition_state
        )

    item, summary = await _run_real_critical_value_018_worker(
        monkeypatch,
        generate=generate,
    )

    assert item["status"] == expected_status
    assert item["reason_code"] == expected_reason
    assert len(calls) == 1
    assert calls[0]["enable_thinking"] is False
    assert summary["critical_value_018_stage2_llm_call_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ("provider_error", "contract_error"))
async def test_running_worker_contains_real_018_stage2_failure_as_data_gap(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    calls = 0

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if failure_mode == "provider_error":
            raise RuntimeError("provider unavailable")
        return {
            "choices": [
                {"finish_reason": "stop", "message": {"content": "{}"}}
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 1,
                "total_tokens": 11,
            },
        }

    item, summary = await _run_real_critical_value_018_worker(
        monkeypatch,
        generate=generate,
    )

    assert item["status"] == "data_quality_gap"
    assert item["reason_code"] == "critical_value_stage2_fact_unavailable"
    assert calls == 1
    assert summary["critical_value_018_stage2_llm_call_count"] == 1


@pytest.mark.asyncio
async def test_batch_worker_runs_stage2_only_for_structured_triggers_and_summarizes_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    event = {
        "event_type": "disease_changes",
        "event_id": "severity-order:ORDER-1",
        "event_source_type": "inpat_nondrug_order",
        "event_source_id": "ORDER-1",
        "event_time": "2026-09-16 08:00:00",
        "event_kind": "severity_critical",
        "trigger_confirmed": True,
    }
    monkeypatch.setattr(
        batch_worker,
        "load_disease_change_015016_facts",
        lambda **_kwargs: {
            "event_facts": {"disease_changes": [event]},
            "event_source_state_by_rule": {
                "LX0916-015": "structured_complete",
                "LX0916-016": "structured_complete",
            },
            "diagnostic": {"llm_call_count": 0},
        },
    )
    captured: list[dict[str, Any]] = []

    async def extract_stage2(**kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs)
        enriched = {
            **event,
            "stage2_state_by_rule": {
                "LX0916-015": "ready",
                "LX0916-016": "ready",
            },
            "stage2_facts": [],
        }
        return {
            "event_facts": {"disease_changes": [enriched]},
            "event_source_state_by_rule": {
                "LX0916-015": "structured_complete",
                "LX0916-016": "structured_complete",
            },
            "diagnostic": {
                "code": "disease_change_stage2_ready",
                "event_count": 1,
                "llm_call_count": 1,
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "model_elapsed_ms": 250,
                "failure_count": 0,
            },
        }

    monkeypatch.setattr(
        batch_worker, "extract_disease_change_stage2_facts", extract_stage2
    )
    observed_contexts: list[dict[str, Any]] = []

    def execute(
        context: dict[str, Any], _rule_ids: tuple[str, ...]
    ) -> Luxian0916Execution:
        observed_contexts.append(context)
        return _complete_execution()

    monkeypatch.setattr(batch_worker, "execute_luxian_0916", execute)

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert len(captured) == 1
    assert captured[0]["evidence_payload"]["programmatic_timeline"]["documents"] == {}
    assert captured[0]["scene"] == "running"
    assert callable(captured[0]["generate"])
    assert observed_contexts[0]["event_facts"]["disease_changes"][0][
        "stage2_state_by_rule"
    ] == {"LX0916-015": "ready", "LX0916-016": "ready"}
    assert workspace.completed is not None
    summary = workspace.completed["summary"]
    assert summary["disease_change_stage2_llm_call_count"] == 1
    assert summary["disease_change_stage2_prompt_tokens"] == 120
    assert summary["disease_change_stage2_completion_tokens"] == 30
    assert summary["disease_change_stage2_total_tokens"] == 150
    assert summary["disease_change_stage2_model_elapsed_ms"] == 250
    assert summary["disease_change_stage2_failure_count"] == 0
    assert summary["disease_change_stage2_usage_incomplete_count"] == 0


@pytest.mark.asyncio
async def test_batch_worker_contains_unexpected_stage2_failure_to_015016(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    event = {
        "event_type": "disease_changes",
        "event_id": "severity-order:ORDER-1",
        "event_source_type": "inpat_nondrug_order",
        "event_source_id": "ORDER-1",
        "event_time": "2026-09-16 08:00:00",
        "event_kind": "severity_critical",
        "trigger_confirmed": True,
    }
    monkeypatch.setattr(
        batch_worker,
        "load_disease_change_015016_facts",
        lambda **_kwargs: {
            "event_facts": {"disease_changes": [event]},
            "event_source_state_by_rule": {
                "LX0916-015": "structured_complete",
                "LX0916-016": "structured_complete",
            },
            "diagnostic": {"llm_call_count": 0},
        },
    )

    async def fail_stage2(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("private provider detail")

    monkeypatch.setattr(
        batch_worker, "extract_disease_change_stage2_facts", fail_stage2
    )
    observed: list[dict[str, Any]] = []

    def execute(
        context: dict[str, Any], _rule_ids: tuple[str, ...]
    ) -> Luxian0916Execution:
        observed.append(context)
        return Luxian0916Execution(
            results=tuple(_result(rule.rule_id) for rule in LUXIAN_0916_RULE_CATALOG)
        )

    monkeypatch.setattr(batch_worker, "execute_luxian_0916", execute)

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.failed == []
    assert workspace.completed is not None
    assert workspace.completed["summary"]["success_count"] == 1
    assert workspace.completed["summary"]["disease_change_stage2_failure_count"] == 2
    assert (
        workspace.completed["summary"]["disease_change_stage2_usage_incomplete_count"]
        == 1
    )
    protected_event = observed[0]["event_facts"]["disease_changes"][0]
    assert protected_event["stage2_state_by_rule"] == {
        "LX0916-015": "internal_failure",
        "LX0916-016": "internal_failure",
    }
    assert "stage2_facts" not in protected_event


@pytest.mark.asyncio
async def test_batch_worker_contains_invalid_stage2_output_to_015016(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    event = {
        "event_type": "disease_changes",
        "event_id": "severity-order:ORDER-1",
        "event_source_type": "inpat_nondrug_order",
        "event_source_id": "ORDER-1",
        "event_time": "2026-09-16 08:00:00",
        "event_kind": "severity_critical",
        "trigger_confirmed": True,
    }
    monkeypatch.setattr(
        batch_worker,
        "load_disease_change_015016_facts",
        lambda **_kwargs: {
            "event_facts": {"disease_changes": [event]},
            "event_source_state_by_rule": {
                "LX0916-015": "structured_complete",
                "LX0916-016": "structured_complete",
            },
        },
    )

    async def invalid_stage2(**_kwargs: Any) -> object:
        return None

    monkeypatch.setattr(
        batch_worker, "extract_disease_change_stage2_facts", invalid_stage2
    )
    observed: list[dict[str, Any]] = []

    def execute(
        context: dict[str, Any], _rule_ids: tuple[str, ...]
    ) -> Luxian0916Execution:
        observed.append(context)
        return _complete_execution()

    monkeypatch.setattr(batch_worker, "execute_luxian_0916", execute)

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.failed == []
    assert workspace.completed is not None
    assert observed[0]["event_facts"]["disease_changes"][0]["stage2_state_by_rule"] == {
        "LX0916-015": "internal_failure",
        "LX0916-016": "internal_failure",
    }


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
        lambda *_args: _complete_execution(),
    )

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.failed == []
    assert workspace.completed is not None
    assert workspace.completed["persist_record_envelopes"] is False
    assert workspace.completed["summary"]["execution_status"] == "partial_failed"
    assert workspace.completed["summary"]["success_count"] == 1
    assert workspace.completed["summary"]["failed_count"] == 1
    assert workspace.completed["summary"]["completed_rule_count"] == 32
    assert workspace.completed["summary"]["failed_rule_count"] == 32
    assert workspace.completed["items"][0]["visit_id"] == "OK"
    assert len(workspace.completed["failed_records"]) == 32
    assert {
        failure["rule_id"] for failure in workspace.completed["failed_records"]
    } == {rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG}
    assert all(
        failure["visit_id"] == "BROKEN"
        and failure["error_phase"] == "record_execution"
        and failure["error_type"] == "LookupError"
        for failure in workspace.completed["failed_records"]
    )


@pytest.mark.asyncio
async def test_rule_failure_marks_partial_failed_without_illegal_customer_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: Luxian0916Execution(
            results=tuple(
                _result(
                    rule.rule_id,
                    status=(
                        "data_quality_gap"
                        if rule.rule_id == "LX0916-001"
                        else "compliant"
                    ),
                )
                for rule in LUXIAN_0916_RULE_CATALOG
                if rule.rule_id != "LX0916-002"
            ),
            failures=(Luxian0916RuleFailure("LX0916-002", "TimeoutError"),),
        ),
    )

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.completed is not None
    assert workspace.completed["persist_record_envelopes"] is False
    assert workspace.completed["items"][0]["status"] == "data_quality_gap"
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
    assert workspace.completed["summary"]["execution_status"] == "partial_failed"
    assert workspace.completed["summary"]["success_count"] == 0
    assert workspace.completed["summary"]["failed_count"] == 1
    assert workspace.completed["summary"]["completed_rule_count"] == 31
    assert workspace.completed["summary"]["failed_rule_count"] == 1


@pytest.mark.asyncio
async def test_all_rule_failures_mark_task_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: Luxian0916Execution(
            results=(),
            failures=tuple(
                Luxian0916RuleFailure(rule.rule_id, "TimeoutError")
                for rule in LUXIAN_0916_RULE_CATALOG
            ),
        ),
    )

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.completed is not None
    assert workspace.completed["items"] == []
    assert len(workspace.completed["failed_records"]) == 32
    assert workspace.completed["summary"]["execution_status"] == "failed"
    assert workspace.completed["summary"]["success_count"] == 0
    assert workspace.completed["summary"]["failed_count"] == 1
    assert workspace.completed["summary"]["completed_rule_count"] == 0
    assert workspace.completed["summary"]["failed_rule_count"] == 32


@pytest.mark.asyncio
async def test_batch_worker_persists_one_locatable_semantic_extraction_failure_per_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(
        job=_job(),
        records=[_record(), _record(patient_id="P-2", visit_id="V-2")],
    )
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0916_bundle",
        lambda **_kwargs: {
            "structured_context": {},
            "source_documents": [
                {
                    "document_id": "A-1",
                    "source_table": "admission_record",
                    "content": "受控测试文书",
                }
            ],
        },
    )
    monkeypatch.setattr(
        batch_worker,
        "build_programmatic_evidence_payload",
        lambda **_kwargs: {
            "programmatic_timeline": {
                "documents": {
                    "admission_record": [
                        {"document_id": "A-1", "content": "受控测试文书"}
                    ]
                }
            }
        },
    )
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: _complete_execution(),
    )

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916",
        workspace=workspace,
        semantic_generate=_invalid_semantic_generate,
    )

    assert workspace.completed is not None
    summary = workspace.completed["summary"]
    assert summary["semantic_llm_call_count"] == 2
    assert summary["semantic_extraction_invalid_count"] == 2
    assert summary["semantic_extraction_failures"] == [
        {
            "institute_id": "I-1",
            "patient_id": "P-1",
            "visit_id": "V-1",
            "record_id": "V-1",
            "code": "semantic_extraction_invalid",
            "document_count": 1,
            "llm_call_count": 1,
            "failure_stage": "json_syntax",
        },
        {
            "institute_id": "I-1",
            "patient_id": "P-2",
            "visit_id": "V-2",
            "record_id": "V-2",
            "code": "semantic_extraction_invalid",
            "document_count": 1,
            "llm_call_count": 1,
            "failure_stage": "json_syntax",
        },
    ]
    assert all(
        "patient_name" not in item and "content" not in item
        for item in summary["semantic_extraction_failures"]
    )


@pytest.mark.asyncio
async def test_batch_worker_persists_locatable_successful_contract_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(job=_job(), records=[_record()])
    _patch_loaders(monkeypatch)

    async def extract(**_kwargs: Any) -> dict[str, Any]:
        return {
            "semantic_facts": {},
            "event_facts": {},
            "document_facts": {},
            "discharge_facts": {},
            "event_source_state_by_rule": {},
            "diagnostic": {
                "code": "semantic_extraction_ready",
                "document_count": 1,
                "llm_call_count": 2,
                "contract_retry_applied": True,
                "contract_retry_detail": "invalid_course_event_item_fields",
            },
        }

    monkeypatch.setattr(batch_worker, "extract_luxian_0916_facts", extract)
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: _complete_execution(),
    )

    await batch_worker.run_luxian_0916_batch_job(
        "job-0916", workspace=workspace, semantic_generate=_semantic_generate
    )

    assert workspace.completed is not None
    summary = workspace.completed["summary"]
    assert summary["semantic_llm_call_count"] == 2
    assert summary["semantic_extraction_invalid_count"] == 0
    assert summary["semantic_contract_retry_count"] == 1
    assert summary["semantic_contract_retries"] == [
        {
            "institute_id": "I-1",
            "patient_id": "P-1",
            "visit_id": "V-1",
            "record_id": "V-1",
            "code": "semantic_contract_retry_applied",
            "llm_call_count": 2,
            "contract_retry_detail": "invalid_course_event_item_fields",
        }
    ]
    assert "patient_name" not in summary["semantic_contract_retries"][0]


def test_semantic_extraction_failure_only_persists_allowed_contract_detail() -> None:
    identity = {"institute_id": "I-1", "patient_id": "P-1", "visit_id": "V-1"}
    record = {"record_id": "V-1"}
    allowed = batch_worker._semantic_extraction_failure(
        identity=identity,
        record=record,
        diagnostic={
            "code": "semantic_extraction_invalid",
            "document_count": 1,
            "llm_call_count": 1,
            "failure_stage": "contract_validation",
            "failure_detail": "invalid_course_event_documentation_fields",
            "contract_retry_detail": "invalid_course_event_item_fields",
        },
    )
    rejected = batch_worker._semantic_extraction_failure(
        identity=identity,
        record=record,
        diagnostic={
            "code": "semantic_extraction_invalid",
            "document_count": 1,
            "llm_call_count": 1,
            "failure_stage": "contract_validation",
            "failure_detail": "private exception or patient content",
        },
    )

    assert allowed["failure_detail"] == "invalid_course_event_documentation_fields"
    assert allowed["contract_retry_detail"] == "invalid_course_event_item_fields"
    assert "failure_detail" not in rejected


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
