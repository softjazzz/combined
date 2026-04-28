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
DEFAULT_OUTPUT_CSV = DOC_ROOT / "second_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "second_batch_semantic_regression_matrix.summary.json"

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
SECOND_BATCH_RULE_ID_SET = {"SC-039", "SC-069", "SC-146"}
SECOND_BATCH_SOURCE = "manual_problem_sample_pool_second_batch_regression"


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
        case_id="semantic-b2-core-001",
        stage="second_batch",
        record_id="2327691",
        patient_name="邹世科",
        issue_family="会诊记录内容质量/复制粘贴/结论不足",
        manual_issue_text="2026年2月4日会诊记录中存在大量复制其他科室会诊意见的情况，并无综合会诊结果提出建设性诊疗意见。",
        primary_rule_id="SC-069",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="会诊记录",
        notes="第二批 SC-069 精确锚点。当前批次已切到 standard + record_rule_map，但最新基线仍未命中。",
    ),
    MatrixCase(
        case_id="semantic-b2-core-002",
        stage="second_batch",
        record_id="2304958",
        patient_name="陈桂芳",
        issue_family="危急值记录不完整/处理不充分",
        manual_issue_text="2026年3月11日危急值处理记录尽描写“ 2026-03-11 电解质3:K 2.76mmol/l,行静脉补钾。”未描述危急值报告、处置时间及具体补钾情况",
        primary_rule_id="SC-039",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        notes="第二批 SC-039 锚点之一。当前样本验证链路已修复串扰，但该样本仍未稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b2-core-003",
        stage="second_batch",
        record_id="1962757",
        patient_name="张敦满",
        issue_family="危急值记录不完整/处理不充分",
        manual_issue_text="9月15日及9月16日，危急值处理记录不规范，仅记录：K 1.68mmol/l、K 2.05mmol/l,无其它内容。",
        primary_rule_id="SC-039",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        notes="第二批 SC-039 锚点之二。当前这条仍会触发 bundle 标准评估回退，需要继续排 evidence/prompt。",
    ),
    MatrixCase(
        case_id="semantic-b2-core-004",
        stage="second_batch",
        record_id="2212522",
        patient_name="熊良钦",
        issue_family="诊疗医嘱与病程记录不一致",
        manual_issue_text="在术前小结及术前讨论之前，已经下达手术医嘱。",
        primary_rule_id="SC-146",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        notes="第二批 SC-146 当前已在最新硅基流动基线中稳定命中。",
    ),
    MatrixCase(
        case_id="semantic-b2-observe-001",
        stage="second_batch_observe",
        record_id="2104927",
        patient_name="温远明",
        issue_family="诊疗医嘱与病程记录不一致",
        manual_issue_text="12月4日日常病程记录内容不全仅描述“停心电监护，复查头颅CT。继续目前治疗方案。”未描写患者情况及停医嘱原因。",
        primary_rule_id="SC-146",
        expected_status="non_compliant",
        expected_hit_type="observe",
        target_document_type="日常病程记录",
        current_status="observe",
        notes="当前仍被分类到 daily_course_analysis/SC-036，需决定是否拆分成 SC-146 子口径。",
    ),
    MatrixCase(
        case_id="semantic-b2-observe-002",
        stage="second_batch_observe",
        record_id="2324802",
        patient_name="颜友芳",
        issue_family="会诊记录内容质量/结论不足",
        manual_issue_text="会诊记录意见为定期复查血常规、血凝、DIC、大便隐血（未明确具体复查时间），请会诊执行记录中描述准会诊意见执行，但实际会诊7天后均未进行复查。",
        primary_rule_id="SC-069",
        expected_status="non_compliant",
        expected_hit_type="observe",
        target_document_type="会诊记录",
        current_status="observe",
        notes="混合了 SC-069 与 SC-070 的边界，目前仍保留为会诊执行样本观察项。",
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


def _find_latest_second_batch_job_id(workspace: CustomQCWorkspaceService) -> str:
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

    for row in rows:
        job_id = _safe_text(row.get("id"))
        if not job_id:
            continue
        job = workspace.get_batch_job_for_processing(job_id=job_id) or {}
        filters = dict(job.get("filters") or {})
        if _safe_text(filters.get("source")) != SECOND_BATCH_SOURCE:
            continue
        rule_ids = {
            _safe_text(item).upper()
            for item in list(filters.get("rule_ids") or [])
            if _safe_text(item)
        }
        if rule_ids == SECOND_BATCH_RULE_ID_SET:
            return job_id
    raise RuntimeError("未找到最近的第二批语义规则回归 batch")


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


def _build_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool_service = CustomQCSamplePoolService()
    workspace = CustomQCWorkspaceService()
    pool_id = _find_pool_id(pool_service)
    primary_batch_job_id = _find_latest_second_batch_job_id(workspace)
    job = workspace.get_batch_job_for_processing(job_id=primary_batch_job_id) or {}
    job_filters = dict(job.get("filters") or {})
    rows: list[dict[str, Any]] = []
    summary = {
        "pool_id": pool_id,
        "target_pool_name": TARGET_POOL_NAME,
        "primary_batch_job_id": primary_batch_job_id,
        "case_count": len(MATRIX_CASES),
        "core_case_count": 0,
        "observe_case_count": 0,
        "batch_hit_count": 0,
        "batch_miss_count": 0,
        "cases_with_narrowed_primary_rule": 0,
        "execution_strategy": _safe_text(job_filters.get("execution_strategy")),
    }
    for case in MATRIX_CASES:
        pool_row = _get_sample_pool_row(pool_service, pool_id=pool_id, record_id=case.record_id) or {}
        candidate_rules = _normalize_rule_ids(pool_row.get("candidate_rule_ids"))
        primary_batch_result = _get_job_rule_result(
            workspace,
            job_id=primary_batch_job_id,
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
