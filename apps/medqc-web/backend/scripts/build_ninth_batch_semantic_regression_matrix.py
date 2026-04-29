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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "ninth_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "ninth_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session


TARGET_POOL_NAME = "0426"
SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
NINTH_BATCH_RULE_ID_SET = {"SC-032", "SC-083"}
NINTH_BATCH_SOURCE = "manual_problem_sample_pool_ninth_batch_regression"


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
        case_id="semantic-b9-core-001",
        stage="ninth_batch",
        record_id="2104927",
        patient_name="温远明",
        issue_family="病程记录病情变化记录不全",
        manual_issue_text="12月4日日常病程记录内容不全仅描述“停心电监护，复查头颅CT。继续目前治疗方案。”未描写患者情况及停医嘱原因。",
        primary_rule_id="SC-032",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，说明该样本更适合作为 SC-032 观察位，待后续补更强锚点。",
    ),
    MatrixCase(
        case_id="semantic-b9-core-002",
        stage="ninth_batch",
        record_id="2110349",
        patient_name="古洪忠",
        issue_family="病程记录病情变化记录不全",
        manual_issue_text="2025.11.20病程记录缺患者病情变化、目前症状、体征、阳性检查检验结果。仅记录抽取血常规、电解质的目的。",
        primary_rule_id="SC-032",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，说明该样本更适合作为 SC-032 观察位，待后续补更强锚点。",
    ),
    MatrixCase(
        case_id="semantic-b9-core-003",
        stage="ninth_batch",
        record_id="2037363",
        patient_name="郑国荣",
        issue_family="病程记录病情变化记录不全",
        manual_issue_text="10月29日日常病程记录后无病程，书写不及时，且病历内容书写过于简略，对患者病情、查体情况、诊疗情况未明确说明。",
        primary_rule_id="SC-032",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前最新 batch 未稳定打出缺陷，先保留为 SC-032 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b9-core-004",
        stage="ninth_batch",
        record_id="2209876",
        patient_name="朱成明",
        issue_family="病程记录病情变化记录不全",
        manual_issue_text="2月4日、2月5日连续两次病程记录新建后未书写",
        primary_rule_id="SC-032",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前最新 batch 未稳定打出缺陷，先保留为 SC-032 观察位。",
    ),
    MatrixCase(
        case_id="semantic-b9-core-005",
        stage="ninth_batch",
        record_id="2104341",
        patient_name="代亚军",
        issue_family="四级手术未MDT",
        manual_issue_text="四级手术无多学科讨论记录",
        primary_rule_id="SC-083",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前讨论",
    ),
    MatrixCase(
        case_id="semantic-b9-core-006",
        stage="ninth_batch",
        record_id="2107085",
        patient_name="游国明",
        issue_family="四级手术未MDT",
        manual_issue_text="四级手术无多学科讨论记录",
        primary_rule_id="SC-083",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前讨论",
    ),
    MatrixCase(
        case_id="semantic-b9-core-007",
        stage="ninth_batch",
        record_id="2198921",
        patient_name="王明德",
        issue_family="四级手术未MDT",
        manual_issue_text="患者行腹腔镜下直肠前切除术，国考四级手术术前无多学科会诊。",
        primary_rule_id="SC-083",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前讨论",
    ),
    MatrixCase(
        case_id="semantic-b9-core-008",
        stage="ninth_batch",
        record_id="2213827",
        patient_name="熊明英",
        issue_family="四级手术未MDT",
        manual_issue_text="国考四级手术术前无多学科会诊。",
        primary_rule_id="SC-083",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前讨论",
    ),
    MatrixCase(
        case_id="semantic-b9-core-009",
        stage="ninth_batch",
        record_id="2278814",
        patient_name="任刚",
        issue_family="四级手术未MDT",
        manual_issue_text="四级肿瘤手术，多学科会诊不能代替MDT",
        primary_rule_id="SC-083",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="术前讨论",
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


def _list_recent_ninth_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
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
        if _safe_text(filters.get("source")) != NINTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(NINTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第九批语义规则回归 batch")
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
    batch_job_ids = _list_recent_ninth_batch_job_ids(workspace)
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
    narrowed = 0

    for case in MATRIX_CASES:
        sample_row = _get_sample_pool_row(pool_service, pool_id=pool_id, record_id=case.record_id) or {}
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
                "actual_job_id": latest_job_id,
                "findings": _safe_text((actual_result or {}).get("findings"))[:200],
                "evidence": _safe_text((actual_result or {}).get("evidence"))[:200],
                "notes": case.notes,
            }
        )

    summary = {
        "pool_id": pool_id,
        "target_pool_name": TARGET_POOL_NAME,
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
