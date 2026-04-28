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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "third_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "third_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    _batch_jobs_table,
    _session,
)


TARGET_POOL_NAME = "0426"
SAMPLE_SC_DRAFT_ID = "sc-sample-rule-library"
THIRD_BATCH_RULE_ID_SET = {"SC-026", "SC-008", "SC-033"}
THIRD_BATCH_SOURCE = "manual_problem_sample_pool_third_batch_regression"


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
        case_id="semantic-b3-core-001",
        stage="third_batch",
        record_id="2035546",
        patient_name="张在碧",
        issue_family="首次病程鉴别诊断不足",
        manual_issue_text="入院后首次病程记录中鉴别诊断不全，未结合附件区包块及右下腹痛作完整分析。",
        primary_rule_id="SC-026",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="首次病程记录",
        notes="当前通过 senior/daily fallback + 文本兜底稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b3-core-002",
        stage="third_batch",
        record_id="2068229",
        patient_name="韦庆书",
        issue_family="首次病程鉴别诊断不足",
        manual_issue_text="首次病程仅给出单一诊断，缺少对其他可能病因的鉴别分析。",
        primary_rule_id="SC-026",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="首次病程记录",
        notes="当前通过 senior/daily fallback + 文本兜底稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b3-core-003",
        stage="third_batch",
        record_id="2126353",
        patient_name="傅国辉",
        issue_family="首次病程鉴别诊断不足",
        manual_issue_text="首次病程诊断依据和鉴别诊断过薄，未形成完整推理。",
        primary_rule_id="SC-026",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="首次病程记录",
        notes="当前通过 senior/daily fallback + 文本兜底稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b3-core-004",
        stage="third_batch",
        record_id="2110297",
        patient_name="黄瑞芳",
        issue_family="入院记录主诉不规范/症状不具体",
        manual_issue_text="入院记录主诉过于泛化，仅描述受伤事件和时长，缺少关键症状。",
        primary_rule_id="SC-008",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
        notes="当前由文本兜底稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b3-core-005",
        stage="third_batch",
        record_id="2073404",
        patient_name="王淑琼",
        issue_family="入院记录主诉不规范/症状不具体",
        manual_issue_text="主诉只写跌伤过程，未明确主要症状。",
        primary_rule_id="SC-008",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
        notes="当前由文本兜底稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b3-core-006",
        stage="third_batch",
        record_id="2194387",
        patient_name="蒋明素",
        issue_family="入院记录主诉不规范/症状不具体",
        manual_issue_text="主诉仅写外伤和时长，缺少伴随症状描述。",
        primary_rule_id="SC-008",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="入院记录",
        notes="当前由文本兜底稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b3-core-007",
        stage="third_batch",
        record_id="1880557",
        patient_name="万明春",
        issue_family="日常病程用药/处理未体现",
        manual_issue_text="使用抗菌药物治疗后，病程只写输注反应，未完整体现用药目的及处理计划。",
        primary_rule_id="SC-033",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        notes="当前通过优先命中左氧氟沙星相关病程稳定打出。",
    ),
    MatrixCase(
        case_id="semantic-b3-core-008",
        stage="third_batch",
        record_id="2048454",
        patient_name="郑玉芳",
        issue_family="日常病程用药/处理未体现",
        manual_issue_text="病程仅写复查和密观病情变化，未体现具体用药方案及治疗措施。",
        primary_rule_id="SC-033",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        notes="当前由文本兜底稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b3-observe-001",
        stage="third_batch_observe",
        record_id="2298532",
        patient_name="王德怀",
        issue_family="日常病程用药/处理未体现",
        manual_issue_text="3.27用药病程记录未体现。",
        primary_rule_id="SC-033",
        expected_status="non_compliant",
        expected_hit_type="observe",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="观察位：当前快照文书已多次明确记录头孢唑林、奥美拉唑、补液、白蛋白等治疗，人工锚点与现有病历正文不一致，不再阻塞第三批核心通过率。",
    ),
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_rule_ids(value: Any) -> list[str]:
    result: list[str] = []
    for item in list(value or []):
        text = _safe_text(item).upper()
        if text and text not in result:
            result.append(text)
    return result


def _find_pool_id(service: CustomQCSamplePoolService) -> str:
    result = service.list_pools(page=1, page_size=50, query=TARGET_POOL_NAME)
    for item in list(result.items or []):
        if _safe_text(item.get("name")) == TARGET_POOL_NAME:
            return _safe_text(item.get("id"))
    raise RuntimeError(f"未找到样本池: {TARGET_POOL_NAME}")


