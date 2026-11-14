"""LX0609 影子运行时的窄来源真值与确定性事实 Provider。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from app.services.bundles import assembly as bundle_assembly  # noqa: F401

from . import deterministic_gate, planner, runtime_shadow_assembler, source_manifest_builder
from .evidence_material import (
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .evidence_snapshot_provider import classify_current_visit_surgery_order_rows
from .source_manifest import QueryStatus
from .surgery_procedure_catalog import catalog_surgery_state
from .source_evidence_reader import (
    authoritative_document_time_value,
    SURGERY_TIME_FIELDS,
    SourceEvidenceUnavailable,
    canonical_source_evidence,
    digest_source_evidence,
    has_strict_performed_time,
    has_trusted_performed_surgery,
    parse_strict_performed_time,
    read_luxian_0609_runtime_source_rows,
    trusted_performed_surgery_times,
)

_QUERY_VERSION = "runtime_source_v1"
_EXTRACTOR_VERSION = "rts-v1"
_MAPPING_POLICY_VERSION = "rtm-v2"
_MAX_SOURCES = 6
_PERFORMED_TIME_FORMAT = "%Y-%m-%d %H:%M:%S+08"
_TARGET_QUALIFICATION_POLICY_VERSION = deterministic_gate.TARGET_QUALIFICATION_POLICY_VERSION
_MIN_SUBSTANTIVE_TARGET_LENGTH = 16
# 兼容已验收 provider 的测试 seam；实现位于共享读侧模块。
_BEGIN_END_FIELDS = SURGERY_TIME_FIELDS
_SourceUnavailable = SourceEvidenceUnavailable


@dataclass(frozen=True)
class RuntimeShadowProvidedInputs:
    source_query_observations: tuple[source_manifest_builder.SourceQueryObservation, ...]
    extraction_inputs: tuple[runtime_shadow_assembler.RuntimePairExtractionInput, ...]
    target_qualifications: tuple[deterministic_gate.TargetQualification, ...]
    evidence_payload: Mapping[str, Any]


def _read_snapshot_source_rows(
    *,
    source_key: str,
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
) -> tuple[
    list[dict[str, Any]], QueryStatus, SourceCompleteness, str, str
]:
    observations = tuple(
        item
        for item in evidence_snapshot.observations
        if item.source_key == source_key
    )
    if len(observations) != 1:
        raise ValueError("snapshot source observation is missing or duplicated")
    observation = observations[0]
    if observation.query_state is QueryStatus.UNAVAILABLE:
        return (
            [],
            QueryStatus.UNAVAILABLE,
            observation.completeness,
            "source_table_unavailable",
            "",
        )
    if observation.query_state is QueryStatus.ERROR:
        return [], QueryStatus.ERROR, observation.completeness, "", "source_query_failed"
    if (
        evidence_materials is None
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("snapshot material store mismatch")
    try:
        # Phase 2 仅做旧执行器输入适配：snapshot 仍保留 TRUNCATED 真值，
        # 此处读取有界前缀以保持旧 provider 行为；后续统一 reducer 才能据
        # completeness 阻止用截断材料形成否定结论。
        rows = evidence_materials.bounded_rows(source_key)
    except EvidenceMaterialUnavailable:
        raise ValueError("snapshot material source is unavailable") from None
    return (
        [dict(row) for row in rows],
        observation.query_state,
        observation.completeness,
        "",
        "",
    )


def _canonical(value: Any) -> str:
    return canonical_source_evidence(value)


def _digest(value: Any) -> str:
    return digest_source_evidence(value)


def _required_pairs(plan: planner.ShadowRulePlan) -> tuple[tuple[str, str], ...]:
    return tuple(sorted({
        (requirement.fact_type, source_key)
        for rule in plan.planned_rules
        for requirement in rule.trigger_requirements
        for source_key in requirement.allowed_source_keys
    }))


def _has_performed_time(row: Mapping[str, Any]) -> bool:
    return has_strict_performed_time(row)


def _parse_performed_time(value: Any) -> datetime | None:
    return parse_strict_performed_time(value)


def _substantive_target_body(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    return len(candidate) >= _MIN_SUBSTANTIVE_TARGET_LENGTH and candidate not in {"[]", "{}", "null", "None"}


def _parse_presurg_record_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip().replace("Z", "+00:00")
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2})?",
            candidate,
        ):
            return None
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


def _target_qualification_material_hash(source_key: str, row: Mapping[str, Any]) -> str | None:
    """将资格判定的白名单输入绑定为不可逆行摘要，绝不输出原值。"""
    if source_key == "presurg_summary":
        material = {
            "record_content": row.get("record_content").strip() if isinstance(row.get("record_content"), str) else "",
            "record_time": str(authoritative_document_time_value(row) or "").strip(),
        }
    elif source_key == "surgery_safecheck_record":
        material = {
            "record_content": row.get("record_content").strip() if isinstance(row.get("record_content"), str) else "",
        }
    else:
        return None
    return _digest({"target_source_key": source_key, "qualification_material": material})


def provide_luxian_0609_runtime_shadow_inputs(
    *, plan: planner.ShadowRulePlan, institute_id: str, patient_id: str, visit_id: str,
    source_schema: str | None = None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
) -> RuntimeShadowProvidedInputs:
    if not isinstance(plan, planner.ShadowRulePlan) or not plan.planned_rules:
        raise TypeError("plan must be nonzero ShadowRulePlan")
    if not all(isinstance(value, str) and value.strip() for value in (institute_id, patient_id, visit_id)):
        raise ValueError("invalid source coordinates")
    if visit_id != plan.visit_ref:
        raise ValueError("visit scope mismatch")
    expected_sources = tuple(sorted({source for rule in plan.planned_rules for source in rule.required_source_keys}))
    if len(expected_sources) > _MAX_SOURCES:
        raise ValueError("too many planned sources")
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    completeness_by_source: dict[str, SourceCompleteness | None] = {}
    observations: list[source_manifest_builder.SourceQueryObservation] = []
    for source_key in expected_sources:
        if evidence_snapshot is not None:
            (
                rows,
                query_status,
                completeness,
                reason_code,
                error_code,
            ) = _read_snapshot_source_rows(
                source_key=source_key,
                evidence_snapshot=evidence_snapshot,
                evidence_materials=evidence_materials,
            )
            completeness_by_source[source_key] = completeness
            observations.append(
                source_manifest_builder.SourceQueryObservation.create(
                    source_key=source_key,
                    query_status=query_status,
                    query_version=_QUERY_VERSION,
                    reason_code=reason_code,
                    error_code=error_code,
                )
            )
            rows_by_source[source_key] = rows
            continue
        try:
            rows = read_luxian_0609_runtime_source_rows(
                source_key=source_key, institute_id=institute_id, patient_id=patient_id,
                visit_id=visit_id, source_schema=source_schema,
            )
        except _SourceUnavailable:
            rows = []
            observations.append(source_manifest_builder.SourceQueryObservation.create(
                source_key=source_key, query_status=QueryStatus.UNAVAILABLE,
                query_version=_QUERY_VERSION, reason_code="source_table_unavailable",
            ))
        except Exception:
            rows = []
            observations.append(source_manifest_builder.SourceQueryObservation.create(
                source_key=source_key, query_status=QueryStatus.ERROR,
                query_version=_QUERY_VERSION, error_code="source_query_failed",
            ))
        else:
            observations.append(source_manifest_builder.SourceQueryObservation.create(
                source_key=source_key,
                query_status=QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY,
                query_version=_QUERY_VERSION,
            ))
        rows_by_source[source_key] = rows
        completeness_by_source[source_key] = None

    status_by_source = {item.source_key: item.query_status for item in observations}
    visit_scope_ref = _digest({"institute_id": institute_id, "patient_id": patient_id, "visit_id": visit_id})
    documents: dict[str, list[dict[str, str]]] = {}
    signals_by_pair: dict[tuple[str, str], tuple[runtime_shadow_assembler.RuntimeStructuredFactSignal, ...]] = {}
    order_state_by_source: dict[str, str] = {}
    for source_key in expected_sources:
        safe_rows: list[dict[str, str]] = []
        signals: list[runtime_shadow_assembler.RuntimeStructuredFactSignal] = []
        order_row_states: dict[str, bool] = {}
        order_state = ""
        source_completeness = completeness_by_source[source_key]
        if source_key == "inpat_nondrug_order" and source_completeness is not None:
            order_state, _ = classify_current_visit_surgery_order_rows(
                rows=tuple(rows_by_source[source_key]),
                completeness=source_completeness,
            )
            if source_completeness is SourceCompleteness.COMPLETE:
                for row in rows_by_source[source_key]:
                    row_state, _ = classify_current_visit_surgery_order_rows(
                        rows=(row,), completeness=SourceCompleteness.COMPLETE
                    )
                    order_row_states[_canonical(row)] = row_state == "affirmed"
            order_state_by_source[source_key] = order_state
        materials = []
        for row in rows_by_source[source_key]:
            surgery_times: dict[str, str] = {}
            if source_key == "surgery_record":
                surgery_times = {
                    field: str(row.get(field) or "").strip()
                    for field in _BEGIN_END_FIELDS
                    if str(row.get(field) or "").strip()
                }
            elif source_key == "mr_surgery" and isinstance(row.get("surgery_begin_datetime"), datetime):
                surgery_times = {"surgery_begin_datetime": row["surgery_begin_datetime"].isoformat()}
            material = {
                "source_key": source_key,
                "surgery_times": surgery_times,
            }
            qualification_material_hash = _target_qualification_material_hash(source_key, row)
            if qualification_material_hash is not None:
                material["qualification_material_hash"] = qualification_material_hash
            has_performed_time = has_trusted_performed_surgery(
                source_key=source_key, row=row
            )
            if source_key == "mr_surgery":
                # 029/030/032 的适用性不能由首页“手术及操作”清单触发。
                # 该表同时包含输血、CRRT、置管、穿刺等治疗性操作；032
                # 必须以正式 surgery_record 为准。
                has_performed_time = False
            has_surgery_order = order_row_states.get(_canonical(row), False)
            materials.append((material, has_performed_time, has_surgery_order))
        materials.sort(key=lambda item: _canonical(item[0]))
        occurrences: dict[str, int] = {}
        for material, has_performed_time, has_surgery_order in materials:
            material_key = _canonical(material)
            occurrence = occurrences.get(material_key, 0)
            occurrences[material_key] = occurrence + 1
            ref_material = {
                "source_key": source_key, "visit_scope_ref": visit_scope_ref,
                "material": material, "occurrence": occurrence,
            }
            row_ref = _digest(ref_material)
            safe_row = {"row_ref": row_ref, "source_snapshot": _digest({"snapshot": ref_material})}
            if "qualification_material_hash" in material:
                safe_row["qualification_material_hash"] = material["qualification_material_hash"]
            safe_rows.append(safe_row)
            if has_surgery_order:
                signals.append(
                    runtime_shadow_assembler.RuntimeStructuredFactSignal(
                        signal_ref=_digest({"signal": "ordered", "row_ref": row_ref}),
                        fact_type="current_visit_surgery_order_confirmed",
                        source_key=source_key,
                        event_status="ordered",
                        source_record_ref=row_ref,
                        source_document_type="runtime_structured",
                        extractor_version=_EXTRACTOR_VERSION,
                        mapping_policy_version=_MAPPING_POLICY_VERSION,
                    )
                )
            if has_performed_time:
                signals.append(runtime_shadow_assembler.RuntimeStructuredFactSignal(
                    signal_ref=_digest({"signal": "performed", "row_ref": row_ref}),
                    fact_type="current_visit_surgery_confirmed", source_key=source_key,
                    event_status="performed", source_record_ref=row_ref,
                    source_document_type="runtime_structured", extractor_version=_EXTRACTOR_VERSION,
                    mapping_policy_version=_MAPPING_POLICY_VERSION,
                ))
        documents[source_key] = safe_rows
        fact_type = (
            "current_visit_surgery_order_confirmed"
            if source_key == "inpat_nondrug_order"
            else "current_visit_surgery_confirmed"
        )
        signals_by_pair[(fact_type, source_key)] = tuple(signals)

    outcomes: list[runtime_shadow_assembler.RuntimePairExtractionInput] = []
    for fact_type, source_key in _required_pairs(plan):
        status = status_by_source[source_key]
        rows = rows_by_source[source_key]
        signals = signals_by_pair.get((fact_type, source_key), ())
        if status is QueryStatus.UNAVAILABLE:
            state, processed, reason = "not_run", 0, "source_unavailable"
        elif status is QueryStatus.ERROR:
            state, processed, reason = "not_run", 0, "source_query_error"
        elif (
            fact_type == "current_visit_surgery_order_confirmed"
            and evidence_snapshot is not None
            and (
                completeness_by_source[source_key]
                is not SourceCompleteness.COMPLETE
                or order_state_by_source.get(source_key) == "uncertain"
            )
        ):
            state, processed, reason = "not_run", 0, "extractor_not_run"
        else:
            state, processed, reason = "complete", len(rows), ""
        outcomes.append(runtime_shadow_assembler.RuntimePairExtractionInput(
            fact_type=fact_type, source_key=source_key, state=state,
            extractor_version=_EXTRACTOR_VERSION, mapping_policy_version=_MAPPING_POLICY_VERSION,
            processed_record_count=processed, positive_signals=signals, reason_code=reason,
        ))
    surgery_record_times = tuple(
        parsed
        for row in rows_by_source.get("surgery_record", ())
        for parsed in trusted_performed_surgery_times(source_key="surgery_record", row=row)
    )
    # 已实施时间只能来自原始手术文书，首页不作回退。
    confirmed_surgery_times = surgery_record_times
    earliest_surgery_time = min(confirmed_surgery_times) if confirmed_surgery_times else None
    observation_by_source = {item.source_key: item for item in observations}
    qualifications: list[deterministic_gate.TargetQualification] = []
    for rule in plan.planned_rules:
        if rule.rule_id not in ("LX0609-04-01-01", "LX0609-04-03-01"):
            continue
        if observation_by_source[rule.target_source_key].query_status is not QueryStatus.AVAILABLE:
            continue
        target_rows = rows_by_source[rule.target_source_key]
        target_snapshot_hash = _digest({"source_key": rule.target_source_key, "documents": documents[rule.target_source_key]})
        if rule.rule_id == "LX0609-04-01-01":
            qualified_count = sum(
                1
                for row in target_rows
                if _substantive_target_body(row.get("record_content"))
                and (record_time := _parse_presurg_record_time(authoritative_document_time_value(row))) is not None
                and earliest_surgery_time is not None
                and record_time <= earliest_surgery_time
            )
        else:
            qualified_count = sum(1 for row in target_rows if _substantive_target_body(row.get("record_content")))
        qualifications.append(deterministic_gate.TargetQualification(
            visit_ref=plan.visit_ref, rule_id=rule.rule_id, target_source_key=rule.target_source_key,
            qualification_policy_version=_TARGET_QUALIFICATION_POLICY_VERSION,
            target_snapshot_hash=target_snapshot_hash, qualified_document_count=qualified_count,
        ))
    return RuntimeShadowProvidedInputs(
        source_query_observations=tuple(observations),
        extraction_inputs=tuple(outcomes),
        target_qualifications=tuple(qualifications),
        evidence_payload={"programmatic_timeline": {"documents": documents}},
    )
