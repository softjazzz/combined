"""CDM 自动取材的来源范围；查询成功不等于上游临床材料完整。"""

from dataclasses import replace

from . import case_material_snapshot as material

PROTOCOL = "cdm-auto-v1"
GAPS = frozenset({"table_missing", "columns_missing", "empty_unconfirmed"})
SPECIFIC_DATA_GAPS = frozenset({
    "source_unavailable", "source_truncated", "authoritative_time_missing",
    "authoritative_report_time_missing", "authoritative_time_conflict",
    "document_completion_time_missing", "association_failed", "linkage_unresolved",
    "semantic_extraction_unresolved",
})
UNSUPPLIED_SOURCE_STATES = frozenset({"table_missing", "columns_missing", "not_supplied"})


def validate_read_contract(report):
    """缺供给按来源保存；权限与连接安全不能降格成临床资料不足。"""
    try:
        if not report.get("read_only") or not report.get("account_read_only"):
            raise material.MaterialSnapshotError(
                "material_source_contract_incomplete", stage="source_validation"
            )
        statuses = {}
        for item in report["dependencies"]:
            status = item["status"]
            if status == "columns_missing" and {
                "institute_id",
                "patient_id",
                "visit_id",
            }.intersection(item.get("missing_columns", ())):
                raise material.MaterialSnapshotError(
                    "material_identity_or_source_mismatch", stage="source_validation"
                )
            if status not in {
                "structure_ready",
                "rows_present",
                "zero_rows",
                "table_missing",
                "columns_missing",
            }:
                raise material.MaterialSnapshotError(
                    "material_source_contract_incomplete", stage="source_validation"
                )
            statuses[item["table"]] = status
        return statuses
    except Exception as error:
        material.tag_capture_stage(error, "source_validation")
        raise


def source_scope(source_key):
    from . import primary_material_projection as primary
    selected_scope = primary.scope(source_key)
    if selected_scope is not None:
        return selected_scope
    state = material.context()
    automatic = (state or {}).get("automatic_material")
    if automatic is None:
        return None  # 原快照保持旧合同，不重新判定历史结果。
    if (
        source_key == "daily_course_record"
        and state.get("daily_material_manifest") is not None
    ):
        from .daily_material_projection import scope

        return {**scope(source_key), "status": "available"}
    sources = automatic["sources"]
    return sources.get(source_key, sources.get(source_key.split(".")[0]))


def describe_source(columns, rows, status="structure_ready"):
    if status not in {"table_missing", "columns_missing"}:
        status = "available" if rows else "empty_unconfirmed"
        # 只在真实正文列存在时标记，纯结构化表不能因没有 record_content 判空。
        body_fields = set(columns).intersection({"record_content", "surgery_process"})
        if (
            rows
            and body_fields
            and not any(
                str(row.get(key) or "").strip() for row in rows for key in body_fields
            )
        ):
            status = "body_empty"
    return {
        "protocol": PROTOCOL,
        "status": status,
        "coverage": "unknown",
        "can_judge_clinical_absence": False,
        "row_count": len(rows),
        "publication": "receipt_unverified",
    }


def guard_decision(decision, source_keys, *, consumed_observations=()):
    """仅新自动快照参与；绑定已通过后，相关缺口转待核，不掩盖技术失败。"""
    from .luxian_0609.decision_model import (
        ApplicabilityState,
        EvidenceState,
        QcDirection,
    )

    if (
        decision.applicability is ApplicabilityState.ERROR
        or decision.evidence_state is EvidenceState.TECHNICAL_ERROR
    ):
        return decision
    scopes = [scope for key in source_keys if (scope := source_scope(key)) is not None]
    if not scopes:
        return decision
    if decision.evidence_state is EvidenceState.DATA_GAP and decision.reason_code in SPECIFIC_DATA_GAPS:
        if any(item.query_state.value == "error" for item in consumed_observations):
            return replace(
                decision, applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR, qc_direction=QcDirection.UNKNOWN,
                reason_code="source_query_error", criterion_results=(), positive_document_refs=(),
                confidence=None, evaluator_version="cdm-auto-scope-v1",
            )
        if any(item.query_state.value == "unavailable" for item in consumed_observations):
            return replace(decision, reason_code="source_unavailable")
        if any(item.completeness.value == "truncated" for item in consumed_observations):
            return replace(decision, reason_code="source_truncated")
        if decision.reason_code in {"source_unavailable", "source_truncated"} or all(
            scope["status"] not in UNSUPPLIED_SOURCE_STATES for scope in scopes
        ):
            return decision
    if decision.qc_direction is QcDirection.DEFECT and decision.positive_document_refs:
        return decision  # Binding 已验证为本轮真实文书引用，owner 明确声明独立证明。
    # 正文空仍可能有该规则需要的结构化字段；是否缺少必要正文由 owner 判断。
    gap = any(scope["status"] in GAPS for scope in scopes)
    if decision.evidence_state is EvidenceState.DATA_GAP:
        gap = gap or any(scope["status"] == "not_supplied" for scope in scopes)
    if decision.affirmative_applicability:
        from .luxian_0609.applicability_receipt import AFFIRMATIVE_SCOPE_STATES

        gap = any(scope["status"] not in AFFIRMATIVE_SCOPE_STATES for scope in scopes)
    # 通用 DEFECT 合同不能证明是否包含“没找到”推断；覆盖未知时保守交待核。
    # 明确数值/时间超阈值仍须依赖材料齐全；其余独立规则照常交付。
    absence_dependent = not decision.affirmative_applicability and decision.reason_code in {
        "required_document_missing",
        "trigger_absent_complete",
        "performed_event_absent",
        "requirement_violated",
        "defect_proven",
    }
    unknown_coverage = any(
        not scope.get("can_judge_clinical_absence", False) for scope in scopes
    )
    if not gap and not (absence_dependent and unknown_coverage):
        return decision
    return replace(
        decision,
        applicability=ApplicabilityState.UNKNOWN,
        evidence_state=EvidenceState.DATA_GAP,
        qc_direction=QcDirection.UNKNOWN,
        reason_code="source_readiness_unproven",
        criterion_results=(),
        affirmative_applicability=False,
        confidence=None,
        evaluator_version="cdm-auto-scope-v1",
    )
