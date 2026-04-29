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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "twelfth_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "twelfth_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session


SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
TWELFTH_BATCH_RULE_ID_SET = {"SC-068", "SC-080"}
TWELFTH_BATCH_SOURCE = "manual_problem_sample_pool_twelfth_batch_regression"


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
        case_id="semantic-b12-core-001",
        stage="twelfth_batch",
        record_id="2169426",
        patient_name="李健",
        issue_family="申请会诊记录未按规定书写",
        manual_issue_text="入院诊断中反流性食管炎、甲亢、慢性胃炎、肺气肿。无诊断依据。会诊申请中，仅描述转氨酶、胆红素升高，建议详细描述。",
        primary_rule_id="SC-068",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="会诊记录",
    ),
    MatrixCase(
        case_id="semantic-b12-core-002",
        stage="twelfth_batch",
        record_id="2027741",
        patient_name="朱永枝",
        issue_family="术前小结缺失",
        manual_issue_text="患者10月15日行肾动脉栓塞术肾动脉造影术，术后手术记录有缺项。缺术后首次病程记录，缺术前小结。",
        primary_rule_id="SC-080",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前小结",
    ),
    MatrixCase(
        case_id="semantic-b12-core-003",
        stage="twelfth_batch",
        record_id="2236078",
        patient_name="文兴全",
        issue_family="术前小结缺失",
        manual_issue_text="手术患者缺术前小结、术前讨论及术后连续三天查房记录（包含术后第一天术者查房记录）",
        primary_rule_id="SC-080",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前小结",
    ),
    MatrixCase(
        case_id="semantic-b12-core-004",
        stage="twelfth_batch",
        record_id="2305896",
        patient_name="古洪禄",
        issue_family="术前小结缺失",
        manual_issue_text="术前小结、术前讨论新建后未书写",
        primary_rule_id="SC-080",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前小结",
    ),
    MatrixCase(
        case_id="semantic-b12-obs-001",
        stage="twelfth_batch",
        record_id="1874568",
        patient_name="许敬华",
        issue_family="术前小结缺失",
        manual_issue_text="无术前小结",
        primary_rule_id="SC-080",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前小结",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，先保留为 SC-080 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b12-obs-002",
        stage="twelfth_batch",
        record_id="2218096",
        patient_name="张厚易",
        issue_family="术前小结缺失",
        manual_issue_text="患者在静脉麻醉下行前庭大腺囊肿造口术，无术前小结及手术记录。",
        primary_rule_id="SC-080",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前小结",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，先保留为 SC-080 观察位。",
    ),
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _list_recent_twelfth_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
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
        if _safe_text(filters.get("source")) != TWELFTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(TWELFTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第十二批语义规则回归 batch")
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
    batch_job_ids = _list_recent_twelfth_batch_job_ids(workspace)
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
