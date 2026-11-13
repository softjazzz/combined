"""CDM 自动取材的来源范围；查询成功不等于上游临床材料完整。"""

from dataclasses import replace

from . import case_material_snapshot as material

PROTOCOL = "cdm-auto-v1"
GAPS = frozenset({"table_missing", "columns_missing", "empty_unconfirmed"})


def validate_read_contract(report):
    """缺供给按来源保存；权限与连接安全不能降格成临床资料不足。"""
    if not report.get("read_only") or not report.get("account_read_only"):
        raise material.MaterialSnapshotError("material_source_contract_incomplete")
    statuses = {}
    for item in report["dependencies"]:
        status = item["status"]
        if status == "columns_missing" and {
            "institute_id",
            "patient_id",
            "visit_id",
        }.intersection(item.get("missing_columns", ())):
            raise material.MaterialSnapshotError("material_identity_or_source_mismatch")
        if status not in {
            "structure_ready",
            "rows_present",
            "zero_rows",
            "table_missing",
            "columns_missing",
        }:
            raise material.MaterialSnapshotError("material_source_contract_incomplete")
        statuses[item["table"]] = status
    return statuses


def source_scope(source_key):
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


def guard_decision(decision, source_keys):
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
    if decision.qc_direction is QcDirection.DEFECT and decision.positive_document_refs:
        return decision  # Binding 已验证为本轮真实文书引用，owner 明确声明独立证明。
    # 正文空仍可能有该规则需要的结构化字段；是否缺少必要正文由 owner 判断。
    gap = any(scope["status"] in GAPS for scope in scopes)
    # 通用 DEFECT 合同不能证明是否包含“没找到”推断；覆盖未知时保守交待核。
    # 明确数值/时间超阈值仍须依赖材料齐全；其余独立规则照常交付。
    absence_dependent = decision.reason_code in {
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
        confidence=None,
        evaluator_version="cdm-auto-scope-v1",
    )
