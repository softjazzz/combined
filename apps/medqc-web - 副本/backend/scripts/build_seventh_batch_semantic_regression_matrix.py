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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "seventh_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "seventh_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session


TARGET_POOL_NAME = "0426"
SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
SEVENTH_BATCH_RULE_ID_SET = {"SC-062", "SC-063", "SC-087", "SC-089", "SC-128", "LX-021"}
SEVENTH_BATCH_SOURCE = "manual_problem_sample_pool_seventh_batch_regression"


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
    current_status: str = "observe"
    notes: str = ""


MATRIX_CASES: tuple[MatrixCase, ...] = (
    MatrixCase(
        case_id="semantic-b7-observe-001",
        stage="seventh_batch_observe",
        record_id="1962806",
        patient_name="钟星文",
        issue_family="交接班记录缺失/缺项",
        manual_issue_text="管床医生发生变更未书写交接班记录",
        primary_rule_id="SC-062",
        expected_status="observe",
        expected_hit_type="observe",
        target_document_type="交接班记录",
        current_status="observe",
        notes="观察位：问题文本直指 SC-062，但本地 PG 与 0426 快照均无 handoff/handover 正文，暂不能作为核心锚点。",
    ),
    MatrixCase(
        case_id="semantic-b7-blocked-001",
        stage="seventh_batch_blocked",
        record_id="1931889",
        patient_name="刘佳钦",
        issue_family="手术同意书/知情同意签署异常",
        manual_issue_text="手术同意书签字人员非授权受托人",
        primary_rule_id="SC-128",
        expected_status="blocked",
        expected_hit_type="blocked",
        target_document_type="知情同意书",
        current_status="blocked",
        notes="blocked：问题文本最贴 SC-128，但本地 PG 中 `surgery_inform_consent/docpat_commu_record/surgery_record/presurg_summary/presurg_discussion` 均无正文，当前无法形成可交付核心锚点。",
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


def _list_recent_seventh_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
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
        if _safe_text(filters.get("source")) != SEVENTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(SEVENTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第七批语义规则回归 batch")
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
    batch_job_ids = _list_recent_seventh_batch_job_ids(workspace)

    rows: list[dict[str, Any]] = []
    observe_count = 0
    blocked_count = 0
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
        if case.current_status == "blocked":
            actual_status = "blocked"
            hit_type = "blocked"
            blocked_count += 1
        elif case.current_status == "observe" and actual_status == "missing":
            actual_status = "not_stored"
            hit_type = "observe"
            observe_count += 1
        else:
            hit_type = case.expected_hit_type
            if case.current_status == "observe":
                observe_count += 1

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
        "core_case_count": 0,
        "observe_case_count": observe_count,
        "blocked_case_count": blocked_count,
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
