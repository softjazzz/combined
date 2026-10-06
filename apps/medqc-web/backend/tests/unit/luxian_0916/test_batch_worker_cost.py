from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
import json
from typing import Any

import pytest

from app.services.luxian_0916 import batch_worker
from app.services.luxian_0916.contracts import Luxian0916RuleResult
from app.services.luxian_0916.orchestrator import Luxian0916Execution
from app.services.luxian_0916.rule_catalog import LUXIAN_0916_RULE_CATALOG
from app.services.luxian_0916.semantic_extractor import extract_luxian_0916_facts


class Workspace:
    def __init__(self, count: int = 1, job_id: str = "cost-job") -> None:
        self.job = {
            "id": job_id,
            "scope": "running",
            "filters": {
                "rule_set_key": batch_worker.LUXIAN_0916_RULE_SET_KEY,
            },
        }
        self.records = [
            {
                "institute_id": "I",
                "patient_id": f"P{i}",
                "visit_id": f"V{i}",
                "record_id": f"V{i}",
            }
            for i in range(count)
        ]
        self.completed: dict[str, Any] | None = None
        self.failed: list[dict[str, Any]] = []

    def get_batch_job_for_processing(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["job_id"] == self.job["id"]
        return self.job

    def mark_batch_job_running(self, **kwargs: Any) -> bool:
        return True

    def collect_records(self, **kwargs: Any) -> list[dict[str, str]]:
        return self.records

    def hydrate_records_with_medical_text(
        self,
        records: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        return records

    def update_batch_job_progress(self, **kwargs: Any) -> None:
        pass

    def complete_batch_job(self, **kwargs: Any) -> None:
        self.completed = kwargs

    def fail_batch_job(self, **kwargs: Any) -> None:
        self.failed.append(kwargs)


@pytest.fixture
def boundaries(monkeypatch: pytest.MonkeyPatch) -> tuple[Luxian0916RuleResult, ...]:
    """隔离外部读取，保留 Worker 的实际逐病例与交付校验流程。"""
    monkeypatch.setattr(batch_worker, "load_luxian_0916_bundle", lambda **kwargs: {})
    monkeypatch.setattr(
        batch_worker, "build_programmatic_evidence_payload", lambda **kwargs: {}
    )
    monkeypatch.setattr(
        batch_worker, "add_luxian_0916_evidence_sources", lambda **kwargs: {}
    )
    monkeypatch.setattr(batch_worker, "build_luxian_0916_context", lambda **kwargs: {})
    monkeypatch.setattr(
        batch_worker, "merge_luxian_0916_semantic_facts", lambda **kwargs: {}
    )
    monkeypatch.setattr(
        batch_worker, "build_critical_value_018_facts", lambda **kwargs: {}
    )
    monkeypatch.setattr(
        batch_worker, "load_disease_change_015016_facts", lambda **kwargs: {}
    )
    monkeypatch.setattr(
        batch_worker, "merge_critical_value_018_facts", lambda **kwargs: {}
    )
    monkeypatch.setattr(
        batch_worker, "merge_disease_change_015016_facts", lambda **kwargs: {}
    )
    results = tuple(
        Luxian0916RuleResult(
            rule_id=rule_id,
            status="compliant",
            reason_code="document_complete",
            findings="判定原文",
            evidence=("证据原文",),
            suggestion="建议原文",
            document_anchors=(
                {"document_type": "admission_record", "document_id": "A"},
            ),
            decision_facts={"unchanged": True},
            diagnostics={"origin": "executor"},
        )
        for rule_id in (rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)
    )
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: Luxian0916Execution(results=results),
    )

    async def no_stage2(**kwargs: Any) -> dict[str, Any]:
        return {"diagnostic": {"total_tokens": 99999, "model_elapsed_ms": 99999}}

    async def shared(**kwargs: Any) -> dict[str, Any]:
        await kwargs["generate"]("shared", response_format={"type": "json_object"})
        return {"diagnostic": {"llm_call_count": 1}}

    monkeypatch.setattr(batch_worker, "extract_luxian_0916_facts", shared)
    monkeypatch.setattr(
        batch_worker, "extract_critical_value_018_stage2_facts", no_stage2
    )
    monkeypatch.setattr(batch_worker, "extract_disease_change_stage2_facts", no_stage2)
    return results


def response(tokens: Any = 10, seconds: Any = 0.5) -> dict[str, Any]:
    return {
        "_usage_breakdown": {"total_tokens": tokens},
        "usage": {"total_tokens": 1},
        "_api_time": seconds,
    }


async def run(
    workspace: Workspace,
    generate: batch_worker.SemanticGenerate,
    concurrency: int = 4,
) -> dict[str, Any]:
    await batch_worker.run_luxian_0916_batch_job(
        workspace.job["id"],
        workspace=workspace,
        max_record_concurrency=concurrency,
        semantic_generate=generate,
    )
    assert not workspace.failed
    assert workspace.completed is not None
    return workspace.completed["summary"]


def assert_cost(
    summary: dict[str, Any],
    tokens: int,
    seconds: float,
    calls: int,
    usage_missing: int = 0,
    time_missing: int = 0,
) -> None:
    assert summary["total_tokens"] == tokens
    assert summary["total_processing_time"] == pytest.approx(seconds)
    assert summary["llm_generate_call_count"] == calls
    assert summary["llm_usage_incomplete_count"] == usage_missing
    assert summary["llm_time_incomplete_count"] == time_missing
    assert summary["llm_usage_complete"] is (usage_missing == 0)
    assert summary["llm_time_complete"] is (time_missing == 0)


@pytest.mark.asyncio
async def test_four_concurrent_known_costs_preserve_response_and_clinical_fields(
    boundaries: tuple[Luxian0916RuleResult, ...],
) -> None:
    workspace = Workspace(4)
    # 仅复用已保存 v2 产物的去标识成本 metadata，不重放整包模型输出。
    responses = [
        response(tokens, seconds)
        for tokens, seconds in [
            (4795, 21.108564615249634),
            (5453, 22.99766182899475),
            (5486, 24.258418560028076),
            (4753, 18.483602285385132),
        ]
    ]
    original = copy.deepcopy(responses)
    active = peak = index = 0
    all_started = asyncio.Event()

    async def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal active, peak, index
        assert args == ("shared",)
        assert kwargs == {"response_format": {"type": "json_object"}}
        current = index
        index += 1
        active += 1
        peak = max(peak, active)
        if active == 4:
            all_started.set()
        await asyncio.wait_for(all_started.wait(), timeout=2)
        active -= 1
        return responses[current]

    summary = await run(workspace, generate)
    assert peak == 4
    assert_cost(summary, 20487, 86.84824728965759, 4)
    assert responses == original
    for item in workspace.completed["items"]:
        expected = next(
            result.to_dict()
            for result in boundaries
            if result.rule_id == item["rule_id"]
        )
        assert {key: item[key] for key in expected} == expected
    assert workspace.completed["persist_record_envelopes"] is False


@pytest.mark.asyncio
async def test_real_shared_contract_retry_and_both_stage2_calls_count_once(
    boundaries: tuple[Luxian0916RuleResult, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        batch_worker, "extract_luxian_0916_facts", extract_luxian_0916_facts
    )
    monkeypatch.setattr(
        batch_worker,
        "add_luxian_0916_evidence_sources",
        lambda **kwargs: {
            "programmatic_timeline": {
                "documents": {
                    "admission_record": [
                        {"document_id": "A", "content": "入院记录正文"},
                    ]
                }
            },
        },
    )
    observed = []

    async def stage2(**kwargs: Any) -> dict[str, Any]:
        received = await kwargs["generate"]("stage2", max_completion_tokens=50)
        assert received is observed[-1]
        return {"diagnostic": {"llm_call_count": 1, "total_tokens": 99999}}

    monkeypatch.setattr(batch_worker, "extract_critical_value_018_stage2_facts", stage2)
    monkeypatch.setattr(batch_worker, "extract_disease_change_stage2_facts", stage2)

    async def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = response(100 + len(observed), 1)
        content = {
            "semantic_facts": {},
            "event_facts": {},
            "document_facts": {},
            "discharge_facts": {},
        }
        if not observed:
            content["event_facts"] = {"unrecognized_event": []}
        result["choices"] = [{"message": {"content": json.dumps(content)}}]
        observed.append(result)
        return result

    summary = await run(Workspace(), generate)
    assert summary["semantic_contract_retry_count"] == 1
    assert summary["semantic_llm_call_count"] == 2
    assert summary["critical_value_018_stage2_llm_call_count"] == 1
    assert summary["disease_change_stage2_llm_call_count"] == 1
    assert_cost(summary, 406, 4, 4)


@pytest.mark.asyncio
async def test_no_generate_is_complete_zero(
    boundaries: tuple[Luxian0916RuleResult, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_shared(**kwargs: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(batch_worker, "extract_luxian_0916_facts", no_shared)

    async def forbidden(*args: Any, **kwargs: Any) -> dict[str, Any]:
        pytest.fail("未触发模型时不得调用 generate")

    assert_cost(await run(Workspace(), forbidden), 0, 0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result,tokens,seconds,usage_missing,time_missing",
    [
        ({"usage": {"total_tokens": 7}, "_api_time": 0}, 7, 0, 0, 0),
        (
            {"_usage_breakdown": {}, "usage": {"total_tokens": 7}, "_api_time": 1},
            7,
            1,
            0,
            0,
        ),
        ({"_usage_breakdown": {"total_tokens": 0}, "_api_time": 1}, 0, 1, 1, 0),
        (
            {
                "_usage_breakdown": {"total_tokens": 0},
                "usage": {"total_tokens": 0},
                "_api_time": 0,
            },
            0,
            0,
            0,
            0,
        ),
        ({}, 0, 0, 1, 1),
        (response(True, True), 0, 0, 1, 1),
        (response(-1, -1), 0, 0, 1, 1),
        (response(1.5, float("nan")), 0, 0, 1, 1),
        (response("12", float("inf")), 0, 0, 1, 1),
        ({"usage": {"total_tokens": False}, "_api_time": "2"}, 0, 0, 1, 1),
    ],
)
async def test_missing_invalid_or_synthetic_stats_remain_explicit(
    boundaries: tuple[Luxian0916RuleResult, ...],
    result: dict[str, Any],
    tokens: int,
    seconds: float,
    usage_missing: int,
    time_missing: int,
) -> None:
    original = copy.deepcopy(result)

    async def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return result

    summary = await run(Workspace(), generate)
    assert_cost(summary, tokens, seconds, 1, usage_missing, time_missing)
    assert summary["execution_status"] == "completed"
    assert result.keys() == original.keys()


@pytest.mark.asyncio
async def test_exception_passes_through_and_retains_known_prior_cost(
    boundaries: tuple[Luxian0916RuleResult, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = TimeoutError("private provider detail")
    calls = 0

    async def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise error
        return response(20, 2)

    async def shared(**kwargs: Any) -> dict[str, Any]:
        await kwargs["generate"]("first")
        try:
            await kwargs["generate"]("second")
        except TimeoutError as caught:
            assert caught is error
            return {
                "diagnostic": {
                    "code": "semantic_extraction_invalid",
                    "failure_stage": "generation",
                    "failed_rule_ids": ["LX0916-010"],
                    "llm_call_count": 2,
                }
            }
        pytest.fail("generate 异常必须原样传播")

    monkeypatch.setattr(batch_worker, "extract_luxian_0916_facts", shared)
    workspace = Workspace()
    summary = await run(workspace, generate)
    assert_cost(summary, 20, 2, 2, 1, 1)
    assert summary["execution_status"] == "completed"
    assert "private provider detail" not in str(workspace.completed)


@pytest.mark.asyncio
async def test_concurrent_jobs_keep_costs_local(
    boundaries: tuple[Luxian0916RuleResult, ...],
) -> None:
    async def cheap(*args: Any, **kwargs: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        return response(3, 1)

    async def expensive(*args: Any, **kwargs: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        return response(90, 5)

    first, second = await asyncio.gather(
        run(Workspace(2, "cheap"), cheap),
        run(Workspace(3, "expensive"), expensive),
    )
    assert_cost(first, 6, 2, 2)
    assert_cost(second, 270, 15, 3)


@pytest.mark.asyncio
async def test_real_shared_generation_failure_preserves_failure_transport(
    boundaries: tuple[Luxian0916RuleResult, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        batch_worker, "extract_luxian_0916_facts", extract_luxian_0916_facts
    )
    monkeypatch.setattr(
        batch_worker,
        "add_luxian_0916_evidence_sources",
        lambda **kwargs: {
            "programmatic_timeline": {
                "documents": {
                    "admission_record": [
                        {"document_id": "A", "content": "入院记录正文"},
                    ]
                }
            },
        },
    )
    results = tuple(
        replace(
            result,
            status="data_quality_gap",
            reason_code="semantic_fact_unavailable",
            decision_facts={},
        )
        if result.rule_id == "LX0916-002"
        else result
        for result in boundaries
    )
    monkeypatch.setattr(
        batch_worker,
        "execute_luxian_0916",
        lambda *_args: Luxian0916Execution(results=results),
    )

    async def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise TimeoutError("private failure detail")

    workspace = Workspace()
    summary = await run(workspace, generate)
    assert_cost(summary, 0, 0, 1, 1, 1)
    assert summary["execution_status"] == "partial_failed"
    assert workspace.completed["failed_records"] == [
        {
            "institute_id": "I",
            "patient_id": "P0",
            "visit_id": "V0",
            "record_id": "V0",
            "error_phase": "semantic_extraction",
            "rule_id": "LX0916-002",
            "error_type": "SemanticGenerationError",
        }
    ]
    assert len(workspace.completed["items"]) == 31
    assert "private failure detail" not in str(workspace.completed)
