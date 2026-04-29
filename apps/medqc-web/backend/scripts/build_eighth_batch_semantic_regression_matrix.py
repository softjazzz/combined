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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "eighth_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "eighth_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table, _session


TARGET_POOL_NAME = "0426"
SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
EIGHTH_BATCH_RULE_ID_SET = {"SC-009", "SC-011", "SC-012", "SC-018", "SC-019", "SC-020", "SC-025"}
EIGHTH_BATCH_SOURCE = "manual_problem_sample_pool_eighth_batch_regression"


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
        case_id="semantic-b8-core-001",
        stage="eighth_batch",
        record_id="1891128",
        patient_name="徐朝华",
        issue_family="入院记录体格检查/专科检查缺项",
        manual_issue_text="入院记录中无专科检查",
        primary_rule_id="SC-018",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
    ),
    MatrixCase(
        case_id="semantic-b8-core-002",
        stage="eighth_batch",
        record_id="2024757",
        patient_name="游德利",
        issue_family="现病史记录不全或描述不清",
        manual_issue_text="现病史未描述疼痛性质、持续时间、缓解方式等，既往史未询问出患者既往有肺结核病史。",
        primary_rule_id="SC-009",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，说明该样本更适合作为 SC-009 观察位，待后续补更强锚点。",
    ),
    MatrixCase(
        case_id="semantic-b8-core-003",
        stage="eighth_batch",
        record_id="2023362",
        patient_name="程天金",
        issue_family="阴性/阳性症状缺失",
        manual_issue_text="首次病程记录鉴别诊断不全面，患者既往有糖尿病史，入院诊断未诊断该疾病。现病史阴性症状采集不全面，不能支撑鉴别诊断。",
        primary_rule_id="SC-011",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
        current_status="observe",
        notes="问题文本混合了 admission 与 first_course 语义；当前样本池候选规则已更偏向 SC-026，不再作为 SC-011 核心锚点。",
    ),
    MatrixCase(
        case_id="semantic-b8-core-004",
        stage="eighth_batch",
        record_id="1915821",
        patient_name="魏治伦",
        issue_family="诊治经过记录不全",
        manual_issue_text="现病史中主诉有咽痛，但未详细记录疼痛的性质、持续时间、是否有缓解方式等；诉有咳痰，未记录痰液的性状、咳痰的频率、是否有伴随症状等；未记录在当地卫生院具体的治疗情况；未记录在我院门诊的检查项目及结果；无体重变化情况的记录。",
        primary_rule_id="SC-012",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
    ),
    MatrixCase(
        case_id="semantic-b8-core-005",
        stage="eighth_batch",
        record_id="2199041",
        patient_name="陈锡芬",
        issue_family="辅助检查记录不完善/不准确",
        manual_issue_text="入院记录中“院外辅助检查”写为“院内辅助检查”",
        primary_rule_id="SC-019",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
        current_status="observe",
        notes="当前最新 batch 下判定为 compliant，先保留为 SC-019 观察位，待后续补更强锚点。",
    ),
    MatrixCase(
        case_id="semantic-b8-core-006",
        stage="eighth_batch",
        record_id="2208257",
        patient_name="万先富",
        issue_family="入院诊断遗漏/顺序错误",
        manual_issue_text="患者既往有高血压病史，入院诊断未诊断高血压，医嘱中未体现高血压用药情况，患者既往行“左侧腹股沟疝修补术”，体格检查无相关描述；2025.11.11行“超声引导下左肾穿刺活检术”，未书写有创操作记录。",
        primary_rule_id="SC-020",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
    ),
    MatrixCase(
        case_id="semantic-b8-core-007",
        stage="eighth_batch",
        record_id="1919190",
        patient_name="潘泗澄",
        issue_family="首次病程缺诊断依据/鉴别诊断/计划",
        manual_issue_text="首次病程中只有主诊断有诊断依据及鉴别诊断，其余诊断均未书写诊断依据及鉴别诊断",
        primary_rule_id="SC-025",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="首次病程记录",
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


def _list_recent_eighth_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
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
        if _safe_text(filters.get("source")) != EIGHTH_BATCH_SOURCE:
            continue
        rule_ids = {_safe_text(item).upper() for item in list(filters.get("rule_ids") or []) if _safe_text(item)}
        if rule_ids and rule_ids.issubset(EIGHTH_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第八批语义规则回归 batch")
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
    batch_job_ids = _list_recent_eighth_batch_job_ids(workspace)
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
        actual_job_id = latest_job_id
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
                "actual_job_id": actual_job_id,
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
