#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = BACKEND_ROOT.parent
DEFAULT_LEDGER_CSV = WEB_ROOT / "docs" / "0418" / "QC" / "sheet2_verification_ledger_seed.csv"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.routers.qc_sample_pools import _resolve_sample_validation_execution_strategy
from app.routers.qc_sichuan import _run_sichuan_workspace_batch_job
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.sample_validation_rule_sets import (
    SAMPLE_PROGRAMMATIC_RULE_IDS,
    get_sample_programmatic_rule_set,
    resolve_sample_validation_pseudo_draft,
)

PROGRAMMATIC_RULE_ID_SET = {
    str(rule_id).strip().upper()
    for rule_id in SAMPLE_PROGRAMMATIC_RULE_IDS
    if str(rule_id).strip()
}
LEDGER_RESULT_COLUMNS = (
    "verification_status",
    "job_id",
    "evidence_status",
    "evidence_summary",
    "next_action",
)
PENDING_STATUS_SET = {"", "pending", "queued"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 issue_family 逐条运行 Sheet2 主规则核验")
    parser.add_argument(
        "--ledger-csv",
        default=str(DEFAULT_LEDGER_CSV),
        help="ledger CSV 路径，默认使用 docs/0418/QC/sheet2_verification_ledger_seed.csv",
    )
    parser.add_argument(
        "--issue-family",
        dest="issue_families",
        action="append",
        default=[],
        help="按问题族过滤，可重复传入；支持整列值或分号拆分后的单个 issue_family",
    )
    parser.add_argument(
        "--created-by",
        default="sheet2_issue_family_verification",
        help="批量任务 created_by 标识",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多处理多少条匹配记录，0 表示不限制",
    )
    parser.add_argument(
        "--include-non-pending",
        action="store_true",
        help="默认仅处理 verification_status 为空/pending/queued 的记录；传入后允许重跑已处理记录",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="可选，输出执行摘要 JSON",
    )
    return parser.parse_args()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _split_issue_families(value: str) -> list[str]:
    parts = [value or ""]
    for sep in ("；", ";"):
        expanded: list[str] = []
        for item in parts:
            expanded.extend(item.split(sep))
        parts = expanded
    return [part.strip() for part in parts if part and part.strip()]


def _normalize_issue_family_token(value: str) -> str:
    return _safe_text(value).casefold()


def _row_matches_issue_family(row_issue_family: str, selected_issue_families: list[str]) -> bool:
    if not selected_issue_families:
        return True
    row_tokens = {
        _normalize_issue_family_token(row_issue_family),
        *(_normalize_issue_family_token(item) for item in _split_issue_families(row_issue_family)),
    }
    row_tokens.discard("")
    selected_tokens = {_normalize_issue_family_token(item) for item in selected_issue_families if _safe_text(item)}
    return bool(row_tokens & selected_tokens)


def _normalize_fieldnames(fieldnames: list[str] | None) -> list[str]:
    normalized = list(fieldnames or [])
    for column in LEDGER_RESULT_COLUMNS:
        if column not in normalized:
            normalized.append(column)
    return normalized


def _read_ledger_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = _normalize_fieldnames(reader.fieldnames)
        rows = []
        for row in reader:
            normalized = {name: _safe_text(row.get(name)) for name in fieldnames}
            rows.append(normalized)
        return fieldnames, rows


def _write_ledger_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _truncate(text: Any, limit: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 3)].rstrip("，,。；; ") + "..."


def _normalize_rule_id(rule_id: str) -> str:
    return _safe_text(rule_id).upper()


def _status_for(job: dict[str, Any], *, record_id: str, rule_id: str) -> dict[str, Any] | None:
    normalized_record_id = _safe_text(record_id)
    normalized_rule_id = _normalize_rule_id(rule_id)
    for item in list(job.get("items") or []):
        item_record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
        item_rule_id = _normalize_rule_id(item.get("rule_id") or item.get("rule_code"))
        if item_record_id == normalized_record_id and item_rule_id == normalized_rule_id:
            return dict(item)
    return None


