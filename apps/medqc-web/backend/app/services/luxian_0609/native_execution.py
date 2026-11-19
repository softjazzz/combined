"""LX0609-04-01-01、LX0609-04-02-02、LX0609-04-03-01 正式原生确定性执行切片。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from . import planner, runtime_shadow_assembler, runtime_shadow_input_provider, shadow_execution
from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .evidence_snapshot_provider import classify_current_visit_surgery_order_rows
from .source_manifest import QueryStatus
from .surgery_applicability import performed_surgery_rows, resolve_surgery_applicability
from .surgery_record_coverage import (
    definitely_uncovered_surgery_rows,
    same_day_surgery_coverage_unresolved,
)
from .surgery_procedure_catalog import is_non_surgical_procedure_order
from .surgery_safecheck_evidence import SAFECHECK_BEGIN_FIELDS, has_qualified_safecheck


_Minute = tuple[int, int, int, int, int]


# 029 已迁入 surgery_document 异步执行器；这里仅保留纯存在性判定。
NATIVE_RULE_IDS = ("LX0609-04-02-02", "LX0609-04-03-01")
NATIVE_LEGACY_RULE_IDS_BY_RULE_ID = MappingProxyType(
    {
        "LX0609-04-01-01": ("CL-181", "SC-081"),
        "LX0609-04-02-02": ("LX-025", "SC-095"),
        "LX0609-04-03-01": ("SC-102", "LXE-33"),
    }
)
NATIVE_MAPPED_RULE_IDS = tuple(
    legacy_rule_id
    for native_rule_id in NATIVE_RULE_IDS
    for legacy_rule_id in NATIVE_LEGACY_RULE_IDS_BY_RULE_ID[native_rule_id]
)
_PLAN_SCHEMA = "planner-v1"
_RULE_PLAN = "029-030-032-v1"
_ASSEMBLER_SCHEMA = "assembler-v1"
_ASSEMBLER_POLICY = "runtime-v1"
_MANIFEST_SCHEMA = "manifest-v1"
_BUNDLE_SCHEMA = "bundle-v1"
_COVERAGE_SCHEMA = "coverage-v1"
_COVERAGE_POLICY = "coverage-v1"
_GATE_SCHEMA = "gate-v1"
_GATE_POLICY = "gate-v1"
_FINDING_SCHEMA = "finding-v1"
_FINDING_POLICY = "policy-v1"
_AGGREGATION_SCHEMA = "aggregation-v1"
_AGGREGATION_POLICY = "aggregation-v1"
_EXECUTION_SCHEMA = "execution-v1"
_EXECUTION_POLICY = "native-v1"
_PACKAGE_VERSION = "lx0609-native-v1"
_TYPED_EVALUATOR_VERSION = "surgery-presence-ruledecision-v3"
_TYPED_RULE_SOURCE_KEYS = MappingProxyType(
    {
        "LX0609-04-01-01": frozenset(
            {"presurg_summary", "surgery_record"}
        ),
        "LX0609-04-02-02": frozenset(
            {"inpat_nondrug_order", "surgery_record", "evaluation_context.horizon"}
        ),
        "LX0609-04-03-01": frozenset(
            {"surgery_safecheck_record", "surgery_record"}
        ),
    }
)
_SAFE_CHECK_SURGERY_TIME_PATTERN = re.compile(
    r"(?<![\u4e00-\u9fffA-Za-z0-9_])手术时间\s*[:：]\s*"
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}"
    r"(?:Z|[+-]\d{2}(?::\d{2})?)?)"
    r"(?=$|[\r\n]|[ \t]+[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9（）()_-]*\s*[:：])"
)
_SAFE_CHECK_SURGERY_TIME_LABEL_PATTERN = re.compile(
    r"(?<![\u4e00-\u9fffA-Za-z0-9_])手术时间\s*[:：]"
)
_COMPLETE_SURGERY_DATETIME_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})"
    r"(Z|[+-]\d{2}(?::\d{2})?)?$"
)
_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_SURGERY_CONTENT_PLACEHOLDERS = frozenset({"无", "无。", "-", "/"})


@dataclass(frozen=True)
class NativeExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    execution_fingerprint: str = ""
    terminal_reason_code: str = ""


def legacy_rule_ids_for_native_rule_ids(rule_ids: Sequence[str]) -> tuple[str, ...]:
    """原生开关关闭时才展开旧执行 ID，保持客户入口不携带映射细节。"""
    selected = {
        str(rule_id or "").strip().upper()
        for rule_id in rule_ids
        if str(rule_id or "").strip()
    }
    return tuple(
        legacy_rule_id
        for native_rule_id in NATIVE_RULE_IDS
        if native_rule_id in selected
        for legacy_rule_id in NATIVE_LEGACY_RULE_IDS_BY_RULE_ID[native_rule_id]
    )


def native_rule_ids_from_wrappers(
    *, wrapper_rules: Sequence[dict[str, Any]], prepared_rule_ids: set[str]
) -> tuple[str, ...]:
    selected: list[str] = []
    for wrapper in wrapper_rules:
        rule_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
        mapped = {
            str(value or "").strip().upper()
            for value in list(wrapper.get("mapped_rule_ids") or [])
            if str(value or "").strip()
        }
        if rule_id in NATIVE_RULE_IDS and (rule_id in prepared_rule_ids or mapped.intersection(prepared_rule_ids)):
            selected.append(rule_id)
    return tuple(rule_id for rule_id in NATIVE_RULE_IDS if rule_id in selected)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _customer_state(final_state: str) -> str:
    return "uncertain" if final_state == "evaluation_unknown" else final_state


def build_luxian_0609_native_result(
    *, rule_id: str, final_state: str, finding_kind: str, reason_code: str
) -> dict[str, Any]:
    """构造不携带映射、坐标或原文的客户安全原生结果。"""
    status = _customer_state(final_state)
    message = {
        "compliant": "未发现该项缺失。",
        "non_compliant": "相关文书未满足要求。",
        "not_applicable": "当前就诊不适用该项。",
        "data_gap": "当前可用资料不足，暂不能形成可靠结论。",
        "technical_error": "自动判定暂不可用，建议稍后重试。",
        "uncertain": "当前资料存在冲突，建议人工确认。",
    }[status]
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable"},
        "findings": message,
        "evidence": "",
        "suggestion": "请结合当前就诊相关文书确认。",
        "confidence": 1.0 if status in {"compliant", "non_compliant", "not_applicable"} else 0.0,
        "metadata": {
            "execution_source": "lx0609_native",
            "executor_type": "program",
            "finding_kind": finding_kind,
            "source_state": final_state,
            "reason_code": reason_code,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def _technical_results(rule_ids: Sequence[str], *, reason_code: str) -> NativeExecutionResult:
    results = tuple(
        build_luxian_0609_native_result(
            rule_id=rule_id,
            final_state="technical_error",
            finding_kind="technical_failure",
            reason_code=reason_code,
        )
        for rule_id in rule_ids
    )
    return NativeExecutionResult(
        results=results,
        planned_rule_ids=tuple(rule_ids),
        terminal_reason_code=reason_code,
    )


def _minute_key(value: object) -> tuple[int, int, int, int, int] | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        matched = _COMPLETE_SURGERY_DATETIME_PATTERN.fullmatch(text)
        if matched is None:
            return None
        date_time, offset = matched.groups()
        if offset and re.fullmatch(r"[+-]\d{2}", offset):
            offset = f"{offset}:00"
        try:
            parsed = datetime.fromisoformat(
                f"{date_time}{'+00:00' if offset == 'Z' else offset or ''}"
            )
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_HOSPITAL_TIMEZONE)
    else:
        parsed = parsed.astimezone(_HOSPITAL_TIMEZONE)
    return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute)


def _safecheck_surgery_minute(row: Mapping[str, Any]) -> tuple[_Minute | None, bool]:
    """第二项表示有时间材料，但无法得到唯一有效分钟。"""

    content = str(row.get("record_content") or "")
    labels = len(_SAFE_CHECK_SURGERY_TIME_LABEL_PATTERN.findall(content))
    matches = _SAFE_CHECK_SURGERY_TIME_PATTERN.findall(content)
    if labels > 1 or len(matches) != labels:
        return None, True
    raw = [row[field] for field in SAFECHECK_BEGIN_FIELDS if str(row.get(field) or "").strip()]
    minutes = {_minute_key(value) for value in (*raw, *matches)}
    if None in minutes or len(minutes) > 1:
        return None, True
    return (next(iter(minutes)), False) if minutes else (None, False)


def _unique_document_minutes(
    rows: Sequence[Mapping[str, Any]],
    *,
    minute_resolver: Callable[[Mapping[str, Any]], tuple[int, int, int, int, int] | None],
) -> dict[tuple[int, int, int, int, int], str] | None:
    """按文书 ID 去重后建立唯一分钟索引；任一歧义均失败关闭。"""
    minute_by_document_id: dict[str, tuple[int, int, int, int, int]] = {}
    for row in rows:
        document_id = str(row.get("document_id") or "").strip()
        minute = minute_resolver(row)
        if not document_id or minute is None:
            return None
        previous = minute_by_document_id.get(document_id)
        if previous is not None:
            if previous != minute:
                return None
            continue
        minute_by_document_id[document_id] = minute

    document_id_by_minute: dict[tuple[int, int, int, int, int], str] = {}
    for document_id, minute in minute_by_document_id.items():
        if minute in document_id_by_minute:
            return None
        document_id_by_minute[minute] = document_id
    return document_id_by_minute


def _surgery_document_minutes(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[tuple[int, int, int, int, int], str],
    set[tuple[int, int, int, int, int]],
] | None:
    """返回唯一手术分钟索引及其中有实质记录的确认事件。"""
    minute_by_document_id: dict[str, tuple[int, int, int, int, int]] = {}
    material_by_document_id: dict[str, bool] = {}
    for row in rows:
        document_id = str(row.get("document_id") or "").strip()
        minutes = {_minute_key(row[field]) for field in SAFECHECK_BEGIN_FIELDS if str(row.get(field) or "").strip()}
        if not document_id or len(minutes) != 1 or None in minutes:
            return None
        minute = next(iter(minutes))
        assert minute is not None
        previous = minute_by_document_id.get(document_id)
        if previous is not None and previous != minute:
            return None
        minute_by_document_id[document_id] = minute
        contents = (
            str(row.get(field) or "").strip()
            for field in ("surgery_process", "record_content")
        )
        material_by_document_id[document_id] = material_by_document_id.get(
            document_id, False
        ) or any(
            content and content not in _SURGERY_CONTENT_PLACEHOLDERS
            for content in contents
        )

    document_id_by_minute: dict[tuple[int, int, int, int, int], str] = {}
    confirmed_minutes: set[tuple[int, int, int, int, int]] = set()
    for document_id, minute in minute_by_document_id.items():
        if minute in document_id_by_minute:
            return None
        document_id_by_minute[minute] = document_id
        if material_by_document_id[document_id]:
            confirmed_minutes.add(minute)
    return document_id_by_minute, confirmed_minutes


def _resolve_multi_surgery_safecheck_linkage(
    *,
    surgery_rows: Sequence[Mapping[str, Any]],
    safecheck_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str] | None:
    """仅为032按客户确认的“手术时间”字段做精确分钟双向唯一关联。"""
    surgery_minutes = _surgery_document_minutes(surgery_rows)
    if surgery_minutes is None:
        return "data_gap", "association_failed"
    surgery_by_minute, confirmed_minutes = surgery_minutes
    if not surgery_by_minute:
        return None
    if len(surgery_by_minute) == 1 and confirmed_minutes and len(safecheck_rows) <= 1:
        if safecheck_rows:
            minute, invalid = _safecheck_surgery_minute(safecheck_rows[0])
            if invalid or (minute is not None and minute not in surgery_by_minute):
                return "data_gap", "association_failed"
        # 单台单表没有时间字段时保留原资格门槛，不推断额外的时间事实。
        return None

    safecheck_by_minute = _unique_document_minutes(
        safecheck_rows,
        minute_resolver=lambda row: _safecheck_surgery_minute(row)[0],
    )
    if safecheck_by_minute is None:
        return "data_gap", "association_failed"
    if set(safecheck_by_minute).difference(surgery_by_minute):
        return "data_gap", "association_failed"
    uncertain_minutes = set(surgery_by_minute).difference(confirmed_minutes)
    if uncertain_minutes.difference(safecheck_by_minute):
        return "data_gap", "association_failed"
    if confirmed_minutes.difference(safecheck_by_minute):
        return "non_compliant", "required_document_missing"
    # 同台时间可以定位空表，但不能代替既有的核查内容证据。
    if any(not has_qualified_safecheck(row) for row in safecheck_rows):
        return "data_gap", "required_field_missing"
    return "compliant", "requirement_satisfied"


def build_luxian_0609_native_technical_results(
    rule_ids: Sequence[str], *, reason_code: str = "native_result_incomplete"
) -> NativeExecutionResult:
    """为正式入口构造数量完整且不回显异常的失败结果。"""
    selected = tuple(rule_id for rule_id in NATIVE_RULE_IDS if rule_id in set(rule_ids))
    return _technical_results(selected, reason_code=reason_code)


def _typed_rule_decision(
    *,
    rule_id: str,
    final_state: str,
    snapshot: Luxian0609EvidenceSnapshot,
    non_compliant_reason: str = "required_document_missing",
    reason_override: str = "",
    selected_fact_refs: Sequence[str] | None = None,
) -> RuleDecision:
    refs = (
        tuple(selected_fact_refs)
        if selected_fact_refs is not None
        else tuple(
            observation.snapshot_ref.removeprefix("sha256:")
            for observation in snapshot.observations
            if observation.source_key in _TYPED_RULE_SOURCE_KEYS[rule_id]
        )
    )
    if final_state in {"compliant", "non_compliant", "not_applicable"} and not refs:
        raise ValueError("typed surgery presence decision requires evidence refs")
    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            non_compliant_reason,
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "required_field_missing",
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "executor_exception",
        ),
        "evaluation_unknown": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "evidence_conflict",
        ),
    }
    try:
        applicability, evidence_state, qc_direction, reason_code = dimensions[
            final_state
        ]
    except KeyError:
        raise ValueError("unsupported surgery presence final state") from None
    if reason_code == "required_document_blank":
        reason_code = "defect_proven"
    if reason_override:
        reason_code = reason_override
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=_TYPED_EVALUATOR_VERSION,
        confidence=None,
    )


def _selected_surgery_presence_fact_refs(
    *,
    rule_id: str,
    final_state: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, ...] | None:
    """为已判定的存在性结果选择同一会话内的真实文书坐标。

    030 合规时覆盖全部手术记录；032 合规及关联缺口时覆盖本次参与关联
    的手术记录与核查表。缺核查表的 032 缺陷只保留手术事件坐标，不能
    由后层反查或猜测。没有实际手术文书的既有状态继续使用来源观察坐标。
    """

    if final_state not in {"compliant", "non_compliant", "data_gap"}:
        return None
    source_keys = ["surgery_record"]
    if rule_id == "LX0609-04-03-01" and final_state in {"compliant", "data_gap"}:
        source_keys.append("surgery_safecheck_record")
    refs: list[str] = []
    for source_key in source_keys:
        try:
            refs.extend(
                reference
                for reference, _ in materials.document_rows(
                    source_key, snapshot=snapshot
                )
            )
        except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
            if final_state != "data_gap":
                raise
    selected = tuple(dict.fromkeys(refs))
    if rule_id == "LX0609-04-02-02" and final_state == "non_compliant" and not selected:
        order_rows = materials.document_rows(
            "inpat_nondrug_order", snapshot=snapshot
        )
        selected = tuple(
            reference
            for reference, row in order_rows
            if classify_current_visit_surgery_order_rows(
                rows=(row,), completeness=SourceCompleteness.COMPLETE
            )[0]
            == "affirmed"
        )
    if not selected and final_state != "data_gap":
        raise ValueError("surgery presence selected evidence is empty")
    return selected


def _surgery_order_obligation(*, snapshot: Luxian0609EvidenceSnapshot,
                            materials: Luxian0609EvidenceMaterialStore) -> tuple[str, str] | None:
    """030 与 029（仅医嘱触发、缺术前小结时）共用的安全门控；不从文本推定实施。"""
    from .evaluation_horizon import read_frozen_evaluation_horizon, after_frozen_horizon
    from ..discharge_time import hospital_business_time
    try:
        orders = [row for _, row in materials.document_rows("inpat_nondrug_order", snapshot=snapshot)
                  if str(row.get("order_type") or "").strip() == "手术" and not is_non_surgical_procedure_order(row)]
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return "data_gap", "candidate_scope_incomplete"
    if not orders:
        return None
    canceled = [row for row in orders if str(row.get("order_status") or "").strip()
                in {"取消", "撤销", "作废", "已取消", "已撤销", "已作废"}
                or row.get("canceled_datetime")]
    applicability = resolve_surgery_applicability(snapshot=snapshot, materials=materials,
                                                source_keys=("surgery_record",))
    if applicability.is_performed_surgery:
        # 单事件同时有取消和实施的结构化证据，不能借另一类证据消除冲突。
        if len(orders) == 1 and canceled:
            return "data_gap", "association_failed"
        return None
    for source in ("surgery_record",):
        observation = next((item for item in snapshot.observations if item.source_key == source), None)
        if observation is None or observation.query_state is QueryStatus.UNAVAILABLE:
            return "data_gap", "source_readiness_unproven"
        if observation.query_state is QueryStatus.ERROR:
            return "technical_error", "source_query_error"
        if observation.completeness is not SourceCompleteness.COMPLETE:
            return "data_gap", "candidate_scope_incomplete"
    if len(canceled) == len(orders):
        if any(row.get("carried_datetime") for row in canceled):
            return "data_gap", "association_failed"
        return "not_applicable", "trigger_absent_complete"
    horizon, _, error = read_frozen_evaluation_horizon(snapshot=snapshot, materials=materials)
    if error:
        return "technical_error" if error == "source_query_error" else "data_gap", error
    future = []
    for row in orders:
        if row in canceled:
            continue
        raw = str(row.get("planned_start_datetime") or "")
        try:
            time = hospital_business_time(datetime.fromisoformat(raw.replace("Z", "+00:00"))) if ":" in raw else None
        except ValueError:
            time = None
        future.append(str(row.get("order_status") or "").strip() != "停止" and time is not None and after_frozen_horizon(time, horizon))
    if future and all(future):
        return "not_applicable", "evaluation_window_not_mature"
    return "data_gap", "source_readiness_unproven"


def _surgery_presence_display_trigger_facts(
    *, rule_id: str, provided: Any
) -> dict[str, Any]:
    """把 provider 已确认的 030 触发来源投影为客户 facts。"""

    if rule_id != "LX0609-04-02-02":
        # 032 的展示事实合同沿用既有手术实施判定；本次修复只收紧 030。
        return {"performed_surgery_confirmed": True}

    extraction_inputs = getattr(provided, "extraction_inputs", ())
    if not isinstance(extraction_inputs, (tuple, list)):
        return {}
    order_confirmed = False
    for extraction_input in extraction_inputs:
        fact_type = getattr(extraction_input, "fact_type", None)
        source_key = getattr(extraction_input, "source_key", None)
        signals = getattr(extraction_input, "positive_signals", ())
        if (
            fact_type == "current_visit_surgery_confirmed"
            and source_key
            in {"surgery_application", "surgery_record"}
            and any(
                getattr(signal, "event_status", None) == "performed"
                for signal in signals
            )
        ):
            return {
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            }
        if (
            fact_type == "current_visit_surgery_order_confirmed"
            and source_key == "inpat_nondrug_order"
            and any(
                getattr(signal, "event_status", None) in {"ordered", "performed"}
                for signal in signals
            )
        ):
            order_confirmed = True
    if order_confirmed:
        return {
            "surgery_trigger_kind": "surgery_order",
            "surgery_order_confirmed": True,
        }
    return {}


def execute_luxian_0609_native_rules(
    *,
    rule_ids: Sequence[str],
    visit_id: str,
    institute_id: str,
    patient_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeExecutionResult:
    """同步运行已验收链；异常隔离为客户安全的 technical_error。"""
    selected = tuple(rule_id for rule_id in NATIVE_RULE_IDS if rule_id in set(rule_ids))
    if not selected:
        return NativeExecutionResult((), ())
    typed_requested = frozenset(
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    )
    if not typed_requested.issubset(set(selected)):
        raise ValueError("unsupported typed surgery presence scope")
    typed_selected = tuple(
        rule_id for rule_id in selected if rule_id in typed_requested
    )
    if typed_selected and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed surgery presence rules require one evidence session")
    if not all(isinstance(value, str) and value.strip() for value in (visit_id, institute_id, patient_id)):
        return _technical_results(selected, reason_code="native_coordinates_unavailable")
    try:
        created_at = _now()
        plan = planner.build_luxian_0609_shadow_plan(
            visit_ref=visit_id,
            selected_rule_ids=selected,
            scoped_customer_rule_ids=selected,
            record_rule_map={visit_id: list(selected)},
            planner_schema_version=_PLAN_SCHEMA,
            rule_plan_version=_RULE_PLAN,
            created_at=created_at,
        )
        planned = tuple(item.rule_id for item in plan.planned_rules)
        provided = runtime_shadow_input_provider.provide_luxian_0609_runtime_shadow_inputs(
            plan=plan,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
        )
        assembly = runtime_shadow_assembler.assemble_luxian_0609_runtime_shadow_inputs(
            plan=plan,
            evidence_payload=provided.evidence_payload,
            source_query_observations=provided.source_query_observations,
            extraction_inputs=provided.extraction_inputs,
            assembler_schema_version=_ASSEMBLER_SCHEMA,
            assembler_policy_version=_ASSEMBLER_POLICY,
            created_at=created_at,
        )
        execution = shadow_execution.build_luxian_0609_shadow_execution(
            visit_ref=visit_id,
            selected_rule_ids=selected,
            scoped_customer_rule_ids=selected,
            record_rule_map={visit_id: list(selected)},
            evidence_payload=provided.evidence_payload,
            source_query_observations=assembly.source_query_observations,
            fact_pairs=assembly.fact_pairs,
            deterministic_coverage_outcomes=assembly.deterministic_coverage_outcomes,
            target_qualifications=provided.target_qualifications,
            redaction_terms=(),
            planner_schema_version=_PLAN_SCHEMA,
            rule_plan_version=_RULE_PLAN,
            manifest_schema_version=_MANIFEST_SCHEMA,
            bundle_schema_version=_BUNDLE_SCHEMA,
            coverage_schema_version=_COVERAGE_SCHEMA,
            coverage_policy_version=_COVERAGE_POLICY,
            gate_schema_version=_GATE_SCHEMA,
            gate_policy_version=_GATE_POLICY,
            finding_schema_version=_FINDING_SCHEMA,
            finding_policy_version=_FINDING_POLICY,
            aggregation_schema_version=_AGGREGATION_SCHEMA,
            aggregation_policy_version=_AGGREGATION_POLICY,
            execution_schema_version=_EXECUTION_SCHEMA,
            execution_policy_version=_EXECUTION_POLICY,
            package_version=_PACKAGE_VERSION,
            planner_created_at=created_at,
            manifest_created_at=created_at,
            bundle_created_at=created_at,
            coverage_created_at=created_at,
            gate_created_at=created_at,
            finding_created_at=created_at,
            aggregation_created_at=created_at,
            created_at=created_at,
        )
    except Exception:
        return _technical_results(selected, reason_code="native_execution_failure")

    def result_reason(rule_id: str, final_state: str) -> str:
        if final_state == "technical_error":
            # 影子链技术失败必须使用RuleDecision允许的原因，不能被通用成功标记覆盖。
            return "executor_exception"
        if final_state == "data_gap":
            return "required_field_missing"
        if final_state != "non_compliant":
            return "native_deterministic"
        if rule_id == "LX0609-04-02-02":
            return "required_document_missing"
        if rule_id != "LX0609-04-03-01":
            return "requirement_violated"
        timeline = provided.evidence_payload.get("programmatic_timeline")
        documents = timeline.get("documents") if isinstance(timeline, Mapping) else None
        rows = (
            documents.get("surgery_safecheck_record")
            if isinstance(documents, Mapping)
            else None
        )
        return (
            "required_document_blank"
            if isinstance(rows, list) and rows
            else "required_document_missing"
        )

    reason_by_rule_id = {
        result.rule_id: result_reason(result.rule_id, result.final_state.value)
        for result in execution.results
    }
    final_state_by_rule_id = {
        result.rule_id: result.final_state.value for result in execution.results
    }
    if "LX0609-04-03-01" in typed_selected and evidence_materials is not None:
        try:
            linkage_outcome = _resolve_multi_surgery_safecheck_linkage(
                surgery_rows=tuple(evidence_materials.rows("surgery_record")),
                safecheck_rows=tuple(
                    evidence_materials.rows("surgery_safecheck_record")
                ),
            )
        except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
            linkage_outcome = ("data_gap", "association_failed")
        if (
            linkage_outcome is not None
            and final_state_by_rule_id.get("LX0609-04-03-01") != "technical_error"
        ):
            final_state_by_rule_id["LX0609-04-03-01"], reason_by_rule_id[
                "LX0609-04-03-01"
            ] = linkage_outcome
    if (
        "LX0609-04-02-02" in typed_selected
        and final_state_by_rule_id.get("LX0609-04-02-02") != "technical_error"
        and evidence_snapshot is not None
        and evidence_materials is not None
    ):
        try:
            obligation = _surgery_order_obligation(snapshot=evidence_snapshot, materials=evidence_materials)
        except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
            obligation = ("data_gap", "candidate_scope_incomplete")
        if obligation is not None:
            final_state_by_rule_id["LX0609-04-02-02"], reason_by_rule_id["LX0609-04-02-02"] = obligation
    all_results = tuple(
        build_luxian_0609_native_result(
            rule_id=result.rule_id,
            final_state=final_state_by_rule_id[result.rule_id],
            finding_kind=result.finding_kind.value,
            reason_code=reason_by_rule_id[result.rule_id],
        )
        for result in execution.results
    )
    if tuple(item["rule_id"] for item in all_results) != planned:
        return _technical_results(planned, reason_code="native_result_incomplete")
    typed_set = set(typed_selected)
    selected_fact_refs_by_rule: dict[str, tuple[str, ...] | None] = {}
    if evidence_snapshot is not None and evidence_materials is not None:
        for rule_id in typed_set:
            try:
                if (
                    final_state_by_rule_id[rule_id] == "data_gap"
                    and reason_by_rule_id[rule_id] != "association_failed"
                ):
                    selected_fact_refs_by_rule[rule_id] = (tuple(ref for ref, row in evidence_materials.document_rows(
                        "inpat_nondrug_order", snapshot=evidence_snapshot) if str(row.get("order_type") or "").strip() == "手术") or None) if rule_id == "LX0609-04-02-02" else None
                else:
                    selected_fact_refs_by_rule[rule_id] = (
                        _selected_surgery_presence_fact_refs(
                            rule_id=rule_id,
                            final_state=final_state_by_rule_id[rule_id],
                            snapshot=evidence_snapshot,
                            materials=evidence_materials,
                        )
                    )
            except (
                EvidenceMaterialTruncated,
                EvidenceMaterialUnavailable,
                TypeError,
                ValueError,
            ):
                # C/NC 必须带执行器从本次材料中选定的逐文书坐标；不能静默
                # 回退为来源观察 ref，否则公共投影会重新丢失客户定位。
                final_state_by_rule_id[rule_id] = "technical_error"
                reason_by_rule_id[rule_id] = "executor_exception"
    decisions = tuple(
        _typed_rule_decision(
            rule_id=str(item["rule_id"]),
            final_state=final_state_by_rule_id[str(item["rule_id"])],
            snapshot=evidence_snapshot,
            non_compliant_reason=reason_by_rule_id[str(item["rule_id"])],
            reason_override=(
                reason_by_rule_id[str(item["rule_id"])]
                if final_state_by_rule_id[str(item["rule_id"])] in {"data_gap", "technical_error"}
                or reason_by_rule_id[str(item["rule_id"])] == "evaluation_window_not_mature"
                else ""
            ),
            selected_fact_refs=selected_fact_refs_by_rule.get(
                str(item["rule_id"])
            ),
        )
        for item in all_results
        if item["rule_id"] in typed_set and evidence_snapshot is not None
    )
    results = tuple(item for item in all_results if item["rule_id"] not in typed_set)
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    target_documents = {
        "LX0609-04-02-02": "surgery_record",
        "LX0609-04-03-01": "surgery_safecheck_record",
    }
    for result in execution.results:
        rule_id = result.rule_id
        target_document = target_documents.get(rule_id)
        if target_document is None:
            continue
        trigger_facts = _surgery_presence_display_trigger_facts(
            rule_id=rule_id,
            provided=provided,
        )
        if rule_id == "LX0609-04-02-02" and not trigger_facts:
            # 030 的判定结果没有可观察的已组装触发信号时，不能凭状态猜测
            # “已实施手术”；状态与原因码仍由上游执行器原样保留。
            continue
        effective_state = final_state_by_rule_id.get(rule_id, result.final_state.value)
        if effective_state == "compliant":
            # 030/032 都是纯存在性判定。合规时也保存已核对的通过事实，避免客户侧
            # 只能看到“合规”而不知道检查了什么；原文定位仍由 RuleDecision
            # 在同一 Evidence Session 内反查，不能在这里猜测文书 ID。
            customer_display_facts.append(
                (
                    rule_id,
                    {
                        "verification_kind": "surgery_document_present",
                        "target_document": target_document,
                        **trigger_facts,
                    },
                )
            )
            continue
        if effective_state != "non_compliant":
            continue
        customer_display_facts.append(
            (
                rule_id,
                {
                    "failure_kind": (
                        "surgery_document_blank"
                        if reason_by_rule_id.get(rule_id) == "required_document_blank"
                        else "surgery_document_missing"
                    ),
                    "target_document": target_document,
                    **trigger_facts,
                },
            )
        )
    return NativeExecutionResult(
        results=results,
        planned_rule_ids=planned,
        decisions=decisions,
        customer_display_facts=tuple(customer_display_facts),
        execution_fingerprint=execution.fingerprint(),
    )
