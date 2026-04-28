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

from app.routers.qc_sichuan import _run_sichuan_workspace_batch_job
from app.services.bundles.assembly import refresh_scene_bundles_for_rows
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.qc_input_adapters.running_final_bundle_runtime import load_running_final_bundle
from app.services.sample_programmatic_evidence import build_programmatic_evidence_payload
from app.services.sample_validation_rule_sets import (
    SAMPLE_PROGRAMMATIC_RULE_IDS,
    apply_programmatic_rule_runtime_overrides,
    get_sample_programmatic_rule_set,
    resolve_sample_validation_pseudo_draft,
)
from app.services.sichuan_qc_service import SichuanQCService


DEFAULT_RECORD_IDS: tuple[str, ...] = ("1880757", "2137894", "2193241", "2341278")
DEFAULT_EXPECTATIONS: dict[str, dict[str, str]] = {
    "1880757": {"SC-048": "non_compliant", "SC-049": "non_compliant"},
    "2137894": {"SC-048": "non_compliant"},
    "2193241": {"SC-048": "non_compliant", "SC-049": "non_compliant", "SC-096": "uncertain"},
    "2341278": {"SC-048": "compliant", "SC-049": "compliant"},
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行样本硬门槛程序规则固定样本回归")
    parser.add_argument(
        "--record-id",
        dest="record_ids",
        action="append",
        default=[],
        help="指定病历 visit_id，可重复传入；默认使用固定 4 条样本",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="可选，回归结果 JSON 输出路径",
    )
    parser.add_argument(
        "--skip-refresh-final-bundle",
        action="store_true",
        help="跳过 final bundle 重建，仅使用现有 bundle",
    )
    parser.add_argument(
        "--created-by",
        default="sample_programmatic_regression",
        help="批量任务 created_by 标识",
    )
    return parser.parse_args()


def _normalize_record_ids(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized or list(DEFAULT_RECORD_IDS)


def _normalize_executor_breakdown(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {
            "program": int(value.get("program") or 0),
            "llm": int(value.get("llm") or 0),
        }
    if isinstance(value, list):
        output = {"program": 0, "llm": 0}
        for item in value:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip().lower()
            if key in output:
                output[key] = int(item.get("count") or 0)
        return output
    return {"program": 0, "llm": 0}


def _status_for(job: dict[str, Any], *, record_id: str, rule_id: str) -> dict[str, Any] | None:
    for item in list(job.get("items") or []):
        item_record_id = str(item.get("record_id") or item.get("visit_id") or "").strip()
        item_rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        if item_record_id == record_id and item_rule_id == rule_id:
            return dict(item)
    return None


async def _evaluate_direct_rule_statuses(
    *,
    qc_service: SichuanQCService,
    record: dict[str, Any],
    rule_ids: list[str],
) -> dict[str, dict[str, Any]]:
    bundle = load_running_final_bundle(
        scene="final",
        institute_id=str(record.get("institute_id") or "").strip(),
        patient_id=str(record.get("patient_id") or "").strip(),
        visit_id=str(record.get("visit_id") or record.get("record_id") or "").strip(),
        schema="public",
    )
    evidence_payload = build_programmatic_evidence_payload(
        bundle=bundle,
        medical_text=str(record.get("medical_text") or ""),
    )
    rules: list[dict[str, Any]] = []
    for rule_id in rule_ids:
        rule = qc_service.get_rule_by_id(rule_id)
        if not rule:
            raise RuntimeError(f"未找到规则: {rule_id}")
        rules.append(apply_programmatic_rule_runtime_overrides(rule))
    result = await qc_service.evaluate_document_with_rules(
        document_id=str(record.get("visit_id") or record.get("record_id") or "").strip(),
        content=str(evidence_payload.get("primary_document_text") or ""),
        document_type="出院记录",
        rules=rules,
        evidence_source="timeline",
        evidence_payload=evidence_payload,
        bucket_strategy="fixed_packs",
        quality_profile="throughput_v1",
        batch_output_mode="minimal",
        enable_selective_refine=False,
        refine_confidence_threshold=0.0,
        max_refine_candidates=0,
        use_execution_cache=False,
    )
    output: dict[str, dict[str, Any]] = {}
    for item in list(result.get("evaluation_results") or []):
        key = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        if key:
            output[key] = dict(item)
    return output


async def _build_expectation_checks(
    job: dict[str, Any],
    *,
    selected_record_ids: list[str],
    record_map: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    direct_result_cache: dict[str, dict[str, Any]] = {}
    qc_service: SichuanQCService | None = None
    for record_id in selected_record_ids:
        expected_rule_statuses = DEFAULT_EXPECTATIONS.get(record_id, {})
        for rule_id, expected_status in expected_rule_statuses.items():
            item = _status_for(job, record_id=record_id, rule_id=rule_id)
            result_source = "batch"
            if item is None:
                if qc_service is None:
                    qc_service = SichuanQCService()
                cached = direct_result_cache.get(record_id)
                if cached is None:
                    cached = await _evaluate_direct_rule_statuses(
                        qc_service=qc_service,
                        record=record_map[record_id],
                        rule_ids=sorted(expected_rule_statuses.keys()),
                    )
                    direct_result_cache[record_id] = cached
                item = cached.get(rule_id)
                result_source = "direct_programmatic_eval"
            actual_status = str((item or {}).get("status") or "").strip().lower()
            checks.append(
                {
                    "type": "rule_status",
                    "record_id": record_id,
                    "rule_id": rule_id,
                    "expected": expected_status,
                    "actual": actual_status,
                    "passed": actual_status == expected_status,
                    "source": result_source,
                    "evidence": str((item or {}).get("evidence") or "")[:160],
                    "findings": str((item or {}).get("findings") or "")[:160],
                }
            )
    return checks, direct_result_cache


def _load_bundle_admission(record: dict[str, Any]) -> dict[str, Any]:
    bundle = load_running_final_bundle(
        scene="final",
        institute_id=str(record.get("institute_id") or "").strip(),
        patient_id=str(record.get("patient_id") or "").strip(),
        visit_id=str(record.get("visit_id") or record.get("record_id") or "").strip(),
        schema="public",
    )
    return {
        "visit_id": str(record.get("visit_id") or record.get("record_id") or "").strip(),
        "admission_datetime": str(bundle.get("admission_datetime") or "").strip(),
        "discharge_datetime": str(bundle.get("discharge_datetime") or "").strip(),
        "bundle_updated_at": str(bundle.get("bundle_updated_at") or "").strip(),
    }


async def _run_regression(args: argparse.Namespace) -> dict[str, Any]:
    workspace = CustomQCWorkspaceService()
    selected_record_ids = _normalize_record_ids(args.record_ids)
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
    hydrated_records = workspace.hydrate_records_with_medical_text(records)
    record_map = {
        str(item.get("visit_id") or item.get("record_id") or "").strip(): dict(item)
        for item in hydrated_records
        if str(item.get("visit_id") or item.get("record_id") or "").strip()
    }
    missing_record_ids = [record_id for record_id in selected_record_ids if record_id not in record_map]
    if missing_record_ids:
        raise RuntimeError(f"未找到目标病历: {', '.join(missing_record_ids)}")

    selected_records = [record_map[record_id] for record_id in selected_record_ids]
    if not args.skip_refresh_final_bundle:
        refresh_scene_bundles_for_rows(
            scene="final",
            rows=selected_records,
            bundle_schema="public",
            trigger_source="sample_programmatic_regression",
            continue_on_error=False,
        )

    bundle_admissions = [_load_bundle_admission(record) for record in selected_records]
    admission_checks = [
        {
            "type": "bundle_admission",
            "record_id": item["visit_id"],
            "expected": "non_empty",
            "actual": item["admission_datetime"],
            "passed": bool(item["admission_datetime"]),
        }
        for item in bundle_admissions
    ]

    rule_set = get_sample_programmatic_rule_set()
    draft = resolve_sample_validation_pseudo_draft(
        validation_mode="programmatic",
        pool_name="样本硬门槛回归基线",
        rule_count=len(rule_set.rule_ids),
    )
    job = workspace.create_batch_job(
        draft=draft,
        created_by=str(args.created_by or "").strip() or "sample_programmatic_regression",
        scope="all",
        filters={
            "rule_ids": list(rule_set.rule_ids),
            "rule_set_key": rule_set.key,
            "rule_set_name": rule_set.name,
            "rule_set_version": rule_set.version,
            "execution_strategy": rule_set.execution_strategy,
            "quality_profile": rule_set.quality_profile,
            "bucket_strategy": rule_set.bucket_strategy,
            "batch_output_mode": rule_set.batch_output_mode,
            "enable_selective_refine": False,
            "refine_confidence_threshold": 0.0,
            "max_refine_candidates": 0,
            "source": "sample_programmatic_regression",
            "selected_record_ids": selected_record_ids,
            "selected_sample_count": len(selected_record_ids),
            "dedup_record_count": len(selected_record_ids),
            "effective_scope": "all",
            "validation_mode": "programmatic",
        },
        record_ids=selected_record_ids,
        total_records=len(selected_record_ids),
        draft_ids=list(rule_set.rule_ids),
        execution_mode="multi",
        run_mode="parallel",
        rule_count=len(rule_set.rule_ids),
    )

    await _run_sichuan_workspace_batch_job(job["id"])
    completed_job = workspace.get_batch_job_for_processing(job_id=job["id"])
    if not completed_job:
        raise RuntimeError(f"未找到批量任务: {job['id']}")

    summary = dict(completed_job.get("summary") or {})
    executor_breakdown = _normalize_executor_breakdown(summary.get("executor_breakdown"))
    job_rule_ids = [str(item).strip().upper() for item in list((completed_job.get("filters") or {}).get("rule_ids") or [])]
    fixed_rule_checks = [
        {
            "type": "fixed_rule_pack",
            "expected": list(SAMPLE_PROGRAMMATIC_RULE_IDS),
            "actual": job_rule_ids,
            "passed": job_rule_ids == list(SAMPLE_PROGRAMMATIC_RULE_IDS),
        },
        {
            "type": "llm_executor",
            "expected": 0,
            "actual": executor_breakdown.get("llm", 0),
            "passed": executor_breakdown.get("llm", 0) == 0,
        },
        {
            "type": "program_executor_positive",
            "expected": ">0",
            "actual": executor_breakdown.get("program", 0),
            "passed": executor_breakdown.get("program", 0) > 0,
        },
    ]
    expectation_checks, direct_result_cache = await _build_expectation_checks(
        completed_job,
        selected_record_ids=selected_record_ids,
        record_map=record_map,
    )
    checks = [*fixed_rule_checks, *admission_checks, *expectation_checks]

    report = {
        "job_id": str(completed_job.get("id") or ""),
        "status": str(completed_job.get("status") or ""),
        "scope": str(completed_job.get("scope") or ""),
        "validation_mode": str((completed_job.get("filters") or {}).get("validation_mode") or ""),
        "rule_set_key": str((completed_job.get("filters") or {}).get("rule_set_key") or ""),
        "record_ids": selected_record_ids,
        "bundle_admissions": bundle_admissions,
        "executor_breakdown": executor_breakdown,
        "checks": checks,
        "all_passed": all(bool(item.get("passed")) for item in checks),
        "target_results": {
            record_id: {
                rule_id: {
                    "status": str((_status_for(completed_job, record_id=record_id, rule_id=rule_id) or {}).get("status") or ""),
                    "source": "batch"
                    if _status_for(completed_job, record_id=record_id, rule_id=rule_id) is not None
                    else "direct_programmatic_eval",
                    "evidence": str(
                        (
                            _status_for(completed_job, record_id=record_id, rule_id=rule_id)
                            or direct_result_cache.get(record_id, {}).get(rule_id)
                            or {}
                        ).get("evidence")
                        or ""
                    )[:160],
                    "findings": str(
                        (
                            _status_for(completed_job, record_id=record_id, rule_id=rule_id)
                            or direct_result_cache.get(record_id, {}).get(rule_id)
                            or {}
                        ).get("findings")
                        or ""
                    )[:160],
                    "status": str(
                        (
                            _status_for(completed_job, record_id=record_id, rule_id=rule_id)
                            or direct_result_cache.get(record_id, {}).get(rule_id)
                            or {}
                        ).get("status")
                        or ""
                    ),
                }
                for rule_id in sorted(DEFAULT_EXPECTATIONS.get(record_id, {}).keys())
            }
            for record_id in selected_record_ids
            if DEFAULT_EXPECTATIONS.get(record_id)
        },
    }
    if args.output_json:
        output_path = Path(args.output_json).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        report["output_json"] = str(output_path)
    return report


def main() -> int:
    args = _parse_args()
    report = asyncio.run(_run_regression(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("all_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
