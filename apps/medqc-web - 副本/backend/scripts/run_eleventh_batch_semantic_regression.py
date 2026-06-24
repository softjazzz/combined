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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.routers.qc_sample_pools import _resolve_sample_validation_execution_strategy
from app.routers.qc_sichuan import _run_sichuan_workspace_batch_job
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.sample_validation_rule_sets import resolve_sample_validation_pseudo_draft


DEFAULT_POOL_ID = "a627718c-bde9-4cd3-af9d-7856c072525e"
DEFAULT_POOL_NAME = "0426"
DEFAULT_RECORD_IDS: tuple[str, ...] = (
    "2295052",  # SC-067 core
    "2312534",  # SC-067 observe
    "2033353",  # SC-077 core
    "2129217",  # SC-077 core
    "1874568",  # SC-080 observe
    "2218096",  # SC-080 observe
    "2341278",  # SC-080 observe
    "2199396",  # SC-086 observe
    "1947412",  # SC-086 observe
)

DEFAULT_RECORD_RULE_MAP: dict[str, list[str]] = {
    "2295052": ["SC-067"],
    "2312534": ["SC-067"],
    "2033353": ["SC-077"],
    "2129217": ["SC-077"],
    "1874568": ["SC-080"],
    "2218096": ["SC-080"],
    "2341278": ["SC-080"],
    "2199396": ["SC-086"],
    "1947412": ["SC-086"],
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行第十一批语义规则真实样本回归")
    parser.add_argument(
        "--record-id",
        dest="record_ids",
        action="append",
        default=[],
        help="指定病历 visit_id，可重复传入；默认使用第十一批固定样本",
    )
    parser.add_argument(
        "--created-by",
        default="eleventh_batch_semantic_regression",
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


async def _run_regression(args: argparse.Namespace) -> dict[str, Any]:
    workspace = CustomQCWorkspaceService()
    requested_record_ids = _normalize_record_ids(args.record_ids)
    record_rule_map = {
        record_id: list(DEFAULT_RECORD_RULE_MAP.get(record_id) or [])
        for record_id in requested_record_ids
        if list(DEFAULT_RECORD_RULE_MAP.get(record_id) or [])
    }
    if not record_rule_map:
        raise RuntimeError("第十一批样本未找到可执行病历")

    selected_record_ids = list(record_rule_map)
    rule_ids = sorted(
        {
            _safe_text(rule_id)
            for rule_list in record_rule_map.values()
            for rule_id in list(rule_list or [])
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
        raise RuntimeError("第十一批样本病历未同步到当前 PG，无法执行")

    draft = resolve_sample_validation_pseudo_draft(
        validation_mode="sc",
        pool_name=f"{DEFAULT_POOL_NAME}第十一批语义回归",
        rule_count=len(rule_ids),
    )
    job = workspace.create_batch_job(
        draft=draft,
        created_by=_safe_text(args.created_by) or "eleventh_batch_semantic_regression",
        scope="all",
        filters={
            "rule_ids": rule_ids,
            "rule_set_key": "",
            "rule_set_name": "SC样本规则模式",
            "rule_set_version": "running-batch-11",
            "execution_strategy": execution_strategy,
            "quality_profile": "throughput_v1",
            "bucket_strategy": "fixed_packs",
            "batch_output_mode": "minimal",
            "enable_selective_refine": False,
            "refine_confidence_threshold": 0.0,
            "max_refine_candidates": 0,
            "source": "manual_problem_sample_pool_eleventh_batch_regression",
            "sample_pool_id": DEFAULT_POOL_ID,
            "selected_record_ids": selected_record_ids,
            "selected_sample_item_ids": [],
            "selected_sample_count": len(selected_record_ids),
            "dedup_record_count": len(selected_record_ids),
            "record_rule_map": record_rule_map,
            "effective_scope": "all",
            "validation_mode": "sc",
            "max_parallel_records": 6,
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

    report = {
        "pool_id": DEFAULT_POOL_ID,
        "job_id": _safe_text(completed_job.get("id")),
        "status": _safe_text(completed_job.get("status")),
        "requested_record_ids": requested_record_ids,
        "record_ids": selected_record_ids,
        "rule_ids": rule_ids,
        "record_rule_map": record_rule_map,
        "execution_strategy": execution_strategy,
        "summary": dict(completed_job.get("summary") or {}),
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
