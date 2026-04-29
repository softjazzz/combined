#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOC_ROOT = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
DEFAULT_OUTPUT_CSV = DOC_ROOT / "tenth_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "tenth_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session


SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
TENTH_BATCH_RULE_ID_SET = {"SC-098", "LX-016"}
TENTH_BATCH_SOURCE = "manual_problem_sample_pool_tenth_batch_regression"


@dataclass(frozen=True)
class MatrixCase:
    case_id: str
    stage: str
    record_id: str
    patient_name: str
    issue_family: str
    manual_issue_text: str
    primary_rule_id: str
    expected_status: str
    expected_hit_type: str
    target_document_type: str = ""
    current_status: str = "core"
    notes: str = ""


MATRIX_CASES: tuple[MatrixCase, ...] = (
    MatrixCase(
        case_id="semantic-b10-core-001",
        stage="tenth_batch",
        record_id="1888334",
        patient_name="蒋齐芬",
        issue_family="手术记录签名异常",
        manual_issue_text="手术记录中手术名称与术前讨论及术前小结中手术名称不一致",
        primary_rule_id="SC-098",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="手术记录",
    ),
    MatrixCase(
        case_id="semantic-b10-core-002",
        stage="tenth_batch",
        record_id="2260499",
        patient_name="王孝芳",
        issue_family="手术记录签名异常",
        manual_issue_text="手术记录手术结束时间错误（3月10日19:55误写为3月11日19:55）",
        primary_rule_id="SC-098",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="手术记录",
    ),
    MatrixCase(
        case_id="semantic-b10-core-003",
        stage="tenth_batch",
        record_id="2291788",
        patient_name="唐克模",
        issue_family="手术记录签名异常",
        manual_issue_text="手术记录病历记录时间早于手术结束时间涉嫌伪造病历",
        primary_rule_id="SC-098",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="手术记录",
    ),
    MatrixCase(
        case_id="semantic-b10-core-004",
        stage="tenth_batch",
        record_id="1996981",
        patient_name="余基群",
        issue_family="会诊执行记录书写不规范",
        manual_issue_text="请会诊执行记录书写不规范仅描述“遵会诊意见执行”",
        primary_rule_id="LX-016",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
    ),
    MatrixCase(
        case_id="semantic-b10-core-005",
        stage="tenth_batch",
        record_id="2337741",
        patient_name="余定远",
        issue_family="请会诊执行记录复制粘贴严重",
        manual_issue_text="请会诊执行记录中复制粘贴严重，记录中“余同贵科！谢邀！我科愿随访”直接引用会诊意见未进行修改。",
        primary_rule_id="LX-016",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
    ),
    MatrixCase(
        case_id="semantic-b10-core-006",
        stage="tenth_batch",
        record_id="2052129",
        patient_name="胡启凤",
        issue_family="手术记录签名异常",
        manual_issue_text="输血后评价记录时间记录错误，记录时间早于输血时间",
        primary_rule_id="SC-098",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="手术记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，先保留为 SC-098 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b10-core-007",
        stage="tenth_batch",
        record_id="1912027",
        patient_name="雷良贵",
        issue_family="无会诊意见执行记录",
        manual_issue_text="无会诊意见执行记录",
        primary_rule_id="LX-016",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，先保留为 LX-016 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b10-core-008",
        stage="tenth_batch",
        record_id="2168750",
        patient_name="张乃宣",
        issue_family="请会诊执行记录书写不规范",
        manual_issue_text="请会诊执行记录书写不规范仅描述“遵会诊意见执行”",
        primary_rule_id="LX-016",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，先保留为 LX-016 观察位。",
    ),
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _list_recent_tenth_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
    session = _session()
    try:
        table = _batch_jobs_table()
        rows = (
            session.execute(
                select(table.c.id)
                .where(table.c.draft_id == SAMPLE_SC_DRAFT_ID, table.c.status == "completed")
                .order_by(desc(table.c.created_at))
                .limit(30)
            )
            .mappings()
            .all()
        )
    finally:
        session.close()

    result: list[str] = []
    for row in rows:
        job_id = _safe_text(row.get("id"))
        if not job_id:
            continue
        job = workspace.get_batch_job_for_processing(job_id=job_id) or {}
        filters = dict(job.get("filters") or {})
        if _safe_text(filters.get("source")) != TENTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(TENTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第十批语义规则回归 batch")
    return result


def _get_job_rule_result(
    workspace: CustomQCWorkspaceService,
    *,
    job_id: str,
    record_id: str,
    rule_id: str,
) -> dict[str, Any] | None:
    job = workspace.get_batch_job_for_processing(job_id=job_id) or {}
    for item in list(job.get("items") or []):
        item_record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
        item_rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        if item_record_id == record_id and item_rule_id == rule_id.upper():
            return dict(item)
    return None


def _build_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workspace = CustomQCWorkspaceService()
    batch_job_ids = _list_recent_tenth_batch_job_ids(workspace)
    latest_job_id = batch_job_ids[0]
    latest_job = workspace.get_batch_job_for_processing(job_id=latest_job_id) or {}
    latest_filters = dict(latest_job.get("filters") or {})
    latest_record_rule_map = {
        _safe_text(record_id): [_safe_text(rule_id).upper() for rule_id in list(rule_ids or []) if _safe_text(rule_id)]
        for record_id, rule_ids in dict(latest_filters.get("record_rule_map") or {}).items()
        if _safe_text(record_id)
    }
    latest_failed_records = list(latest_job.get("failed_records") or [])

    rows: list[dict[str, Any]] = []
    core_hits = 0
    core_misses = 0
    observe_hits = 0
    observe_misses = 0

    for case in MATRIX_CASES:
        actual_result = _get_job_rule_result(
            workspace,
            job_id=latest_job_id,
            record_id=case.record_id,
            rule_id=case.primary_rule_id,
        )
        actual_status = _safe_text((actual_result or {}).get("status")).lower()
        if not actual_status:
            failed_item = next(
                (
                    item
                    for item in latest_failed_records
                    if _safe_text(item.get("record_id") or item.get("visit_id")) == case.record_id
                    and _safe_text(item.get("rule_id") or item.get("rule_code")).upper() == case.primary_rule_id
                ),
                None,
            )
            if failed_item is not None:
                actual_status = "failed"
            elif case.primary_rule_id in list(latest_record_rule_map.get(case.record_id) or []):
                actual_status = "compliant"
            else:
                actual_status = "missing"

        hit_type = case.expected_hit_type if actual_status == case.expected_status else "miss"
        if case.current_status == "core" and actual_status == case.expected_status:
            core_hits += 1
        elif case.current_status == "core":
            core_misses += 1
        elif actual_status == case.expected_status:
            observe_hits += 1
        else:
            observe_misses += 1

        rows.append(
            {
                "case_id": case.case_id,
                "stage": case.stage,
                "record_id": case.record_id,
                "patient_name": case.patient_name,
                "issue_family": case.issue_family,
                "manual_issue_text": case.manual_issue_text,
                "primary_rule_id": case.primary_rule_id,
                "expected_status": case.expected_status,
                "actual_status": actual_status,
                "hit_type": hit_type,
                "target_document_type": case.target_document_type,
                "current_status": case.current_status,
                "actual_job_id": latest_job_id,
                "findings": _safe_text((actual_result or {}).get("findings"))[:200],
                "evidence": _safe_text((actual_result or {}).get("evidence"))[:200],
                "notes": case.notes,
            }
        )

    summary = {
        "primary_batch_job_ids": [latest_job_id],
        "reference_batch_job_ids": batch_job_ids[1:],
        "case_count": len(MATRIX_CASES),
        "core_case_count": sum(1 for case in MATRIX_CASES if case.current_status == "core"),
        "observe_case_count": sum(1 for case in MATRIX_CASES if case.current_status == "observe"),
        "skip_case_count": 0,
        "batch_hit_count": core_hits,
        "batch_miss_count": core_misses,
        "observe_hit_count": observe_hits,
        "observe_miss_count": observe_misses,
    }
    return rows, summary


def main() -> None:
    rows, summary = _build_rows()
    DEFAULT_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "case_id",
                "stage",
                "record_id",
                "patient_name",
                "issue_family",
                "manual_issue_text",
                "primary_rule_id",
                "expected_status",
                "actual_status",
                "hit_type",
                "target_document_type",
                "current_status",
                "actual_job_id",
                "findings",
                "evidence",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    DEFAULT_OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
