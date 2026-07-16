from __future__ import annotations

import argparse
import asyncio
import copy
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
_JSON_FIELDS = (
    "structured_context",
    "document_hits",
    "data_quality_flags",
    "source_doc_priority",
)

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


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
        self._replay_index = 0

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
        if self._replay_index >= len(self._records):
            raise RuntimeError("A/B重放调用次数超过基线")
        expected_hash, response = self._records[self._replay_index]
        self._replay_index += 1
        if self._prompt_hash(prompt) != expected_hash:
            raise RuntimeError("A/B模型输入发生变化")
        return copy.deepcopy(response)

    @property
    def call_count(self) -> int:
        return len(self._records)

    def assert_complete(self) -> None:
        if self._replay_index != len(self._records):
            raise RuntimeError("A/B重放调用次数少于基线")


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
) -> dict[str, Any]:
    if tuple(rule_ids) != EXPECTED_LUXIAN_0609_RULE_IDS:
        raise RuntimeError("全49点回归禁止使用空列表或非客户规则范围")
    result = await asyncio.wait_for(
        service.evaluate_running_final_bundle_input(
            bundle=bundle,
            rule_ids=list(rule_ids),
            bucket_strategy="domain_only",
            quality_profile="throughput_v1",
            batch_output_mode="full",
            enable_selective_refine=False,
            use_execution_cache=False,
            rule_set_key="luxian_0609_qc_v1",
        ),
        timeout=timeout_seconds,
    )
    validate_full_luxian_0609_results(result)
    return result


async def evaluate_snapshot_sidecar_ab_case(
    *,
    service: Any,
    settings: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
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
    )


async def evaluate_unified_engine_ab_case(
    *,
    service: Any,
    settings: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
) -> dict[str, Any]:
    """复用同一次真实模型响应，比较冻结旧链与统一执行信封正式入口。"""

    return await _evaluate_runtime_flag_ab_case(
        service=service,
        settings=settings,
        bundle=bundle,
        rule_ids=rule_ids,
        timeout_seconds=timeout_seconds,
        candidate_flag="LUXIAN_0609_UNIFIED_ENGINE_ENABLED",
        mode_label="unified_engine",
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
    typed_007_audits: list[dict[str, Any]] = []
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
            if item.rule_id == "LX0609-007":
                typed_007_audits.append(
                    {
                        "final_state": item.final_state.value,
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
        )

        setattr(settings, candidate_flag, True)
        if mode_label == "unified_engine":
            settings.LUXIAN_0609_RULE_DECISION_007_ENABLED = True
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
        )
        replay.assert_complete()
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
        "tokens_match": baseline_tokens == candidate_tokens,
        "logical_llm_call_count": replay.call_count,
        "snapshot_build_count": len(snapshot_hashes),
        "result_count": len(candidate_states),
    }
    if mode_label == "unified_engine" and family_reader_calls["baseline"] > 0:
        comparison["controlled_fact_query_count"] = controlled_fact_query_count
    if baseline_states != candidate_states:
        comparison["state_differences"] = [
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
    if mode_label == "unified_engine":
        if len(typed_007_audits) != 1:
            raise RuntimeError("007每病例必须且只能形成一个类型化决策")
        if typed_007_audits[0]["fact_ref_count"] <= 0:
            raise RuntimeError("007类型化决策必须绑定安全证据引用")
        if (
            family_reader_calls["baseline"] > 0
            and controlled_fact_query_count != 1
        ):
            raise RuntimeError("007受控医嘱事实每病例必须且只能查询一次")
        if family_reader_calls["candidate"] != 0:
            raise RuntimeError("统一引擎已迁移规则族仍在自行查库")
        comparison.update(
            {
                "baseline_family_reader_calls": family_reader_calls["baseline"],
                "candidate_family_reader_calls": family_reader_calls["candidate"],
                "typed_007_decision_count": len(typed_007_audits),
                "typed_007_fact_ref_count": typed_007_audits[0]["fact_ref_count"],
                "typed_007_model_call_count": 0,
            }
        )
    return comparison


async def run(args: argparse.Namespace) -> int:
    from app.core.settings import get_settings
    from app.services.sichuan_qc_service import SichuanQCService

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
                )
                if not comparison["states_match"] or not comparison["tokens_match"]:
                    raise RuntimeError("A/B状态或token发生变化")
                summary = {
                    "case_label": case["case_label"],
                    **comparison,
                    "elapsed_ms": int((time.perf_counter() - started) * 1000),
                }
            else:
                result = await evaluate_full_luxian_0609_case(
                    service=service,
                    bundle=bundle,
                    rule_ids=rule_ids,
                    timeout_seconds=float(args.timeout_seconds),
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
                    "total_tokens": int(token_usage.get("total_tokens") or 0),
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
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
