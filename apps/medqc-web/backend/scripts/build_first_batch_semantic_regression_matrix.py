#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOC_ROOT = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
DEFAULT_OUTPUT_CSV = DOC_ROOT / "first_batch_semantic_regression_matrix.csv"
DEFAULT_OUTPUT_JSON = DOC_ROOT / "first_batch_semantic_regression_matrix.summary.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService


TARGET_POOL_NAME = "0426"
PRIMARY_BATCH_JOB_ID = "d2760286-7714-4c8e-a1c1-2dd92e7e855e"
LEGACY_BATCH_JOB_ID = "58bf98e6-e57d-45b2-9714-5dd3658f9f3e"


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
    contrast_rule_ids: tuple[str, ...] = ()
    target_document_type: str = ""
    current_status: str = "core"
    notes: str = ""


MATRIX_CASES: tuple[MatrixCase, ...] = (
    MatrixCase(
        case_id="semantic-core-001",
        stage="first_batch",
        record_id="2104525",
        patient_name="汪明海",
        issue_family="会诊执行记录缺失/未写执行情况",
        manual_issue_text="12月11日请会诊执行记录不能体现会诊执行情况",
        primary_rule_id="SC-070",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        target_document_type="日常病程记录",
        notes="当前工作区基线下样本池候选规则已收窄到 SC-070，但最近 bundle 修复后的真实 batch 仍未形成稳定命中，需作为重跑优先样本。",
    ),
    MatrixCase(
        case_id="semantic-core-002",
        stage="first_batch",
        record_id="2188335",
        patient_name="黄显秀",
        issue_family="会诊意见已写遵执但实际未落实",
        manual_issue_text="1月23日康复科会诊建议给予针灸、低频、中药贴敷、关节松动术、偏瘫肢体综合训练、肌力训练等康复治疗以舒经通络、滑利关节。请会诊执行记录中书写遵会诊意见。但实际并未按照会诊意见执行。",
        primary_rule_id="SC-070",
        expected_status="non_compliant",
        expected_hit_type="same_family_hit",
        contrast_rule_ids=("LX-016",),
        target_document_type="日常病程记录",
        notes="主规则用 SC-070；LX-016 仅保留为对照，不纳入首轮样本验证白名单。",
    ),
    MatrixCase(
        case_id="semantic-core-003",
        stage="first_batch",
        record_id="2083787",
        patient_name="付学云",
        issue_family="上级查房内容空洞/复制粘贴/身份异常",
        manual_issue_text="2025.11.18田安琴主治医师查房记录无内容；11月17日及11月18日，无输血前评估、无输血记录、无输血后评估。",
        primary_rule_id="SC-050",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        contrast_rule_ids=("SC-049", "SC-052"),
        target_document_type="上级查房记录",
        notes="这条是第一批查房内容问题的稳定锚点样本，优先用于验证 SC-050。",
    ),
    MatrixCase(
        case_id="semantic-core-004",
        stage="first_batch",
        record_id="2246915",
        patient_name="黄金莲",
        issue_family="病程记录缺分析/缺处理意见",
        manual_issue_text="患者行经阴道子宫切除术，术前无尿路感染，术后诊断尿路感染。未请泌尿外科会诊，未分析原因。",
        primary_rule_id="SC-036",
        expected_status="non_compliant",
        expected_hit_type="exact_hit",
        contrast_rule_ids=("SC-033", "SC-032"),
        target_document_type="日常病程记录",
        notes="作为 SC-036 的 exact-hit 基线样本保留；最近 bundle 修复后的正式 batch 尚未覆盖到这条。",
    ),
    MatrixCase(
        case_id="semantic-core-005",
        stage="first_batch",
        record_id="2311318",
        patient_name="范永勤",
        issue_family="病程记录缺分析/缺处理意见",
        manual_issue_text="4.7检验结果肾功异常，病程记录未分析，未请相应科室会诊",
        primary_rule_id="SC-036",
        expected_status="non_compliant",
        expected_hit_type="same_family_hit",
        contrast_rule_ids=("SC-033", "SC-032"),
        target_document_type="日常病程记录",
        notes="当前稳定命中证据是 ESR/PCT/CRP，而不是原题里的 UA 381μmol/L，回归时必须显式标为 same_family_hit。",
    ),
    MatrixCase(
        case_id="semantic-observe-001",
        stage="second_batch_candidate",
        record_id="2207717",
        patient_name="邹才林",
        issue_family="上级查房内容空洞/复制粘贴/身份异常",
        manual_issue_text="2月4日副主任医师查房记录与2月3日主治医师查房记录复制粘贴严重（相识度100%）",
        primary_rule_id="SC-050",
        expected_status="non_compliant",
        expected_hit_type="miss",
        contrast_rule_ids=("SC-049", "SC-052"),
        target_document_type="上级查房记录",
        current_status="observe",
        notes="这条更适合作为第二批“复制粘贴/高度重复”专项规则的观察样本，当前不纳入首轮稳定回归通过口径。",
    ),
)