def _failed_record_for(job: dict[str, Any], *, record_id: str) -> dict[str, Any] | None:
    normalized_record_id = _safe_text(record_id)
    for item in list(job.get("failed_records") or []):
        item_record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
        if item_record_id == normalized_record_id:
            return dict(item)
    return None


def _resolve_validation_mode(rule_id: str) -> str:
    return "programmatic" if _normalize_rule_id(rule_id) in PROGRAMMATIC_RULE_ID_SET else "sc"


def _build_job_filters(
    *,
    row: dict[str, str],
    record_id: str,
    primary_rule_id: str,
) -> tuple[str, dict[str, Any]]:
    validation_mode = _resolve_validation_mode(primary_rule_id)
    if validation_mode == "programmatic":
        rule_set = get_sample_programmatic_rule_set()
        execution_strategy = rule_set.execution_strategy
        return validation_mode, {
            "rule_ids": [primary_rule_id],
            "rule_set_key": rule_set.key,
            "rule_set_name": rule_set.name,
            "rule_set_version": rule_set.version,
            "execution_strategy": execution_strategy,
            "quality_profile": rule_set.quality_profile,
            "bucket_strategy": rule_set.bucket_strategy,
            "batch_output_mode": rule_set.batch_output_mode,
            "enable_selective_refine": False,
            "refine_confidence_threshold": 0.0,
            "max_refine_candidates": 0,
            "source": "sheet2_issue_family_verification",
            "selected_record_ids": [record_id],
            "selected_sample_count": 1,
            "dedup_record_count": 1,
            "record_rule_map": {record_id: [primary_rule_id]},
            "effective_scope": "all",
            "validation_mode": validation_mode,
            "max_parallel_records": 1,
            "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
            "sheet2_issue_family": _safe_text(row.get("issue_family")),
            "sheet2_manual_issue_text": _safe_text(row.get("manual_issue_text")),
        }

    execution_strategy = _resolve_sample_validation_execution_strategy(
        validation_mode="sc",
        rule_ids=[primary_rule_id],
    )
    return validation_mode, {
        "rule_ids": [primary_rule_id],
        "rule_set_key": "",
        "rule_set_name": "SC样本规则模式",
        "rule_set_version": "sheet2-primary-rule-v1",
        "execution_strategy": execution_strategy,
        "quality_profile": "throughput_v1",
        "bucket_strategy": "fixed_packs",
        "batch_output_mode": "minimal",
        "enable_selective_refine": False,
        "refine_confidence_threshold": 0.0,
        "max_refine_candidates": 0,
        "source": "sheet2_issue_family_verification",
        "selected_record_ids": [record_id],
        "selected_sample_count": 1,
        "dedup_record_count": 1,
        "record_rule_map": {record_id: [primary_rule_id]},
        "effective_scope": "all",
        "validation_mode": validation_mode,
        "max_parallel_records": 1,
        "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
        "sheet2_issue_family": _safe_text(row.get("issue_family")),
        "sheet2_manual_issue_text": _safe_text(row.get("manual_issue_text")),
    }


def _derive_evidence_status(item: dict[str, Any] | None, *, job_status: str) -> str:
    if job_status != "completed":
        return "job_failed"
    if not item:
        return "missing_result"

    status = _safe_text(item.get("status")).lower()
    findings = _safe_text(item.get("findings"))
    evidence = _safe_text(item.get("evidence"))
    evidence_verified = item.get("evidence_verified")

    if status in {"compliant", "not_applicable"} and not evidence and not findings:
        return "no_issue_detected"
    if status == "non_compliant":
        if evidence and evidence_verified is True:
            return "evidence_verified"
        if evidence and evidence_verified is False:
            return "evidence_unverified"
        if evidence:
            return "evidence_present"
        if findings:
            return "findings_only"
        return "evidence_missing"
    if status == "uncertain":
        return "uncertain_with_evidence" if (evidence or findings) else "uncertain_no_evidence"
    if evidence and evidence_verified is True:
        return "evidence_verified"
    if evidence:
        return "evidence_present"
    if findings:
        return "findings_only"
    return "evidence_missing"