def _list_recent_third_batch_job_ids(workspace: CustomQCWorkspaceService) -> list[str]:
    session = _session()
    try:
        table = _batch_jobs_table()
        rows = (
            session.execute(
                select(table.c.id)
                .where(
                    table.c.draft_id == SAMPLE_SC_DRAFT_ID,
                    table.c.status == "completed",
                )
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
        if _safe_text(filters.get("source")) != THIRD_BATCH_SOURCE:
            continue
        rule_ids = {
            _safe_text(item).upper()
            for item in list(filters.get("rule_ids") or [])
            if _safe_text(item)
        }
        if rule_ids and rule_ids.issubset(THIRD_BATCH_RULE_ID_SET):
            result.append(job_id)
    if not result:
        raise RuntimeError("未找到最近的第三批语义规则回归 batch")
    return result


def _get_sample_pool_row(
    service: CustomQCSamplePoolService,
    *,
    pool_id: str,
    record_id: str,
) -> dict[str, Any] | None:
    rows = service.get_runnable_items(
        pool_id=pool_id,
        validation_mode="sc",
        record_ids=[record_id],
    )
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
        if item_record_id == record_id and item_rule_id == _safe_text(rule_id).upper():
            return dict(item)
    return None


def _pick_latest_case_job(
    workspace: CustomQCWorkspaceService,
    *,
    recent_job_ids: list[str],
    record_id: str,
    rule_id: str,
) -> tuple[str, dict[str, Any] | None]:
    normalized_rule_id = _safe_text(rule_id).upper()
    for job_id in recent_job_ids:
        job = workspace.get_batch_job_for_processing(job_id=job_id) or {}
        filters = dict(job.get("filters") or {})
        rule_ids = {
            _safe_text(item).upper()
            for item in list(filters.get("rule_ids") or [])
            if _safe_text(item)
        }
        if normalized_rule_id not in rule_ids:
            continue
        result = _get_job_rule_result(
            workspace,
            job_id=job_id,
            record_id=record_id,
            rule_id=rule_id,
        )
        return job_id, result
    return "", None


def _build_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool_service = CustomQCSamplePoolService()
    workspace = CustomQCWorkspaceService()
    pool_id = _find_pool_id(pool_service)
    recent_job_ids = _list_recent_third_batch_job_ids(workspace)
    rows: list[dict[str, Any]] = []
    summary = {
        "pool_id": pool_id,
        "target_pool_name": TARGET_POOL_NAME,
        "primary_batch_job_ids": recent_job_ids,
        "case_count": len(MATRIX_CASES),
        "core_case_count": 0,
        "observe_case_count": 0,
        "batch_hit_count": 0,
        "batch_miss_count": 0,
        "cases_with_narrowed_primary_rule": 0,
    }
    for case in MATRIX_CASES:
        pool_row = _get_sample_pool_row(pool_service, pool_id=pool_id, record_id=case.record_id) or {}
        candidate_rules = _normalize_rule_ids(pool_row.get("candidate_rule_ids"))
        primary_batch_job_id, primary_batch_result = _pick_latest_case_job(
            workspace,
            recent_job_ids=recent_job_ids,
            record_id=case.record_id,
            rule_id=case.primary_rule_id,
        )
        primary_batch_status = _safe_text((primary_batch_result or {}).get("status")).lower() or "missing"
        batch_hit = primary_batch_status == case.expected_status.lower()
        if case.current_status == "observe":
            summary["observe_case_count"] += 1
        else:
            summary["core_case_count"] += 1
            if batch_hit:
                summary["batch_hit_count"] += 1
            else:
                summary["batch_miss_count"] += 1
        if candidate_rules == [case.primary_rule_id]:
            summary["cases_with_narrowed_primary_rule"] += 1
        rows.append(
            {
                "case_id": case.case_id,
                "stage": case.stage,
                "current_status": case.current_status,
                "record_id": case.record_id,
                "patient_name": case.patient_name,
                "issue_family": case.issue_family,
                "manual_issue_text": case.manual_issue_text,
                "issue_category": _safe_text(pool_row.get("issue_category")),
                "sample_item_id": _safe_text(pool_row.get("id")),
                "coverage_type": _safe_text(pool_row.get("coverage_type")),
                "bundle_status": _safe_text(pool_row.get("bundle_status")),
                "current_candidate_rule_ids": "|".join(candidate_rules),
                "primary_rule_id": case.primary_rule_id,
                "expected_status": case.expected_status,
                "expected_hit_type": case.expected_hit_type,
                "target_document_type": case.target_document_type,
                "primary_batch_job_id": primary_batch_job_id,
                "primary_batch_status": primary_batch_status,
                "primary_batch_target_document_type": _safe_text((primary_batch_result or {}).get("target_document_type")),
                "primary_batch_findings": _safe_text((primary_batch_result or {}).get("findings")),
                "notes": case.notes,
            }
        )
    return rows, summary


def _write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    DEFAULT_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with DEFAULT_OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    DEFAULT_OUTPUT_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    rows, summary = _build_rows()
    _write_outputs(rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
