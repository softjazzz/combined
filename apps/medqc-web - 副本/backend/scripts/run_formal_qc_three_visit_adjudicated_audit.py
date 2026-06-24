#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import run_final_fast_screen  # noqa: E402
from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results  # noqa: E402
from app.services.qc_result_postprocessor import (  # noqa: E402
    postprocess_qc_results,
    summarize_postprocessed_results,
)
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
RELEASE_MR = REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto" / "mr.csv"
RULES_RUNTIME = BACKEND_ROOT / "app" / "data" / "sichuan_rules_146.json"
RULES_UPDATED = BACKEND_ROOT / "app" / "data" / "sichuan_rules_146_updated.json"
DEFAULT_VISIT_IDS = ["1915580", "2024757", "2287309"]
DEFAULT_FALLBACK_VISIT_IDS = ["2246915", "1883111"]
TERMINAL_DISPLAY_STATUSES = {
    "confirmed_defect",
    "data_quality_gap",
    "rejected_by_system",
    "technical_error_internal",
}
CROSS_DOC_OR_TEMPORAL_RULES = {
    "SC-036",
    "SC-038",
    "SC-050",
    "SC-051",
    "SC-070",
    "SC-074",
    "SC-083",
    "SC-097",
    "SC-100",
    "SC-107",
    "SC-118",
    "SC-123",
    "SC-125",
    "SC-143",
    "SC-146",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _truncate(value: Any, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", _safe_text(value))
    return text[:limit]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(item) for item in payload if isinstance(item, dict)]


def _load_visit_keys() -> dict[str, dict[str, str]]:
    rows = _read_csv_rows(RELEASE_MR)
    return {_safe_text(row.get("visit_id")): row for row in rows if _safe_text(row.get("visit_id"))}


def _normalize_rule_id(value: Any) -> str:
    return _safe_text(value).upper()


def _load_rules_by_id() -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in _read_json_rows(RULES_RUNTIME) + _read_json_rows(RULES_UPDATED):
        rid = _normalize_rule_id(row.get("rule_id") or row.get("rule_code"))
        if not rid:
            continue
        next_row = dict(merged.get(rid) or {})
        next_row.update(row)
        next_row["rule_id"] = rid
        merged[rid] = next_row
    return merged


def _bundle_profile(bundle: dict[str, Any]) -> dict[str, Any]:
    hits = dict(bundle.get("document_hits") or {})
    source_docs = [dict(item) for item in list(bundle.get("source_documents") or []) if isinstance(item, dict)]
    docs_with_text = [item for item in source_docs if _safe_text(item.get("content"))]
    joined_text = "\n".join(_safe_text(item.get("content")) for item in docs_with_text)
    abnormal_keywords = ["异常", "阳性", "偏高", "偏低", "危急", "感染", "结节", "积液", "梗", "骨折", "低钾"]
    surgery_tables = {
        "mr_surgery",
        "surgery_record",
        "anesthesia_record",
        "presurg_summary",
        "presurg_discussion",
        "postsurg_firstcourse_record",
        "surgery_safecheck_record",
    }
    return {
        "document_hits": hits,
        "document_hit_count": sum(1 for value in hits.values() if bool(value)),
        "document_missing_count": sum(1 for value in hits.values() if not bool(value)),
        "data_quality_flags": list(bundle.get("data_quality_flags") or []),
        "source_document_count": len(source_docs),
        "source_document_with_text_count": len(docs_with_text),
        "is_surgery": any(bool(hits.get(table)) for table in surgery_tables),
        "has_consultation": bool(hits.get("consultation_record")),
        "has_blood": bool(hits.get("bloodtrans_record") or hits.get("blood_application")),
        "abnormal_keyword_hit_count": sum(joined_text.count(keyword) for keyword in abnormal_keywords),
    }


def _counter_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_safe_text(row.get(key)) or "blank" for row in rows))


def _issue_priority(item: dict[str, Any]) -> tuple[int, str]:
    status_order = {
        "confirmed_defect": 0,
        "data_quality_gap": 1,
        "rejected_by_system": 2,
        "technical_error_internal": 3,
    }
    return (status_order.get(_safe_text(item.get("display_status")), 9), _safe_text(item.get("rule_id")))


