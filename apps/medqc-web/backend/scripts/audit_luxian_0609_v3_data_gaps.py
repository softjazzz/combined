"""只读清账 LX0609 v3 验证集的 data_gap 结果及唯一资料链。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import sqlalchemy as sa


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

POOL_ID = "luxian-0609-0426-syn-v3"
EXPECTED_RECORD_COUNT = 38
EXPECTED_RULE_COUNT = 75
ROOT_CAUSES = frozenset(
    {
        "source_truly_absent",
        "source_sync_missing",
        "material_read_missing",
        "field_mapping_missing",
        "event_linkage_failed",
        "authoritative_time_missing",
        "evaluation_window_not_mature",
        "applicability_unresolved",
        "synthetic_record_conflict",
        "rule_definition_pending",
        "technical_error_misclassified",
        "other_with_evidence",
    }
)
_EVALUATION_HORIZON_RULE_IDS = frozenset(
    {
        "LX0609-008",
        "LX0609-009",
        "LX0609-011",
        "LX0609-012",
        "LX0609-014",
        "LX0609-015",
        "LX0609-020",
        "LX0609-023",
    }
)
CSV_COLUMNS = (
    "record_id",
    "visit_id",
    "rule_id",
    "status",
    "reason_code",
    "customer_conclusion",
    "data_gap_details",
    "rule_dependencies",
    "required_source_keys",
    "source_observations",
    "material_summary",
    "evidence_delivery_trace",
    "customer_fact_delivery_trace",
    "workspace_envelope_match",
    "first_abnormal_layer",
    "primary_root_cause",
    "classification_confidence",
    "classification_evidence",
    "native_decision_trace",
)


class AuditContractError(ValueError):
    """审计输入或冻结结果不符合既定合同。"""


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _current_commit() -> str:
    completed = subprocess.run(
        ["git", "-c", "safe.directory=D:/LLM/LX888", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _coordinate_hash(rows: Iterable[Mapping[str, Any]]) -> str:
    coordinates = sorted(
        (
            _text(row.get("institute_id")),
            _text(row.get("patient_id")),
            _text(row.get("visit_id")),
        )
        for row in rows
    )
    return hashlib.sha256(_canonical_json(coordinates).encode("utf-8")).hexdigest()


class _BorrowedConnectionEngine:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def connect(self) -> Any:
        return nullcontext(self._connection)


@contextmanager
def _borrowed_reader_environment(
    connection: Any, *, columns_by_table: Mapping[str, tuple[str, ...]]
) -> Any:
    """让既有 source reader 使用同一个只读一致性事务。"""

    from app.services.bundles import assembly as bundle_assembly

    original_engine = bundle_assembly.engine
    original_get_columns = bundle_assembly._get_table_columns
    bundle_assembly.engine = _BorrowedConnectionEngine(connection)
    bundle_assembly._get_table_columns = lambda _schema, table: columns_by_table.get(
        str(table), ()
    )
    try:
        yield
    finally:
        bundle_assembly.engine = original_engine
        bundle_assembly._get_table_columns = original_get_columns


def _load_columns(connection: Any, *, schema: str, table: str) -> tuple[str, ...]:
    rows = connection.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "ORDER BY ordinal_position"
        ),
        {"schema": schema, "table": table},
    ).mappings()
    return tuple(_text(row.get("column_name")) for row in rows)


def _source_keys_for_rule(rule_id: str) -> tuple[str, ...]:
    from app.services.luxian_0609.source_registry import (
        resolve_luxian_0609_controlled_fact_source_keys,
        resolve_luxian_0609_decision_support_source_keys,
        resolve_luxian_0609_rule_sources,
    )

    source_entries = resolve_luxian_0609_rule_sources((rule_id,))[rule_id]
    keys = [
        source_key
        for entry in source_entries
        for source_key in entry.source_keys
    ]
    keys.extend(resolve_luxian_0609_controlled_fact_source_keys((rule_id,)))
    keys.extend(resolve_luxian_0609_decision_support_source_keys((rule_id,)))
    if rule_id in _EVALUATION_HORIZON_RULE_IDS:
        keys.append("evaluation_context.horizon")
    return tuple(dict.fromkeys(key for key in keys if key))


def _serialize_observations(session: Any, required_keys: tuple[str, ...]) -> dict[str, Any]:
    observations = {item.source_key: item for item in session.snapshot.observations}
    output: dict[str, Any] = {}
    for key in required_keys:
        item = observations.get(key)
        if item is None:
            output[key] = {"query_state": "not_requested"}
            continue
        output[key] = item.to_dict()
    return output


def _material_summary(session: Any, required_keys: tuple[str, ...]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in required_keys:
        if key == "evaluation_context.horizon" or "." in key:
            summary[key] = {"present": None, "runtime_derived": True}
            continue
        if not session.materials.has_source(key):
            summary[key] = {"present": False}
            continue
        material = session.materials.source(key)
        summary[key] = {
            "present": True,
            "row_count": len(material.rows),
            "truncated": material.truncated,
        }
    return summary


def _is_unavailable(observations: Mapping[str, Any]) -> bool:
    return any(
        isinstance(item, Mapping)
        and item.get("query_state") in {"unavailable", "error"}
        for item in observations.values()
    )


def _has_reader_capability_gap(observations: Mapping[str, Any]) -> bool:
    return any(
        isinstance(item, Mapping)
        and item.get("reason_code")
        in {"SOURCE_READER_NOT_REGISTERED", "SOURCE_CAPABILITY_UNAVAILABLE"}
        for item in observations.values()
    )


def _is_empty(observations: Mapping[str, Any]) -> bool:
    return any(
        isinstance(item, Mapping) and item.get("query_state") == "empty"
        for item in observations.values()
    )


def classify_gap(
    *,
    reason_code: str,
    observations: Mapping[str, Any],
    material_summary: Mapping[str, Any],
    required_source_keys: tuple[str, ...],
    workspace_envelope_match: bool,
) -> tuple[str, str, str, str]:
    """只依据可复核资料链分类，不把未持久化 Decision 猜成根因。"""

    observations = {
        key: observations[key] for key in required_source_keys if key in observations
    }

    if not workspace_envelope_match:
        return (
            "technical_error_misclassified",
            "workspace_to_envelope",
            "confirmed",
            "任务原始项与保存 Envelope 的状态、原因或客户交付字段不一致。",
        )
    if _has_reader_capability_gap(observations):
        return (
            "other_with_evidence",
            "source_registry",
            "confirmed",
            "必需来源在当前唯一资料链中被明确标记为未注册或能力不可用；这不是源库同步为空的证据。",
        )
    if _is_unavailable(observations):
        return (
            "source_sync_missing",
            "evidence_snapshot",
            "confirmed",
            "重建 EvidenceSnapshot 显示必需来源不可用或读取出错。",
        )
    if any(
        isinstance(item, Mapping) and item.get("present") is False
        for item in material_summary.values()
    ):
        return (
            "material_read_missing",
            "material_store",
            "confirmed",
            "Snapshot 已声明可读来源，但对应 MaterialStore 未提供可消费材料。",
        )
    if reason_code == "authoritative_time_missing":
        return (
            "authoritative_time_missing",
            "native_result_projection",
            "confirmed",
            "Native 后的任务原始项已明确给出权威时间缺失原因；历史原始 Decision 未持久化。",
        )
    if reason_code == "evaluation_window_not_mature":
        return (
            "evaluation_window_not_mature",
            "native_result_projection",
            "confirmed",
            "Native 后的任务原始项已明确给出评价窗口尚未届满原因；历史原始 Decision 未持久化。",
        )
    if reason_code in {"linkage_unresolved", "association_failed"}:
        if not _is_empty(observations):
            return (
                "event_linkage_failed",
                "native_result_projection",
                "indicated",
                "相关来源已读取但任务原始项仍报告关联失败；原始 Decision 未持久化，不能事后区分数据关联不足与算法关联失败。",
            )
    if reason_code == "applicability_source_gap":
        return (
            "applicability_unresolved",
            "native_result_projection",
            "confirmed",
            "任务原始项明确缺少适用性判断资料；未将其误判为确定的不适用。",
        )
    if reason_code == "source_unavailable" or _is_empty(observations):
        return (
            "source_truly_absent",
            "source_pg",
            "indicated",
            "重建 Snapshot 显示至少一个必需来源为空；需以规则具体必需字段确认是否为临床资料本身不存在。",
        )
    if reason_code == "required_field_missing":
        return (
            "other_with_evidence",
            "native_result_projection",
            "unresolved",
            "来源可读但历史任务未持久化原始 Decision/字段提取；不能仅凭泛化原因码断言字段映射缺失。",
        )
    return (
        "other_with_evidence",
        "native_result_projection",
        "unresolved",
        "当前持久化信息不足以证明首次异常层，未推断为系统缺陷。",
    )


def _compare_delivery(raw: Mapping[str, Any], envelope: Mapping[str, Any]) -> tuple[bool, list[str]]:
    differences: list[str] = []
    checks = {
        "status": (raw.get("status"), envelope.get("status")),
        "reason_code": (raw.get("reason_code"), envelope.get("reason_code")),
        "conclusion": (
            raw.get("source_conclusion")
            or raw.get("findings")
            or raw.get("customer_message"),
            envelope.get("conclusion") or envelope.get("findings"),
        ),
        "suggestion": (raw.get("suggestion"), envelope.get("suggestion")),
    }
    for key, (left, right) in checks.items():
        if _canonical_json(left) != _canonical_json(right):
            differences.append(key)
    raw_gap = raw.get("data_gap_details") or {}
    envelope_gap = envelope.get("data_gap_details") or {}
    if not isinstance(raw_gap, Mapping) or not isinstance(envelope_gap, Mapping):
        if _canonical_json(raw_gap) != _canonical_json(envelope_gap):
            differences.append("data_gap_details")
    elif any(
        _canonical_json(value) != _canonical_json(envelope_gap.get(key))
        for key, value in raw_gap.items()
    ):
        # Envelope 可附加 source_status；只要原字段保持原值就仍是原样交付。
        differences.append("data_gap_details")
    return not differences, differences


def _evidence_delivery_trace(
    raw: Mapping[str, Any], envelope: Mapping[str, Any]
) -> dict[str, Any]:
    """记录 Canonical 到 Envelope 的证据授权投影，不以无授权引用冒充丢失。"""

    raw_rows: list[Mapping[str, Any]] = []
    for key in ("customer_evidence", "evidence_items", "evidence_refs"):
        value = raw.get(key)
        if isinstance(value, list):
            raw_rows.extend(item for item in value if isinstance(item, Mapping))
    locatable_keys = (
        "source_ref",
        "document_ref",
        "fact_ref",
        "source_document_id",
        "document_id",
    )
    raw_locatable = [
        item
        for item in raw_rows
        if any(_text(item.get(key)) for key in locatable_keys)
    ]
    envelope_rows = envelope.get("evidence")
    envelope_rows = envelope_rows if isinstance(envelope_rows, list) else []
    envelope_refs = [
        _text(item.get("source_ref"))
        for item in envelope_rows
        if isinstance(item, Mapping) and _text(item.get("source_ref"))
    ]
    if not raw_rows:
        state = "no_canonical_evidence_items"
    elif not raw_locatable:
        state = "canonical_evidence_unlocatable"
    elif not envelope_refs:
        state = "locatable_evidence_not_delivered"
    else:
        state = "locatable_evidence_delivered"
    return {
        "state": state,
        "canonical_evidence_item_count": len(raw_rows),
        "canonical_locatable_ref_count": len(raw_locatable),
        "envelope_evidence_count": len(envelope_rows),
        "envelope_source_refs": envelope_refs,
    }


def _customer_fact_delivery_trace(
    raw: Mapping[str, Any], envelope: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "canonical_customer_display_facts": raw.get("customer_display_facts"),
        "canonical_decision_facts": raw.get("decision_facts"),
        "envelope_customer_display_facts": envelope.get("customer_display_facts"),
        "envelope_decision_facts": envelope.get("decision_facts"),
    }


def _task_snapshot_by_record(filters: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(item.get("record_id")): dict(item)
        for item in filters.get("record_scene_snapshot") or ()
        if isinstance(item, Mapping) and _text(item.get("record_id"))
    }


def _evaluation_inputs(
    snapshot: Mapping[str, Any], *, fallback_task_date: str
) -> tuple[str | None, str | None, str | None]:
    scene = _text(snapshot.get("resolved_scene") or snapshot.get("record_scene"))
    if scene == "final":
        return None, "authoritative_discharge", None
    if scene == "running":
        frozen_date = _text(snapshot.get("evaluation_horizon")) or fallback_task_date
        return frozen_date, "frozen_task_date", None
    return None, "disabled", "authoritative_time_missing"


def _load_evidence_sessions(
    connection: Any,
    *,
    coordinates_by_record: Mapping[str, Mapping[str, str]],
    filters: Mapping[str, Any],
    source_schema: str,
    created_at: str,
) -> dict[str, Any]:
    from app.services.luxian_0609.evidence_snapshot_provider import (
        build_luxian_0609_evidence_read_session,
    )
    from app.services.luxian_0609.executor_registry import (
        resolve_legacy_executor_material_source_keys,
    )
    from app.services.luxian_0609.native_package import (
        build_luxian_0609_package_plan_from_settings,
        load_luxian_0609_dependency_inventory,
    )
    from app.services.luxian_0609.source_evidence_reader import _SNAPSHOT_SOURCE_FIELDS

    selected_rule_ids = tuple(filters.get("rule_ids") or ())
    if len(selected_rule_ids) != EXPECTED_RULE_COUNT:
        raise AuditContractError("frozen_job_rule_ids_not_75")
    class _AllNativeAuditSettings:
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED = True
        LUXIAN_0609_NATIVE_MDT_040_ENABLED = True
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED = True
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED = True
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED = True
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED = True
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED = True
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED = True
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED = True
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED = True
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED = True
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED = True
        LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED = True

    package_plan = build_luxian_0609_package_plan_from_settings(
        inventory=load_luxian_0609_dependency_inventory(),
        selected_rule_ids=selected_rule_ids,
        settings=_AllNativeAuditSettings(),
    )
    additional_source_keys = resolve_legacy_executor_material_source_keys(
        tuple(key for key, _rules in package_plan.native_executor_batches),
        selected_rule_ids=package_plan.selected_rule_ids,
    )
    physical_keys = tuple(key for key in _SNAPSHOT_SOURCE_FIELDS if "." not in key)
    columns_by_table = {
        key: _load_columns(connection, schema=source_schema, table=key)
        for key in physical_keys
    }
    snapshots = _task_snapshot_by_record(filters)
    sessions: dict[str, Any] = {}
    with _borrowed_reader_environment(connection, columns_by_table=columns_by_table):
        for record_id, coordinate in coordinates_by_record.items():
            as_of_date, policy, unavailable_reason = _evaluation_inputs(
                snapshots.get(record_id, {}), fallback_task_date=created_at[:10]
            )
            sessions[record_id] = build_luxian_0609_evidence_read_session(
                selected_rule_ids=package_plan.selected_rule_ids,
                institute_id=coordinate["institute_id"],
                patient_id=coordinate["patient_id"],
                visit_id=coordinate["visit_id"],
                source_schema=source_schema,
                created_at=created_at,
                evaluation_as_of_date=as_of_date,
                evaluation_horizon_policy=policy,
                horizon_unavailable_reason=unavailable_reason,
                additional_source_keys=additional_source_keys,
            )
    return sessions


def execute_audit(connection: Any, *, job_id: str, started_at: str, commit: str) -> dict[str, Any]:
    from app.database.connection import DB_SCHEMA_MODE
    from app.services.bundles import assembly as bundle_assembly
    from app.services.luxian_0609.native_package import (
        load_luxian_0609_dependency_inventory,
    )
    from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts

    schema = "qc" if DB_SCHEMA_MODE == "split" else "public"
    job = connection.execute(
        sa.text(
            f"SELECT id::text AS id, status, total_records, success_count, failed_count, "
            f"filters_json, items_json, created_at, finished_at "
            f"FROM {schema}.custom_qc_batch_jobs WHERE id::text = :job_id"
        ),
        {"job_id": job_id},
    ).mappings().one_or_none()
    if job is None:
        raise AuditContractError("job_not_found")
    filters = _json(job["filters_json"], {})
    if _text(filters.get("sample_pool_id")) != POOL_ID:
        raise AuditContractError("job_not_v3_pool")
    if _text(job.get("status")) != "completed":
        raise AuditContractError("job_not_completed")
    if int(job.get("total_records") or 0) != EXPECTED_RECORD_COUNT:
        raise AuditContractError("job_record_count_not_38")
    if int(filters.get("rule_count") or 0) != EXPECTED_RULE_COUNT:
        raise AuditContractError("job_rule_count_not_75")

    raw_items = _json(job["items_json"], [])
    if not isinstance(raw_items, list):
        raise AuditContractError("job_items_not_array")
    raw_by_key = {
        (_text(item.get("record_id")), _text(item.get("rule_id"))): item
        for item in raw_items
        if isinstance(item, Mapping)
    }
    envelopes = connection.execute(
        sa.text(
            f"SELECT record_id::text AS record_id, institute_id::text AS institute_id, "
            f"patient_id::text AS patient_id, visit_id::text AS visit_id, envelope_json "
            f"FROM {schema}.luxian_0609_record_result_envelopes WHERE job_id::text = :job_id "
            "ORDER BY record_id::text"
        ),
        {"job_id": job_id},
    ).mappings().all()
    if len(envelopes) != EXPECTED_RECORD_COUNT:
        raise AuditContractError("envelope_record_count_not_38")
    coordinates_by_record = {
        _text(row["record_id"]): {
            "institute_id": _text(row["institute_id"]),
            "patient_id": _text(row["patient_id"]),
            "visit_id": _text(row["visit_id"]),
        }
        for row in envelopes
    }
    envelope_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in envelopes:
        envelope = _json(row["envelope_json"], {})
        items = envelope.get("items") if isinstance(envelope, Mapping) else None
        if not isinstance(items, list):
            raise AuditContractError("envelope_items_not_array")
        for item in items:
            if isinstance(item, Mapping):
                envelope_by_key[(_text(row["record_id"]), _text(item.get("rule_id")))] = item
    if len(envelope_by_key) != EXPECTED_RECORD_COUNT * EXPECTED_RULE_COUNT:
        raise AuditContractError("envelope_items_not_2850")

    sessions = _load_evidence_sessions(
        connection,
        coordinates_by_record=coordinates_by_record,
        filters=filters,
        source_schema=bundle_assembly._default_source_schema(),
        created_at=started_at,
    )
    contracts = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}
    dependencies = {item.rule_id: item for item in load_luxian_0609_dependency_inventory()}
    details: list[dict[str, Any]] = []
    for key, envelope_item in sorted(envelope_by_key.items()):
        record_id, rule_id = key
        if envelope_item.get("status") != "data_gap":
            continue
        raw_item = raw_by_key.get(key)
        if raw_item is None:
            raise AuditContractError("workspace_raw_item_missing")
        contract = contracts[rule_id]
        dependency = dependencies[rule_id]
        required_keys = _source_keys_for_rule(rule_id)
        session = sessions[record_id]
        observations = _serialize_observations(session, required_keys)
        materials = _material_summary(session, required_keys)
        matched, differences = _compare_delivery(raw_item, envelope_item)
        evidence_trace = _evidence_delivery_trace(raw_item, envelope_item)
        fact_trace = _customer_fact_delivery_trace(raw_item, envelope_item)
        cause, layer, confidence, evidence = classify_gap(
            reason_code=_text(envelope_item.get("reason_code")),
            observations=observations,
            material_summary=materials,
            required_source_keys=required_keys,
            workspace_envelope_match=matched,
        )
        if cause not in ROOT_CAUSES:
            raise AuditContractError("unknown_root_cause")
        raw_trace = raw_item.get("diagnostic_trace")
        details.append(
            {
                "record_id": record_id,
                "visit_id": coordinates_by_record[record_id]["visit_id"],
                "rule_id": rule_id,
                "status": _text(envelope_item.get("status")),
                "reason_code": _text(envelope_item.get("reason_code")),
                "customer_conclusion": _text(
                    envelope_item.get("conclusion") or envelope_item.get("findings")
                ),
                "data_gap_details": envelope_item.get("data_gap_details") or {},
                "rule_dependencies": list(contract.data_dependencies),
                "required_source_keys": list(required_keys),
                "source_observations": observations,
                "material_summary": materials,
                "evidence_delivery_trace": evidence_trace,
                "customer_fact_delivery_trace": fact_trace,
                "workspace_envelope_match": matched,
                "delivery_differences": differences,
                "first_abnormal_layer": layer,
                "primary_root_cause": cause,
                "classification_confidence": confidence,
                "classification_evidence": evidence,
                "native_decision_trace": {
                    "available": False,
                    "reason": "historical_rule_decision_not_persisted",
                    "observable_native_projection": {
                        "source_status": _text(raw_item.get("source_status")),
                        "source_conclusion": _text(raw_item.get("source_conclusion")),
                        "executor_type": _text(raw_item.get("executor_type")),
                        "execution_domain": _text(raw_item.get("execution_domain")),
                        "diagnostic_trace_keys": sorted(raw_trace) if isinstance(raw_trace, Mapping) else [],
                    },
                },
                "executor_key": dependency.executor_key,
                "family_key": dependency.family_key,
                "snapshot_hash": session.snapshot.snapshot_hash,
            }
        )
    return {
        "audit_started_at": started_at,
        "git_commit": commit,
        "job": {
            "id": _text(job["id"]),
            "created_at": str(job["created_at"]),
            "finished_at": str(job["finished_at"]),
            "record_count": int(job["total_records"]),
            "success_count": int(job["success_count"] or 0),
            "failed_count": int(job["failed_count"] or 0),
            "rule_count": int(filters["rule_count"]),
            "engine_config": {
                key: filters.get(key)
                for key in (
                    "execution_mode",
                    "execution_strategy",
                    "execution_rule_count",
                    "max_parallel_records",
                    "model_code",
                    "quality_profile",
                    "run_mode",
                    "validation_mode",
                )
            },
        },
        "coordinate_hash": _coordinate_hash(coordinates_by_record.values()),
        "status_counts": dict(Counter(_text(item.get("status")) for item in envelope_by_key.values())),
        "details": details,
    }


def _write_csv(path: Path, details: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for item in details:
            writer.writerow(
                {
                    column: _canonical_json(item[column])
                    if isinstance(item.get(column), (dict, list))
                    else item.get(column, "")
                    for column in CSV_COLUMNS
                }
            )


def _render_report(report: Mapping[str, Any]) -> str:
    details = list(report["details"])
    by_rule = Counter(item["rule_id"] for item in details)
    by_cause = Counter(item["primary_root_cause"] for item in details)
    by_confidence = Counter(item["classification_confidence"] for item in details)
    capability_gaps = [
        item for item in details if item["first_abnormal_layer"] == "source_registry"
    ]
    capability_by_rule = Counter(item["rule_id"] for item in capability_gaps)
    evidence_states = Counter(
        item["evidence_delivery_trace"]["state"] for item in details
    )
    truth_causes = {
        "source_truly_absent",
        "source_sync_missing",
        "authoritative_time_missing",
        "evaluation_window_not_mature",
        "applicability_unresolved",
    }
    confirmed_true = sum(
        1
        for item in details
        if item["primary_root_cause"] in truth_causes
        and item["classification_confidence"] == "confirmed"
    )
    indicated_true = sum(
        1
        for item in details
        if item["primary_root_cause"] in truth_causes
        and item["classification_confidence"] == "indicated"
    )
    indicated_other = sum(
        1
        for item in details
        if item["classification_confidence"] == "indicated"
        and item["primary_root_cause"] not in truth_causes
    )
    confirmed_wrong = sum(
        count
        for cause, count in by_cause.items()
        if cause in {"material_read_missing", "field_mapping_missing", "technical_error_misclassified"}
    )
    unresolved = sum(
        1 for item in details if item["classification_confidence"] == "unresolved"
    )
    lines = [
        "# 泸县0609真实病历合成验证集 v3 data_gap 根因清账",
        "",
        "## 冻结基线",
        "",
        f"- 审计 Git：`{report['git_commit']}`",
        f"- 冻结任务：`{report['job']['id']}`（运行完成：{report['job']['finished_at']}）",
        f"- 病例 / 规则：{report['job']['record_count']} / {report['job']['rule_count']}",
        f"- 三坐标集合哈希：`{report['coordinate_hash']}`",
        f"- 引擎配置：`{_canonical_json(report['job']['engine_config'])}`",
        f"- 最终状态：`{_canonical_json(report['status_counts'])}`",
        "",
        "本报告在单个 `REPEATABLE READ, READ ONLY` 事务中重建当前资料快照，未写入数据库、未运行质控、未调用 LLM。",
        "",
        "## data_gap 汇总",
        "",
        f"- data_gap：**{len(details)}** 条，涉及 **{len({item['record_id'] for item in details})}** 份病例。",
        f"- 已证实的真实/保守资料缺口：{confirmed_true} 条；存在资料缺口指征、但尚不能定性：{indicated_true} 条；存在关联失败指征、但尚不能定性为引擎缺陷：{indicated_other} 条；已证实的交付/读取错误：{confirmed_wrong} 条；证据不足、不得臆断：{unresolved} 条。",
        f"- 分类置信度：`{_canonical_json(dict(by_confidence))}`。",
        "",
        "### 按主要根因",
        "",
        "|根因|条数|",
        "|---|---:|",
        *[f"|{cause}|{count}|" for cause, count in by_cause.most_common()],
        "",
        "### 影响最大的三个根因",
        "",
        *[
            f"- `{cause}`：{count} 条。"
            for cause, count in by_cause.most_common(3)
        ],
        "",
        "### 真实缺失与错误 data_gap 比例",
        "",
        f"- 仅以可证实结果计：真实/保守资料缺口 {confirmed_true}，错误 data_gap {confirmed_wrong}；比例为 `{confirmed_true}:{confirmed_wrong}`。",
        f"- 另有 {indicated_true} 条来源为空指征、{indicated_other} 条关联失败指征和 {unresolved} 条未解析项，均不得强行并入任一侧。",
        "",
        "### 按规则（全部见 CSV）",
        "",
        "|规则|data_gap 条数|",
        "|---|---:|",
        *[f"|{rule_id}|{count}|" for rule_id, count in by_rule.most_common()],
        "",
        "## 资料链结论与限制",
        "",
        "1. 每一条 CSV 均记录了规则依赖、重建 Snapshot 的查询状态/行数、MaterialStore 行数/截断、任务原始项与 Envelope 一致性及首次可观察异常层。",
        "2. 历史任务没有持久化逐规则 `RuleDecision` 或当时的 Snapshot Observation；因此本审计不能伪造‘历史原始 Decision 已完全回放’。CSV 统一标记 `historical_rule_decision_not_persisted`。",
        "3. `required_field_missing` 且来源已读取的结果统一保守归为 `other_with_evidence`，不把泛化文案擅自判成字段映射缺陷。",
        "4. Evidence 交付状态：`"
        + _canonical_json(dict(evidence_states))
        + "`。其中 `canonical_evidence_unlocatable` 表示 Canonical 任务项有 evidence_items 但没有可授权引用，Envelope 为空是安全投影结果；不能据此宣称客户有可定位证据。",
        "5. 本阶段未修改任何规则、Canonical、Envelope、API、前端、LLM 调用或资料链。是否进入最多两个确定性修复，必须先从 CSV 中选出至少影响 3 条且能定位首次丢失位置的根因。",
        "",
        "## 下一步建议",
        "",
        "1. 本阶段没有修复项：任务限定为只读审计，不能为了减少 data_gap 改写状态。",
        "2. 未修复的资料能力项："
        + (
            "；".join(
                f"`{rule_id}` {count} 条" for rule_id, count in capability_by_rule.most_common()
            )
            or "无"
        )
        + "。它们的首次可观察异常层是 Source Registry/Reader 能力，不是可在本任务中凭空补齐的源数据；修复会引入新的资料读取能力，触发停止条件。",
        "3. `authoritative_time_missing` 分布在多个规则族，现有证据指向合成记录缺少规则所需的权威时间，而非一个可安全共用的代码缺陷；应先补验证资料或逐规则确认时间来源。",
        "4. 对 `unresolved` 项保留 data_gap，先补可观测 trace 或在用户批准后用受控重跑验证，不能直接改变临床结论。",
        "5. 本报告完成后暂停，等待独立审核确认根因分类与范围。",
        "",
    ]
    return "\n".join(lines)


def run_read_only(engine: Any, operation: Any) -> Any:
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            return operation(connection)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True, help="已完成的38病例 v3 全量任务 ID")
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=Path(r"C:\tmp\medqc-lx0609-review\v3-data-gap-details.csv"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=REPO_ROOT / "docs/audits/2026-08-04-lx0609-v3-data-gap-root-cause.md",
    )
    return parser.parse_args()


def main() -> int:
    from app.database.connection import engine

    args = _arguments()
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report = run_read_only(
        engine,
        lambda connection: execute_audit(
            connection,
            job_id=args.job_id,
            started_at=started_at,
            commit=_current_commit(),
        ),
    )
    _write_csv(args.csv_output.resolve(), report["details"])
    args.report_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report_output.resolve().write_text(
        _render_report(report), encoding="utf-8", newline="\n"
    )
    print(
        f"job_id={report['job']['id']} data_gap={len(report['details'])} "
        f"csv={args.csv_output.resolve()} report={args.report_output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
