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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "fourth_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "fourth_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session


TARGET_POOL_NAME = "0426"
SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
FOURTH_BATCH_RULE_ID_SET = {"SC-027", "SC-097"}
FOURTH_BATCH_SOURCE = "manual_problem_sample_pool_fourth_batch_regression"


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
        case_id="semantic-b4-core-001",
        stage="fourth_batch",
        record_id="2040917",
        patient_name="张高芬",
        issue_family="首次病程诊疗计划不全面/不具体",
        manual_issue_text="入院记录初步诊断不全，首次病程诊疗计划止痛、止血未写明具体措施。",
        primary_rule_id="SC-027",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="首次病程记录",
        notes="当前通过 senior_course fallback 命中，首程原表正文为空不再阻塞。",
    ),
    MatrixCase(
        case_id="semantic-b4-core-002",
        stage="fourth_batch",
        record_id="2068785",
        patient_name="薛尚贵",
        issue_family="首次病程诊疗计划不全面/不具体",
        manual_issue_text="首次病程记录诊疗计划营养支持、止咳化痰、止痛，未给出具体的用药方案，未描述相关检验检查的目的。",
        primary_rule_id="SC-027",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="首次病程记录",
        notes="当前通过 ICU 相关病程/查房正文回退命中。",
    ),
    MatrixCase(
        case_id="semantic-b4-core-003",
        stage="fourth_batch",
        record_id="1888334",
        patient_name="蒋齐芬",
        issue_family="手术记录缺项/描述不清/签名异常",
        manual_issue_text="手术记录中手术名称与术前讨论及术前小结中手术名称不一致。",
        primary_rule_id="SC-097",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="手术记录",
        notes="当前通过 surgery domain bundle 稳定命中，主文书不再走 SC-146。",
    ),
    MatrixCase(
        case_id="semantic-b4-core-004",
        stage="fourth_batch",
        record_id="2191940",
        patient_name="李祥飞",
        issue_family="手术记录缺项/描述不清/签名异常",
        manual_issue_text="手术记录手术结束时间错误（1月26日10：00误写为1月27日10:00）。",
        primary_rule_id="SC-097",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="手术记录",
        notes="当前通过 surgery domain bundle 稳定命中。",
    ),
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _find_pool_id(service: CustomQCSamplePoolService) -> str:
    result = service.list_pools(page=1, page_size=50, query=TARGET_POOL_NAME)
    for item in list(result.items or []):
        if _safe_text(item.get("name")) == TARGET_POOL_NAME:
            return _safe_text(item.get("id"))
    raise RuntimeError(f"未找到样本池: {TARGET_POOL_NAME}")


def _list_recent_fourth_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
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
        if _safe_text(filters.get("source")) != FOURTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(FOURTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第四批语义规则回归 batch")
    return result


def _get_sample_pool_row(service: CustomQCSamplePoolService, *, pool_id: str, record_id: str) -> dict[str, Any] | None:
    rows = service.get_runnable_items(pool_id=pool_id, validation_mode="sc", record_ids=[record_id])
    return dict(rows[0]) if rows else None


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
    pool_service = CustomQCSamplePoolService()
    workspace = CustomQCWorkspaceService()
    pool_id = _find_pool_id(pool_service)
    batch_job_ids = _list_recent_fourth_batch_job_ids(workspace)

    rows: list[dict[str, Any]] = []
    core_hits = 0
    core_misses = 0
    narrowed = 0

    for case in MATRIX_CASES:
        sample_row = _get_sample_pool_row(pool_service, pool_id=pool_id, record_id=case.record_id) or {}
        actual_result = None
        actual_job_id = ""
        for job_id in batch_job_ids:
            actual_result = _get_job_rule_result(
                workspace,
                job_id=job_id,
                record_id=case.record_id,
                rule_id=case.primary_rule_id,
            )
            if actual_result:
                actual_job_id = job_id
                break

        actual_status = _safe_text((actual_result or {}).get("status")).lower() or "missing"
        hit_type = case.expected_hit_type if actual_status == case.expected_status else "miss"
        if case.current_status == "core":
            if actual_status == case.expected_status:
                core_hits += 1
            else:
                core_misses += 1
        if list(sample_row.get("candidate_rule_ids") or []) == [case.primary_rule_id]:
            narrowed += 1

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
                "candidate_rule_ids": ",".join(list(sample_row.get("candidate_rule_ids") or [])),
                "matched_visit_id": _safe_text(sample_row.get("matched_visit_id")),
                "actual_job_id": actual_job_id,
                "findings": _safe_text((actual_result or {}).get("findings"))[:200],
                "evidence": _safe_text((actual_result or {}).get("evidence"))[:200],
                "notes": case.notes,
            }
        )

    summary = {
        "pool_id": pool_id,
        "target_pool_name": TARGET_POOL_NAME,
        "primary_batch_job_ids": batch_job_ids,
        "case_count": len(MATRIX_CASES),
        "core_case_count": sum(1 for case in MATRIX_CASES if case.current_status == "core"),
        "observe_case_count": sum(1 for case in MATRIX_CASES if case.current_status == "observe"),
        "skip_case_count": sum(1 for case in MATRIX_CASES if case.current_status == "skip"),
        "batch_hit_count": core_hits,
        "batch_miss_count": core_misses,
        "cases_with_narrowed_primary_rule": narrowed,
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
                "candidate_rule_ids",
                "matched_visit_id",
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