def _auto_quality_assessment(item: dict[str, Any]) -> tuple[str, str]:
    display_status = _safe_text(item.get("display_status"))
    evidence = _safe_text(item.get("evidence"))
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    reason = _safe_text(item.get("adjudicator_reason"))
    rule_id = _normalize_rule_id(item.get("rule_id"))
    first_pass_display = _safe_text(item.get("first_pass_display_status"))
    confidence = _safe_float(item.get("adjudicator_confidence"))

    if display_status == "confirmed_defect":
        if len(evidence) < 30:
            return "confirmed_evidence_weak", "确认缺陷证据片段偏短，需人工核对完整文书。"
        if not first_pass_display and not reason:
            return "confirmed_first_pass_needs_spot_check", "该条由一审准入直接确认，未经过二审 reason/quote 补充，需抽查。"
        if reason and quote and confidence >= 0.7:
            if rule_id in CROSS_DOC_OR_TEMPORAL_RULES:
                return "confirmed_needs_cross_doc_spot_check", "跨文书/时间链类确认缺陷需人工抽查对照证据是否完整。"
            return "confirmed_likely_showable", "二审 reason 与 supporting_quote 较完整，可作为页面展示候选。"
        return "confirmed_needs_spot_check", "二审解释或置信度不足，需人工抽查。"
    if display_status == "data_quality_gap":
        return "data_gap_reasonable", "已归入数据缺口，不归责医生；需核对是否缺源文书或 bundle 证据。"
    if display_status == "rejected_by_system":
        return "rejected_needs_false_negative_spot_check", "系统驳回需抽查是否误驳回真实缺陷。"
    if display_status == "technical_error_internal":
        return "technical_error_needs_rerun", "技术异常不进入医生问题清单，需优先复跑或排查 provider。"
    return "not_review_target", "合规/不适用结果不在本次质量抽检主清单。"


