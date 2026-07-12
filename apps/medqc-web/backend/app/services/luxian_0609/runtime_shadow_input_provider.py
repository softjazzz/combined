"""LX0609 影子运行时的窄来源真值与确定性事实 Provider。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

from app.services.bundles import assembly as bundle_assembly

from . import deterministic_gate, planner, runtime_shadow_assembler, source_manifest_builder
from .source_manifest import QueryStatus

_QUERY_VERSION = "runtime_source_v1"
_EXTRACTOR_VERSION = "rts-v1"
_MAPPING_POLICY_VERSION = "rtm-v1"
_MAX_SOURCES = 5
_PERFORMED_TIME_FORMAT = "%Y-%m-%d %H:%M:%S+08"
_PRESURG_RECORD_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_TARGET_QUALIFICATION_POLICY_VERSION = deterministic_gate.TARGET_QUALIFICATION_POLICY_VERSION
_MIN_SUBSTANTIVE_TARGET_LENGTH = 16
_BEGIN_END_FIELDS = (
    "surgery_begin_time", "surgery_begin_datetime",
    "surgery_end_time", "surgery_end_datetime",
)


class _SourceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class RuntimeShadowProvidedInputs:
    source_query_observations: tuple[source_manifest_builder.SourceQueryObservation, ...]
    extraction_inputs: tuple[runtime_shadow_assembler.RuntimePairExtractionInput, ...]
    target_qualifications: tuple[deterministic_gate.TargetQualification, ...]
    evidence_payload: Mapping[str, Any]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _source_limit(source_key: str) -> int:
    return int(getattr(bundle_assembly, "_DOMAIN_FETCH_LIMITS", {}).get(source_key, 50))


def read_luxian_0609_runtime_source_rows(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> list[dict[str, Any]]:
    """生产读侧 seam；仅选择计数及手术时间所需字段。"""
    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise _SourceUnavailable()
    schema = trusted_schema
    engine = bundle_assembly.engine
    if engine is None:
        raise _SourceUnavailable()
    columns = set(bundle_assembly._get_table_columns(schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise _SourceUnavailable()
    selected = [field for field in _BEGIN_END_FIELDS if source_key == "surgery_record" and field in columns]
    if source_key == "presurg_summary":
        selected.extend(field for field in ("record_content", "record_time") if field in columns)
    if source_key == "surgery_safecheck_record":
        selected.extend(field for field in ("record_content",) if field in columns)
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected) or "1 AS row_marker"
    order_candidates = (*getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()), "document_id", "id", *_BEGIN_END_FIELDS)
    order_columns = [field for field in order_candidates if field in columns]
    order_sql = ""
    if order_columns:
        order_sql = " ORDER BY " + ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST" for field in order_columns
        )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{order_sql} LIMIT :limit_rows"
    )
    with engine.connect() as conn:
        rows = conn.execute(bundle_assembly.text(sql), {
            "institute_id": institute_id, "patient_id": patient_id,
            "visit_id": visit_id, "limit_rows": _source_limit(source_key),
        }).mappings().all()
    return [dict(row) for row in rows]


def _required_pairs(plan: planner.ShadowRulePlan) -> tuple[tuple[str, str], ...]:
    return tuple(sorted({
        (requirement.fact_type, source_key)
        for rule in plan.planned_rules
        for requirement in rule.trigger_requirements
        for source_key in requirement.allowed_source_keys
    }))


def _has_performed_time(row: Mapping[str, Any]) -> bool:
    for field in _BEGIN_END_FIELDS:
        value = row.get(field)
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        try:
            parsed = datetime.strptime(candidate, _PERFORMED_TIME_FORMAT)
        except ValueError:
            continue
        if parsed.strftime(_PERFORMED_TIME_FORMAT) == candidate:
            return True
    return False


def _parse_performed_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    try:
        parsed = datetime.strptime(candidate, _PERFORMED_TIME_FORMAT)
    except ValueError:
        return None
    return parsed if parsed.strftime(_PERFORMED_TIME_FORMAT) == candidate else None


def _substantive_target_body(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    return len(candidate) >= _MIN_SUBSTANTIVE_TARGET_LENGTH and candidate not in {"[]", "{}", "null", "None"}


def _parse_presurg_record_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    try:
        parsed = datetime.strptime(candidate, _PRESURG_RECORD_TIME_FORMAT)
    except ValueError:
        return None
    return parsed if parsed.strftime(_PRESURG_RECORD_TIME_FORMAT) == candidate else None


def _target_qualification_material_hash(source_key: str, row: Mapping[str, Any]) -> str | None:
    """将资格判定的白名单输入绑定为不可逆行摘要，绝不输出原值。"""
    if source_key == "presurg_summary":
        material = {
            "record_content": row.get("record_content").strip() if isinstance(row.get("record_content"), str) else "",
            "record_time": row.get("record_time").strip() if isinstance(row.get("record_time"), str) else "",
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
    observations: list[source_manifest_builder.SourceQueryObservation] = []
    for source_key in expected_sources:
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

    status_by_source = {item.source_key: item.query_status for item in observations}
    visit_scope_ref = _digest({"institute_id": institute_id, "patient_id": patient_id, "visit_id": visit_id})
    documents: dict[str, list[dict[str, str]]] = {}
    signals_by_pair: dict[tuple[str, str], tuple[runtime_shadow_assembler.RuntimeStructuredFactSignal, ...]] = {}
    for source_key in expected_sources:
        safe_rows: list[dict[str, str]] = []
        signals: list[runtime_shadow_assembler.RuntimeStructuredFactSignal] = []
        materials = []
        for row in rows_by_source[source_key]:
            material = {
                "source_key": source_key,
                "surgery_times": {
                    field: str(row.get(field) or "").strip()
                    for field in _BEGIN_END_FIELDS
                    if source_key == "surgery_record" and str(row.get(field) or "").strip()
                },
            }
            qualification_material_hash = _target_qualification_material_hash(source_key, row)
            if qualification_material_hash is not None:
                material["qualification_material_hash"] = qualification_material_hash
            materials.append((material, source_key == "surgery_record" and _has_performed_time(row)))
        materials.sort(key=lambda item: _canonical(item[0]))
        occurrences: dict[str, int] = {}
        for material, has_performed_time in materials:
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
            if has_performed_time:
                signals.append(runtime_shadow_assembler.RuntimeStructuredFactSignal(
                    signal_ref=_digest({"signal": "performed", "row_ref": row_ref}),
                    fact_type="current_visit_surgery_confirmed", source_key=source_key,
                    event_status="performed", source_record_ref=row_ref,
                    source_document_type="runtime_structured", extractor_version=_EXTRACTOR_VERSION,
                    mapping_policy_version=_MAPPING_POLICY_VERSION,
                ))
        documents[source_key] = safe_rows
        signals_by_pair[("current_visit_surgery_confirmed", source_key)] = tuple(signals)

    outcomes: list[runtime_shadow_assembler.RuntimePairExtractionInput] = []
    for fact_type, source_key in _required_pairs(plan):
        status = status_by_source[source_key]
        rows = rows_by_source[source_key]
        signals = signals_by_pair.get((fact_type, source_key), ())
        if status is QueryStatus.UNAVAILABLE:
            state, processed, reason = "not_run", 0, "source_unavailable"
        elif status is QueryStatus.ERROR:
            state, processed, reason = "not_run", 0, "source_query_error"
        else:
            state, processed, reason = "complete", len(rows), ""
        outcomes.append(runtime_shadow_assembler.RuntimePairExtractionInput(
            fact_type=fact_type, source_key=source_key, state=state,
            extractor_version=_EXTRACTOR_VERSION, mapping_policy_version=_MAPPING_POLICY_VERSION,
            processed_record_count=processed, positive_signals=signals, reason_code=reason,
        ))
    confirmed_surgery_times = tuple(
        parsed
        for row in rows_by_source.get("surgery_record", ())
        for parsed in (_parse_performed_time(row.get(field)) for field in _BEGIN_END_FIELDS)
        if parsed is not None
    )
    earliest_surgery_time = min(confirmed_surgery_times) if confirmed_surgery_times else None
    observation_by_source = {item.source_key: item for item in observations}
    qualifications: list[deterministic_gate.TargetQualification] = []
    for rule in plan.planned_rules:
        if rule.rule_id not in ("LX0609-029", "LX0609-032"):
            continue
        if observation_by_source[rule.target_source_key].query_status is not QueryStatus.AVAILABLE:
            continue
        target_rows = rows_by_source[rule.target_source_key]
        target_snapshot_hash = _digest({"source_key": rule.target_source_key, "documents": documents[rule.target_source_key]})
        if rule.rule_id == "LX0609-029":
            qualified_count = sum(
                1
                for row in target_rows
                if _substantive_target_body(row.get("record_content"))
                and (record_time := _parse_presurg_record_time(row.get("record_time"))) is not None
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
