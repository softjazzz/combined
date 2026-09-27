"""LX0609 Fast5 通用只读验收器。

本模块只编排五个私有坐标病例调用既有准生产旁路；不调用 router、任务、
客户结果或任何写入接口。返回值是严格白名单投影，可供调用方打印安全 JSON。
病例映射始终由调用方在进程内传入，既不读取也不写入文件。
"""

from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import math
import re
from time import perf_counter
from typing import Any, Awaitable, Callable, Iterable, Mapping, Sequence

from app.services.luxian_0609.preproduction_bundle_reader import (
    read_luxian_0609_preproduction_bundle,
)
from app.services.luxian_0609.preproduction_runner import (
    run_luxian_0609_preproduction,
)
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts


FAST5_SCHEMA_VERSION = "lx0609-fast5-readonly-v1"
FAST5_RULE_IDS = (
    "LX0609-02-01-04",
    "LX0609-02-01-05",
    "LX0609-06-01-02",
    "LX0609-06-01-04",
    "LX0609-06-01-05",
    "LX0609-06-03-03",
    "LX0609-06-03-04",
    "LX0609-12-01-02",
    "LX0609-04-02-03",
    "LX0609-04-02-04",
    "LX0609-05-01-01",
    "LX0609-11-01-01",
)
FAST5_FAMILIES = {
    "course": ("LX0609-02-01-04", "LX0609-02-01-05", "LX0609-12-01-02"),
    "exam_lab": (
        "LX0609-06-01-02",
        "LX0609-06-01-04",
        "LX0609-06-01-05",
        "LX0609-06-03-03",
        "LX0609-06-03-04",
    ),
    "surgery": ("LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01", "LX0609-11-01-01"),
}
_STATES = (
    "compliant",
    "non_compliant",
    "not_applicable",
    "data_gap",
    "technical_error",
    "evaluation_unknown",
)
_CASE_KEYS = frozenset(
    {"case_label", "scene", "institute_id", "patient_id", "visit_id"}
)
_CODE_RE = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")

BundleLoader = Callable[..., Mapping[str, Any]]
Runner = Callable[..., Awaitable[Mapping[str, Any]]]


class Fast5ContractError(ValueError):
    """Fast5 合同错误；消息不包含病例输入或底层异常。"""


