"""只读复跑 LX0609 独立准生产引擎固定20例。

输入病例映射只在进程内使用；输出仅保留安全 case 标签、坐标摘要、准生产
DTO 与聚合指标，可直接交给 ``build_luxian_0609_golden_ledger.py`` 构建候选账本。
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import date
import json
import math
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any, Awaitable, Callable, Mapping, Sequence

from app.core.settings import get_settings
from app.services.luxian_0609.preproduction_bundle_reader import (
    read_luxian_0609_preproduction_bundle,
)
from app.services.luxian_0609.preproduction_runner import (
    run_luxian_0609_preproduction,
)
from app.services.luxian_0609.phase_scope import partition_luxian_0609_rule_scope
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from scripts.build_luxian_0609_golden_ledger import (
    API_BATCH_SCHEMA_VERSION,
    build_candidate_ledger,
    canonical_digest,
)
from scripts.build_luxian_0609_runtime_manifest import (
    runtime_manifest_hash,
    validate_runtime_manifest_current,
)


CASE_MAP_SCHEMA_VERSION = "lx0609-preproduction-benchmark20-case-map-v1"
SELECTOR_VERSION_DEFAULT = "lx0609-preproduction-benchmark20-v1"
_CASE_LABEL_RE = re.compile(r"^case-(?:0[1-9]|1[0-9]|20)$")
_SAFE_CODE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_ATTESTED_REASON_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_ATTESTED_STATES = frozenset(
    {
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_gap",
        "evaluation_unknown",
        "technical_error",
    }
)
_CASE_KEYS = {
    "case_label",
    "scene",
    "institute_id",
    "patient_id",
    "visit_id",
}
_AUTHORITY_EXECUTOR_TYPES = {
    "program_only": "program",
    "program_then_optional_llm": "llm",
}

BundleLoader = Callable[..., Mapping[str, Any]]
Runner = Callable[..., Awaitable[Mapping[str, Any]]]


class BenchmarkContractError(ValueError):
    """固定且不回显输入的20例验收合同错误。"""


def _rule_attestations() -> tuple[tuple[str, ...], dict[str, str]]:
    all_contracts = tuple(load_luxian_0609_rule_contracts())
    all_rule_ids = tuple(
        str(getattr(item, "rule_id", "") or "") for item in all_contracts
    )
    rule_ids, _withheld_rule_ids = partition_luxian_0609_rule_scope(all_rule_ids)
    contracts_by_rule_id = {str(item.rule_id): item for item in all_contracts}
    if (
        not rule_ids
        or len(rule_ids) != len(set(rule_ids))
        or any(rule_id not in contracts_by_rule_id for rule_id in rule_ids)
    ):
        raise BenchmarkContractError("invalid LX0609 executable rule scope")
    executor_types: dict[str, str] = {}
    for rule_id in rule_ids:
        contract = contracts_by_rule_id[rule_id]
        authority = str(getattr(contract, "decision_authority", "") or "").strip()
        executor_type = _AUTHORITY_EXECUTOR_TYPES.get(authority)
        if executor_type is None:
            raise BenchmarkContractError("invalid LX0609 decision authority")
        executor_types[rule_id] = executor_type
    if len(executor_types) != len(rule_ids):
        raise BenchmarkContractError("invalid LX0609 decision authority attestation")
    return rule_ids, executor_types


def _select_rule_attestations(
    selected_rule_ids: Sequence[str] | None,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """校验显式子集并按目录规范顺序返回。

    ``None`` 是唯一的全量可执行规则语义；空集或非规范规则均在读取病例前
    fail-closed。这样小范围 Golden 候选不会伪装成全量复跑。
    """

    catalog_rule_ids, catalog_executor_types = _rule_attestations()
    if selected_rule_ids is None:
        return catalog_rule_ids, catalog_executor_types
    if isinstance(selected_rule_ids, (str, bytes)) or not isinstance(
        selected_rule_ids, Sequence
    ):
        raise BenchmarkContractError("invalid selected rule scope")

    requested_rule_ids = tuple(selected_rule_ids)
    if not requested_rule_ids:
        raise BenchmarkContractError("invalid selected rule scope")
    selected_set: set[str] = set()
    for rule_id in requested_rule_ids:
        if (
            not isinstance(rule_id, str)
            or rule_id not in catalog_executor_types
            or rule_id in selected_set
        ):
            raise BenchmarkContractError("invalid selected rule scope")
        selected_set.add(rule_id)
    canonical_rule_ids = tuple(
        rule_id for rule_id in catalog_rule_ids if rule_id in selected_set
    )
    if len(canonical_rule_ids) != len(requested_rule_ids):
        raise BenchmarkContractError("invalid selected rule scope")
    return (
        canonical_rule_ids,
        {
            rule_id: catalog_executor_types[rule_id]
            for rule_id in canonical_rule_ids
        },
    )


def _validate_evaluation_date(value: str) -> str:
    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise BenchmarkContractError("invalid evaluation_as_of_date") from exc
    if parsed.isoformat() != normalized:
        raise BenchmarkContractError("invalid evaluation_as_of_date")
    return normalized


def _runtime_identity(
    runtime_manifest: Mapping[str, Any],
    *,
    observed_git_head: str | None = None,
) -> dict[str, str]:
    """校验 Task1 清单并投影 Golden 所需的不可变运行身份。"""

    try:
        git_head = validate_runtime_manifest_current(
            runtime_manifest,
            observed_git_head=observed_git_head,
        )
    except (TypeError, ValueError) as exc:
        raise BenchmarkContractError("stale or invalid runtime manifest") from exc
    rule_set = runtime_manifest.get("rule_set")
    if not isinstance(rule_set, Mapping):
        raise BenchmarkContractError("stale or invalid runtime manifest")
    policy_version = str(rule_set.get("version") or "").strip()
    rule_ids = tuple(str(item or "").strip() for item in rule_set.get("rule_ids") or ())
    expected = tuple(
        str(getattr(item, "rule_id", "") or "")
        for item in load_luxian_0609_rule_contracts()
    )
    if (
        not _SAFE_CODE_RE.fullmatch(policy_version)
        or rule_ids != expected
        or int(rule_set.get("rule_count") or 0) != len(expected)
    ):
        raise BenchmarkContractError("stale or invalid runtime manifest")
    return {
        "git_head": git_head,
        "policy_version": policy_version,
        "runtime_manifest_hash": runtime_manifest_hash(runtime_manifest),
    }


def _validate_case_map(value: Mapping[str, Any]) -> tuple[str, tuple[dict[str, str], ...]]:
    if not isinstance(value, Mapping):
        raise BenchmarkContractError("invalid case map")
    unexpected_top_level = set(value) - {
        "schema_version",
        "selector_version",
        "cases",
    }
    if unexpected_top_level:
        raise BenchmarkContractError("invalid case map")
    schema_version = str(value.get("schema_version") or "").strip()
    if schema_version and schema_version != CASE_MAP_SCHEMA_VERSION:
        raise BenchmarkContractError("invalid case map schema")
    selector_version = str(
        value.get("selector_version") or SELECTOR_VERSION_DEFAULT
    ).strip()
    if not _SAFE_CODE_RE.fullmatch(selector_version):
        raise BenchmarkContractError("invalid selector version")
    raw_cases = value.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != 20:
        raise BenchmarkContractError("case map must contain exactly 20 cases")

    expected_labels = tuple(f"case-{index:02d}" for index in range(1, 21))
    normalized_cases: list[dict[str, str]] = []
    seen_coordinates: set[tuple[str, str, str, str]] = set()
    for index, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, Mapping) or set(raw_case) != _CASE_KEYS:
            raise BenchmarkContractError("invalid case map entry")
        case_label = str(raw_case.get("case_label") or "").strip()
        if (
            not _CASE_LABEL_RE.fullmatch(case_label)
            or case_label != expected_labels[index]
        ):
            raise BenchmarkContractError("case labels must be ordered case-01..case-20")
        scene = str(raw_case.get("scene") or "").strip().lower()
        if scene not in {"running", "final"}:
            raise BenchmarkContractError("invalid case scene")
        coordinates = tuple(
            str(raw_case.get(field) or "").strip()
            for field in ("institute_id", "patient_id", "visit_id")
        )
        if any(not item or len(item) > 256 for item in coordinates):
            raise BenchmarkContractError("invalid case coordinates")
        coordinate_key = (scene, *coordinates)
        if coordinate_key in seen_coordinates:
            raise BenchmarkContractError("duplicate case coordinates")
        seen_coordinates.add(coordinate_key)
        normalized_cases.append(
            {
                "case_label": case_label,
                "scene": scene,
                "institute_id": coordinates[0],
                "patient_id": coordinates[1],
                "visit_id": coordinates[2],
            }
        )
    return selector_version, tuple(normalized_cases)


def _coordinate_hash(case: Mapping[str, str]) -> str:
    return canonical_digest(
        {
            "domain": "lx0609-preproduction-benchmark20-coordinate-v1",
            "scene": case["scene"],
            "institute_id": case["institute_id"],
            "patient_id": case["patient_id"],
            "visit_id": case["visit_id"],
        }
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def _validate_response(
    value: Mapping[str, Any],
    *,
    expected_rule_ids: tuple[str, ...],
    executor_types: Mapping[str, str],
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        raise BenchmarkContractError("invalid preproduction response")
    if str(value.get("schema_version") or "") != "lx0609-preproduction-runner-v1":
        raise BenchmarkContractError("invalid preproduction response")
    results = value.get("results")
    metrics = value.get("metrics")
    if not isinstance(results, list) or not isinstance(metrics, Mapping):
        raise BenchmarkContractError("invalid preproduction response")
    actual_rule_ids = tuple(
        str(item.get("rule_id") or "").strip().upper()
        for item in results
        if isinstance(item, Mapping)
    )
    if actual_rule_ids != expected_rule_ids or len(results) != len(expected_rule_ids):
        raise BenchmarkContractError(
            "preproduction response must contain selected ordered rules"
        )
    metric_names = (
        "llm_call_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "technical_error_count",
        "rule_decision_count",
        "typed_shadow_adapter_count",
        "legacy_projection_count",
    )
    if any(
        type(metrics.get(name)) is not int or int(metrics.get(name) or 0) < 0
        for name in metric_names
    ):
        raise BenchmarkContractError("invalid preproduction token metrics")
    prompt_tokens = int(metrics.get("prompt_tokens") or 0)
    completion_tokens = int(metrics.get("completion_tokens") or 0)
    total_tokens = int(metrics.get("total_tokens") or 0)
    llm_call_count = int(metrics.get("llm_call_count") or 0)
    if (
        total_tokens != prompt_tokens + completion_tokens
        or (llm_call_count == 0 and total_tokens != 0)
        or (llm_call_count > 0 and total_tokens == 0)
    ):
        raise BenchmarkContractError("invalid preproduction token metrics")
    if type(metrics.get("usage_complete")) is not bool:
        raise BenchmarkContractError("invalid preproduction usage attribution")
    usage_error_reason = metrics.get("usage_error_reason")
    if not isinstance(usage_error_reason, str) or (
        usage_error_reason and not _ATTESTED_REASON_RE.fullmatch(usage_error_reason)
    ):
        raise BenchmarkContractError("invalid preproduction usage attribution")
    if (
        not metrics["usage_complete"]
        or usage_error_reason
        or type(metrics.get("unattributed_prompt_tokens")) is not int
        or int(metrics["unattributed_prompt_tokens"]) != 0
        or type(metrics.get("unattributed_completion_tokens")) is not int
        or int(metrics["unattributed_completion_tokens"]) != 0
        or type(metrics.get("unattributed_total_tokens")) is not int
        or int(metrics["unattributed_total_tokens"]) != 0
    ):
        raise BenchmarkContractError("incomplete preproduction usage attribution")
    api_time_seconds = metrics.get("api_time_seconds")
    if (
        isinstance(api_time_seconds, bool)
        or not isinstance(api_time_seconds, (int, float))
        or not math.isfinite(float(api_time_seconds))
        or float(api_time_seconds) < 0
    ):
        raise BenchmarkContractError("invalid preproduction usage attribution")
    raw_attributions = metrics.get("usage_attributions")
    if not isinstance(raw_attributions, list) or not raw_attributions:
        raise BenchmarkContractError("missing preproduction usage attribution")
    expected_fields = {
        "executor_key",
        "llm_call_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "covered_customer_rule_ids",
        "latency_ms",
    }
    rule_position = {
        rule_id: index for index, rule_id in enumerate(expected_rule_ids)
    }
    seen_executors: set[str] = set()
    seen_rules: set[str] = set()
    attribution_calls = 0
    attribution_prompt = 0
    attribution_completion = 0
    attribution_total = 0
    attribution_latency_ms = 0.0
    for attribution in raw_attributions:
        if not isinstance(attribution, Mapping) or set(attribution) != expected_fields:
            raise BenchmarkContractError("invalid preproduction usage attribution")
        executor_key = attribution.get("executor_key")
        if (
            not isinstance(executor_key, str)
            or not _ATTESTED_REASON_RE.fullmatch(executor_key)
            or executor_key in seen_executors
        ):
            raise BenchmarkContractError("invalid preproduction usage attribution")
        seen_executors.add(executor_key)
        token_fields = (
            "llm_call_count",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        )
        if any(
            type(attribution.get(field)) is not int
            or int(attribution[field]) < 0
            for field in token_fields
        ):
            raise BenchmarkContractError("invalid preproduction usage attribution")
        latency_ms = attribution.get("latency_ms")
        if (
            isinstance(latency_ms, bool)
            or not isinstance(latency_ms, (int, float))
            or not math.isfinite(float(latency_ms))
            or float(latency_ms) < 0
        ):
            raise BenchmarkContractError("invalid preproduction usage attribution")
        covered_rule_ids = attribution.get("covered_customer_rule_ids")
        if (
            not isinstance(covered_rule_ids, list)
            or not covered_rule_ids
            or any(
                not isinstance(rule_id, str) or rule_id not in rule_position
                for rule_id in covered_rule_ids
            )
            or len(covered_rule_ids) != len(set(covered_rule_ids))
            or covered_rule_ids
            != sorted(covered_rule_ids, key=rule_position.__getitem__)
            or seen_rules.intersection(covered_rule_ids)
        ):
            raise BenchmarkContractError("invalid preproduction usage attribution")
        seen_rules.update(covered_rule_ids)
        calls = int(attribution["llm_call_count"])
        prompt = int(attribution["prompt_tokens"])
        completion = int(attribution["completion_tokens"])
        total = int(attribution["total_tokens"])
        if (
            total != prompt + completion
            or (calls == 0 and total != 0)
            or (calls > 0 and total == 0)
            or (
                total > 0
                and not any(
                    executor_types[rule_id] == "llm"
                    for rule_id in covered_rule_ids
                )
            )
        ):
            raise BenchmarkContractError("invalid preproduction usage attribution")
        attribution_calls += calls
        attribution_prompt += prompt
        attribution_completion += completion
        attribution_total += total
        attribution_latency_ms += float(latency_ms)
    latency_tolerance_ms = 0.001 + len(raw_attributions) * 0.0005
    if (
        seen_rules != set(expected_rule_ids)
        or attribution_calls != llm_call_count
        or attribution_prompt != prompt_tokens
        or attribution_completion != completion_tokens
        or attribution_total != total_tokens
        or not math.isclose(
            attribution_latency_ms,
            float(api_time_seconds) * 1000.0,
            rel_tol=0.0,
            abs_tol=latency_tolerance_ms,
        )
    ):
        raise BenchmarkContractError("incomplete preproduction usage attribution")
    return results, metrics


def _golden_response(
    response: Mapping[str, Any],
    *,
    results: Sequence[Mapping[str, Any]],
    executor_types: Mapping[str, str],
    evidence_attestations: Mapping[str, Mapping[str, str]],
    runtime_bound: bool = False,
) -> dict[str, Any]:
    """投影Golden所需最小响应，排除runner性能字段和客户长文本。"""

    projected_results: list[dict[str, Any]] = []
    for result in results:
        rule_id = str(result.get("rule_id") or "").strip().upper()
        executor_type = str(executor_types.get(rule_id) or "").strip()
        if executor_type not in {"program", "llm"}:
            raise BenchmarkContractError("missing LX0609 decision authority attestation")
        attestation = evidence_attestations.get(rule_id)
        if not isinstance(attestation, Mapping):
            raise BenchmarkContractError("missing rule evidence attestation")
        evidence_attestation = str(attestation.get("evidence_hash") or "").strip()
        observed_state = str(attestation.get("observed_state") or "").strip()
        reason_code = str(attestation.get("reason_code") or "").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", evidence_attestation):
            raise BenchmarkContractError("missing rule evidence attestation")
        if str(result.get("status") or "").strip().lower() != observed_state:
            raise BenchmarkContractError("attested result state mismatch")
        projected_result = {
                "rule_id": rule_id,
                "status": observed_state,
                "metadata": {
                    "reason_code": reason_code,
                    "executor_type": executor_type,
                },
                "evidence_items": [
                    {"evidence_attestation": evidence_attestation}
                ],
            }
        if runtime_bound:
            projected_result["evidence_source_types"] = ["evidence_snapshot"]
        projected_results.append(projected_result)
    projected_response = {
        "schema_version": str(response.get("schema_version") or ""),
        "results": projected_results,
    }
    if runtime_bound:
        metrics = response.get("metrics")
        if not isinstance(metrics, Mapping):
            raise BenchmarkContractError("missing preproduction usage attribution")
        projected_response["metrics"] = {
            "llm_call_count": int(metrics["llm_call_count"]),
            "prompt_tokens": int(metrics["prompt_tokens"]),
            "completion_tokens": int(metrics["completion_tokens"]),
            "total_tokens": int(metrics["total_tokens"]),
            "usage_complete": bool(metrics["usage_complete"]),
            "usage_error_reason": str(metrics["usage_error_reason"]),
            "unattributed_prompt_tokens": int(
                metrics["unattributed_prompt_tokens"]
            ),
            "unattributed_completion_tokens": int(
                metrics["unattributed_completion_tokens"]
            ),
            "unattributed_total_tokens": int(metrics["unattributed_total_tokens"]),
            "api_time_seconds": float(metrics["api_time_seconds"]),
            "usage_attributions": [
                {
                    "executor_key": str(item["executor_key"]),
                    "llm_call_count": int(item["llm_call_count"]),
                    "prompt_tokens": int(item["prompt_tokens"]),
                    "completion_tokens": int(item["completion_tokens"]),
                    "total_tokens": int(item["total_tokens"]),
                    "covered_customer_rule_ids": list(
                        item["covered_customer_rule_ids"]
                    ),
                    "latency_ms": float(item["latency_ms"]),
                }
                for item in metrics["usage_attributions"]
            ],
        }
    return projected_response


async def build_benchmark_batch(
    *,
    case_map: Mapping[str, Any],
    evaluation_as_of_date: str,
    bundle_loader: BundleLoader = read_luxian_0609_preproduction_bundle,
    runner: Runner = run_luxian_0609_preproduction,
    llm_client: Any,
    base_settings: Any,
    runtime_manifest: Mapping[str, Any],
    fail_on_technical_error: bool = True,
    selected_rule_ids: Sequence[str] | None = None,
    observed_git_head: str | None = None,
) -> dict[str, Any]:
    """顺序执行固定20例并返回可进入Golden候选构建器的安全批次。"""

    selector_version, cases = _validate_case_map(case_map)
    as_of_date = _validate_evaluation_date(evaluation_as_of_date)
    runtime_identity = _runtime_identity(
        runtime_manifest,
        observed_git_head=observed_git_head,
    )
    full_rule_ids, _ = _rule_attestations()
    selected_rule_ids, executor_types = _select_rule_attestations(selected_rule_ids)
    is_selected_subset = selected_rule_ids != full_rule_ids
    rule_set_digest = canonical_digest(
        [
            {
                "rule_id": rule_id,
                "executor_type": executor_types[rule_id],
            }
            for rule_id in selected_rule_ids
        ]
    )
    safe_selector: list[dict[str, str]] = []
    output_cases: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    latencies: list[float] = []
    llm_call_count = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    technical_error_count = 0
    maturity: dict[str, int] | None = None
    all_evidence_hashes: set[str] = set()
    batch_started = perf_counter()

    for case in cases:
        coordinate_hash = _coordinate_hash(case)
        safe_selector.append(
            {
                "case_label": case["case_label"],
                "coordinate_hash": coordinate_hash,
            }
        )
        evidence_attestation_rows: list[Mapping[str, str]] = []
        try:
            bundle = bundle_loader(
                scene=case["scene"],
                institute_id=case["institute_id"],
                patient_id=case["patient_id"],
                visit_id=case["visit_id"],
                schema="public",
            )
            response = await runner(
                bundle=bundle,
                selected_customer_rule_ids=selected_rule_ids,
                evaluation_as_of_date=as_of_date,
                llm_client=llm_client,
                base_settings=base_settings,
                model_name=str(getattr(llm_client, "model", "") or ""),
                evidence_attestation_sink=evidence_attestation_rows.extend,
            )
        except Exception:
            raise BenchmarkContractError("benchmark case execution failed") from None
        results, metrics = _validate_response(
            response,
            expected_rule_ids=selected_rule_ids,
            executor_types=executor_types,
        )
        if (
            len(evidence_attestation_rows) != len(selected_rule_ids)
            or tuple(
                str(item.get("rule_id") or "").strip().upper()
                for item in evidence_attestation_rows
                if isinstance(item, Mapping)
            )
            != selected_rule_ids
        ):
            raise BenchmarkContractError("invalid evidence attestation scope")
        evidence_attestations: dict[str, dict[str, str]] = {}
        for item in evidence_attestation_rows:
            if not isinstance(item, Mapping) or set(item) != {
                "rule_id",
                "evidence_hash",
                "observed_state",
                "reason_code",
            }:
                raise BenchmarkContractError("invalid evidence attestation")
            rule_id = str(item.get("rule_id") or "").strip().upper()
            evidence_hash = str(item.get("evidence_hash") or "").strip().lower()
            observed_state = str(item.get("observed_state") or "").strip().lower()
            reason_code = str(item.get("reason_code") or "").strip().lower()
            if (
                rule_id in evidence_attestations
                or not re.fullmatch(r"[0-9a-f]{64}", evidence_hash)
                or observed_state not in _ATTESTED_STATES
                or not _ATTESTED_REASON_RE.fullmatch(reason_code)
            ):
                raise BenchmarkContractError("invalid evidence attestation")
            evidence_attestations[rule_id] = {
                "evidence_hash": evidence_hash,
                "observed_state": observed_state,
                "reason_code": reason_code,
            }
        evidence_hashes = {
            item["evidence_hash"] for item in evidence_attestations.values()
        }
        if len(evidence_hashes) != len(selected_rule_ids):
            raise BenchmarkContractError("duplicate evidence attestation")
        if all_evidence_hashes.intersection(evidence_hashes):
            raise BenchmarkContractError("duplicate cross-case evidence attestation")
        all_evidence_hashes.update(evidence_hashes)
        output_cases.append(
            {
                "case_label": case["case_label"],
                "coordinate_hash": coordinate_hash,
                "evidence_attestations": {
                    rule_id: item["evidence_hash"]
                    for rule_id, item in evidence_attestations.items()
                },
                "response": _golden_response(
                    response,
                    results=results,
                    executor_types=executor_types,
                    evidence_attestations=evidence_attestations,
                    runtime_bound=True,
                ),
            }
        )
        status_counts.update(str(item.get("status") or "technical_error") for item in results)
        case_technical_errors = sum(
            str(item.get("status") or "") == "technical_error" for item in results
        )
        if fail_on_technical_error and case_technical_errors:
            raise BenchmarkContractError("benchmark contains technical_error")
        technical_error_count += case_technical_errors
        latencies.append(float(metrics.get("wall_time_ms") or 0.0))
        llm_call_count += int(metrics.get("llm_call_count") or 0)
        prompt_tokens += int(metrics.get("prompt_tokens") or 0)
        completion_tokens += int(metrics.get("completion_tokens") or 0)
        total_tokens += int(metrics.get("total_tokens") or 0)
        case_maturity = {
            "rule_decision_count": int(metrics.get("rule_decision_count") or 0),
            "typed_shadow_adapter_count": int(
                metrics.get("typed_shadow_adapter_count") or 0
            ),
            "legacy_projection_count": int(metrics.get("legacy_projection_count") or 0),
        }
        if maturity is None:
            maturity = case_maturity
        elif maturity != case_maturity:
            raise BenchmarkContractError("inconsistent rule maturity metrics")

    selector_digest = canonical_digest(
        {
            "selector_version": selector_version,
            "selector": safe_selector,
        }
    )
    if len(all_evidence_hashes) != len(cases) * len(selected_rule_ids):
        raise BenchmarkContractError("incomplete benchmark evidence attestations")
    summary = {
        "case_count": len(output_cases),
        "judgment_count": sum(status_counts.values()),
        "status_counts": dict(sorted(status_counts.items())),
        "technical_error_count": technical_error_count,
        "llm_call_count": llm_call_count,
        "input_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "total_wall_time_ms": round(sum(latencies), 3),
        "batch_wall_time_ms": round((perf_counter() - batch_started) * 1000.0, 3),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        "rule_maturity": maturity or {},
        "selector_digest": selector_digest,
        "rule_set_digest": rule_set_digest,
    }
    if is_selected_subset:
        summary["selected_rule_count"] = len(selected_rule_ids)
    batch: dict[str, Any] = {
        "schema_version": API_BATCH_SCHEMA_VERSION,
        "selector_version": selector_version,
        "selector_digest": selector_digest,
        "rule_set_digest": rule_set_digest,
        "evaluation_as_of_date": as_of_date,
        "cases": output_cases,
        "summary": summary,
    }
    batch.update(runtime_identity)
    batch["sample_type"] = "real"
    if is_selected_subset:
        # 子集必须在输出中显式标明，禁止作为全量可执行规则基准引用。
        batch["rule_scope"] = {
            "mode": "selected_subset",
            "selected_rule_ids": list(selected_rule_ids),
        }

    # 复用Golden候选构建器的完整递归隐私、响应形状和980行唯一性校验。
    build_candidate_ledger(
        batch,
        candidate_version="benchmark20-validation-v1",
        generated_at="1970-01-01T00:00:00Z",
    )
    if fail_on_technical_error and technical_error_count:
        raise BenchmarkContractError("benchmark contains technical_error")
    return batch


def _build_llm_client() -> Any:
    # 与独立准生产API使用相同配置工厂；保持单客户端、顺序执行、无新增缓存。
    from app.services.llm_config_loader import build_adjudicator_runtime_config
    from app.services.qc_llm_client import SichuanQCLLMClient

    return SichuanQCLLMClient(build_adjudicator_runtime_config())


def _read_case_map(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        raise BenchmarkContractError("case map is unavailable or invalid") from None
    if not isinstance(value, Mapping):
        raise BenchmarkContractError("invalid case map")
    return value


def _read_runtime_manifest(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        raise BenchmarkContractError("runtime manifest is unavailable or invalid") from None
    if not isinstance(value, Mapping):
        raise BenchmarkContractError("runtime manifest is unavailable or invalid")
    return value


def _write_output(path: Path, batch: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(batch, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LX0609独立准生产固定20例只读复跑")
    parser.add_argument("--case-map", type=Path, required=True)
    parser.add_argument("--evaluation-as-of-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument(
        "--allow-technical-error",
        action="store_true",
        help="允许输出含technical_error的诊断批次；默认任何technical_error均失败",
    )
    parser.add_argument(
        "--rule-id",
        action="append",
        default=None,
        help="可重复：仅运行指定规范LX0609规则；未指定时运行全部可执行规则",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        batch = asyncio.run(
            build_benchmark_batch(
                case_map=_read_case_map(args.case_map),
                evaluation_as_of_date=args.evaluation_as_of_date,
                llm_client=_build_llm_client(),
                base_settings=get_settings(),
                fail_on_technical_error=not args.allow_technical_error,
                selected_rule_ids=(
                    tuple(args.rule_id) if args.rule_id is not None else None
                ),
                runtime_manifest=_read_runtime_manifest(args.runtime_manifest),
            )
        )
        _write_output(args.output, batch)
    except Exception:
        print("LX0609 benchmark20 failed safely", file=sys.stderr)
        return 1
    output_summary = {
        "schema_version": API_BATCH_SCHEMA_VERSION,
        "case_count": batch["summary"]["case_count"],
        "judgment_count": batch["summary"]["judgment_count"],
        "technical_error_count": batch["summary"]["technical_error_count"],
        "selector_digest": batch["selector_digest"],
        "rule_set_digest": batch["rule_set_digest"],
    }
    if "rule_scope" in batch:
        output_summary["rule_scope"] = batch["rule_scope"]
    print(json.dumps(output_summary, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
