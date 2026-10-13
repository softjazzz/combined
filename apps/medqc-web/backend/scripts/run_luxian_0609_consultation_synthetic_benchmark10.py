"""LX0609 会诊 020–023 合成资料真实模型手动基准。

该脚本只读取显式提供的合成夹具；不会读取业务数据库或病历。它必须由操作者
显式传入 --real-model 才会构造真实模型客户端，不能用于 CI。
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
from statistics import median
import sys
import time
from typing import Any, Callable, Mapping, Sequence


_RULE_IDS = ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04")
_FORMAL_ROUNDS = 10
# 合成病例只有会诊意见、没有会诊申请内容：021 会诊申请单按现行口径为不适用。
_EXPECTED_STATUS_BY_RULE = {
    rule_id: "not_applicable" if rule_id == "LX0609-03-01-02" else "compliant"
    for rule_id in _RULE_IDS
}
_EXPECTED_REASON_BY_RULE = {
    rule_id: "trigger_absent_complete" if rule_id == "LX0609-03-01-02" else "requirement_satisfied"
    for rule_id in _RULE_IDS
}


class _BenchmarkClient:
    """只在内存记录合成基准的调用统计与 Prompt，不输出 Prompt。"""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.prompts: list[str] = []
        self.response_usage: list[dict[str, int]] = []
        self.delegate_generate_count = 0

    async def generate(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.delegate_generate_count += 1
        response = await self._delegate.generate(prompt)
        if not isinstance(response, Mapping):
            raise TypeError("benchmark LLM response must be an object")
        self.response_usage.append(_usage_from_response(response))
        return dict(response)


def _usage_from_response(response: Mapping[str, Any]) -> dict[str, int]:
    raw_usage = response.get("_usage_breakdown")
    if not isinstance(raw_usage, Mapping):
        raw_usage = response.get("usage")
    raw_usage = raw_usage if isinstance(raw_usage, Mapping) else {}
    prompt = int(raw_usage.get("prompt_tokens") or raw_usage.get("input_tokens") or 0)
    completion = int(
        raw_usage.get("completion_tokens") or raw_usage.get("output_tokens") or 0
    )
    total = int(raw_usage.get("total_tokens") or prompt + completion)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def _usage_total(items: Sequence[Mapping[str, int]]) -> dict[str, int]:
    return {
        field: sum(int(item.get(field) or 0) for item in items)
        for field in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def _status_by_rule(report: Mapping[str, Any]) -> dict[str, str]:
    return {
        rule_id: str(item.get("status") or "")
        for item in report.get("results", ())
        if isinstance(item, Mapping)
        for rule_id in (str(item.get("rule_id") or "").upper(),)
        if rule_id in _RULE_IDS
    }


def _reason_by_rule(report: Mapping[str, Any]) -> dict[str, str]:
    return {
        rule_id: str(item.get("reason_code") or "")
        for item in report.get("results", ())
        if isinstance(item, Mapping)
        for rule_id in (str(item.get("rule_id") or "").upper(),)
        if rule_id in _RULE_IDS
    }


def _retry_recheck_inference(prompts: Sequence[str]) -> dict[str, Any]:
    """只按同一合成病例的内存 Prompt 统计，不把推测伪装成公共执行 trace。"""

    frequencies = Counter(prompts)
    duplicate_count = sum(count - 1 for count in frequencies.values() if count > 1)
    return {
        "retry_attempted_inferred": duplicate_count > 0,
        "recheck_attempted_inferred": len(frequencies) > 2,
        "duplicate_prompt_generate_count": duplicate_count,
        "legacy_path": "not_invoked_direct_native_chain",
        "inference_scope": "synthetic_direct_native_chain",
    }


def _runtime_config(delegate: Any, *, execution_mode: str) -> dict[str, Any]:
    if execution_mode != "real_model":
        return {"execution_mode": execution_mode}
    return {
        "execution_mode": execution_mode,
        "provider_code": str(getattr(delegate, "provider_code", "") or ""),
        "model": str(getattr(delegate, "model", "") or ""),
        "temperature": float(getattr(delegate, "temperature", 0.0) or 0.0),
        "top_p": float(getattr(delegate, "top_p", 0.0) or 0.0),
        "max_tokens": int(getattr(delegate, "max_tokens", 0) or 0),
        "timeout_seconds": int(getattr(delegate, "timeout_seconds", 0) or 0),
    }


def _failure_type(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, (ConnectionError, OSError)):
        return "transport_error"
    return "formal_synthetic_chain_failed"


def _round_gate(run: Mapping[str, Any]) -> dict[str, bool]:
    statuses = run.get("status_by_rule")
    reasons = run.get("reason_code_by_rule")
    complete = (
        isinstance(statuses, Mapping)
        and isinstance(reasons, Mapping)
        and set(statuses) == set(_RULE_IDS)
        and set(reasons) == set(_RULE_IDS)
    )
    expected_outcomes = (
        complete
        and dict(statuses) == _EXPECTED_STATUS_BY_RULE
        and dict(reasons) == _EXPECTED_REASON_BY_RULE
    )
    no_technical_error = (
        isinstance(statuses, Mapping)
        and all(status != "technical_error" for status in statuses.values())
    )
    # 第一阶段、执行判断，以及 023 原判合规时的会诊措施逐项核对（2026-10-12）。
    expected_calls = (
        int(run.get("logical_llm_call_count") or 0) == 3
        and int(run.get("delegate_generate_count") or 0) == 3
    )
    prompt_equal = run.get("prompt_equal_to_reference") is True
    usage = run.get("usage_conservation")
    usage_conserved = isinstance(usage, Mapping) and usage.get("conserved") is True
    completed = run.get("run_status") == "completed"
    return {
        "completed": completed,
        "rules_complete": complete,
        "expected_outcomes": expected_outcomes,
        "no_technical_error": no_technical_error,
        "expected_logical_calls": expected_calls,
        "prompt_equal_to_reference": prompt_equal,
        "usage_conserved": usage_conserved,
        "passed": all(
            (
                completed,
                complete,
                expected_outcomes,
                no_technical_error,
                expected_calls,
                prompt_equal,
                usage_conserved,
            )
        ),
    }


async def _run_one(
    *,
    fixture_path: Path,
    client_factory: Callable[[], Any],
    reference_prompts: tuple[str, ...] | None,
    round_number: int,
    warmup: bool,
    execution_mode: str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    from scripts import verify_consultation_family_acceptance as verify

    delegate = client_factory()
    client = _BenchmarkClient(delegate)
    started = time.perf_counter()
    try:
        report = await verify.run_formal_synthetic_chain(
            fixture_path,
            llm_client=client,
        )
        if any(
            isinstance(item, Mapping) and item.get("status") == "technical_error"
            for item in report.get("results", ())
        ):
            run_status = "technical_error"
            failure_kind = "native_technical_error"
        else:
            run_status = "completed"
            failure_kind = ""
    except Exception as error:
        report = {}
        run_status = "technical_error"
        failure_kind = _failure_type(error)
    end_to_end_duration_ms = round((time.perf_counter() - started) * 1000, 3)
    prompts = tuple(client.prompts)
    response_usage = _usage_total(client.response_usage)
    execution_usage = {
        field: int(report.get(field) or 0)
        for field in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    llm_call_count = int(report.get("llm_call_count") or 0)
    usage_conserved = run_status == "completed" and (
        execution_usage == response_usage
        and llm_call_count == client.delegate_generate_count
    )
    run = {
        "round": round_number,
        "warmup": warmup,
        "run_status": run_status,
        "failure_kind": failure_kind,
        "api_duration_ms": round(float(report.get("api_time") or 0.0) * 1000, 3),
        "end_to_end_duration_ms": end_to_end_duration_ms,
        "http_attempt_count": None,
        "http_attempt_count_state": "unavailable_without_public_execution_trace",
        "logical_llm_call_count": llm_call_count,
        "delegate_generate_count": client.delegate_generate_count,
        "prompt_count": len(prompts),
        "prompt_lengths": [len(prompt) for prompt in prompts],
        "prompt_equal_to_reference": (
            prompts == reference_prompts
            if reference_prompts is not None
            else True
        ),
        "prompt_tokens": execution_usage["prompt_tokens"],
        "completion_tokens": execution_usage["completion_tokens"],
        "total_tokens": execution_usage["total_tokens"],
        "usage_conservation": {
            "execution": execution_usage,
            "delegate_responses": response_usage,
            "conserved": usage_conserved,
        },
        "retry_recheck_fallback": _retry_recheck_inference(prompts),
        "model_runtime": _runtime_config(
            delegate,
            execution_mode=execution_mode,
        ),
        "status_by_rule": _status_by_rule(report),
        "reason_code_by_rule": _reason_by_rule(report),
    }
    run["gate"] = _round_gate(run)
    return run, prompts


async def run_benchmark10(
    fixture_path: Path,
    *,
    client_factory: Callable[[], Any],
    execution_mode: str = "controlled",
) -> dict[str, Any]:
    """运行 1 次预热和固定 10 次正式采样；仅合成输入，调用方决定客户端。"""

    warmup, reference_prompts = await _run_one(
        fixture_path=fixture_path,
        client_factory=client_factory,
        reference_prompts=None,
        round_number=0,
        warmup=True,
        execution_mode=execution_mode,
    )
    if warmup["gate"]["passed"] is not True:
        return {
            "fixture_kind": "synthetic_consultation_performance_benchmark",
            "execution_mode": execution_mode,
            "network_observation": "unknown",
            "database_used": False,
            "warmup": warmup,
            "runs": [],
            "formal_round_count": 0,
            "formal_rounds_completed": 0,
            "aborted_after_warmup_failure": True,
            "median_api_duration_ms": None,
            "median_end_to_end_duration_ms": None,
            "prompt_equal_all_formal_rounds": False,
            "usage_conserved_all_formal_rounds": False,
            "model_runtime": warmup["model_runtime"],
            "benchmark_passed": False,
        }
    runs = []
    for round_number in range(1, _FORMAL_ROUNDS + 1):
        run, _ = await _run_one(
            fixture_path=fixture_path,
            client_factory=client_factory,
            reference_prompts=reference_prompts,
            round_number=round_number,
            warmup=False,
            execution_mode=execution_mode,
        )
        runs.append(run)
    completed_runs = [item for item in runs if item["run_status"] == "completed"]
    benchmark_passed = (
        warmup["gate"]["passed"] is True
        and len(runs) == _FORMAL_ROUNDS
        and len(completed_runs) == _FORMAL_ROUNDS
        and all(item["gate"]["passed"] is True for item in runs)
    )
    return {
        "fixture_kind": "synthetic_consultation_performance_benchmark",
        "execution_mode": execution_mode,
        "network_observation": "unknown",
        "database_used": False,
        "warmup": warmup,
        "runs": runs,
        "formal_round_count": len(runs),
        "formal_rounds_completed": len(completed_runs),
        "median_api_duration_ms": (
            round(median(item["api_duration_ms"] for item in completed_runs), 3)
            if completed_runs
            else None
        ),
        "median_end_to_end_duration_ms": (
            round(median(item["end_to_end_duration_ms"] for item in completed_runs), 3)
            if completed_runs
            else None
        ),
        "prompt_equal_all_formal_rounds": bool(runs) and all(
            item["prompt_equal_to_reference"] for item in runs
        ),
        "usage_conserved_all_formal_rounds": bool(runs) and all(
            bool(item["usage_conservation"]["conserved"]) for item in runs
        ),
        "model_runtime": warmup["model_runtime"],
        "benchmark_passed": benchmark_passed,
    }


def _real_client_factory() -> Callable[[], Any]:
    from app.services.llm_observability import (
        LLMObservabilityRecorder,
        NullLLMCallEventStore,
    )
    from app.services.qc_llm_client import SichuanQCLLMClient

    def build() -> SichuanQCLLMClient:
        client = SichuanQCLLMClient(
            observability_recorder=LLMObservabilityRecorder(
                store=NullLLMCallEventStore()
            )
        )
        if not client.api_endpoint or not client.api_key or client.allow_mock_when_unconfigured:
            raise RuntimeError("真实模型基准需要已配置的非 mock LLM_ENDPOINT、LLM_API_KEY 与模型")
        client.temperature = 0.0
        return client

    return build


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="LX0609 会诊 020–023 合成资料真实模型基准")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument(
        "--real-model",
        action="store_true",
        help="确认使用已配置的真实模型；不传此参数绝不联网。",
    )
    args = parser.parse_args(argv)
    if not args.real_model:
        parser.error("真实模型基准必须显式传入 --real-model")
    report = asyncio.run(
        run_benchmark10(
            args.fixture.resolve(),
            client_factory=_real_client_factory(),
            execution_mode="real_model",
        )
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["benchmark_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
