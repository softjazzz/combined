#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers.qc_sample_pools import _resolve_sample_validation_execution_strategy
from app.routers.qc_sichuan import _run_sichuan_workspace_batch_job
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


LEDGER_CSV = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sheet2_verification_ledger_seed.csv"
DEFAULT_POOL_NAME = "0426"
DEFAULT_CREATED_BY = "sheet2_issue_family_verification"
PROGRAMMATIC_RULE_IDS = set(SAMPLE_PROGRAMMATIC_RULE_IDS) | {"SC-072", "LXE-35"}
DEFAULT_FAMILIES: tuple[str, ...] = (
    "病程记录缺分析/缺处理意见",
    "上级查房内容空洞/复制粘贴/身份异常",
    "会诊执行记录缺失/未写执行情况",
    "首次病程记录存在/时效",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按问题族逐条执行 Sheet2 台账核验")
    parser.add_argument("--ledger", default=str(LEDGER_CSV), help="台账 CSV 路径")
    parser.add_argument("--pool", default=DEFAULT_POOL_NAME, help="样本池名称，仅用于任务元数据")
    parser.add_argument("--created-by", default=DEFAULT_CREATED_BY, help="批量任务 created_by")
    parser.add_argument("--issue-family", dest="issue_families", action="append", default=[], help="指定 issue_family，可重复传入")
    parser.add_argument("--sheet2-row-id", dest="row_ids", action="append", default=[], help="指定台账 row id，可重复传入")
    parser.add_argument("--limit-per-family", type=int, default=0, help="每个问题族最多执行多少条，0 表示不限制")
    parser.add_argument(
        "--rule-slot",
        choices=("primary", "primary-retry", "secondary-first"),
        default="primary",
        help="执行主规则或首个次规则",
    )
    parser.add_argument(
        "--secondary-rule-id",
        dest="secondary_rule_ids",
        action="append",
        default=[],
        help="当 --rule-slot=secondary-first 时，指定要执行的次规则，可重复传入",
    )
    parser.add_argument(
        "--override-rule-id",
        default="",
        help="对本次选中的所有条目强制使用该规则执行，用于 C 线映射试跑",
    )
    parser.add_argument("--output-json", default="", help="可选，输出本轮汇总 JSON")
    parser.add_argument("--dry-run", action="store_true", help="只生成选择结果，不执行任务")
    return parser.parse_args()


def _load_ledger(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _write_ledger(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _select_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    issue_families = {_safe_text(item) for item in (args.issue_families or []) if _safe_text(item)}
    row_ids = {_safe_text(item) for item in (args.row_ids or []) if _safe_text(item)}
    requested_secondary_rule_ids = {
        _safe_text(item).upper()
        for item in (args.secondary_rule_ids or [])
        if _safe_text(item)
    }
    if not issue_families and not row_ids:
        issue_families = set(DEFAULT_FAMILIES)

    selected: list[dict[str, str]] = []
    family_counts: Counter[str] = Counter()
    for row in rows:
        row_id = _safe_text(row.get("sheet2_row_id"))
        next_action = _safe_text(row.get("next_action"))
        if args.rule_slot == "primary":
            if _safe_text(row.get("verification_status")) != "pending":
                continue
            if next_action not in {
                "按主规则做真实核验",
                "先跑现有规则并记录缺口",
                "先核现有证据，再补语义规则",
            }:
                continue
        elif args.rule_slot == "primary-retry":
            if _safe_text(row.get("verification_status")) != "miss":
                continue
        else:
            if _safe_text(row.get("verification_status")) != "miss":
                continue
            if row_id not in row_ids and next_action != "补跑secondary_rule_ids":
                continue
        if not _safe_text(row.get("visit_id")) or not _safe_text(row.get("primary_rule_id")):
            continue
        if args.rule_slot == "secondary-first" and not _resolve_rule_id(row, rule_slot=args.rule_slot, requested_secondary_rule_ids=requested_secondary_rule_ids):
            continue
        family = _safe_text(row.get("issue_family"))
        if row_ids and row_id not in row_ids:
            continue
        if issue_families and family not in issue_families and row_id not in row_ids:
            continue
        if args.limit_per_family and family_counts[family] >= int(args.limit_per_family):
            continue
        selected.append(row)
        family_counts[family] += 1
    return selected


def _group_rows_by_family(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_safe_text(row.get("issue_family"))].append(row)
    return dict(grouped)


def _first_secondary_rule_id(row: dict[str, str]) -> str:
    for item in (_safe_text(row.get("secondary_rule_ids")) or "").split("|"):
        rule_id = _safe_text(item).upper()
        if rule_id:
            return rule_id
    return ""


def _resolve_rule_id(
    row: dict[str, str],
    *,
    rule_slot: str,
    requested_secondary_rule_ids: set[str] | None = None,
    override_rule_id: str = "",
) -> str:
    normalized_override = _safe_text(override_rule_id).upper()
    if normalized_override:
        return normalized_override
    if rule_slot != "secondary-first":
        return _safe_text(row.get("primary_rule_id")).upper()
    normalized_requested = {item.upper() for item in (requested_secondary_rule_ids or set()) if item}
    secondary_rule_ids = [
        _safe_text(item).upper()
        for item in (_safe_text(row.get("secondary_rule_ids")) or "").split("|")
        if _safe_text(item)
    ]
    if normalized_requested:
        for rule_id in secondary_rule_ids:
            if rule_id in normalized_requested:
                return rule_id
        return ""
    return secondary_rule_ids[0] if secondary_rule_ids else ""


def _normalize_executor_breakdown(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {
            "program": int(value.get("program") or 0),
            "llm": int(value.get("llm") or 0),
        }
    return {"program": 0, "llm": 0}


def _find_item(job: dict[str, Any], *, record_id: str, rule_id: str) -> dict[str, Any] | None:
    normalized_rule_id = _safe_text(rule_id).upper()
    for item in list(job.get("items") or []):
        item_record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
        item_rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        if item_record_id == record_id and item_rule_id == normalized_rule_id:
            return dict(item)
    return None


def _find_failed_record(job: dict[str, Any], *, record_id: str, rule_id: str) -> dict[str, Any] | None:
    normalized_rule_id = _safe_text(rule_id).upper()
    for item in list(job.get("failed_records") or []):
        item_record_id = _safe_text(item.get("record_id") or item.get("visit_id"))
        item_rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).upper()
        if item_record_id == record_id and item_rule_id == normalized_rule_id:
            return dict(item)
    return None


def _summarize_text(*values: Any, limit: int = 160) -> str:
    for value in values:
        text = _safe_text(value)
        if text:
            return text[:limit]
    return ""


def _derive_hit_status(row: dict[str, str], item: dict[str, Any]) -> str:
    status = _safe_text(item.get("status")).lower()
    if status != "non_compliant":
        return "miss"
    primary_rule_id = _safe_text(row.get("primary_rule_id")).upper()
    if primary_rule_id in PROGRAMMATIC_RULE_IDS:
        return "exact_hit"
    return "same_family_hit"


def _derive_next_action_for_miss(row: dict[str, str]) -> str:
    if _safe_text(row.get("secondary_rule_ids")):
        return "补跑secondary_rule_ids"
    return "转C线补规则"


async def _run_family_batch(
    *,
    pool_name: str,
    created_by: str,
    family: str,
    rows: list[dict[str, str]],
    rule_slot: str,
    requested_secondary_rule_ids: set[str] | None = None,
    override_rule_id: str = "",
) -> dict[str, Any]:
    workspace = CustomQCWorkspaceService()
    record_ids = []
    record_rule_map: dict[str, list[str]] = {}
    rule_ids: list[str] = []
    for row in rows:
        record_id = _safe_text(row.get("visit_id"))
        rule_id = _resolve_rule_id(
            row,
            rule_slot=rule_slot,
            requested_secondary_rule_ids=requested_secondary_rule_ids,
            override_rule_id=override_rule_id,
        )
        if not record_id or not rule_id:
            continue
        if record_id not in record_ids:
            record_ids.append(record_id)
        record_rule_map[record_id] = [rule_id]
        if rule_id not in rule_ids:
            rule_ids.append(rule_id)

    records = workspace.collect_records(
        scope="all",
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=record_ids,
    )
    if not records:
        raise RuntimeError(f"{family} 未找到可执行病历")

    validation_mode = (
        "programmatic"
        if rule_ids and all(rule_id in PROGRAMMATIC_RULE_IDS for rule_id in rule_ids)
        else "sc"
    )
    programmatic_rule_set = get_sample_programmatic_rule_set()
    if validation_mode == "programmatic":
        rule_set_key = programmatic_rule_set.key
        rule_set_name = programmatic_rule_set.name
        rule_set_version = programmatic_rule_set.version
    else:
        rule_set_key = ""
        rule_set_name = "SC样本规则模式"
        rule_set_version = "sheet2-ledger-v1"
    execution_strategy = _resolve_sample_validation_execution_strategy(
        validation_mode=validation_mode,
        rule_ids=rule_ids,
    )
    draft = resolve_sample_validation_pseudo_draft(
        validation_mode=validation_mode,
        pool_name=f"{pool_name}-{family}",
        rule_count=len(rule_ids),
    )
    job = workspace.create_batch_job(
        draft=draft,
        created_by=created_by,
        scope="all",
        filters={
            "rule_ids": rule_ids,
            "rule_set_key": rule_set_key,
            "rule_set_name": rule_set_name,
            "rule_set_version": rule_set_version,
            "execution_strategy": execution_strategy,
            "quality_profile": "throughput_v1",
            "bucket_strategy": "fixed_packs",
            "batch_output_mode": "minimal",
            "enable_selective_refine": False,
            "refine_confidence_threshold": 0.0,
            "max_refine_candidates": 0,
            "source": "manual_problem_sample_pool_sheet2_verification",
            "sample_pool_id": pool_name,
            "selected_record_ids": record_ids,
            "selected_sample_count": len(rows),
            "dedup_record_count": len(record_ids),
            "record_rule_map": record_rule_map,
            "effective_scope": "all",
            "validation_mode": validation_mode,
            "max_parallel_records": 4,
        },
        record_ids=record_ids,
        total_records=len(records),
        draft_ids=rule_ids,
        execution_mode="multi",
        run_mode="parallel",
        rule_count=len(rule_ids),
    )
    await _run_sichuan_workspace_batch_job(job["id"])
    completed_job = workspace.get_batch_job_for_processing(job_id=job["id"])
    if not completed_job:
        raise RuntimeError(f"{family} 批量任务未返回结果: {job['id']}")
    if validation_mode == "programmatic":
        await _repair_programmatic_missing_items(
            job=completed_job,
            rows=rows,
            records=records,
            rule_slot=rule_slot,
            requested_secondary_rule_ids=requested_secondary_rule_ids,
            override_rule_id=override_rule_id,
        )
    return dict(completed_job)


async def _repair_programmatic_missing_items(
    *,
    job: dict[str, Any],
    rows: list[dict[str, str]],
    records: list[dict[str, Any]],
    rule_slot: str,
    requested_secondary_rule_ids: set[str] | None = None,
    override_rule_id: str = "",
) -> None:
    record_map = {_safe_text(item.get("record_id") or item.get("visit_id")): dict(item) for item in records}
    qc_service = SichuanQCService()
    items = list(job.get("items") or [])
    repaired = 0

    for row in rows:
        record_id = _safe_text(row.get("visit_id"))
        rule_id = _resolve_rule_id(
            row,
            rule_slot=rule_slot,
            requested_secondary_rule_ids=requested_secondary_rule_ids,
            override_rule_id=override_rule_id,
        )
        if not record_id or not rule_id:
            continue
        existing_item = _find_item(job, record_id=record_id, rule_id=rule_id)
        existing_status = _safe_text((existing_item or {}).get("status")).lower()
        if existing_item and existing_status != "uncertain":
            continue
        if _find_failed_record(job, record_id=record_id, rule_id=rule_id):
            continue
        record = record_map.get(record_id) or {}
        institute_id = _safe_text(record.get("institute_id"))
        patient_id = _safe_text(record.get("patient_id"))
        visit_id = _safe_text(record.get("visit_id") or record_id)
        if not visit_id:
            continue
        bundle: dict[str, Any] | None = None
        if institute_id and patient_id:
            scene = "final" if _safe_text(record.get("scope")).lower() == "final" else "running"
            try:
                bundle = load_running_final_bundle(
                    scene=scene,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    schema="public",
                )
            except Exception:
                bundle = None
        elif record:
            bundle = {
                "visit_id": visit_id,
                "medical_text": _safe_text(record.get("medical_text")),
                "structured_context": {"documents": {}},
            }
        else:
            bundle = {
                "visit_id": visit_id,
                "medical_text": "",
                "structured_context": {"documents": {}},
            }
        evidence_payload = build_programmatic_evidence_payload(
            bundle=bundle,
            medical_text=_safe_text(record.get("medical_text")),
        )
        if rule_id == "SC-098":
            surgery_events = list(
                (
                    _safe_dict(evidence_payload.get("programmatic_timeline")).get("documents")
                    or {}
                ).get("surgery_record")
                or []
            )
            if not surgery_events:
                evidence_payload = build_programmatic_evidence_payload(
                    bundle={
                        "visit_id": visit_id,
                        "medical_text": _safe_text(record.get("medical_text")),
                        "structured_context": {"documents": {}},
                    },
                    medical_text=_safe_text(record.get("medical_text")),
                )
        primary_document_text = _safe_text(
            evidence_payload.get("primary_document_text")
            or bundle.get("medical_text")
            or record.get("medical_text")
        )
        raw_rule = qc_service.get_rule_by_id(rule_id)
        if not raw_rule:
            continue
        rule = apply_programmatic_rule_runtime_overrides(raw_rule)
        result = await qc_service.evaluate_document_with_rules(
            document_id=record_id,
            content=primary_document_text,
            document_type="病历文书",
            rules=[rule],
            evidence_source="timeline",
            evidence_payload=evidence_payload,
            bucket_strategy="fixed_packs",
            quality_profile="throughput_v1",
            batch_output_mode="minimal",
            enable_selective_refine=False,
            refine_confidence_threshold=0.0,
            max_refine_candidates=0,
        )
        eval_items = list(result.get("evaluation_results") or [])
        if not eval_items:
            continue
        eval_item = dict(eval_items[0])
        status = _safe_text(eval_item.get("status")).lower()
        if status not in {"non_compliant", "uncertain"}:
            continue
        metadata = dict(eval_item.get("metadata") or {})
        normalized_item = {
            "rule_job_id": "",
            "rule_id": _safe_text(eval_item.get("rule_id") or rule_id),
            "rule_code": rule_id,
            "rule_name": _safe_text(eval_item.get("rule_name") or rule.get("name") or rule_id),
            "record_id": record_id,
            "visit_id": visit_id,
            "patient_name": _safe_text(record.get("patient_name")),
            "department": _safe_text(record.get("department")),
            "status": status,
            "is_compliant": bool(eval_item.get("is_compliant") is True),
            "findings": _safe_text(eval_item.get("findings")),
            "evidence": _safe_text(eval_item.get("evidence")),
            "suggestion": _safe_text(eval_item.get("suggestion")),
            "confidence": float(eval_item.get("confidence") or 0),
            "executor_type": _safe_text(metadata.get("executor_type") or "program"),
            "document_type": "病历文书",
            "target_document_type": "病历文书",
            "evidence_source": _safe_text(metadata.get("evidence_source") or "timeline"),
            "model_version": _safe_text(metadata.get("model_version") or "programmatic-v1"),
        }
        replaced = False
        if existing_item:
            for index, current in enumerate(items):
                current_record_id = _safe_text(current.get("record_id") or current.get("visit_id"))
                current_rule_id = _safe_text(current.get("rule_id") or current.get("rule_code")).upper()
                if current_record_id == record_id and current_rule_id == rule_id:
                    items[index] = normalized_item
                    replaced = True
                    break
        if not replaced:
            items.append(normalized_item)
        repaired += 1

    if repaired:
        job["items"] = items


def _apply_job_results(
    *,
    family: str,
    rows: list[dict[str, str]],
    job: dict[str, Any],
    rule_slot: str,
    requested_secondary_rule_ids: set[str] | None = None,
    override_rule_id: str = "",
) -> dict[str, Any]:
    job_id = _safe_text(job.get("id"))
    result_counter: Counter[str] = Counter()
    updated_rows: list[dict[str, str]] = []

    for row in rows:
        record_id = _safe_text(row.get("visit_id"))
        rule_id = _resolve_rule_id(
            row,
            rule_slot=rule_slot,
            requested_secondary_rule_ids=requested_secondary_rule_ids,
            override_rule_id=override_rule_id,
        )
        item = _find_item(job, record_id=record_id, rule_id=rule_id)
        failed = _find_failed_record(job, record_id=record_id, rule_id=rule_id)
        updated = dict(row)
        updated["job_id"] = job_id
        if item:
            verification_status = _derive_hit_status(row, item)
            updated["verification_status"] = verification_status
            updated["evidence_status"] = _safe_text(item.get("status")).lower() or "non_compliant"
            updated["evidence_summary"] = _summarize_text(item.get("findings"), item.get("evidence"))
            updated["next_action"] = "已核验完成"
            result_counter[verification_status] += 1
        elif failed:
            updated["verification_status"] = "miss"
            updated["evidence_status"] = "failed"
            updated["evidence_summary"] = _summarize_text(failed.get("error"), failed.get("reason"))
            updated["next_action"] = "转C线补规则" if rule_slot == "secondary-first" else _derive_next_action_for_miss(row)
            result_counter["miss"] += 1
        else:
            updated["verification_status"] = "miss"
            updated["evidence_status"] = "compliant_or_no_issue"
            if rule_slot == "secondary-first":
                updated["evidence_summary"] = f"次规则 {rule_id} 执行完成，未产生问题项。"
                updated["next_action"] = "转C线补规则"
            else:
                updated["evidence_summary"] = "主规则执行完成，未产生问题项。"
                updated["next_action"] = _derive_next_action_for_miss(row)
            result_counter["miss"] += 1
        updated_rows.append(updated)

    return {
        "family": family,
        "job_id": job_id,
        "updated_rows": updated_rows,
        "result_breakdown": dict(result_counter),
        "executor_breakdown": _normalize_executor_breakdown((job.get("summary") or {}).get("executor_breakdown")),
        "items_count": len(job.get("items") or []),
        "failed_count": len(job.get("failed_records") or []),
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    ledger_path = Path(args.ledger).resolve()
    fieldnames, ledger_rows = _load_ledger(ledger_path)
    selected_rows = _select_rows(ledger_rows, args)
    grouped_rows = _group_rows_by_family(selected_rows)
    requested_secondary_rule_ids = {
        _safe_text(item).upper()
        for item in (args.secondary_rule_ids or [])
        if _safe_text(item)
    }
    override_rule_id = _safe_text(args.override_rule_id).upper()

    report = {
        "ledger": str(ledger_path),
        "pool": _safe_text(args.pool) or DEFAULT_POOL_NAME,
        "created_by": _safe_text(args.created_by) or DEFAULT_CREATED_BY,
        "selected_row_count": len(selected_rows),
        "families": [],
    }
    if args.dry_run:
        report["families"] = [
            {
                "issue_family": family,
                "row_count": len(rows),
                "record_ids": sorted({_safe_text(row.get("visit_id")) for row in rows if _safe_text(row.get("visit_id"))}),
                "rule_ids": sorted(
                    {
                        _resolve_rule_id(
                            row,
                            rule_slot=args.rule_slot,
                            requested_secondary_rule_ids={
                                _safe_text(item).upper()
                                for item in (args.secondary_rule_ids or [])
                                if _safe_text(item)
                            },
                            override_rule_id=override_rule_id,
                        )
                        for row in rows
                        if _resolve_rule_id(
                            row,
                            rule_slot=args.rule_slot,
                            requested_secondary_rule_ids={
                                _safe_text(item).upper()
                                for item in (args.secondary_rule_ids or [])
                                if _safe_text(item)
                            },
                            override_rule_id=override_rule_id,
                        )
                    }
                ),
            }
            for family, rows in grouped_rows.items()
        ]
        return report

    by_row_id = {row["sheet2_row_id"]: row for row in ledger_rows}
    for family, rows in grouped_rows.items():
        try:
            job = await _run_family_batch(
                pool_name=_safe_text(args.pool) or DEFAULT_POOL_NAME,
                created_by=_safe_text(args.created_by) or DEFAULT_CREATED_BY,
                family=family,
                rows=rows,
                rule_slot=args.rule_slot,
                requested_secondary_rule_ids=requested_secondary_rule_ids,
                override_rule_id=override_rule_id,
            )
        except RuntimeError as exc:
            error_text = _safe_text(exc)
            if "未找到可执行病历" in error_text:
                for row in rows:
                    updated = dict(row)
                    updated["evidence_status"] = "workspace_record_missing"
                    updated["evidence_summary"] = "workspace.collect_records 未命中本地病历。"
                    updated["next_action"] = "先核原始文书是否缺失，再判定是否skip"
                    by_row_id[updated["sheet2_row_id"]] = updated
                report["families"].append(
                    {
                        "issue_family": family,
                        "row_count": len(rows),
                        "job_id": "",
                        "result_breakdown": {},
                        "executor_breakdown": {"program": 0, "llm": 0},
                        "items_count": 0,
                        "failed_count": 0,
                        "blocked_reason": error_text,
                    }
                )
                continue
            raise
        applied = _apply_job_results(
            family=family,
            rows=rows,
            job=job,
            rule_slot=args.rule_slot,
            requested_secondary_rule_ids=requested_secondary_rule_ids,
            override_rule_id=override_rule_id,
        )
        for updated in applied["updated_rows"]:
            by_row_id[updated["sheet2_row_id"]] = updated
        report["families"].append(
            {
                "issue_family": family,
                "row_count": len(rows),
                "job_id": applied["job_id"],
                "result_breakdown": applied["result_breakdown"],
                "executor_breakdown": applied["executor_breakdown"],
                "items_count": applied["items_count"],
                "failed_count": applied["failed_count"],
            }
        )

    updated_rows = [by_row_id[row["sheet2_row_id"]] for row in ledger_rows]
    _write_ledger(ledger_path, fieldnames, updated_rows)
    report["verification_status_breakdown"] = dict(Counter(_safe_text(row.get("verification_status")) for row in updated_rows))
    return report


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run(args))
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    output_path = _safe_text(args.output_json)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