def _digest(*, domain: str, value: Any) -> str:
    payload = repr((domain, value)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_evaluation_as_of_date(value: str) -> str:
    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise Fast5ContractError("invalid evaluation date") from exc
    if parsed.isoformat() != normalized:
        raise Fast5ContractError("invalid evaluation date")
    return normalized


def _validate_case_map(value: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    if not isinstance(value, Mapping) or set(value) != {"cases"}:
        raise Fast5ContractError("invalid Fast5 case map")
    raw_cases = value.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != 5:
        raise Fast5ContractError("Fast5 requires exactly five cases")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, Mapping) or set(raw_case) != _CASE_KEYS:
            raise Fast5ContractError("invalid Fast5 case map")
        label = str(raw_case.get("case_label") or "").strip()
        if label != f"case-{index:02d}":
            raise Fast5ContractError("Fast5 cases must be case-01..case-05")
        scene = str(raw_case.get("scene") or "").strip().lower()
        if scene not in {"running", "final"}:
            raise Fast5ContractError("invalid Fast5 scene")
        coordinates = tuple(
            str(raw_case.get(field) or "").strip()
            for field in ("institute_id", "patient_id", "visit_id")
        )
        if any(not item or len(item) > 256 for item in coordinates):
            raise Fast5ContractError("invalid Fast5 coordinates")
        key = (scene, *coordinates)
        if key in seen:
            raise Fast5ContractError("duplicate Fast5 coordinates")
        seen.add(key)
        normalized.append(
            {
                "case_label": label,
                "scene": scene,
                "institute_id": coordinates[0],
                "patient_id": coordinates[1],
                "visit_id": coordinates[2],
            }
        )
    return tuple(normalized)


def _resolve_selected_rule_ids(
    *,
    family: str = "all",
    selected_rule_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    catalog = tuple(
        str(getattr(contract, "rule_id", "") or "").strip().upper()
        for contract in load_luxian_0609_rule_contracts()
    )
    expected_fast5_order = tuple(rule_id for rule_id in catalog if rule_id in FAST5_RULE_IDS)
    if expected_fast5_order != FAST5_RULE_IDS:
        raise Fast5ContractError("invalid Fast5 catalog order")
    normalized_family = str(family or "all").strip().lower()
    if normalized_family == "all":
        allowed = FAST5_RULE_IDS
    else:
        allowed = FAST5_FAMILIES.get(normalized_family)
        if allowed is None:
            raise Fast5ContractError("invalid Fast5 family")
    if selected_rule_ids is None:
        return tuple(allowed)
    supplied = tuple(str(item or "").strip().upper() for item in selected_rule_ids)
    if not supplied or any(not item for item in supplied) or len(supplied) != len(set(supplied)):
        raise Fast5ContractError("invalid Fast5 rule scope")
    if any(item not in allowed for item in supplied):
        raise Fast5ContractError("invalid Fast5 rule scope")
    expected = tuple(item for item in catalog if item in set(supplied))
    if supplied != expected:
        raise Fast5ContractError("Fast5 rule scope order mismatch")
    return supplied


def _coordinate_hash(case: Mapping[str, str]) -> str:
    return _digest(
        domain="lx0609-fast5-coordinate-v1",
        value=(
            case["scene"],
            case["institute_id"],
            case["patient_id"],
            case["visit_id"],
        ),
    )


def _private_terms(value: Any, *, key: str = "") -> set[str]:
    """只用于最终投影自检，不把收集到的内容带出本函数。"""
    private_keys = (
        "institute_id", "patient_id", "visit_id", "medical_text", "record_content",
        "content", "text", "prompt", "response", "coordinate", "date", "time",
    )
    found: set[str] = set()
    normalized_key = str(key or "").lower()
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            found.update(_private_terms(child_value, key=str(child_key)))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_private_terms(item, key=key))
    elif isinstance(value, str) and any(item in normalized_key for item in private_keys):
        if len(value.strip()) >= 4:
            found.add(value.strip())
    return found


def _safe_code(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if _CODE_RE.fullmatch(normalized) else None


def _project_results(
    value: Mapping[str, Any],
    *,
    selected_rule_ids: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, float | int]]:
    if not isinstance(value, Mapping):
        raise Fast5ContractError("invalid Fast5 runner response")
    if value.get("schema_version") != "lx0609-preproduction-runner-v1":
        raise Fast5ContractError("invalid Fast5 runner response")
    raw_results = value.get("results")
    raw_metrics = value.get("metrics")
    if not isinstance(raw_results, list) or not isinstance(raw_metrics, Mapping):
        raise Fast5ContractError("invalid Fast5 runner response")
    rule_ids = tuple(
        str(item.get("rule_id") or "").strip().upper()
        for item in raw_results
        if isinstance(item, Mapping)
    )
    if rule_ids != selected_rule_ids or len(raw_results) != len(selected_rule_ids):
        raise Fast5ContractError("invalid Fast5 runner scope")
    results: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, Mapping):
            raise Fast5ContractError("invalid Fast5 runner result")
        status = str(item.get("status") or "").strip().lower()
        if status not in _STATES:
            raise Fast5ContractError("invalid Fast5 result status")
        metadata = item.get("metadata")
        safe_metadata: dict[str, str] = {}
        if isinstance(metadata, Mapping):
            for key in ("reason_code", "execution_source", "executor_type"):
                safe = _safe_code(metadata.get(key))
                if safe is not None:
                    safe_metadata[key] = safe
        results.append(
            {
                "rule_id": str(item.get("rule_id") or "").strip().upper(),
                "status": status,
                "metadata": safe_metadata,
            }
        )
    metrics = {
        "wall_time_ms": max(0.0, float(raw_metrics.get("wall_time_ms") or 0.0)),
        "llm_call_count": max(0, int(raw_metrics.get("llm_call_count") or 0)),
        "prompt_tokens": max(0, int(raw_metrics.get("prompt_tokens") or 0)),
        "completion_tokens": max(0, int(raw_metrics.get("completion_tokens") or 0)),
        "total_tokens": max(0, int(raw_metrics.get("total_tokens") or 0)),
    }
    return results, metrics


def _technical_results(selected_rule_ids: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": rule_id,
            "status": "technical_error",
            "metadata": {"reason_code": "fast5_case_execution_failed"},
        }
        for rule_id in selected_rule_ids
    ]


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(item) for item in values)
    position = (len(ordered) - 1) * percentile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)


