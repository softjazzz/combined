from __future__ import annotations

import argparse
import asyncio
import copy
from datetime import date
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from sqlalchemy import text


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
DEFAULT_CASE_MAP = ROOT / "tmp-lx0609-0426-current-audit" / "private-case-map.json"
EXPECTED_LUXIAN_0609_RULE_IDS = tuple(
    f"LX0609-{number:03d}" for number in range(1, 50)
)
_CASE_LABEL = re.compile(r"case-\d{2}")
_FIXED10_CASE_LABELS = tuple(f"case-{index:02d}" for index in range(1, 11))
_COURSE_SEVERITY_RULE_IDS = ("LX0609-008", "LX0609-009")
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PROMPT_RULE_ID = re.compile(r"\bLX0609-\d{3}\b")
_RULE_STATES = frozenset(
    {
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_gap",
        "evaluation_unknown",
        "technical_error",
    }
)
_SAFE_EXECUTION_SOURCES = frozenset({"lx0609_native"})
_SAFE_QUERY_STATES = frozenset({"available", "empty", "unavailable", "error"})
_SAFE_COMPLETENESS = frozenset({"complete", "truncated", "unproven"})
_JSON_FIELDS = (
    "structured_context",
    "document_hits",
    "data_quality_flags",
    "source_doc_priority",
)

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _validate_evaluation_as_of_date(value: str | None) -> str:
    """仅接受完整 ISO 自然日，防止回归时用运行时刻替代冻结终点。"""

    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeError("evaluation_as_of_date必须是YYYY-MM-DD") from exc
    if parsed.isoformat() != normalized:
        raise RuntimeError("evaluation_as_of_date必须是YYYY-MM-DD")
    return normalized


def _evaluation_as_of_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_course_severity_expected_matrix(
    value: Sequence[Mapping[str, Any]] | None,
    *,
    evaluation_as_of_date: str,
) -> dict[tuple[str, str], dict[str, str]]:
    """验证固定10例008/009人工事实矩阵，拒绝正文、坐标和原始日期。"""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RuntimeError("008/009固定病例事实矩阵无效")
    expected_keys = {
        "case_label",
        "rule_id",
        "expected_state",
        "expected_reason",
        "manual_fact_basis",
        "horizon_basis",
        "evidence_attestation_hash",
        "evaluation_as_of_hash",
    }
    expected_pairs = tuple(
        (case_label, rule_id)
        for case_label in _FIXED10_CASE_LABELS
        for rule_id in _COURSE_SEVERITY_RULE_IDS
    )
    matrix: dict[tuple[str, str], dict[str, str]] = {}
    expected_as_of_hash = _evaluation_as_of_hash(evaluation_as_of_date)
    for item in value:
        if not isinstance(item, Mapping) or set(item) != expected_keys:
            raise RuntimeError("008/009固定病例事实矩阵无效")
        row = {key: str(item.get(key) or "").strip() for key in expected_keys}
        pair = (row["case_label"], row["rule_id"])
        if (
            pair not in expected_pairs
            or pair in matrix
            or row["expected_state"] not in _RULE_STATES
            or any(
                not _SAFE_CODE.fullmatch(row[key])
                for key in (
                    "expected_reason",
                    "manual_fact_basis",
                    "horizon_basis",
                )
            )
            or not _SHA256.fullmatch(row["evidence_attestation_hash"])
            or row["evaluation_as_of_hash"] != expected_as_of_hash
        ):
            raise RuntimeError("008/009固定病例事实矩阵无效")
        matrix[pair] = row
    if tuple(matrix) != expected_pairs:
        raise RuntimeError("008/009固定病例事实矩阵不完整")
    return matrix


