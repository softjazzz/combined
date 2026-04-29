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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "fifteenth_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "fifteenth_batch_semantic_regression_matrix.summary.json"
DEFAULT_OUTPUT_XLSX = DOC_ROOT / "fifteenth_batch_semantic_regression_matrix.xlsx"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session
from matrix_xlsx_utils import write_matrix_xlsx


SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
FIFTEENTH_BATCH_RULE_ID_SET = {"SC-062", "SC-065", "SC-071", "SC-072", "SC-086", "SC-117", "SC-128"}
FIFTEENTH_BATCH_SOURCE = "manual_problem_sample_pool_fifteenth_batch_regression"


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
        case_id="semantic-b15-core-001",
        stage="fifteenth_batch",
        record_id="2255288",
        patient_name="王树成",
        issue_family="会诊记录时效",
        manual_issue_text="2026-3-4 8:28 书写呼吸科会诊记录，时间节点早于呼吸科会诊接收时间。",
        primary_rule_id="SC-071",
        expected_status="non_compliant",
        expected_hit_type="same_family_hit",
        target_document_type="会诊记录",
    ),
    MatrixCase(
        case_id="semantic-b15-core-002",
        stage="fifteenth_batch",
        record_id="2312534",
        patient_name="陈桂钦",
        issue_family="急会诊记录时效",
        manual_issue_text="4.1会诊记录未书写，病程记录未在规定时间内完成。",
        primary_rule_id="SC-072",
        expected_status="non_compliant",
        expected_hit_type="same_family_hit",
        target_document_type="会诊记录",
    ),
    MatrixCase(
        case_id="semantic-b15-obs-001",
        stage="fifteenth_batch",
        record_id="2017327",
        patient_name="余廷久",
        issue_family="住院超30天阶段小结/讨论缺失",
        manual_issue_text="患者住院超30天，未见住院超30天讨论记录及阶段小结。",
        primary_rule_id="SC-065",
        expected_status="compliant",
        expected_hit_type="miss",
        target_document_type="阶段小结",
        current_status="observe",
        notes="当前快照仅有阶段小结空壳，最新 batch 仍返回 compliant，继续保留观察位。",
    ),
    MatrixCase(
        case_id="semantic-b15-obs-002",
        stage="fifteenth_batch",
        record_id="2199041",
        patient_name="陈锡芬",
        issue_family="出院记录时效异常",
        manual_issue_text="患者2月2日出院，新建出院记录后未在24小时内完成出院记录。",
        primary_rule_id="SC-117",
        expected_status="compliant",
        expected_hit_type="miss",
        target_document_type="出院记录",
        current_status="observe",
        notes="当前出院记录正文仍空，最新 batch 返回 compliant，继续保留观察位。",
    ),
    MatrixCase(
        case_id="semantic-b15-obs-003",
        stage="fifteenth_batch",
        record_id="2199396",
        patient_name="王生明",
        issue_family="术前主刀医生查房/麻醉术前访视缺失",
        manual_issue_text="患者2月4日手术，无术前主刀医师查房记录，无术后首次病程记录及手术记录。",
        primary_rule_id="SC-086",
        expected_status="compliant",
        expected_hit_type="miss",
        target_document_type="术前小结/上级查房记录",
        current_status="observe",
        notes="当前证据仍不足以稳定判缺陷，先保留观察位。",
    ),
    MatrixCase(
        case_id="semantic-b15-obs-004",
        stage="fifteenth_batch",
        record_id="1962806",
        patient_name="钟星文",
        issue_family="交接班记录缺失/缺项",
        manual_issue_text="管床医生发生变更未书写交接班记录。",
        primary_rule_id="SC-062",
        expected_status="compliant",
        expected_hit_type="miss",
        target_document_type="交接班记录",
        current_status="observe",
        notes="本地 PG 与快照均无交接班正文，最新 batch 仍返回 compliant，继续保留观察位。",
    ),
    MatrixCase(
        case_id="semantic-b15-skip-001",
        stage="fifteenth_batch",
        record_id="1931889",
        patient_name="刘佳钦",
        issue_family="手术同意书/知情同意签署异常",
        manual_issue_text="手术同意书签字人员非授权受托人。",
        primary_rule_id="SC-128",
        expected_status="compliant",
        expected_hit_type="miss",
        target_document_type="知情同意书",
        current_status="skip",
        notes="本地 PG 与 0426 快照均缺知情同意正文；当前 batch 返回 compliant 不作为有效验证，维持 blocked/skip。",
    ),
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _list_recent_fifteenth_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
    session = _session()
    try:
        table = _batch_jobs_table()
        rows = (
            session.execute(
                select(table.c.id)
                .where(table.c.draft_id == SAMPLE_SC_DRAFT_ID, table.c.status == "completed")
                .order_by(desc(table.c.created_at))
                .limit(40)
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
        if _safe_text(filters.get("source")) != FIFTEENTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(FIFTEENTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第十五批语义规则回归 batch")
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
    batch_job_ids = _list_recent_fifteenth_batch_job_ids(workspace)
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
        elif case.current_status == "observe" and actual_status == case.expected_status:
            observe_hits += 1
        elif case.current_status == "observe":
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
                "expected_hit_type": case.expected_hit_type,
                "actual_hit_type": hit_type,
                "target_document_type": case.target_document_type,
                "current_status": case.current_status,
                "notes": case.notes,
                "batch_job_id": latest_job_id,
            }
        )

    summary = {
        "primary_batch_job_ids": [latest_job_id],
        "reference_batch_job_ids": batch_job_ids[1:],
        "case_count": len(MATRIX_CASES),
        "core_case_count": sum(1 for item in MATRIX_CASES if item.current_status == "core"),
        "observe_case_count": sum(1 for item in MATRIX_CASES if item.current_status == "observe"),
        "skip_case_count": sum(1 for item in MATRIX_CASES if item.current_status == "skip"),
        "batch_hit_count": core_hits,
        "batch_miss_count": core_misses,
        "observe_hit_count": observe_hits,
        "observe_miss_count": observe_misses,
    }
    return rows, summary


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    rows, summary = _build_rows()
    fieldnames = [
        "case_id",
        "stage",
        "record_id",
        "patient_name",
        "issue_family",
        "manual_issue_text",
        "primary_rule_id",
        "expected_status",
        "actual_status",
        "expected_hit_type",
        "actual_hit_type",
        "target_document_type",
        "current_status",
        "notes",
        "batch_job_id",
    ]
    _write_csv(DEFAULT_OUTPUT_CSV, rows, fieldnames)
    write_matrix_xlsx(DEFAULT_OUTPUT_XLSX, rows, fieldnames)
    DEFAULT_OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