def _normalize_rule_ids(value: Any) -> list[str]:
    result: list[str] = []
    for item in list(value or []):
        text = str(item or "").strip().upper()
        if text and text not in result:
            result.append(text)
    return result


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _find_pool_id(service: CustomQCSamplePoolService) -> str:
    result = service.list_pools(page=1, page_size=50, query=TARGET_POOL_NAME)
    for item in list(result.items or []):
        if _safe_text(item.get("name")) == TARGET_POOL_NAME:
            return _safe_text(item.get("id"))
    raise RuntimeError(f"未找到样本池: {TARGET_POOL_NAME}")


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
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    if not job:
        return None
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
    rows: list[dict[str, Any]] = []
    summary = {
        "pool_id": pool_id,
        "target_pool_name": TARGET_POOL_NAME,
        "primary_batch_job_id": PRIMARY_BATCH_JOB_ID,
        "legacy_batch_job_id": LEGACY_BATCH_JOB_ID,
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
        primary_batch_result = _get_job_rule_result(
            workspace,
            job_id=PRIMARY_BATCH_JOB_ID,
            record_id=case.record_id,
            rule_id=case.primary_rule_id,
        )
        legacy_batch_result = _get_job_rule_result(
            workspace,
            job_id=LEGACY_BATCH_JOB_ID,
            record_id=case.record_id,
            rule_id=case.primary_rule_id,
        )
        primary_batch_status = _safe_text((primary_batch_result or {}).get("status")).lower()
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
                "contrast_rule_ids": "|".join(case.contrast_rule_ids),
                "expected_status": case.expected_status,
                "expected_hit_type": case.expected_hit_type,
                "target_document_type": case.target_document_type,
                "primary_batch_job_id": PRIMARY_BATCH_JOB_ID,
                "primary_batch_status": primary_batch_status or "missing",
                "primary_batch_target_document_type": _safe_text((primary_batch_result or {}).get("target_document_type")),
                "primary_batch_findings": _safe_text((primary_batch_result or {}).get("findings")),
                "legacy_batch_job_id": LEGACY_BATCH_JOB_ID,
                "legacy_batch_status": _safe_text((legacy_batch_result or {}).get("status")).lower() or "missing",
                "legacy_batch_target_document_type": _safe_text((legacy_batch_result or {}).get("target_document_type")),
                "legacy_batch_findings": _safe_text((legacy_batch_result or {}).get("findings")),
                "notes": case.notes,
            }
        )
    return rows, summary


def _write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(summary: dict[str, Any], rows: list[dict[str, Any]], output_path: Path) -> None:
    payload = {
        **summary,
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    rows, summary = _build_rows()
    _write_csv(rows, DEFAULT_OUTPUT_CSV)
    _write_json(summary, rows, DEFAULT_OUTPUT_JSON)
    print(
        json.dumps(
            {
                **summary,
                "output_csv": str(DEFAULT_OUTPUT_CSV),
                "output_json": str(DEFAULT_OUTPUT_JSON),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
