from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping


class _ControlledClient:
    def __init__(self, responses: list[Mapping[str, Any]]) -> None:
        self._responses = [dict(item) for item in responses]

    async def generate(self, _prompt: str) -> dict[str, Any]:
        response = self._responses.pop(0)
        return {
            "content": json.dumps(response["payload"], ensure_ascii=False),
            "usage": dict(response["usage"]),
            "_api_time": response["api_time"],
        }


def test_synthetic_benchmark_runs_one_warmup_and_ten_formal_rounds() -> None:
    from scripts import run_luxian_0609_consultation_synthetic_benchmark10 as benchmark
    from scripts import verify_consultation_family_acceptance as verify

    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )
    fixture = verify._load_fixture(fixture_path)

    report = asyncio.run(
        benchmark.run_benchmark10(
            fixture_path,
            client_factory=lambda: _ControlledClient(fixture["responses"]),
        )
    )

    assert report["formal_round_count"] == 10
    assert report["formal_rounds_completed"] == 10
    assert report["benchmark_passed"] is True
    assert report["warmup"]["round"] == 0
    assert report["warmup"]["warmup"] is True
    assert [item["round"] for item in report["runs"]] == list(range(1, 11))
    assert all(item["warmup"] is False for item in report["runs"])
    assert report["prompt_equal_all_formal_rounds"] is True
    assert report["usage_conserved_all_formal_rounds"] is True
    assert all(item["http_attempt_count"] is None for item in report["runs"])
    assert all(
        item["http_attempt_count_state"] == "unavailable_without_public_execution_trace"
        for item in report["runs"]
    )
    # 第一阶段、执行判断与会诊措施逐项核对（2026-10-12）各 1 次。
    assert all(item["logical_llm_call_count"] == 3 for item in report["runs"])
    assert all(item["delegate_generate_count"] == 3 for item in report["runs"])
    assert all(
        item["usage_conservation"] == {
            "execution": {
                "prompt_tokens": 39,
                "completion_tokens": 12,
                "total_tokens": 51,
            },
            "delegate_responses": {
                "prompt_tokens": 39,
                "completion_tokens": 12,
                "total_tokens": 51,
            },
            "conserved": True,
        }
        for item in report["runs"]
    )
    assert report["execution_mode"] == "controlled"
    assert report["network_observation"] == "unknown"
    assert all(
        item["status_by_rule"]
        == {
            "LX0609-03-01-01": "compliant",
            # 合成病例只有会诊意见、没有会诊申请内容，021 按现行口径不适用。
            "LX0609-03-01-02": "not_applicable",
            "LX0609-03-01-03": "compliant",
            "LX0609-03-01-04": "compliant",
        }
        for item in report["runs"]
    )
    assert all(
        item["reason_code_by_rule"]
        == {
            "LX0609-03-01-01": "requirement_satisfied",
            "LX0609-03-01-02": "trigger_absent_complete",
            "LX0609-03-01-03": "requirement_satisfied",
            "LX0609-03-01-04": "requirement_satisfied",
        }
        for item in report["runs"]
    )


def test_synthetic_benchmark_stops_when_warmup_fails() -> None:
    from scripts import run_luxian_0609_consultation_synthetic_benchmark10 as benchmark

    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )

    class _FailingClient:
        async def generate(self, _prompt: str) -> dict[str, Any]:
            raise TimeoutError("synthetic timeout")

    report = asyncio.run(
        benchmark.run_benchmark10(
            fixture_path,
            client_factory=_FailingClient,
        )
    )

    assert report["aborted_after_warmup_failure"] is True
    assert report["benchmark_passed"] is False
    assert report["formal_round_count"] == 0
    assert report["runs"] == []
    assert report["warmup"]["run_status"] == "technical_error"
    assert report["warmup"]["failure_kind"] == "native_technical_error"


def test_synthetic_benchmark_rejects_native_technical_result_without_delegate_exception() -> None:
    from scripts import run_luxian_0609_consultation_synthetic_benchmark10 as benchmark

    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )

    class _MalformedResponseClient:
        async def generate(self, _prompt: str) -> dict[str, Any]:
            return {
                "content": "not-json",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "_api_time": 0.001,
            }

    report = asyncio.run(
        benchmark.run_benchmark10(
            fixture_path,
            client_factory=_MalformedResponseClient,
        )
    )

    assert report["benchmark_passed"] is False
    assert report["aborted_after_warmup_failure"] is True
    assert report["warmup"]["failure_kind"] == "native_technical_error"


def test_synthetic_benchmark_rejects_usage_non_conservation() -> None:
    from scripts import run_luxian_0609_consultation_synthetic_benchmark10 as benchmark
    from scripts import verify_consultation_family_acceptance as verify

    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )
    fixture = verify._load_fixture(fixture_path)
    class _UsageDriftClient(_ControlledClient):
        async def generate(self, prompt: str) -> dict[str, Any]:
            response = await super().generate(prompt)
            response["_usage_breakdown"] = {
                "prompt_tokens": 999,
                "completion_tokens": 999,
                "total_tokens": 1998,
            }
            return response

    report = asyncio.run(
        benchmark.run_benchmark10(
            fixture_path,
            client_factory=lambda: _UsageDriftClient(deepcopy(fixture["responses"])),
        )
    )

    assert report["benchmark_passed"] is False
    assert report["aborted_after_warmup_failure"] is True
    assert report["warmup"]["gate"]["usage_conserved"] is False


def test_synthetic_benchmark_rejects_prompt_drift() -> None:
    from scripts import run_luxian_0609_consultation_synthetic_benchmark10 as benchmark
    from scripts import verify_consultation_family_acceptance as verify

    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )
    fixture = verify._load_fixture(fixture_path)
    factory_calls = 0

    class _PromptDriftClient(_ControlledClient):
        def __init__(self, responses: list[Mapping[str, Any]], *, drift: bool) -> None:
            super().__init__(responses)
            self._drift = drift

        async def generate(self, prompt: str) -> dict[str, Any]:
            response = await super().generate(prompt)
            if self._drift and self._responses:
                payload = json.loads(response["content"])
                recommendation = payload["consultation_event_facts"][0]["recommendations"][0]
                recommendation["source_quote"] = "继续保肝治疗"
                recommendation["normalized_action"] = "继续保肝治疗"
                response["content"] = json.dumps(payload, ensure_ascii=False)
            return response

    def client_factory() -> _PromptDriftClient:
        nonlocal factory_calls
        client = _PromptDriftClient(
            deepcopy(fixture["responses"]),
            drift=factory_calls > 0,
        )
        factory_calls += 1
        return client

    report = asyncio.run(
        benchmark.run_benchmark10(fixture_path, client_factory=client_factory)
    )

    assert report["benchmark_passed"] is False
    assert any(item["prompt_equal_to_reference"] is False for item in report["runs"])
