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
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from scripts.build_luxian_0609_golden_ledger import (
    API_BATCH_SCHEMA_VERSION,
    build_candidate_ledger,
    canonical_digest,
)


CASE_MAP_SCHEMA_VERSION = "lx0609-preproduction-benchmark20-case-map-v1"
SELECTOR_VERSION_DEFAULT = "lx0609-preproduction-benchmark20-v1"
_CASE_LABEL_RE = re.compile(r"^case-(?:0[1-9]|1[0-9]|20)$")
_SAFE_CODE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
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
    contracts = tuple(load_luxian_0609_rule_contracts())
    rule_ids = tuple(str(getattr(item, "rule_id", "") or "") for item in contracts)
    expected = tuple(f"LX0609-{index:03d}" for index in range(1, 50))
    if rule_ids != expected:
        raise BenchmarkContractError("LX0609 rule catalog is not the expected 49 rules")
    executor_types: dict[str, str] = {}
    for contract in contracts:
        authority = str(getattr(contract, "decision_authority", "") or "").strip()
        executor_type = _AUTHORITY_EXECUTOR_TYPES.get(authority)
        if executor_type is None:
            raise BenchmarkContractError("invalid LX0609 decision authority")
        executor_types[str(contract.rule_id)] = executor_type
    if len(executor_types) != 49:
        raise BenchmarkContractError("invalid LX0609 decision authority attestation")
    return rule_ids, executor_types


def _validate_evaluation_date(value: str) -> str:
    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise BenchmarkContractError("invalid evaluation_as_of_date") from exc
    if parsed.isoformat() != normalized:
        raise BenchmarkContractError("invalid evaluation_as_of_date")
    return normalized


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
        raise BenchmarkContractError("preproduction response must contain ordered 49 rules")
    return results, metrics


def _golden_response(
    response: Mapping[str, Any],
    *,
    results: Sequence[Mapping[str, Any]],
    executor_types: Mapping[str, str],
    evidence_attestations: Mapping[str, str],
) -> dict[str, Any]:
    """投影Golden所需最小响应，排除runner性能字段和客户长文本。"""

    projected_results: list[dict[str, Any]] = []
    for result in results:
        metadata = result.get("metadata")
        reason_code = ""
        if isinstance(metadata, Mapping):
            reason_code = str(metadata.get("reason_code") or "").strip()
        rule_id = str(result.get("rule_id") or "").strip().upper()
        executor_type = str(executor_types.get(rule_id) or "").strip()
        if executor_type not in {"program", "llm"}:
            raise BenchmarkContractError("missing LX0609 decision authority attestation")
        evidence_attestation = str(evidence_attestations.get(rule_id) or "").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", evidence_attestation):
            raise BenchmarkContractError("missing rule evidence attestation")
        projected_results.append(
            {
                "rule_id": rule_id,
                "status": str(result.get("status") or "").strip().lower(),
                "metadata": {
                    "reason_code": reason_code,
                    "executor_type": executor_type,
                },
                "evidence_items": [
                    {"evidence_attestation": evidence_attestation}
                ],
            }
        )
    return {
        "schema_version": str(response.get("schema_version") or ""),
        "results": projected_results,
    }


async def build_benchmark_batch(
    *,
    case_map: Mapping[str, Any],
    evaluation_as_of_date: str,
    bundle_loader: BundleLoader = read_luxian_0609_preproduction_bundle,
    runner: Runner = run_luxian_0609_preproduction,
    llm_client: Any,
    base_settings: Any,
    fail_on_technical_error: bool = True,
) -> dict[str, Any]:
    """顺序执行固定20例并返回可进入Golden候选构建器的安全批次。"""

    selector_version, cases = _validate_case_map(case_map)
    as_of_date = _validate_evaluation_date(evaluation_as_of_date)
    selected_rule_ids, executor_types = _rule_attestations()
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
        evidence_attestations: dict[str, str] = {}
        for item in evidence_attestation_rows:
            if not isinstance(item, Mapping) or set(item) != {
                "rule_id",
                "evidence_hash",
            }:
                raise BenchmarkContractError("invalid evidence attestation")
            rule_id = str(item.get("rule_id") or "").strip().upper()
            evidence_hash = str(item.get("evidence_hash") or "").strip().lower()
            if (
                rule_id in evidence_attestations
                or not re.fullmatch(r"[0-9a-f]{64}", evidence_hash)
            ):
                raise BenchmarkContractError("invalid evidence attestation")
            evidence_attestations[rule_id] = evidence_hash
        if len(set(evidence_attestations.values())) != len(selected_rule_ids):
            raise BenchmarkContractError("duplicate evidence attestation")
        case_evidence_hashes = set(evidence_attestations.values())
        if all_evidence_hashes.intersection(case_evidence_hashes):
            raise BenchmarkContractError("duplicate cross-case evidence attestation")
        all_evidence_hashes.update(case_evidence_hashes)
        output_cases.append(
            {
                "case_label": case["case_label"],
                "coordinate_hash": coordinate_hash,
                "evidence_attestations": evidence_attestations,
                "response": _golden_response(
                    response,
                    results=results,
                    executor_types=executor_types,
                    evidence_attestations=evidence_attestations,
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
    if len(all_evidence_hashes) != 20 * len(selected_rule_ids):
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
    batch = {
        "schema_version": API_BATCH_SCHEMA_VERSION,
        "selector_version": selector_version,
        "selector_digest": selector_digest,
        "rule_set_digest": rule_set_digest,
        "evaluation_as_of_date": as_of_date,
        "cases": output_cases,
        "summary": summary,
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
    parser.add_argument(
        "--allow-technical-error",
        action="store_true",
        help="允许输出含technical_error的诊断批次；默认任何technical_error均失败",
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
            )
        )
        _write_output(args.output, batch)
    except Exception:
        print("LX0609 benchmark20 failed safely", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schema_version": API_BATCH_SCHEMA_VERSION,
                "case_count": batch["summary"]["case_count"],
                "judgment_count": batch["summary"]["judgment_count"],
                "technical_error_count": batch["summary"]["technical_error_count"],
                "selector_digest": batch["selector_digest"],
                "rule_set_digest": batch["rule_set_digest"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