def _build_evidence_summary(
    item: dict[str, Any] | None,
    *,
    job_status: str,
    error_message: str,
    failed_record: dict[str, Any] | None,
) -> str:
    if job_status != "completed":
        return _truncate(error_message or f"batch_status={job_status}", 220)
    if not item:
        failed_reason = _safe_text((failed_record or {}).get("error_message") or (failed_record or {}).get("message"))
        fallback = failed_reason or "批任务已完成，但未找到该病历该规则的明细结果。"
        return _truncate(fallback, 220)

    parts = [f"status={_safe_text(item.get('status')).lower() or 'unknown'}"]
    findings = _safe_text(item.get("findings"))
    evidence = _safe_text(item.get("evidence"))
    if findings:
        parts.append(f"findings={_truncate(findings, 80)}")
    if evidence:
        parts.append(f"evidence={_truncate(evidence, 120)}")
    if item.get("evidence_verified") is not None:
        parts.append(f"evidence_verified={bool(item.get('evidence_verified') is True)}")
    return "；".join(parts)


def _derive_verification_status(item: dict[str, Any] | None, *, job_status: str) -> str:
    if job_status != "completed":
        return "job_failed"
    if not item:
        return "missing_result"
    status = _safe_text(item.get("status")).lower()
    if status == "non_compliant":
        return "verified_hit"
    if status == "uncertain":
        return "verified_uncertain"
    if status in {"compliant", "not_applicable"}:
        return "verified_miss"
    return f"verified_{status or 'unknown'}"


def _derive_next_action(verification_status: str, evidence_status: str) -> str:
    if verification_status == "verified_hit":
        if evidence_status in {"evidence_verified", "evidence_present"}:
            return "主规则已命中，人工确认后可结案"
        return "主规则已命中，但证据偏弱，需人工复核原文"
    if verification_status == "verified_miss":
        return "主规则未命中，后续补跑 secondary_rule_ids 或转人工复核"
    if verification_status == "verified_uncertain":
        return "主规则结果不确定，优先人工复核并评估是否补跑 secondary_rule_ids"
    if verification_status == "missing_result":
        return "批任务已完成但无规则结果，检查 record_rule_map 或规则适用范围"
    if verification_status == "job_failed":
        return "检查批任务错误后重跑主规则"
    if verification_status.startswith("skipped_"):
        return "补齐主规则或病历数据后再执行"
    return "人工复核该条核验结果"


def _build_skip_result(reason: str) -> dict[str, str]:
    verification_status = f"skipped_{reason}"
    return {
        "verification_status": verification_status,
        "job_id": "",
        "evidence_status": "not_run",
        "evidence_summary": reason,
        "next_action": _derive_next_action(verification_status, "not_run"),
    }


