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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "thirteenth_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "thirteenth_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session


SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
THIRTEENTH_BATCH_RULE_ID_SET = {"SC-009", "SC-011", "SC-065", "SC-074", "SC-117"}
THIRTEENTH_BATCH_SOURCE = "manual_problem_sample_pool_thirteenth_batch_regression"


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
        case_id="semantic-b13-core-001",
        stage="thirteenth_batch",
        record_id="2329756",
        patient_name="杜忠海",
        issue_family="输血记录链缺失/不全",
        manual_issue_text="未及时书写输血后评价记录（9月13日输血，9月17日未进行输血后评价。）",
        primary_rule_id="SC-074",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 uncertain，先保留为 SC-074 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b13-core-002",
        stage="thirteenth_batch",
        record_id="2213639",
        patient_name="杜卫红",
        issue_family="输血时间/量/前后记录不一致",
        manual_issue_text="患者2月6日共输注两袋血浆，但输血记录未分别记录输血开始时间及结束时间",
        primary_rule_id="SC-074",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
    ),
    MatrixCase(
        case_id="semantic-b13-core-003",
        stage="thirteenth_batch",
        record_id="1915821",
        patient_name="魏治伦",
        issue_family="现病史记录不全或描述不清",
        manual_issue_text="现病史中主诉有咽痛，但未详细记录疼痛的性质、持续时间、是否有缓解方式等；诉有咳痰，未记录痰液的性状、咳痰的频率、是否有伴随症状等；未记录在当地卫生院具体的治疗情况；未记录在我院门诊的检查项目及结果；无体重变化情况的记录。",
        primary_rule_id="SC-009",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
    ),
    MatrixCase(
        case_id="semantic-b13-core-004",
        stage="thirteenth_batch",
        record_id="2305194",
        patient_name="杨琼芳",
        issue_family="现病史记录不全或描述不清",
        manual_issue_text="患者为肾功能不全患者，入院记录，现病史中未描述小便情况。",
        primary_rule_id="SC-009",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
    ),
    MatrixCase(
        case_id="semantic-b13-core-005",
        stage="thirteenth_batch",
        record_id="2236769",
        patient_name="唐登森",
        issue_family="阴性/阳性症状缺失",
        manual_issue_text="现病史中患者既往十年只有主要症状，无伴随症状及阴性症状。患者长期治疗慢性病的用药情况未记录。",
        primary_rule_id="SC-011",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
    ),
    MatrixCase(
        case_id="semantic-b13-obs-001",
        stage="thirteenth_batch",
        record_id="2024757",
        patient_name="游得利",
        issue_family="现病史记录不全或描述不清",
        manual_issue_text="现病史未描述疼痛性质、持续时间、缓解方式等，既往史未询问出患者既往有肺结核病史。",
        primary_rule_id="SC-009",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
        current_status="observe",
        notes="当前最新 batch 下仍判定为 compliant，继续保留为 SC-009 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b13-obs-002",
        stage="thirteenth_batch",
        record_id="2017327",
        patient_name="余廷久",
        issue_family="住院超30天阶段小结/讨论缺失",
        manual_issue_text="患者住院超30天，未见住院超30天讨论记录及阶段小结。",
        primary_rule_id="SC-065",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="阶段小结",
        current_status="observe",
        notes="当前最新 batch 下未稳定打出缺陷，先保留为 SC-065 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b13-obs-003",
        stage="thirteenth_batch",
        record_id="2199041",
        patient_name="陈锡芬",
        issue_family="出院记录时效异常",
        manual_issue_text="患者2月2日出院，新建出院记录后未在24小时内完成出院记录",
        primary_rule_id="SC-117",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="出院记录",
        current_status="observe",
        notes="当前最新 batch 下未稳定打出缺陷，先保留为 SC-117 观察位。",
    ),
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _list_recent_thirteenth_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
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
        if _safe_text(filters.get("source")) != THIRTEENTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(THIRTEENTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第十三批语义规则回归 batch")
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
    batch_job_ids = _list_recent_thirteenth_batch_job_ids(workspace)
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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    rows, summary = _build_rows()
    _write_csv(DEFAULT_OUTPUT_CSV, rows)
    DEFAULT_OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