def _build_issue_rows(
    *,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    limit_per_bucket: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for display_status in [
        "confirmed_defect",
        "data_quality_gap",
        "rejected_by_system",
        "technical_error_internal",
    ]:
        bucket_rows = [
            dict(item)
            for item in results
            if _safe_text(item.get("display_status")) == display_status
        ]
        bucket_rows.sort(key=_issue_priority)
        for item in bucket_rows[: max(1, limit_per_bucket)]:
            meta = dict(item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {}
            evidence = _safe_text(item.get("evidence"))
            auto_label, auto_reason = _auto_quality_assessment(item)
            rows.append(
                {
                    "job_id": summary.get("job_id", ""),
                    "visit_id": summary.get("visit_id", ""),
                    "patient_id": summary.get("patient_id", ""),
                    "patient_name": summary.get("patient_name", ""),
                    "department": summary.get("department", ""),
                    "rule_id": _safe_text(item.get("rule_id")),
                    "rule_name": _safe_text(item.get("rule_name")),
                    "raw_status": _safe_text(item.get("status")),
                    "first_pass_display_status": _safe_text(item.get("first_pass_display_status")),
                    "display_status": display_status,
                    "display_bucket": _safe_text(item.get("display_bucket")),
                    "postprocess_label": _safe_text(item.get("postprocess_label")),
                    "postprocess_reason": _truncate(item.get("postprocess_reason"), 600),
                    "adjudicated_display_status": _safe_text(item.get("adjudicated_display_status")),
                    "adjudicator_reason": _truncate(item.get("adjudicator_reason"), 700),
                    "adjudicator_supporting_quote": _truncate(item.get("adjudicator_supporting_quote"), 700),
                    "adjudicator_confidence": item.get("adjudicator_confidence", ""),
                    "rule_requirement_match": _safe_text(item.get("rule_requirement_match")),
                    "confidence": item.get("confidence", ""),
                    "target_document_type": _safe_text(item.get("target_document_type") or meta.get("target_document_type")),
                    "pack_id": _safe_text(meta.get("pack_id")),
                    "findings": _truncate(item.get("findings")),
                    "evidence": _truncate(evidence),
                    "suggestion": _truncate(item.get("suggestion"), 700),
                    "evidence_problem_type": _safe_text(item.get("evidence_problem_type")),
                    "can_show_as_defect": item.get("can_show_as_defect", ""),
                    "can_show_to_doctor": item.get("can_show_to_doctor", ""),
                    "internal_only": item.get("internal_only", ""),
                    "auto_quality_label": auto_label,
                    "auto_quality_reason": auto_reason,
                    "manual_quality_label": "",
                    "manual_quality_note": "",
                }
            )
    return rows


async def _run_one_visit(
    *,
    visit_id: str,
    visit_keys: dict[str, dict[str, str]],
    rules_by_id: dict[str, dict[str, Any]],
    pack_concurrency: int,
    limit_per_bucket: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    overall_started = time.perf_counter()
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id，无法运行")

    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    profile = _bundle_profile(bundle)
    qc_service = SichuanQCService()
    if not await qc_service.reload_config():
        raise RuntimeError("无法加载 LLM 运行时配置")
    result = await run_final_fast_screen(
        qc_service=qc_service,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
        rule_ids=list(rule_set.rule_ids),
        quality_profile=rule_set.quality_profile,
        batch_output_mode=rule_set.batch_output_mode,
        pack_concurrency=pack_concurrency,
    )
    raw_results = [
        dict(item)
        for item in list(result.get("evaluation_results") or [])
        if isinstance(item, dict)
    ]
    first_pass = postprocess_qc_results(
        raw_results,
        bundle_metadata=profile,
        mode="formal_final_three_visit_audit",
    )
    adjudicated = await adjudicate_postprocessed_qc_results(
        first_pass,
        rules_by_id=rules_by_id,
        llm_generate=getattr(qc_service.client, "generate", None),
        mode="formal_final_three_visit_audit",
    )
    post_summary = summarize_postprocessed_results(adjudicated)
    token_usage = dict(result.get("token_usage") or {})
    pack_metrics = dict(result.get("pack_metrics") or {})
    raw_status_counts = _counter_by(raw_results, "status")
    display_status_counts = _counter_by(adjudicated, "display_status")
    first_pass_display_counts = _counter_by(first_pass, "display_status")
    job_id = f"script-test-{visit_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    summary = {
        "job_id": job_id,
        "source": "script-test",
        "rule_set_key": rule_set.key,
        "rule_set_name": rule_set.name,
        "validation_mode": "formal_fast_screen_full",
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("name")),
        "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
        "is_surgery": profile["is_surgery"],
        "has_consultation": profile["has_consultation"],
        "has_blood": profile["has_blood"],
        "abnormal_keyword_hit_count": profile["abnormal_keyword_hit_count"],
        "bundle_document_hit_count": profile["document_hit_count"],
        "bundle_document_missing_count": profile["document_missing_count"],
        "source_document_count": profile["source_document_count"],
        "source_document_with_text_count": profile["source_document_with_text_count"],
        "rule_count": len(rule_set.rule_ids),
        "pack_count": _safe_int(pack_metrics.get("total_packs")),
        "llm_call_count": _safe_int(getattr(qc_service.client, "call_count", 0))
        or (
            _safe_int(pack_metrics.get("total_packs"))
            + _safe_int(pack_metrics.get("single_rule_retries"))
            + _safe_int(pack_metrics.get("probe_calls"))
        ),
        "fast_screen_wall_clock_time": _safe_float(pack_metrics.get("wall_clock_time") or result.get("api_time")),
        "wall_clock_time": max(0.0, time.perf_counter() - overall_started),
        "total_processing_time": _safe_float(
            getattr(qc_service.client, "total_api_time", 0.0)
            or pack_metrics.get("sum_pack_api_time")
            or result.get("api_time")
        ),
        "total_tokens": _safe_int(getattr(qc_service.client, "total_tokens", 0))
        or _safe_int(token_usage.get("total_tokens")),
        "prompt_tokens": _safe_int(token_usage.get("prompt_tokens")),
        "completion_tokens": _safe_int(token_usage.get("completion_tokens")),
        "provider_error_count": _safe_int(pack_metrics.get("provider_error_count")),
        "timeout_count": _safe_int(pack_metrics.get("timeout_count")),
        "rate_limit_count": _safe_int(pack_metrics.get("rate_limit_count")),
        "technical_error_internal_count": _safe_int(post_summary.get("technical_error_internal_count")),
        "confirmed_defect_count": _safe_int(post_summary.get("confirmed_defect_count")),
        "data_quality_gap_count": _safe_int(post_summary.get("data_quality_gap_count")),
        "rejected_by_system_count": _safe_int(post_summary.get("rejected_by_system_count")),
        "qc_review_candidate_count": _safe_int(post_summary.get("qc_review_candidate_count")),
        "needs_review_count": _safe_int(post_summary.get("needs_review_count")),
        "raw_status_counts": json.dumps(raw_status_counts, ensure_ascii=False),
        "first_pass_display_status_counts": json.dumps(first_pass_display_counts, ensure_ascii=False),
        "adjudicated_display_status_counts": json.dumps(display_status_counts, ensure_ascii=False),
        "data_quality_flags": json.dumps(profile["data_quality_flags"], ensure_ascii=False),
    }
    issue_rows = _build_issue_rows(
        summary=summary,
        results=adjudicated,
        limit_per_bucket=limit_per_bucket,
    )
    raw = {
        "summary": summary,
        "postprocess_summary": post_summary,
        "pack_metrics": pack_metrics,
        "bundle_profile": profile,
        "raw_status_counts": raw_status_counts,
        "first_pass_display_status_counts": first_pass_display_counts,
        "adjudicated_display_status_counts": display_status_counts,
        "issues": issue_rows,
    }
    return summary, issue_rows, raw


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_float(value: Any) -> str:
    return f"{_safe_float(value):.2f}"


def _write_report(
    path: Path,
    *,
    summaries: list[dict[str, Any]],
    issue_rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    replacements: list[dict[str, Any]],
) -> None:
    count = len(summaries)
    avg_wall = sum(_safe_float(row.get("wall_clock_time")) for row in summaries) / count if count else 0.0
    avg_model = sum(_safe_float(row.get("total_processing_time")) for row in summaries) / count if count else 0.0
    max_wall = max((_safe_float(row.get("wall_clock_time")) for row in summaries), default=0.0)
    avg_calls = sum(_safe_int(row.get("llm_call_count")) for row in summaries) / count if count else 0.0
    terminal_leaks = sum(
        _safe_int(row.get("qc_review_candidate_count")) + _safe_int(row.get("needs_review_count"))
        for row in summaries
    )
    confirmed = [row for row in issue_rows if row.get("display_status") == "confirmed_defect"]
    data_gap = [row for row in issue_rows if row.get("display_status") == "data_quality_gap"]
    rejected = [row for row in issue_rows if row.get("display_status") == "rejected_by_system"]
    technical = [row for row in issue_rows if row.get("display_status") == "technical_error_internal"]
    confirmed_quality_counts = Counter(row.get("auto_quality_label") or "" for row in confirmed)
    rejected_quality_counts = Counter(row.get("auto_quality_label") or "" for row in rejected)
    provider_errors = sum(_safe_int(row.get("provider_error_count")) for row in summaries)
    timeout_errors = sum(_safe_int(row.get("timeout_count")) for row in summaries)
    rate_limit_errors = sum(_safe_int(row.get("rate_limit_count")) for row in summaries)

    lines = [
        "# 正式质控三病历二审裁决抽检报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 执行范围",
        "",
        f"- 实际完成：{count} 份病历；失败：{len(failures)} 份。",
        "- 链路：正式 final `fast_screen_full`，规则集 `sc_content_full_v1`，一审后接入 LLM 二审裁决。",
        "- 运行方式：只读脚本运行，不写医生整改/正式质控业务结果表；`job_id` 使用 `script-test-*` 诊断标识。",
        f"- 终态泄漏检查：`qc_review_candidate/needs_review` 合计 {terminal_leaks}，应为 0。",
        "",
        "## 性能摘要",
        "",
        f"- 平均墙钟耗时：{_format_float(avg_wall)}s；最慢墙钟耗时：{_format_float(max_wall)}s。",
        f"- 平均累计模型处理耗时：{_format_float(avg_model)}s；平均 LLM 调用/pack 数：{_format_float(avg_calls)}。",
        f"- provider_error={provider_errors}，timeout={timeout_errors}，rate_limit={rate_limit_errors}。",
        "",
        "## 四层分流摘要",
        "",
        f"- 确认缺陷：{len(confirmed)} 条。",
        f"- 数据缺口：{len(data_gap)} 条。",
        f"- 系统驳回：{len(rejected)} 条。",
        f"- 技术异常：{len(technical)} 条。",
        f"- 确认缺陷自动初评：{json.dumps(dict(confirmed_quality_counts), ensure_ascii=False)}。",
        f"- 系统驳回抽查提示：{json.dumps(dict(rejected_quality_counts), ensure_ascii=False)}。",
        "",
        "## 分病历结果",
        "",
        "| visit_id | patient_name | department | wall(s) | model(s) | tokens | pack/LLM | confirmed | data_gap | rejected | technical | raw_status | adjudicated_status |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in summaries:
        lines.append(
            "| {visit_id} | {patient_name} | {department} | {wall} | {model} | {tokens} | {packs} | {confirmed} | {data_gap} | {rejected} | {technical} | `{raw}` | `{display}` |".format(
                visit_id=row.get("visit_id", ""),
                patient_name=row.get("patient_name", ""),
                department=row.get("department", ""),
                wall=_format_float(row.get("wall_clock_time")),
                model=_format_float(row.get("total_processing_time")),
                tokens=row.get("total_tokens", 0),
                packs=row.get("llm_call_count", 0),
                confirmed=row.get("confirmed_defect_count", 0),
                data_gap=row.get("data_quality_gap_count", 0),
                rejected=row.get("rejected_by_system_count", 0),
                technical=row.get("technical_error_internal_count", 0),
                raw=row.get("raw_status_counts", "{}"),
                display=row.get("adjudicated_display_status_counts", "{}"),
            )
        )
    lines.extend(
        [
            "",
            "## 二审质量评估",
            "",
            "- 确认缺陷：本轮可作为页面候选，但并非全部都达到“无需抽查”的强证据标准；跨文书/时间链规则和一审直接确认项必须优先抽查。",
            "- 数据缺口：应对应缺源文书、医嘱、检查/检验、会诊或执行证据；不得归责医生。",
            "- 系统驳回：用于承接一审疑似问题但证据不足、规则要件不成立或自相矛盾的条目；需抽查是否误驳回真实缺陷。",
            "- 二审解释：以 `adjudicator_reason` 和 `adjudicator_supporting_quote` 为主要可追溯字段。",
            "",
            "## 当前结论",
            "",
        ]
    )
    can_expand = (
        count >= 3
        and terminal_leaks == 0
        and provider_errors == 0
        and timeout_errors == 0
        and rate_limit_errors == 0
    )
    if can_expand:
        lines.append("- 技术链路可以进入 10-20 份扩展抽检；但结果质量扩展前建议先标注本轮 confirmed/data_gap/rejected 样例，确认二审没有明显过严或误驳回。")
    else:
        lines.append("- 暂不建议扩大到 10-20 份：本轮仍存在终态泄漏、运行失败或 provider/timeout/rate_limit 风险，需要先收口。")
    weak_confirmed = sum(
        count
        for label, count in confirmed_quality_counts.items()
        if label
        not in {
            "confirmed_likely_showable",
        }
    )
    if confirmed and weak_confirmed == 0:
        lines.append("- 页面演示可以展示“确认缺陷/数据缺口/系统驳回/技术异常”四层结构，并可选取 confirmed_defect 作为结果质量样例。")
    elif confirmed:
        lines.append(f"- 页面可以演示四层结构和运行速度；但 {weak_confirmed}/{len(confirmed)} 条 confirmed_defect 仍建议先抽查，不宜直接作为“结果质量可交付”演示。")
    else:
        lines.append("- 页面可演示四层分流机制和速度；结果质量演示仍需更多 confirmed_defect 样例或人工确认。")
    lines.append("- 最大风险优先级：先看二审是否过严/误驳回，其次看数据缺口是否来自本地同步或 bundle 证据组织，再看 confirmed_defect 证据是否足够直接。")
    lines.append("- 下一步建议：如果 rejected 中存在真实缺陷，优先补 evidence 组织或二审 prompt；如果 data_gap 偏多，优先补同步/bundle；暂不调整主规则口径。")
    if replacements:
        lines.extend(["", "## 样本替换说明", ""])
        for item in replacements:
            lines.append(f"- {item.get('from_visit_id')} -> {item.get('to_visit_id')}：{item.get('reason')}")
    if failures:
        lines.extend(["", "## 失败样本", ""])
        for failure in failures:
            lines.append(f"- {failure.get('visit_id')}: {failure.get('error')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    requested = [item.strip() for item in args.visit_ids if item.strip()] or list(DEFAULT_VISIT_IDS)
    fallback = [item.strip() for item in args.fallback_visit_ids if item.strip()] or list(DEFAULT_FALLBACK_VISIT_IDS)
    candidates = requested + [item for item in fallback if item not in requested]
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    summaries: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    raw_runs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    replacements: list[dict[str, Any]] = []

    for visit_id in candidates:
        if len(summaries) >= args.limit:
            break
        try:
            summary, issues, raw = await _run_one_visit(
                visit_id=visit_id,
                visit_keys=visit_keys,
                rules_by_id=rules_by_id,
                pack_concurrency=args.pack_concurrency,
                limit_per_bucket=args.limit_per_bucket,
            )
            if visit_id not in requested and len(summaries) < args.limit:
                missing = requested[len(summaries)] if len(summaries) < len(requested) else "unknown"
                replacements.append(
                    {
                        "from_visit_id": missing,
                        "to_visit_id": visit_id,
                        "reason": "原候选运行失败或不足 3 份，使用 fallback 样本补足。",
                    }
                )
            summaries.append(summary)
            issue_rows.extend(issues)
            raw_runs.append(raw)
            print(
                "completed {visit_id}: wall={wall:.2f}s model={model:.2f}s display={display}".format(
                    visit_id=visit_id,
                    wall=_safe_float(summary.get("wall_clock_time")),
                    model=_safe_float(summary.get("total_processing_time")),
                    display=summary.get("adjudicated_display_status_counts"),
                )
            )
        except Exception as exc:
            failures.append({"visit_id": visit_id, "error": str(exc)})
            print(f"failed {visit_id}: {exc}")

    _write_csv(args.summary_csv, summaries)
    _write_json(
        args.summary_json,
        {
            "runs": summaries,
            "failures": failures,
            "replacements": replacements,
            "raw_runs": raw_runs,
        },
    )
    _write_csv(args.issue_csv, issue_rows)
    _write_json(
        args.issue_json,
        {
            "issues": issue_rows,
            "manual_quality_label_options": [
                "confirmed_reasonable",
                "data_gap_reasonable",
                "rejected_reasonable",
                "possible_false_reject",
                "possible_false_positive",
                "evidence_insufficient",
            ],
        },
    )
    _write_report(
        args.report_md,
        summaries=summaries,
        issue_rows=issue_rows,
        failures=failures,
        replacements=replacements,
    )
    print(f"wrote {args.summary_csv}")
    print(f"wrote {args.issue_csv}")
    print(f"wrote {args.report_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式 final fast_screen_full 三病历二审裁决只读抽检。")
    parser.add_argument("--visit-id", dest="visit_ids", action="append", default=[], help="可重复传入。")
    parser.add_argument("--fallback-visit-id", dest="fallback_visit_ids", action="append", default=[], help="可重复传入。")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--limit-per-bucket", type=int, default=30)
    parser.add_argument("--summary-csv", type=Path, default=DOCS_DIR / "formal_qc_three_visit_adjudicated_run_summary.csv")
    parser.add_argument("--summary-json", type=Path, default=DOCS_DIR / "formal_qc_three_visit_adjudicated_run_summary.json")
    parser.add_argument("--issue-csv", type=Path, default=DOCS_DIR / "formal_qc_three_visit_adjudicated_issue_review.csv")
    parser.add_argument("--issue-json", type=Path, default=DOCS_DIR / "formal_qc_three_visit_adjudicated_issue_review.json")
    parser.add_argument("--report-md", type=Path, default=DOCS_DIR / "正式质控三病历二审裁决抽检报告.md")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