async def _run_single_row(
    *,
    workspace: CustomQCWorkspaceService,
    row: dict[str, str],
    created_by: str,
) -> dict[str, str]:
    row_id = _safe_text(row.get("sheet2_row_id"))
    record_id = _safe_text(row.get("visit_id"))
    primary_rule_id = _normalize_rule_id(row.get("primary_rule_id"))
    issue_family = _safe_text(row.get("issue_family"))
    if not record_id:
        return _build_skip_result("missing_visit_id")
    if not primary_rule_id:
        return _build_skip_result("missing_primary_rule_id")

    records = workspace.collect_records(
        scope="all",
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=[record_id],
    )
    if not records:
        return {
            "verification_status": "job_failed",
            "job_id": "",
            "evidence_status": "job_failed",
            "evidence_summary": f"未找到病历 {record_id}，无法创建批任务",
            "next_action": "检查 visit_id 是否已同步到当前 PG 后重跑",
        }

    validation_mode, filters = _build_job_filters(
        row=row,
        record_id=record_id,
        primary_rule_id=primary_rule_id,
    )
    draft = resolve_sample_validation_pseudo_draft(
        validation_mode=validation_mode,
        pool_name=f"Sheet2-{issue_family or row_id or primary_rule_id}",
        rule_count=1,
    )

    job_id = ""
    try:
        job = workspace.create_batch_job(
            draft=draft,
            created_by=_safe_text(created_by) or "sheet2_issue_family_verification",
            scope="all",
            filters=filters,
            record_ids=[record_id],
            total_records=len(records),
            draft_ids=[primary_rule_id],
            execution_mode="multi",
            run_mode="parallel",
            rule_count=1,
        )
        job_id = _safe_text(job.get("id"))
        await _run_sichuan_workspace_batch_job(job_id)
        completed_job = workspace.get_batch_job_for_processing(job_id=job_id) or {}
    except Exception as exc:
        return {
            "verification_status": "job_failed",
            "job_id": job_id,
            "evidence_status": "job_failed",
            "evidence_summary": _truncate(str(exc), 220),
            "next_action": "检查批任务错误后重跑主规则",
        }

    job_status = _safe_text(completed_job.get("status")).lower()
    error_message = _safe_text(completed_job.get("error_message"))
    item = _status_for(completed_job, record_id=record_id, rule_id=primary_rule_id)
    failed_record = _failed_record_for(completed_job, record_id=record_id)
    verification_status = _derive_verification_status(item, job_status=job_status)
    evidence_status = _derive_evidence_status(item, job_status=job_status)
    evidence_summary = _build_evidence_summary(
        item,
        job_status=job_status,
        error_message=error_message,
        failed_record=failed_record,
    )
    next_action = _derive_next_action(verification_status, evidence_status)
    return {
        "verification_status": verification_status,
        "job_id": _safe_text(completed_job.get("id")) or job_id,
        "evidence_status": evidence_status,
        "evidence_summary": evidence_summary,
        "next_action": next_action,
    }


async def _run_verification(args: argparse.Namespace) -> dict[str, Any]:
    ledger_path = Path(_safe_text(args.ledger_csv) or str(DEFAULT_LEDGER_CSV)).resolve()
    if not ledger_path.exists():
        raise RuntimeError(f"ledger 不存在: {ledger_path}")

    fieldnames, rows = _read_ledger_rows(ledger_path)
    workspace = CustomQCWorkspaceService()
    matched_indexes: list[int] = []
    for index, row in enumerate(rows):
        if not _row_matches_issue_family(_safe_text(row.get("issue_family")), list(args.issue_families or [])):
            continue
        if not args.include_non_pending:
            current_status = _safe_text(row.get("verification_status")).lower()
            if current_status not in PENDING_STATUS_SET:
                continue
        matched_indexes.append(index)

    if not matched_indexes:
        raise RuntimeError("未找到匹配的 ledger 行；请检查 --issue-family 或 verification_status 过滤条件")

    if int(args.limit or 0) > 0:
        matched_indexes = matched_indexes[: int(args.limit)]

    results: list[dict[str, Any]] = []
    for index in matched_indexes:
        row = rows[index]
        row_result = await _run_single_row(
            workspace=workspace,
            row=row,
            created_by=_safe_text(args.created_by),
        )
        for column in LEDGER_RESULT_COLUMNS:
            row[column] = _safe_text(row_result.get(column))
        _write_ledger_rows(ledger_path, fieldnames, rows)
        results.append(
            {
                "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
                "visit_id": _safe_text(row.get("visit_id")),
                "issue_family": _safe_text(row.get("issue_family")),
                "primary_rule_id": _safe_text(row.get("primary_rule_id")),
                **row_result,
            }
        )

    summary = {
        "ledger_csv": str(ledger_path),
        "issue_families": list(args.issue_families or []),
        "processed_count": len(results),
        "matched_count": len(matched_indexes),
        "verification_status_breakdown": {},
        "rows": results,
    }
    for item in results:
        key = _safe_text(item.get("verification_status")) or "unknown"
        summary["verification_status_breakdown"][key] = int(summary["verification_status_breakdown"].get(key) or 0) + 1
    return summary


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run_verification(args))
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    output_path = _safe_text(args.output_json)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
