"""LX0609 影子运行时的窄来源真值与确定性事实 Provider。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from app.services.bundles import assembly as bundle_assembly

from . import planner, runtime_shadow_assembler, source_manifest_builder
from .source_manifest import QueryStatus

_QUERY_VERSION = "runtime_source_v1"
_EXTRACTOR_VERSION = "rts-v1"
_MAPPING_POLICY_VERSION = "rtm-v1"
_MAX_SOURCES = 5
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
    schema = source_schema or bundle_assembly._default_source_schema()
    engine = bundle_assembly.engine
    if engine is None:
        raise _SourceUnavailable()
    columns = set(bundle_assembly._get_table_columns(schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise _SourceUnavailable()
    selected = [field for field in _BEGIN_END_FIELDS if source_key == "surgery_record" and field in columns]
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected) or "1 AS row_marker"
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        "LIMIT :limit_rows"
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
    return any(str(row.get(field) or "").strip() for field in _BEGIN_END_FIELDS)


def provide_luxian_0609_runtime_shadow_inputs(
    *, plan: planner.ShadowRulePlan, institute_id: str, patient_id: str, visit_id: str,
    source_schema: str | None = None,
) -> RuntimeShadowProvidedInputs:
    if not isinstance(plan, planner.ShadowRulePlan) or not plan.planned_rules:
        raise TypeError("plan must be nonzero ShadowRulePlan")
    if not all(isinstance(value, str) and value.strip() for value in (institute_id, patient_id, visit_id)):
        raise ValueError("invalid source coordinates")
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
    documents: dict[str, list[dict[str, str]]] = {}
    signals_by_pair: dict[tuple[str, str], tuple[runtime_shadow_assembler.RuntimeStructuredFactSignal, ...]] = {}
    for source_key in expected_sources:
        safe_rows: list[dict[str, str]] = []
        signals: list[runtime_shadow_assembler.RuntimeStructuredFactSignal] = []
        for index, row in enumerate(rows_by_source[source_key]):
            row_ref = _digest({"source_key": source_key, "row_index": index, "row": row})
            safe_rows.append({"row_ref": row_ref, "source_snapshot": _digest({"source_key": source_key, "row_index": index})})
            if source_key == "surgery_record" and _has_performed_time(row):
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
    return RuntimeShadowProvidedInputs(
        source_query_observations=tuple(observations),
        extraction_inputs=tuple(outcomes),
        evidence_payload={"programmatic_timeline": {"documents": documents}},
    )