def _assert_safe_output(value: Mapping[str, Any], *, private_terms: set[str]) -> None:
    encoded = repr(value)
    if any(term and term in encoded for term in private_terms):
        raise Fast5ContractError("Fast5 output privacy validation failed")
    forbidden = frozenset(
        {
        "institute_id", "patient_id", "visit_id", "medical_text", "record_content",
        "primary_document_text", "prompt", "raw_response", "error_message", "sql",
        }
    )

    def _walk(item: Any) -> bool:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if str(key or "").strip().lower() in forbidden or _walk(child):
                    return True
        elif isinstance(item, (list, tuple)):
            return any(_walk(child) for child in item)
        return False

    if _walk(value):
        raise Fast5ContractError("Fast5 output privacy validation failed")


async def build_fast5_batch(
    *,
    case_map: Mapping[str, Any],
    evaluation_as_of_date: str,
    sample_kind: str,
    family: str = "all",
    selected_rule_ids: Iterable[str] | None = None,
    bundle_loader: BundleLoader = read_luxian_0609_preproduction_bundle,
    runner: Runner = run_luxian_0609_preproduction,
    llm_client: Any,
    base_settings: Any,
) -> dict[str, Any]:
    """顺序运行五例，只返回严格脱敏的 Fast5 验收结果。"""
    normalized_kind = str(sample_kind or "").strip().lower()
    if normalized_kind not in {"real", "synthetic"}:
        raise Fast5ContractError("sample_kind must be real or synthetic")
    cases = _validate_case_map(case_map)
    as_of_date = _validate_evaluation_as_of_date(evaluation_as_of_date)
    selected = _resolve_selected_rule_ids(
        family=family,
        selected_rule_ids=selected_rule_ids,
    )
    private_terms = _private_terms(case_map)
    private_terms.add(as_of_date)
    output_cases: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    latencies: list[float] = []
    totals: Counter[str] = Counter()
    started = perf_counter()

    for case in cases:
        case_started = perf_counter()
        coordinate_hash = _coordinate_hash(case)
        results: list[dict[str, Any]]
        metrics: dict[str, float | int]
        try:
            bundle = bundle_loader(
                scene=case["scene"],
                institute_id=case["institute_id"],
                patient_id=case["patient_id"],
                visit_id=case["visit_id"],
                schema="public",
            )
            private_terms.update(_private_terms(bundle))
            response = await runner(
                bundle=bundle,
                selected_customer_rule_ids=selected,
                evaluation_as_of_date=as_of_date,
                llm_client=llm_client,
                base_settings=base_settings,
                model_name=str(getattr(llm_client, "model", "") or ""),
            )
            private_terms.update(_private_terms(response))
            results, metrics = _project_results(response, selected_rule_ids=selected)
        except Exception:
            results = _technical_results(selected)
            metrics = {
                "wall_time_ms": round((perf_counter() - case_started) * 1000.0, 3),
                "llm_call_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        for result in results:
            statuses[result["status"]] += 1
        latencies.append(float(metrics["wall_time_ms"]))
        for key in ("llm_call_count", "prompt_tokens", "completion_tokens", "total_tokens"):
            totals[key] += int(metrics[key])
        output_cases.append(
            {
                "case_label": case["case_label"],
                "coordinate_hash": coordinate_hash,
                "results": results,
                "metrics": metrics,
            }
        )

    summary = {
        "case_count": len(output_cases),
        "judgment_count": len(output_cases) * len(selected),
        "status_counts": {state: int(statuses.get(state) or 0) for state in _STATES},
        "technical_count": int(statuses.get("technical_error") or 0),
        "technical_error_count": int(statuses.get("technical_error") or 0),
        **{key: int(totals.get(key) or 0) for key in totals},
        "wall_time_p50_ms": _percentile(latencies, 0.50),
        "wall_time_p95_ms": _percentile(latencies, 0.95),
        "batch_wall_time_ms": round((perf_counter() - started) * 1000.0, 3),
    }
    output = {
        "schema_version": FAST5_SCHEMA_VERSION,
        "sample_kind": normalized_kind,
        "selected_rule_ids": list(selected),
        "evaluation_as_of_date_hash": _digest(
            domain="lx0609-fast5-evaluation-as-of-v1", value=as_of_date
        ),
        "cases": output_cases,
        "summary": summary,
    }
    _assert_safe_output(output, private_terms=private_terms)
    return output
