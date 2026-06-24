#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers.qc_sample_pools import _resolve_sample_validation_execution_strategy
from app.routers.qc_sichuan import _run_sichuan_workspace_batch_job
from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.sample_validation_rule_sets import resolve_sample_validation_pseudo_draft


DEFAULT_POOL_NAME = "0426"
DEFAULT_RECORD_IDS: tuple[str, ...] = ("2327691", "1962757", "2128953")
DEFAULT_EXPECTATIONS: dict[str, dict[str, str]] = {
    "2327691": {"SC-069": "non_compliant"},
    "1962757": {"SC-039": "non_compliant"},
    "2128953": {"SC-146": "non_compliant"},
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行第二批语义规则真实样本回归")
    parser.add_argument("--pool", default=DEFAULT_POOL_NAME, help="样本池名称或 id，默认 0426")
    parser.add_argument(
        "--record-id",
        dest="record_ids",
        action="append",
        default=[],
        help="指定病历 visit_id，可重复传入；默认使用第二批核心样本",
    )
    parser.add_argument(
        "--created-by",
        default="second_batch_semantic_regression",
        help="批量任务 created_by 标识",
    )
    parser.add_argument("--output-json", default="", help="可选，回归结果 JSON 输出路径")
    return parser.parse_args()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_record_ids(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        text = _safe_text(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized or list(DEFAULT_RECORD_IDS)


def _resolve_pool_id(service: CustomQCSamplePoolService, identifier: str) -> str:
    text = _safe_text(identifier)
    if not text:
        raise RuntimeError("样本池标识不能为空")
    pool = service.get_pool(pool_id=text)
    if pool:
        return text
    result = service.list_pools(page=1, page_size=100, query=text)
    for item in list(result.items or []):
        if _safe_text(item.get("name")) == text:
            return _safe_text(item.get("id"))
    raise RuntimeError(f"未找到样本池: {text}")


def _normalize_executor_breakdown(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {
            "program": int(value.get("program") or 0),
            "llm": int(value.get("llm") or 0),
        }
    return {"program": 0, "llm": 0}


def _status_for(job: dict[str, Any], *, record_id: str, rule_id: str) -> dict[str, Any] | None:
    normalized_rule_id = _safe_text(rule_id).upper()
    for item in list(job.get("items") or []):
        item_record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
        item_rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        if item_record_id == record_id and item_rule_id == normalized_rule_id:
            return dict(item)
    return None


async def _run_regression(args: argparse.Namespace) -> dict[str, Any]:
    pool_service = CustomQCSamplePoolService()
    workspace = CustomQCWorkspaceService()
    pool_id = _resolve_pool_id(pool_service, str(args.pool or DEFAULT_POOL_NAME))
    refresh_summary = pool_service.refresh_pool_item_classifications(pool_id=pool_id)
    selected_record_ids = _normalize_record_ids(args.record_ids)
    runnable_items = pool_service.get_runnable_items(
        pool_id=pool_id,
        validation_mode="sc",
        record_ids=selected_record_ids,
    )
    if not runnable_items:
        raise RuntimeError("第二批样本未找到可执行病历")

    record_rule_map: dict[str, list[str]] = {}
    for item in runnable_items:
        record_id = _safe_text(item.get("matched_visit_id"))
        if not record_id:
            continue
        bucket = record_rule_map.setdefault(record_id, [])
        for rule_id in list(item.get("candidate_rule_ids") or []):
            normalized_rule_id = _safe_text(rule_id)
            if normalized_rule_id and normalized_rule_id not in bucket:
                bucket.append(normalized_rule_id)

    rule_ids = sorted(
        {
            _safe_text(rule_id)
            for item in runnable_items
            for rule_id in list(item.get("candidate_rule_ids") or [])
            if _safe_text(rule_id)
        }
    )
    execution_strategy = _resolve_sample_validation_execution_strategy(
        validation_mode="sc",
        rule_ids=rule_ids,
    )
    records = workspace.collect_records(
        scope="all",
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=selected_record_ids,
    )
    if not records:
        raise RuntimeError("第二批样本病历未同步到当前 PG，无法执行")

    draft = resolve_sample_validation_pseudo_draft(
        validation_mode="sc",
        pool_name=f"{args.pool}第二批语义回归",
        rule_count=len(rule_ids),
    )
    job = workspace.create_batch_job(
        draft=draft,
        created_by=_safe_text(args.created_by) or "second_batch_semantic_regression",
        scope="all",
        filters={
            "rule_ids": rule_ids,
            "rule_set_key": "",
            "rule_set_name": "SC样本规则模式",
            "rule_set_version": "running-batch-2",
            "execution_strategy": execution_strategy,
            "quality_profile": "throughput_v1",
            "bucket_strategy": "fixed_packs",
            "batch_output_mode": "minimal",
            "enable_selective_refine": False,
            "refine_confidence_threshold": 0.0,
            "max_refine_candidates": 0,
            "source": "manual_problem_sample_pool_second_batch_regression",
            "sample_pool_id": pool_id,
            "selected_record_ids": selected_record_ids,
            "selected_sample_item_ids": [
                _safe_text(item.get("id"))
                for item in runnable_items
                if _safe_text(item.get("id"))
            ],
            "selected_sample_count": len(runnable_items),
            "dedup_record_count": len(selected_record_ids),
            "record_rule_map": record_rule_map,
            "effective_scope": "all",
            "validation_mode": "sc",
            "max_parallel_records": 4,
        },
        record_ids=selected_record_ids,
        total_records=len(records),
        draft_ids=rule_ids,
        execution_mode="multi",
        run_mode="parallel",
        rule_count=len(rule_ids),
    )
    await _run_sichuan_workspace_batch_job(job["id"])
    completed_job = workspace.get_batch_job_for_processing(job_id=job["id"])
    if not completed_job:
        raise RuntimeError(f"未找到批量任务: {job['id']}")

    summary = dict(completed_job.get("summary") or {})
    executor_breakdown = _normalize_executor_breakdown(summary.get("executor_breakdown"))
    checks: list[dict[str, Any]] = [
        {
            "type": "execution_strategy",
            "expected": execution_strategy,
            "actual": _safe_text((completed_job.get("filters") or {}).get("execution_strategy")),
            "passed": _safe_text((completed_job.get("filters") or {}).get("execution_strategy")) == execution_strategy,
        },
        {
            "type": "record_rule_map",
            "expected": record_rule_map,
            "actual": dict((completed_job.get("filters") or {}).get("record_rule_map") or {}),
            "passed": dict((completed_job.get("filters") or {}).get("record_rule_map") or {}) == record_rule_map,
        },
    ]
    for record_id, expected_map in DEFAULT_EXPECTATIONS.items():
        if record_id not in selected_record_ids:
            continue
        for rule_id, expected_status in expected_map.items():
            item = _status_for(completed_job, record_id=record_id, rule_id=rule_id) or {}
            actual_status = _safe_text(item.get("status")).lower() or "missing"
            checks.append(
                {
                    "type": "rule_status",
                    "record_id": record_id,
                    "rule_id": rule_id,
                    "expected": expected_status,
                    "actual": actual_status,
                    "passed": actual_status == expected_status,
                    "findings": _safe_text(item.get("findings"))[:160],
                    "evidence": _safe_text(item.get("evidence"))[:160],
                }
            )

    report = {
        "pool_id": pool_id,
        "refresh_summary": refresh_summary,
        "job_id": _safe_text(completed_job.get("id")),
        "status": _safe_text(completed_job.get("status")),
        "record_ids": selected_record_ids,
        "rule_ids": rule_ids,
        "record_rule_map": record_rule_map,
        "execution_strategy": execution_strategy,
        "executor_breakdown": executor_breakdown,
        "summary": summary,
        "checks": checks,
        "all_passed": all(bool(item.get("passed")) for item in checks),
        "items": list(completed_job.get("items") or []),
        "failed_records": list(completed_job.get("failed_records") or []),
    }
    return report


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run_regression(args))
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    output_path = _safe_text(args.output_json)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