def load_course_severity_expected_matrix(
    path: Path,
    *,
    evaluation_as_of_date: str,
) -> dict[tuple[str, str], dict[str, str]]:
    """只读取外置的安全人工矩阵；解析错误不回显文件内容或路径。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("008/009固定病例事实矩阵不可读取") from exc
    return _validate_course_severity_expected_matrix(
        payload,
        evaluation_as_of_date=evaluation_as_of_date,
    )


def resolve_full_luxian_0609_rule_ids(
    inventory: Sequence[Any] | None = None,
) -> list[str]:
    if inventory is None:
        from app.services.luxian_0609.native_package import (
            load_luxian_0609_dependency_inventory,
        )

        inventory = load_luxian_0609_dependency_inventory()
    rule_ids = [str(getattr(item, "rule_id", "") or "").strip() for item in inventory]
    if tuple(rule_ids) != EXPECTED_LUXIAN_0609_RULE_IDS:
        raise RuntimeError("全49点回归必须显式包含49个客户规则ID，且顺序为LX0609-001..049")
    return rule_ids


def _result_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("evaluation_results", "parsed_evaluation_results", "results"):
        rows = result.get(key)
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)]
    return []


def validate_full_luxian_0609_results(result: Mapping[str, Any]) -> None:
    returned = tuple(
        str(item.get("rule_id") or item.get("rule_code") or "").strip()
        for item in _result_rows(result)
    )
    if returned != EXPECTED_LUXIAN_0609_RULE_IDS:
        raise RuntimeError("LX0609全49点回归结果范围异常：必须返回49个客户规则且顺序一致")


def build_safe_rule_states(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "rule_id": str(item.get("rule_id") or item.get("rule_code") or ""),
            "status": str(item.get("status") or "unknown"),
        }
        for item in rows
    ]


class InMemoryLlmReplay:
    """仅在内存保存响应；以 prompt 摘要保证 A/B 输入完全一致。"""

    def __init__(self, original_generate: Any) -> None:
        self._original_generate = original_generate
        self._records: list[tuple[str, dict[str, Any]]] = []
        self._used_record_indexes: set[int] = set()
        self._replay_count = 0

    @staticmethod
    def _prompt_hash(prompt: str) -> str:
        return hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()

    async def record(self, prompt: str) -> dict[str, Any]:
        response = await self._original_generate(prompt)
        if not isinstance(response, Mapping):
            raise RuntimeError("LLM响应不是对象")
        self._records.append((self._prompt_hash(prompt), copy.deepcopy(dict(response))))
        return response

    async def replay(self, prompt: str) -> dict[str, Any]:
        prompt_hash = self._prompt_hash(prompt)
        for index, (expected_hash, response) in enumerate(self._records):
            if index in self._used_record_indexes or expected_hash != prompt_hash:
                continue
            self._used_record_indexes.add(index)
            self._replay_count += 1
            return copy.deepcopy(response)
        raise RuntimeError("A/B候选模型输入未在基线prompt摘要中出现")

    @property
    def call_count(self) -> int:
        return len(self._records)

    @property
    def replay_count(self) -> int:
        return self._replay_count


def load_private_case_map(path: Path, *, limit: int) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("病例映射必须是数组")
    cases: list[dict[str, str]] = []
    for item in payload[:limit]:
        if not isinstance(item, Mapping):
            raise RuntimeError("病例映射包含非法行")
        row = {
            key: str(item.get(key) or "").strip()
            for key in ("case_label", "institute_id", "patient_id", "visit_id")
        }
        if not _CASE_LABEL.fullmatch(row["case_label"]) or not all(row.values()):
            raise RuntimeError("病例映射缺少安全标签或查询坐标")
        cases.append(row)
    if len(cases) != limit:
        raise RuntimeError(f"病例映射不足{limit}例")
    return cases


def load_bundle_readonly(case: Mapping[str, str]) -> dict[str, Any]:
    from app.database.connection import engine

    if engine is None:
        raise RuntimeError("DATABASE_URL未配置")
    query = text(
        "SELECT * FROM public.running_record_bundle "
        "WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id "
        "LIMIT 1"
    )
    with engine.connect() as connection:
        row = connection.execute(
            query,
            {
                "institute_id": case["institute_id"],
                "patient_id": case["patient_id"],
                "visit_id": case["visit_id"],
            },
        ).mappings().first()
    if row is None:
        raise RuntimeError("病例bundle不存在")
    bundle = dict(row)
    for key in _JSON_FIELDS:
        value = bundle.get(key)
        if not isinstance(value, str):
            continue
        try:
            bundle[key] = json.loads(value)
        except json.JSONDecodeError:
            bundle[key] = {}
    return bundle


async def evaluate_full_luxian_0609_case(
    *,
    service: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
    evaluation_as_of_date: str | None = None,
    offline_pack_probe: bool = False,
) -> dict[str, Any]:
    if tuple(rule_ids) != EXPECTED_LUXIAN_0609_RULE_IDS:
        raise RuntimeError("全49点回归禁止使用空列表或非客户规则范围")
    request_kwargs: dict[str, Any] = {
        "bundle": bundle,
        "rule_ids": list(rule_ids),
        "bucket_strategy": "domain_only",
        "quality_profile": "throughput_v1",
        "batch_output_mode": "full",
        "enable_selective_refine": False,
        "use_execution_cache": False,
        "enable_pack_probe": bool(offline_pack_probe),
        "rule_set_key": "luxian_0609_qc_v1",
    }
    if evaluation_as_of_date is not None:
        request_kwargs["evaluation_as_of_date"] = _validate_evaluation_as_of_date(
            evaluation_as_of_date
        )
    result = await asyncio.wait_for(
        service.evaluate_running_final_bundle_input(**request_kwargs),
        timeout=timeout_seconds,
    )
    validate_full_luxian_0609_results(result)
    return result


def _safe_record_count_bucket(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return "unknown"
    if value == 0:
        return "0"
    if value == 1:
        return "1"
    return "2_plus"


def build_safe_pack_metrics(result: Mapping[str, Any]) -> dict[str, Any]:
    """仅输出离线分包基准所需聚合指标，不返回模型输入或病历内容。"""

    raw_metrics = result.get("pack_metrics")
    if not isinstance(raw_metrics, Mapping):
        raw_metrics = {}
    selected_by_bucket = raw_metrics.get("selected_pack_size_by_bucket")
    if not isinstance(selected_by_bucket, Mapping):
        selected_by_bucket = {}
    return {
        "selection_strategy": str(raw_metrics.get("pack_selection_strategy") or "unknown"),
        "probe_calls": int(raw_metrics.get("probe_calls") or 0),
        "total_packs": int(raw_metrics.get("total_packs") or 0),
        "single_rule_retries": int(raw_metrics.get("single_rule_retries") or 0),
        "pack_parse_retry_count": int(raw_metrics.get("pack_parse_retry_count") or 0),
        "selected_pack_size_by_bucket": {
            str(key): int(value)
            for key, value in selected_by_bucket.items()
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
        },
    }


def _safe_code_or_unknown(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if _SAFE_CODE.fullmatch(normalized) else "unknown"


def _source_keys_for_rule_audit(rule_id: str) -> tuple[str, ...]:
    """只解析注册表声明来源；不得从 bundle 或客户返回猜测来源。"""

    from app.services.luxian_0609.source_registry import (
        resolve_luxian_0609_controlled_fact_source_keys,
        resolve_luxian_0609_decision_support_source_keys,
        resolve_luxian_0609_rule_sources,
    )

    entries = resolve_luxian_0609_rule_sources((rule_id,))[rule_id]
    return tuple(
        sorted(
            {
                *(source_key for entry in entries for source_key in entry.source_keys),
                *resolve_luxian_0609_controlled_fact_source_keys((rule_id,)),
                *resolve_luxian_0609_decision_support_source_keys((rule_id,)),
            }
        )
    )


def _build_safe_formal_source_audit(
    *,
    result: Mapping[str, Any],
    snapshot: Any,
    reduced_decisions: Sequence[Any],
) -> list[dict[str, Any]]:
    """生成可人工核对、但不含快照身份或原始病历的固定审计视图。"""

    observations = {
        str(getattr(item, "source_key", "") or "").strip(): item
        for item in tuple(getattr(snapshot, "observations", ()) or ())
        if _SAFE_CODE.fullmatch(str(getattr(item, "source_key", "") or "").strip())
    }
    decisions_by_rule = {
        str(getattr(item, "rule_id", "") or "").strip(): item
        for item in reduced_decisions
        if str(getattr(item, "rule_id", "") or "").strip()
    }
    result_by_rule = {
        str(item.get("rule_id") or item.get("rule_code") or "").strip(): item
        for item in _result_rows(result)
    }
    audit: list[dict[str, Any]] = []
    for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS:
        result_row = result_by_rule.get(rule_id, {})
        metadata = result_row.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        raw_execution_source = str(metadata.get("execution_source") or "").strip()
        execution_source = (
            raw_execution_source
            if raw_execution_source in _SAFE_EXECUTION_SOURCES
            else "unknown"
        )
        reduced = decisions_by_rule.get(rule_id)
        raw_final_state = getattr(reduced, "final_state", "") if reduced else ""
        raw_final_state = getattr(raw_final_state, "value", raw_final_state)
        typed_final_state = (
            str(raw_final_state)
            if str(raw_final_state) in _RULE_STATES
            else "unknown"
        )
        raw_reason_code = getattr(reduced, "reason_code", "") if reduced else ""
        raw_refs = getattr(reduced, "fact_refs", ()) if reduced else ()
        fact_ref_count = len(raw_refs) if isinstance(raw_refs, (tuple, list)) else 0
        sources: list[dict[str, str]] = []
        for source_key in _source_keys_for_rule_audit(rule_id):
            observation = observations.get(source_key)
            raw_query_state = getattr(observation, "query_state", "") if observation else ""
            raw_query_state = getattr(raw_query_state, "value", raw_query_state)
            raw_completeness = getattr(observation, "completeness", "") if observation else ""
            raw_completeness = getattr(raw_completeness, "value", raw_completeness)
            sources.append(
                {
                    "source_key": source_key,
                    "query_state": (
                        str(raw_query_state)
                        if str(raw_query_state) in _SAFE_QUERY_STATES
                        else "unknown"
                    ),
                    "completeness": (
                        str(raw_completeness)
                        if str(raw_completeness) in _SAFE_COMPLETENESS
                        else "unknown"
                    ),
                    "record_count_bucket": _safe_record_count_bucket(
                        getattr(observation, "record_count", None)
                        if observation
                        else None
                    ),
                }
            )
        audit.append(
            {
                "rule_id": rule_id,
                "status": (
                    str(result_row.get("status") or "unknown")
                    if str(result_row.get("status") or "unknown") in _RULE_STATES
                    else "unknown"
                ),
                "execution_source": execution_source,
                "typed_final_state": typed_final_state,
                "typed_reason_code": _safe_code_or_unknown(raw_reason_code),
                "typed_fact_ref_count": fact_ref_count,
                "sources": sources,
            }
        )
    return audit


def _safe_token_count(value: Any) -> int:
    return (
        int(value)
        if not isinstance(value, bool) and isinstance(value, int) and value >= 0
        else 0
    )


def _safe_usage_counts(response: Any) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response, Mapping) else None
    usage = usage if isinstance(usage, Mapping) else {}
    return {
        "prompt_tokens": _safe_token_count(usage.get("prompt_tokens")),
        "completion_tokens": _safe_token_count(usage.get("completion_tokens")),
        "total_tokens": _safe_token_count(usage.get("total_tokens")),
    }


def _build_safe_token_analysis(
    *,
    result: Mapping[str, Any],
    calls: Sequence[tuple[tuple[str, ...], Mapping[str, int]]],
    model_error_call_count: int,
) -> dict[str, Any]:
    """按唯一规则 ID 归因；多规则或未识别调用永远不猜测、不均摊。"""

    per_rule = {
        rule_id: {
            "rule_id": rule_id,
            "llm_call_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        for rule_id in EXPECTED_LUXIAN_0609_RULE_IDS
    }
    shared = {
        "llm_call_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model_error_call_count": model_error_call_count,
    }
    for rule_ids, usage in calls:
        target = (
            per_rule[rule_ids[0]]
            if len(rule_ids) == 1 and rule_ids[0] in per_rule
            else shared
        )
        target["llm_call_count"] += 1
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            target[key] += _safe_token_count(usage.get(key))

    token_usage = result.get("token_usage")
    token_usage = token_usage if isinstance(token_usage, Mapping) else {}
    official = {
        key: _safe_token_count(token_usage.get(key))
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    wrapped_total = sum(
        int(item["total_tokens"])
        for item in (*per_rule.values(), shared)
    )
    official_total = official["total_tokens"]
    usage_mismatch = wrapped_total != official_total
    return {
        "llm_call_count": len(calls) + model_error_call_count,
        **official,
        "unattributed_tokens": (
            official_total - wrapped_total
            if official_total >= wrapped_total
            else "unknown"
        ),
        "model_error_call_count": model_error_call_count,
        "usage_mismatch": usage_mismatch,
        "token_analysis": list(per_rule.values()),
        "shared_or_unattributed": shared,
    }


async def evaluate_formal_source_audit_case(
    *,
    service: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
    evaluation_as_of_date: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """在同一次正式 service 调用内捕获同源 snapshot 与归约结果。

    该函数不新增数据库或模型调用；它仅暂时包裹 execution 模块的请求内函数。
    """

    from app.services.luxian_0609 import execution as luxian_execution

    original_snapshot_provider = luxian_execution.build_luxian_0609_evidence_snapshot
    original_session_provider = luxian_execution.build_luxian_0609_evidence_read_session
    original_decision_binder = luxian_execution.bind_and_reduce_luxian_0609_rule_decisions
    primary_client = getattr(service, "client", service.adjudicator_client)
    adjudicator_client = service.adjudicator_client
    original_primary_generate = primary_client.generate
    original_adjudicator_generate = adjudicator_client.generate
    rule_engine = getattr(service, "rule_engine", None)
    original_rule_engine_generate = getattr(rule_engine, "_llm_generate", None)
    captured_snapshots: list[Any] = []
    captured_reductions: list[tuple[Any, ...]] = []
    captured_model_calls: list[tuple[tuple[str, ...], Mapping[str, int]]] = []
    model_error_call_count = 0

    def capture_snapshot_provider(**kwargs: Any) -> Any:
        snapshot = original_snapshot_provider(**kwargs)
        captured_snapshots.append(snapshot)
        return snapshot

    def capture_session_provider(**kwargs: Any) -> Any:
        session = original_session_provider(**kwargs)
        captured_snapshots.append(getattr(session, "snapshot", None))
        return session

    def capture_decision_binder(**kwargs: Any) -> tuple[Any, ...]:
        reduced = original_decision_binder(**kwargs)
        captured_reductions.append(tuple(reduced))
        return reduced

    async def capture_generate(
        original_generate: Any,
        prompt: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal model_error_call_count
        # 仅在调用栈内扫描；绝不保存或输出 prompt 原文、摘要或 marker。
        rule_ids = tuple(sorted(set(_PROMPT_RULE_ID.findall(str(prompt)))))
        try:
            response = await original_generate(prompt, *args, **kwargs)
        except Exception:
            model_error_call_count += 1
            raise
        captured_model_calls.append((rule_ids, _safe_usage_counts(response)))
        return response

    try:
        luxian_execution.build_luxian_0609_evidence_snapshot = capture_snapshot_provider
        luxian_execution.build_luxian_0609_evidence_read_session = capture_session_provider
        luxian_execution.bind_and_reduce_luxian_0609_rule_decisions = (
            capture_decision_binder
        )
        primary_client.generate = lambda prompt, *args, **kwargs: capture_generate(
            original_primary_generate, prompt, *args, **kwargs
        )
        if rule_engine is not None and callable(original_rule_engine_generate):
            rule_engine._llm_generate = lambda prompt, *args, **kwargs: capture_generate(
                original_rule_engine_generate, prompt, *args, **kwargs
            )
        if adjudicator_client is not primary_client:
            adjudicator_client.generate = lambda prompt, *args, **kwargs: capture_generate(
            original_adjudicator_generate, prompt, *args, **kwargs
            )
        result = await evaluate_full_luxian_0609_case(
            service=service,
            bundle=bundle,
            rule_ids=rule_ids,
            timeout_seconds=timeout_seconds,
            evaluation_as_of_date=evaluation_as_of_date,
        )
    finally:
        luxian_execution.build_luxian_0609_evidence_snapshot = original_snapshot_provider
        luxian_execution.build_luxian_0609_evidence_read_session = original_session_provider
        luxian_execution.bind_and_reduce_luxian_0609_rule_decisions = original_decision_binder
        primary_client.generate = original_primary_generate
        if rule_engine is not None and callable(original_rule_engine_generate):
            rule_engine._llm_generate = original_rule_engine_generate
        if adjudicator_client is not primary_client:
            adjudicator_client.generate = original_adjudicator_generate

    if len(captured_snapshots) != 1 or captured_snapshots[0] is None:
        raise RuntimeError("同源证据审计快照捕获次数异常")
    if len(captured_reductions) != 1:
        raise RuntimeError("同源证据审计归约捕获次数异常")
    result_repr = repr(result)
    if any(
        marker in result_repr
        for marker in (
            "evidence_snapshot",
            "snapshot_hash",
            "fact_refs",
            "decision_fingerprint",
            "visit_ref",
        )
    ):
        raise RuntimeError("同源证据审计客户返回包含内部对象")
    return (
        result,
        _build_safe_formal_source_audit(
            result=result,
            snapshot=captured_snapshots[0],
            reduced_decisions=captured_reductions[0],
        ),
        _build_safe_token_analysis(
            result=result,
            calls=captured_model_calls,
            model_error_call_count=model_error_call_count,
        ),
    )


async def evaluate_snapshot_sidecar_ab_case(
    *,
    service: Any,
    settings: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
    evaluation_as_of_date: str | None = None,
) -> dict[str, Any]:
    """同一次真实模型响应内存重放，隔离模型随机性比较 sidecar。"""

    return await _evaluate_runtime_flag_ab_case(
        service=service,
        settings=settings,
        bundle=bundle,
        rule_ids=rule_ids,
        timeout_seconds=timeout_seconds,
        candidate_flag="LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED",
        mode_label="sidecar",
        evaluation_as_of_date=evaluation_as_of_date,
    )


async def evaluate_unified_engine_ab_case(
    *,
    service: Any,
    settings: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
    case_label: str = "",
    evaluation_as_of_date: str | None = None,
    course_severity_expected_matrix: (
        Sequence[Mapping[str, Any]]
        | Mapping[tuple[str, str], Mapping[str, Any]]
        | None
    ) = None,
) -> dict[str, Any]:
    """复用同一次真实模型响应，比较冻结旧链与统一执行信封正式入口。"""

    normalized_as_of_date = _validate_evaluation_as_of_date(evaluation_as_of_date)
    normalized_case_label = str(case_label or "").strip()
    if normalized_case_label not in _FIXED10_CASE_LABELS:
        raise RuntimeError("统一引擎008/009回归必须使用固定10例安全标签")
    raw_matrix_rows = (
        tuple(course_severity_expected_matrix.values())
        if isinstance(course_severity_expected_matrix, Mapping)
        else course_severity_expected_matrix
    )
    matrix = _validate_course_severity_expected_matrix(
        raw_matrix_rows,
        evaluation_as_of_date=normalized_as_of_date,
    )
    return await _evaluate_runtime_flag_ab_case(
        service=service,
        settings=settings,
        bundle=bundle,
        rule_ids=rule_ids,
        timeout_seconds=timeout_seconds,
        candidate_flag="LUXIAN_0609_UNIFIED_ENGINE_ENABLED",
        mode_label="unified_engine",
        case_label=normalized_case_label,
        evaluation_as_of_date=normalized_as_of_date,
        course_severity_expected_matrix=matrix,
    )


async def _evaluate_runtime_flag_ab_case(
    *,
    service: Any,
    settings: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
    candidate_flag: str,
    mode_label: str,
    case_label: str = "",
    evaluation_as_of_date: str | None = None,
    course_severity_expected_matrix: Mapping[tuple[str, str], Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """冻结两条迁移开关，只改变一个候选变量，排除串扰和模型随机性。"""

    from app.services.luxian_0609 import execution as luxian_execution
    from app.services.luxian_0609 import (
        native_basic_timeliness,
        native_consultation_execution,
        native_course_quality_execution,
        native_mdt_execution,
        native_surgery_gate_execution,
        native_tumor_pathology_execution,
        native_transfusion_execution,
        runtime_shadow_input_provider,
        source_evidence_reader,
    )
    from app.services import sichuan_qc_service as service_module

    managed_flags = (
        "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED",
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED",
        "LUXIAN_0609_RULE_DECISION_007_ENABLED",
        "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED",
        "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED",
    )
    missing = object()
    original_flags = {
        name: getattr(settings, name, missing) for name in managed_flags
    }
    original_generate = service.adjudicator_client.generate
    original_provider = luxian_execution.build_luxian_0609_evidence_snapshot
    original_session_provider = (
        luxian_execution.build_luxian_0609_evidence_read_session
    )
    original_decision_binder = (
        luxian_execution.bind_and_reduce_luxian_0609_rule_decisions
    )
    original_get_settings = service_module.get_settings
    replay = InMemoryLlmReplay(original_generate)
    snapshot_hashes: list[str] = []
    reader_phase = "baseline"
    family_reader_calls = {"baseline": 0, "candidate": 0}
    controlled_fact_query_count = 0
    course_severity_envelope_calls: dict[str, list[int]] = {
        "baseline": [],
        "candidate": [],
    }
    typed_decision_audits: list[dict[str, Any]] = []
    original_consultation_reader = (
        native_consultation_execution.read_luxian_0609_native_source_rows
    )
    original_mdt_reader = native_mdt_execution.read_luxian_0609_native_source_rows
    original_basic_reader = (
        native_basic_timeliness.read_luxian_0609_course_round_timeline
    )
    original_transfusion_reader = (
        native_transfusion_execution.read_luxian_0609_native_source_rows
    )
    original_course_reader = (
        native_course_quality_execution.read_luxian_0609_native_source_rows
    )
    original_course_executor = (
        luxian_execution.execute_luxian_0609_native_course_quality_rules
    )
    original_surgery_runtime_reader = (
        native_surgery_gate_execution.read_luxian_0609_runtime_source_rows
    )
    original_surgery_native_reader = (
        native_surgery_gate_execution.read_luxian_0609_native_source_rows
    )
    original_tumor_reader = (
        native_tumor_pathology_execution.read_luxian_0609_native_source_rows
    )
    original_presence_reader = (
        runtime_shadow_input_provider.read_luxian_0609_runtime_source_rows
    )
    original_unstable_order_reader = (
        native_course_quality_execution.has_luxian_0609_current_visit_unstable_order
    )
    original_controlled_fact_reader = (
        source_evidence_reader.has_luxian_0609_current_visit_unstable_order
    )

    def counted_consultation_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_consultation_reader(**kwargs)

    def counted_mdt_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_mdt_reader(**kwargs)

    def counted_basic_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_basic_reader(**kwargs)

    def counted_transfusion_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_transfusion_reader(**kwargs)

    def counted_course_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_course_reader(**kwargs)

    async def counted_course_executor(**kwargs):
        envelope = await original_course_executor(**kwargs)
        selected_rule_ids = tuple(str(value) for value in kwargs.get("rule_ids", ()))
        if set(selected_rule_ids).intersection(_COURSE_SEVERITY_RULE_IDS):
            course_severity_envelope_calls[reader_phase].append(
                int(getattr(envelope, "llm_call_count", 0) or 0)
            )
        return envelope

    def counted_surgery_runtime_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_surgery_runtime_reader(**kwargs)

    def counted_surgery_native_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_surgery_native_reader(**kwargs)

    def counted_tumor_reader(**kwargs):
        if kwargs.get("source_key") in {
            "pathology_exam_master",
            "pathology_exam_report",
            "surgery_record",
            "daily_course_record",
            "diagnosis",
            "inpat_drug_order",
            "discharge_record",
        }:
            family_reader_calls[reader_phase] += 1
        return original_tumor_reader(**kwargs)

    def counted_presence_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_presence_reader(**kwargs)

    def counted_unstable_order_reader(**kwargs):
        family_reader_calls[reader_phase] += 1
        return original_unstable_order_reader(**kwargs)

    def counted_controlled_fact_reader(**kwargs):
        nonlocal controlled_fact_query_count
        controlled_fact_query_count += 1
        return original_controlled_fact_reader(**kwargs)

    def counted_provider(**kwargs):
        snapshot = original_provider(**kwargs)
        snapshot_hashes.append(str(snapshot.snapshot_hash))
        return snapshot

    def counted_session_provider(**kwargs):
        session = original_session_provider(**kwargs)
        snapshot_hashes.append(str(session.snapshot.snapshot_hash))
        return session

    def audited_decision_binder(**kwargs):
        reduced = original_decision_binder(**kwargs)
        for item in reduced:
            typed_decision_audits.append(
                {
                    "rule_id": item.rule_id,
                    "final_state": item.final_state.value,
                    "reason_code": getattr(item, "reason_code", ""),
                    "fact_ref_count": len(item.fact_refs),
                }
            )
        return reduced

    try:
        service_module.get_settings = lambda: settings
        for name in managed_flags:
            setattr(settings, name, False)
        if mode_label == "unified_engine":
            native_consultation_execution.read_luxian_0609_native_source_rows = (
                counted_consultation_reader
            )
            native_mdt_execution.read_luxian_0609_native_source_rows = (
                counted_mdt_reader
            )
            native_basic_timeliness.read_luxian_0609_course_round_timeline = (
                counted_basic_reader
            )
            native_transfusion_execution.read_luxian_0609_native_source_rows = (
                counted_transfusion_reader
            )
            native_course_quality_execution.read_luxian_0609_native_source_rows = (
                counted_course_reader
            )
            luxian_execution.execute_luxian_0609_native_course_quality_rules = (
                counted_course_executor
            )
            native_surgery_gate_execution.read_luxian_0609_runtime_source_rows = (
                counted_surgery_runtime_reader
            )
            native_surgery_gate_execution.read_luxian_0609_native_source_rows = (
                counted_surgery_native_reader
            )
            native_tumor_pathology_execution.read_luxian_0609_native_source_rows = (
                counted_tumor_reader
            )
            runtime_shadow_input_provider.read_luxian_0609_runtime_source_rows = (
                counted_presence_reader
            )
            native_course_quality_execution.has_luxian_0609_current_visit_unstable_order = (
                counted_unstable_order_reader
            )
            source_evidence_reader.has_luxian_0609_current_visit_unstable_order = (
                counted_controlled_fact_reader
            )
        service.adjudicator_client.generate = replay.record
        baseline = await evaluate_full_luxian_0609_case(
            service=service,
            bundle=bundle,
            rule_ids=rule_ids,
            timeout_seconds=timeout_seconds,
            evaluation_as_of_date=evaluation_as_of_date,
        )

        setattr(settings, candidate_flag, True)
        if mode_label == "unified_engine":
            settings.LUXIAN_0609_RULE_DECISION_007_ENABLED = True
            settings.LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED = True
            settings.LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED = True
        reader_phase = "candidate"
        service.adjudicator_client.generate = replay.replay
        luxian_execution.build_luxian_0609_evidence_snapshot = counted_provider
        luxian_execution.build_luxian_0609_evidence_read_session = (
            counted_session_provider
        )
        luxian_execution.bind_and_reduce_luxian_0609_rule_decisions = (
            audited_decision_binder
        )
        candidate = await evaluate_full_luxian_0609_case(
            service=service,
            bundle=bundle,
            rule_ids=rule_ids,
            timeout_seconds=timeout_seconds,
            evaluation_as_of_date=evaluation_as_of_date,
        )
    finally:
        for name, value in original_flags.items():
            if value is missing:
                delattr(settings, name)
            else:
                setattr(settings, name, value)
        service.adjudicator_client.generate = original_generate
        native_consultation_execution.read_luxian_0609_native_source_rows = (
            original_consultation_reader
        )
        native_mdt_execution.read_luxian_0609_native_source_rows = original_mdt_reader
        native_basic_timeliness.read_luxian_0609_course_round_timeline = (
            original_basic_reader
        )
        native_transfusion_execution.read_luxian_0609_native_source_rows = (
            original_transfusion_reader
        )
        native_course_quality_execution.read_luxian_0609_native_source_rows = (
            original_course_reader
        )
        luxian_execution.execute_luxian_0609_native_course_quality_rules = (
            original_course_executor
        )
        native_surgery_gate_execution.read_luxian_0609_runtime_source_rows = (
            original_surgery_runtime_reader
        )
        native_surgery_gate_execution.read_luxian_0609_native_source_rows = (
            original_surgery_native_reader
        )
        native_tumor_pathology_execution.read_luxian_0609_native_source_rows = (
            original_tumor_reader
        )
        runtime_shadow_input_provider.read_luxian_0609_runtime_source_rows = (
            original_presence_reader
        )
        native_course_quality_execution.has_luxian_0609_current_visit_unstable_order = (
            original_unstable_order_reader
        )
        source_evidence_reader.has_luxian_0609_current_visit_unstable_order = (
            original_controlled_fact_reader
        )
        luxian_execution.build_luxian_0609_evidence_snapshot = original_provider
        luxian_execution.build_luxian_0609_evidence_read_session = (
            original_session_provider
        )
        luxian_execution.bind_and_reduce_luxian_0609_rule_decisions = (
            original_decision_binder
        )
        service_module.get_settings = original_get_settings

    baseline_states = build_safe_rule_states(_result_rows(baseline))
    candidate_states = build_safe_rule_states(_result_rows(candidate))
    baseline_tokens = int(
        dict(baseline.get("token_usage") or {}).get("total_tokens") or 0
    )
    candidate_tokens = int(
        dict(candidate.get("token_usage") or {}).get("total_tokens") or 0
    )
    if len(snapshot_hashes) != 1:
        raise RuntimeError(f"{mode_label}每病例必须且只能构建一次快照")
    candidate_repr = repr(candidate)
    if (
        snapshot_hashes[0] in candidate_repr
        or "evidence_snapshot" in candidate_repr
        or "unified_engine_used" in candidate_repr
        or "fact_refs" in candidate_repr
        or "decision_fingerprint" in candidate_repr
        or "rule007-authoritative-time" in candidate_repr
    ):
        raise RuntimeError(f"{mode_label}内部执行对象进入客户返回")
    comparison = {
        "states_match": baseline_states == candidate_states,
        "tokens_match": candidate_tokens <= baseline_tokens,
        "logical_llm_call_count": replay.replay_count,
        "snapshot_build_count": len(snapshot_hashes),
        "result_count": len(candidate_states),
    }
    if mode_label == "unified_engine" and family_reader_calls["baseline"] > 0:
        comparison["controlled_fact_query_count"] = controlled_fact_query_count
    if baseline_states != candidate_states:
        state_differences = [
            {
                "rule_id": baseline_row["rule_id"],
                "baseline_status": baseline_row["status"],
                "candidate_status": candidate_row["status"],
            }
            for baseline_row, candidate_row in zip(
                baseline_states, candidate_states
            )
            if baseline_row != candidate_row
        ]
        comparison["state_differences"] = state_differences
    if mode_label == "unified_engine":
        expected_typed_rule_ids = (
            "LX0609-001",
            "LX0609-002",
            "LX0609-004",
            "LX0609-005",
            "LX0609-006",
            "LX0609-007",
            "LX0609-008",
            "LX0609-009",
        )
        if tuple(item["rule_id"] for item in typed_decision_audits) != (
            expected_typed_rule_ids
        ):
            raise RuntimeError("类型化决策范围或顺序异常")
        if any(item["fact_ref_count"] <= 0 for item in typed_decision_audits):
            raise RuntimeError("类型化决策必须绑定安全证据引用")
        typed_007_audit = next(
            item
            for item in typed_decision_audits
            if item["rule_id"] == "LX0609-007"
        )
        typed_basic_audits = tuple(
            item
            for item in typed_decision_audits
            if item["rule_id"] in {"LX0609-001", "LX0609-005", "LX0609-006"}
        )
        if family_reader_calls["baseline"] > 0 and any(
            item["final_state"] != "data_gap"
            or item["reason_code"] != "authoritative_time_missing"
            for item in typed_basic_audits
        ):
            raise RuntimeError("固定10例缺少权威入院时间时基础时限族必须为data_gap")
        expected_migration_rule_ids = {
            "LX0609-001",
            "LX0609-005",
            "LX0609-006",
            "LX0609-008",
            "LX0609-009",
        }
        if course_severity_expected_matrix is None:
            raise RuntimeError("008/009固定病例事实矩阵不完整")
        candidate_by_rule = {
            item["rule_id"]: item["status"] for item in candidate_states
        }
        typed_by_rule = {item["rule_id"]: item for item in typed_decision_audits}
        for rule_id in _COURSE_SEVERITY_RULE_IDS:
            expected = course_severity_expected_matrix[(case_label, rule_id)]
            typed = typed_by_rule[rule_id]
            if (
                candidate_by_rule.get(rule_id) != expected["expected_state"]
                or typed["final_state"] != expected["expected_state"]
                or typed["reason_code"] != expected["expected_reason"]
            ):
                raise RuntimeError("008/009固定病例事实矩阵不匹配")
        unexpected_state_differences = tuple(
            item
            for item in comparison.get("state_differences", ())
            if item["rule_id"] not in expected_migration_rule_ids
            or (
                item["rule_id"] in {"LX0609-001", "LX0609-005", "LX0609-006"}
                and item["candidate_status"] != "data_gap"
            )
        )
        if unexpected_state_differences:
            raise RuntimeError("统一引擎出现非预期状态变化")
        comparison["states_accepted"] = True
        if (
            family_reader_calls["baseline"] > 0
            and controlled_fact_query_count != 1
        ):
            raise RuntimeError("007受控医嘱事实每病例必须且只能查询一次")
        if family_reader_calls["candidate"] != 0:
            raise RuntimeError("统一引擎已迁移规则族仍在自行查库")
        from app.services.luxian_0609.rule_contracts import (
            load_luxian_0609_rule_contracts,
        )

        contracts_by_id = {
            item.rule_id: item for item in load_luxian_0609_rule_contracts()
        }
        if (
            int(contracts_by_id["LX0609-008"].max_llm_calls_per_rule) != 0
            or int(contracts_by_id["LX0609-009"].max_llm_calls_per_rule) > 1
        ):
            raise RuntimeError("008/009模型调用合同异常")
        course_severity_candidate_llm_calls = sum(
            course_severity_envelope_calls["candidate"]
        )
        if course_severity_candidate_llm_calls > 1:
            raise RuntimeError("008/009模型调用超出上限")
        comparison.update(
            {
                "baseline_family_reader_calls": family_reader_calls["baseline"],
                "candidate_family_reader_calls": family_reader_calls["candidate"],
                "typed_decision_count": len(typed_decision_audits),
                "typed_decision_min_fact_ref_count": min(
                    item["fact_ref_count"] for item in typed_decision_audits
                ),
                "typed_model_call_count": 0,
                "typed_007_decision_count": 1,
                "typed_007_fact_ref_count": typed_007_audit["fact_ref_count"],
                "typed_007_model_call_count": 0,
                "typed_008_model_call_count": 0,
                "typed_009_model_call_count": course_severity_candidate_llm_calls,
                "course_severity_matrix_accepted": True,
            }
        )
    return comparison


async def run(args: argparse.Namespace) -> int:
    from app.core.settings import get_settings
    from app.services.sichuan_qc_service import SichuanQCService

    evaluation_as_of_date = _validate_evaluation_as_of_date(
        args.evaluation_as_of_date
    )
    if args.unified_engine_ab and int(args.limit) != len(_FIXED10_CASE_LABELS):
        raise RuntimeError("统一引擎008/009验收必须固定10例")
    course_severity_expected_matrix = (
        load_course_severity_expected_matrix(
            Path(args.course_severity_expected_matrix),
            evaluation_as_of_date=evaluation_as_of_date,
        )
        if args.unified_engine_ab
        else None
    )
    cases = load_private_case_map(Path(args.case_map), limit=int(args.limit))
    rule_ids = resolve_full_luxian_0609_rule_ids()
    service = SichuanQCService()
    settings = get_settings()
    failed = 0
    for case in cases:
        started = time.perf_counter()
        try:
            bundle = load_bundle_readonly(case)
            if args.snapshot_sidecar_ab or args.unified_engine_ab:
                evaluator = (
                    evaluate_snapshot_sidecar_ab_case
                    if args.snapshot_sidecar_ab
                    else evaluate_unified_engine_ab_case
                )
                comparison = await evaluator(
                    service=service,
                    settings=settings,
                    bundle=bundle,
                    rule_ids=rule_ids,
                    timeout_seconds=float(args.timeout_seconds),
                    **(
                        {
                            "case_label": case["case_label"],
                            "evaluation_as_of_date": evaluation_as_of_date,
                            "course_severity_expected_matrix": course_severity_expected_matrix,
                        }
                        if args.unified_engine_ab
                        else {"evaluation_as_of_date": evaluation_as_of_date}
                    ),
                )
                states_accepted = comparison.get(
                    "states_accepted", comparison["states_match"]
                )
                if not states_accepted or not comparison["tokens_match"]:
                    raise RuntimeError("A/B状态或token发生变化")
                summary = {
                    "case_label": case["case_label"],
                    **comparison,
                    "elapsed_ms": int((time.perf_counter() - started) * 1000),
                }
            elif args.formal_source_audit:
                result, source_audit, source_audit_performance = (
                    await evaluate_formal_source_audit_case(
                        service=service,
                        bundle=bundle,
                        rule_ids=rule_ids,
                        timeout_seconds=float(args.timeout_seconds),
                        evaluation_as_of_date=evaluation_as_of_date,
                    )
                )
                rows = _result_rows(result)
                token_usage = result.get("token_usage")
                if not isinstance(token_usage, Mapping):
                    token_usage = {}
                summary = {
                    "case_label": case["case_label"],
                    "result_count": len(rows),
                    "status_counts": dict(
                        Counter(str(item.get("status") or "unknown") for item in rows)
                    ),
                    "rule_states": build_safe_rule_states(rows),
                    "source_audit": source_audit,
                    "source_audit_performance": source_audit_performance,
                    "elapsed_ms": int((time.perf_counter() - started) * 1000),
                    "total_tokens": int(token_usage.get("total_tokens") or 0),
                }
            else:
                result = await evaluate_full_luxian_0609_case(
                    service=service,
                    bundle=bundle,
                    rule_ids=rule_ids,
                    timeout_seconds=float(args.timeout_seconds),
                    evaluation_as_of_date=evaluation_as_of_date,
                    offline_pack_probe=bool(args.offline_pack_probe),
                )
                rows = _result_rows(result)
                status_counts = dict(
                    Counter(str(item.get("status") or "unknown") for item in rows)
                )
                token_usage = result.get("token_usage")
                if not isinstance(token_usage, Mapping):
                    token_usage = {}
                summary = {
                    "case_label": case["case_label"],
                    "result_count": len(rows),
                    "status_counts": status_counts,
                    "rule_states": build_safe_rule_states(rows),
                    "elapsed_ms": int((time.perf_counter() - started) * 1000),
                    "token_usage": {
                        "prompt_tokens": int(token_usage.get("prompt_tokens") or 0),
                        "completion_tokens": int(token_usage.get("completion_tokens") or 0),
                        "total_tokens": int(token_usage.get("total_tokens") or 0),
                    },
                    "pack_metrics": build_safe_pack_metrics(result),
                }
        except Exception as exc:  # noqa: BLE001
            failed += 1
            summary = {
                "case_label": case["case_label"],
                "error_type": type(exc).__name__,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return 1 if failed else 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读运行固定病例的LX0609全49点正式入口回归")
    parser.add_argument("--case-map", default=str(DEFAULT_CASE_MAP))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--offline-pack-probe",
        action="store_true",
        help="仅离线固定样本基准允许探测规则族包大小；线上默认固定分包",
    )
    parser.add_argument(
        "--evaluation-as-of-date",
        required=True,
        help="冻结本次只读回归的权威评价终点，格式YYYY-MM-DD",
    )
    parser.add_argument(
        "--assert-49",
        action="store_true",
        help="显式声明并校验全49个客户规则ID和返回顺序",
    )
    ab_group = parser.add_mutually_exclusive_group()
    ab_group.add_argument(
        "--snapshot-sidecar-ab",
        action="store_true",
        help="捕获一次真实模型响应并内存重放，比较sidecar开关前后结果",
    )
    ab_group.add_argument(
        "--unified-engine-ab",
        action="store_true",
        help="捕获一次真实模型响应并内存重放，比较旧链与统一执行信封",
    )
    ab_group.add_argument(
        "--formal-source-audit",
        action="store_true",
        help="同一次正式主链调用内输出脱敏的规则来源状态审计",
    )
    parser.add_argument(
        "--course-severity-expected-matrix",
        help="仅统一引擎A/B使用的私有008/009安全人工事实矩阵JSON",
    )
    args = parser.parse_args(argv)
    try:
        args.evaluation_as_of_date = _validate_evaluation_as_of_date(
            args.evaluation_as_of_date
        )
    except RuntimeError as exc:
        parser.error(str(exc))
    if args.unified_engine_ab and not str(
        args.course_severity_expected_matrix or ""
    ).strip():
        parser.error("--unified-engine-ab必须提供--course-severity-expected-matrix")
    if not args.unified_engine_ab and args.course_severity_expected_matrix:
        parser.error("--course-severity-expected-matrix仅可用于--unified-engine-ab")
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
