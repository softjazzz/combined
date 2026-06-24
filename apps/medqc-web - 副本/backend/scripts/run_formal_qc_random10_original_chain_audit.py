#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from run_formal_qc_aliyun_bailian_10_visit_audit import (  # noqa: E402
    DEFAULT_VISIT_IDS as PREVIOUS_FIXED_VISIT_IDS,
    _apply_gate,
    _load_sheet2_status,
)
from run_formal_qc_three_visit_adjudicated_audit import (  # noqa: E402
    _bundle_profile,
    _load_rules_by_id,
    _load_visit_keys,
    _run_one_visit,
    _safe_float,
    _safe_int,
    _safe_text,
    _write_csv,
    _write_json,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
SUMMARY_CSV = DOCS_DIR / "formal_qc_random10_original_chain_run_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_random10_original_chain_run_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_random10_original_chain_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_random10_original_chain_issue_review.json"
REPORT_MD = DOCS_DIR / "正式原链路随机10病历质控抽检报告.md"

REQUIRED_DISPLAY_STATUSES = {
    "confirmed_defect",
    "data_quality_gap",
    "rejected_by_system",
    "technical_error_internal",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _truncate(value: Any, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", _safe_text(value))
    return text[:limit]


def _sheet2_bucket(sheet2_status_counts: str) -> str:
    if not sheet2_status_counts:
        return "non_sheet2"
    try:
        counts = json.loads(sheet2_status_counts)
    except Exception:
        return "sheet2_unknown"
    if counts.get("exact_confirmed"):
        return "sheet2_exact"
    if counts.get("blocked_with_reason"):
        return "sheet2_blocked"
    if counts.get("skip"):
        return "sheet2_skip"
    return "sheet2_other"


def _has_short_or_empty_evidence(row: dict[str, Any]) -> bool:
    evidence = _safe_text(row.get("evidence"))
    quote = _safe_text(row.get("adjudicator_supporting_quote") or row.get("source_quote"))
    return len(evidence) < 30 and len(quote) < 20


def _quality_tags(row: dict[str, Any]) -> dict[str, Any]:
    display_status = _safe_text(row.get("display_status"))
    rule_id = _safe_text(row.get("rule_id")).upper()
    evidence = _safe_text(row.get("evidence"))
    quote = _safe_text(row.get("adjudicator_supporting_quote") or row.get("source_quote"))
    reason = _safe_text(row.get("adjudicator_reason") or row.get("postprocess_reason"))
    postprocess_label = _safe_text(row.get("postprocess_label"))
    evidence_problem = _safe_text(row.get("evidence_problem_type"))
    combined = f"{evidence} {quote} {reason} {postprocess_label} {evidence_problem}"

    evidence_too_short = len(evidence) < 30
    quote_missing = len(quote) < 20
    data_gap_terms = ("缺", "未提供", "无法判定", "缺少", "源文书", "医嘱单", "报告单", "执行记录", "bundle")
    rule_applicability_terms = ("不适用", "触发", "无相关", "未见", "规则不成立")
    cross_doc_rules = {"SC-036", "SC-038", "SC-070", "SC-074", "SC-083", "SC-100", "SC-107", "SC-118", "SC-123", "SC-125", "SC-143", "SC-146"}
    data_gap_likely = display_status == "data_quality_gap" or any(term in combined for term in data_gap_terms)
    rule_applicability_risk = rule_id in cross_doc_rules and (quote_missing or "触发" in combined or "不适用" in combined)
    possible_false_positive = (
        display_status == "confirmed_defect"
        and (evidence_too_short or quote_missing or "合规" in combined or "已记录" in combined)
    )
    likely_valid = (
        display_status == "confirmed_defect"
        and not evidence_too_short
        and not quote_missing
        and not possible_false_positive
        and not data_gap_likely
    )

    reasons: list[str] = []
    if likely_valid:
        reasons.append("证据和二审引用较完整，可作为候选缺陷复核。")
    if evidence_too_short:
        reasons.append("evidence 过短。")
    if quote_missing:
        reasons.append("supporting_quote 缺失或过短。")
    if rule_applicability_risk:
        reasons.append("跨文书/触发类规则存在适用性核查风险。")
    if data_gap_likely:
        reasons.append("更像同步、bundle、源文书或跨文书证据缺口。")
    if possible_false_positive:
        reasons.append("confirmed 证据强度不足或存在反向语义，疑似误报。")
    if not reasons:
        reasons.append("需人工按原文核对。")

    return {
        "likely_valid_candidate": likely_valid,
        "evidence_too_short": evidence_too_short,
        "quote_missing": quote_missing,
        "rule_applicability_risk": rule_applicability_risk,
        "data_gap_likely_sync_or_bundle": data_gap_likely,
        "possible_false_positive": possible_false_positive,
        "needs_manual_review_reason": " ".join(reasons),
    }


def _is_duplicate(row: dict[str, Any], seen: Counter[str]) -> bool:
    key = "|".join(
        [
            _safe_text(row.get("visit_id")),
            _safe_text(row.get("rule_id")),
            _truncate(row.get("conclusion"), 120),
            _truncate(row.get("evidence"), 120),
        ]
    )
    seen[key] += 1
    return seen[key] > 1


def _normalize_issue_rows(
    issue_rows: list[dict[str, Any]],
    *,
    summary_by_visit: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: Counter[str] = Counter()
    for row in issue_rows:
        display_status = _safe_text(row.get("display_status"))
        if display_status not in REQUIRED_DISPLAY_STATUSES:
            continue
        summary = summary_by_visit.get(_safe_text(row.get("visit_id")), {})
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        rule_pack = _safe_text(row.get("pack_id") or row.get("rule_pack") or metadata.get("pack_id"))
        source_quote = _safe_text(row.get("adjudicator_supporting_quote") or row.get("supporting_quote") or row.get("evidence"))
        item = {
            "visit_id": row.get("visit_id", ""),
            "patient_name": row.get("patient_name", ""),
            "department": row.get("department", ""),
            "rule_id": row.get("rule_id", ""),
            "rule_name": row.get("rule_name", ""),
            "display_status": display_status,
            "display_bucket": row.get("display_bucket", ""),
            "severity": row.get("severity") or ("high" if display_status == "confirmed_defect" else "medium"),
            "confidence": row.get("confidence", ""),
            "document_type": row.get("target_document_type") or row.get("document_type") or "",
            "evidence_family": row.get("evidence_family") or rule_pack,
            "rule_pack": rule_pack,
            "conclusion": row.get("findings") or row.get("conclusion") or "",
            "evidence": row.get("evidence") or "",
            "suggestion": row.get("suggestion") or "",
            "postprocess_label": row.get("postprocess_label") or "",
            "can_show_as_defect": row.get("can_show_as_defect", ""),
            "internal_only": row.get("internal_only", ""),
            "provider_error": summary.get("provider_error_count", 0),
            "timeout": summary.get("timeout_count", 0),
            "parse_error": summary.get("parse_error_count", 0),
            "model_tokens": summary.get("total_tokens", 0),
            "wall_clock_time": summary.get("wall_clock_time", 0),
            "source_quote": source_quote,
            "supporting_quote": source_quote,
            "adjudicator_reason": row.get("adjudicator_reason", ""),
            "postprocess_reason": row.get("postprocess_reason", ""),
        }
        item.update(_quality_tags({**row, **item}))
        item["is_suspected_duplicate"] = _is_duplicate(item, seen)
        normalized.append(item)
    return normalized


def _profile_visit(visit_id: str, visit_row: dict[str, str]) -> dict[str, Any] | None:
    patient_id = _safe_text(visit_row.get("patient_id"))
    institute_id = _safe_text(visit_row.get("institute_id"))
    if not (patient_id and institute_id and visit_id):
        return None
    try:
        bundle = assemble_final_record_bundle(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema="cdm",
        )
    except Exception:
        return None
    profile = _bundle_profile(bundle)
    if _safe_int(profile.get("source_document_with_text_count")) <= 0:
        return None
    return {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(visit_row.get("name")),
        "department": _safe_text(visit_row.get("discharge_dept_name") or visit_row.get("admission_dept_name")),
        "is_surgery": bool(profile.get("is_surgery")),
        "has_consultation": bool(profile.get("has_consultation")),
        "has_many_exam_lab_abnormal": _safe_int(profile.get("abnormal_keyword_hit_count")) >= 8,
        "bundle_status": "final_bundle_available",
        "source_document_with_text_count": _safe_int(profile.get("source_document_with_text_count")),
        "document_hit_count": _safe_int(profile.get("document_hit_count")),
        "document_missing_count": _safe_int(profile.get("document_missing_count")),
        "abnormal_keyword_hit_count": _safe_int(profile.get("abnormal_keyword_hit_count")),
    }


def _load_excluded_visit_ids(args: argparse.Namespace) -> set[str]:
    excluded: set[str] = set()
    for raw in _safe_text(getattr(args, "exclude_visit_ids", "")).split(","):
        value = raw.strip()
        if value:
            excluded.add(value)
    path = getattr(args, "exclude_visit_ids_file", None)
    if path and Path(path).exists():
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        containers: list[Any] = []
        if isinstance(payload, dict):
            for key in ("selected_profiles", "summaries", "rows", "issues", "visit_ids"):
                value = payload.get(key)
                if isinstance(value, list):
                    containers.extend(value)
        elif isinstance(payload, list):
            containers.extend(payload)
        for item in containers:
            if isinstance(item, dict) and item.get("visit_id"):
                excluded.add(_safe_text(item.get("visit_id")))
            elif item:
                excluded.add(_safe_text(item))
    return excluded


def _select_random_visits(args: argparse.Namespace) -> tuple[list[str], list[dict[str, Any]]]:
    visit_keys = _load_visit_keys()
    sheet2_status = _load_sheet2_status()
    explicit_visit_ids = [
        item.strip()
        for item in _safe_text(getattr(args, "visit_ids", "")).split(",")
        if item.strip()
    ]
    if explicit_visit_ids:
        selected_profiles: list[dict[str, Any]] = []
        for visit_id in explicit_visit_ids:
            visit_row = visit_keys.get(visit_id)
            if not visit_row:
                raise RuntimeError(f"visit_id 不存在或未同步：{visit_id}")
            profile = _profile_visit(visit_id, visit_row)
            if not profile:
                raise RuntimeError(f"visit_id 无可运行 final bundle：{visit_id}")
            profile.update(sheet2_status.get(visit_id, {}))
            profile["sheet2_bucket"] = _sheet2_bucket(_safe_text(profile.get("sheet2_status_counts")))
            profile["is_previous_fixed_sample"] = visit_id in set(PREVIOUS_FIXED_VISIT_IDS)
            profile["is_excluded_sample"] = False
            selected_profiles.append(profile)
        return explicit_visit_ids, selected_profiles

    rng = random.Random(args.random_seed)
    previous = set(PREVIOUS_FIXED_VISIT_IDS)
    excluded = _load_excluded_visit_ids(args)
    candidates = list(visit_keys.items())
    rng.shuffle(candidates)

    profiled: list[dict[str, Any]] = []
    fallback_profiled: list[dict[str, Any]] = []
    max_scan = max(args.max_scan, args.limit * 6)
    for visit_id, visit_row in candidates:
        if visit_id in excluded:
            continue
        profile = _profile_visit(visit_id, visit_row)
        if not profile:
            continue
        sheet2 = sheet2_status.get(visit_id, {})
        profile.update(sheet2)
        profile["sheet2_bucket"] = _sheet2_bucket(_safe_text(profile.get("sheet2_status_counts")))
        profile["is_previous_fixed_sample"] = visit_id in previous
        profile["is_excluded_sample"] = visit_id in excluded
        if visit_id in previous:
            fallback_profiled.append(profile)
        else:
            profiled.append(profile)
        if len(profiled) >= max_scan:
            break

    selected: list[dict[str, Any]] = []

    def add_where(predicate: Any, needed: int) -> None:
        nonlocal selected
        for row in profiled + fallback_profiled:
            if len([item for item in selected if predicate(item)]) >= needed:
                return
            if row["visit_id"] not in {item["visit_id"] for item in selected} and predicate(row):
                selected.append(row)

    add_where(lambda row: bool(row.get("is_surgery")), 4)
    add_where(lambda row: not bool(row.get("is_surgery")), 3)
    add_where(lambda row: bool(row.get("has_consultation")), 4)
    add_where(lambda row: not bool(row.get("has_consultation")), 2)
    add_where(lambda row: row.get("sheet2_bucket") == "sheet2_exact", 2)
    add_where(lambda row: row.get("sheet2_bucket") == "sheet2_blocked", 2)
    add_where(lambda row: bool(row.get("has_many_exam_lab_abnormal")), 2)

    for row in profiled + fallback_profiled:
        if len(selected) >= args.limit:
            break
        if row["visit_id"] not in {item["visit_id"] for item in selected}:
            selected.append(row)

    selected = selected[: args.limit]
    if len(selected) < args.limit:
        raise RuntimeError(f"可运行 final bundle 病历不足：选中 {len(selected)}，预期 {args.limit}")
    return [row["visit_id"] for row in selected], selected


def _summary_metrics(summaries: list[dict[str, Any]], issues: list[dict[str, Any]]) -> dict[str, Any]:
    total_wall = sum(_safe_float(row.get("wall_clock_time")) for row in summaries)
    total_tokens = sum(_safe_int(row.get("total_tokens")) for row in summaries)
    total_calls = sum(_safe_int(row.get("llm_call_count")) for row in summaries)
    return {
        "visit_count": len(summaries),
        "total_wall_clock_time": round(total_wall, 3),
        "avg_wall_clock_time": round(total_wall / len(summaries), 3) if summaries else 0,
        "max_wall_clock_time": max((_safe_float(row.get("wall_clock_time")) for row in summaries), default=0),
        "total_tokens": total_tokens,
        "avg_tokens": round(total_tokens / len(summaries), 1) if summaries else 0,
        "llm_call_count": total_calls,
        "provider_error": sum(_safe_int(row.get("provider_error_count")) for row in summaries),
        "upstream_http_error": sum(_safe_int(row.get("upstream_http_error_count")) for row in summaries),
        "parse_error": sum(_safe_int(row.get("parse_error_count")) for row in summaries),
        "timeout": sum(_safe_int(row.get("timeout_count")) for row in summaries),
        "rate_limit": sum(_safe_int(row.get("rate_limit_count")) for row in summaries),
        "technical_error_internal": sum(_safe_int(row.get("technical_error_internal_count")) for row in summaries),
        "display_status_counts": dict(Counter(_safe_text(row.get("display_status")) for row in issues)),
        "rule_hit_counts": dict(Counter(_safe_text(row.get("rule_id")) for row in issues)),
        "short_or_empty_evidence_count": sum(1 for row in issues if _has_short_or_empty_evidence(row)),
        "suspected_duplicate_count": sum(1 for row in issues if str(row.get("is_suspected_duplicate")).lower() == "true"),
        "confirmed_evidence_risk_count": sum(
            1
            for row in issues
            if row.get("display_status") == "confirmed_defect"
            and (row.get("evidence_too_short") or row.get("quote_missing") or row.get("possible_false_positive"))
        ),
    }


def _write_report(
    path: Path,
    *,
    selected_profiles: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    metrics: dict[str, Any],
    random_seed: int,
) -> None:
    status = "failed_provider_unstable" if failures or any(_safe_text(row.get("stability_status")) != "provider_stability_pass" for row in summaries) else "completed"
    confirmed = [row for row in issues if row.get("display_status") == "confirmed_defect"]
    data_gap = [row for row in issues if row.get("display_status") == "data_quality_gap"]
    rejected = [row for row in issues if row.get("display_status") == "rejected_by_system"]
    repeat_count = sum(1 for row in selected_profiles if row.get("is_previous_fixed_sample"))
    lines = [
        "# 正式原链路随机10病历质控抽检报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 范围",
        "",
        "- 本轮使用当前正式 final `fast_screen_full` / `sc_content_full_v1` 原链路，只读运行。",
        "- 未使用 structured evidence POC 脚本，未接页面，未写正式业务结果表。",
        f"- 随机种子：`{random_seed}`；与之前固定 10 病历重复数：{repeat_count}。",
        f"- report_status：`{status}`。",
        "",
        "## 抽样清单",
        "",
        "| visit_id | patient | dept | surgery | consultation | abnormal | bundle | Sheet2 | repeated_fixed |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in selected_profiles:
        lines.append(
            f"| {row.get('visit_id')} | {row.get('patient_name')} | {row.get('department')} | {row.get('is_surgery')} | {row.get('has_consultation')} | {row.get('has_many_exam_lab_abnormal')} | {row.get('bundle_status')} | `{row.get('sheet2_bucket')}` | {row.get('is_previous_fixed_sample')} |"
        )
    lines.extend(
        [
            "",
            "## 运行统计",
            "",
            f"- 10 病历总耗时：{metrics['total_wall_clock_time']}s；平均耗时：{metrics['avg_wall_clock_time']}s；最慢耗时：{metrics['max_wall_clock_time']}s。",
            f"- LLM 调用数：{metrics['llm_call_count']}；token 总数：{metrics['total_tokens']}；平均 token：{metrics['avg_tokens']}。",
            f"- provider_error={metrics['provider_error']}，upstream_http_error={metrics['upstream_http_error']}，parse_error={metrics['parse_error']}，timeout={metrics['timeout']}，rate_limit={metrics['rate_limit']}，technical_error_internal={metrics['technical_error_internal']}。",
            f"- display_status 分布：`{_json(metrics['display_status_counts'])}`。",
            f"- evidence 为空或过短：{metrics['short_or_empty_evidence_count']}；疑似重复问题：{metrics['suspected_duplicate_count']}。",
            f"- confirmed_defect 中证据不足自动初筛：{metrics['confirmed_evidence_risk_count']}。",
            "",
            "## 分层数量",
            "",
            f"- confirmed_defect：{len(confirmed)}。",
            f"- data_quality_gap：{len(data_gap)}。",
            f"- rejected_by_system：{len(rejected)}。",
            "",
            "## rule_id 命中次数",
            "",
        ]
    )
    for rule_id, count in Counter(row.get("rule_id") for row in issues).most_common(30):
        lines.append(f"- `{rule_id}`：{count}")
    lines.extend(["", "## confirmed_defect 明细", ""])
    for row in confirmed:
        lines.append(
            f"- `{row.get('visit_id')}` `{row.get('rule_id')}` {row.get('rule_name')}：{_truncate(row.get('conclusion'), 180)}；quote={_truncate(row.get('supporting_quote'), 180)}；auto={row.get('needs_manual_review_reason')}"
        )
    lines.extend(["", "## rejected_by_system 抽样复核清单", ""])
    for row in rejected[:50]:
        lines.append(
            f"- `{row.get('visit_id')}` `{row.get('rule_id')}` {row.get('rule_name')}：{_truncate(row.get('adjudicator_reason') or row.get('postprocess_reason'), 220)}；auto={row.get('needs_manual_review_reason')}"
        )
    lines.extend(["", "## 质量结论口径", ""])
    if status != "completed":
        lines.append("- 本轮存在 provider/timeout/parse/technical_error 或运行失败，仅保留运行诊断，不做质量结论。")
    else:
        lines.append("- 本轮稳定性通过，可交外部复核 confirmed_defect / data_quality_gap / rejected_by_system 合理性。")
        lines.append("- 自动初筛标签仅辅助复核，不改变正式结果。")
    if failures:
        lines.extend(["", "## 失败项", ""])
        for row in failures:
            lines.append(f"- `{row.get('visit_id')}`：{row.get('error')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    visit_ids, selected_profiles = _select_random_visits(args)
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    sheet2_status = _load_sheet2_status()
    summaries: list[dict[str, Any]] = []
    raw_issue_rows: list[dict[str, Any]] = []
    raw_runs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for visit_id in visit_ids:
        try:
            summary, issue_rows, raw = await _run_one_visit(
                visit_id=visit_id,
                visit_keys=visit_keys,
                rules_by_id=rules_by_id,
                pack_concurrency=args.pack_concurrency,
                limit_per_bucket=args.limit_per_bucket,
            )
            summary.update(sheet2_status.get(visit_id, {}))
            summary = _apply_gate(summary, raw)
            for row in issue_rows:
                row.update(
                    {
                        "stability_status": summary["stability_status"],
                        "sheet2_status_counts": summary.get("sheet2_status_counts", "{}"),
                        "department": summary.get("department", ""),
                    }
                )
            summaries.append(summary)
            raw_issue_rows.extend(issue_rows)
            raw_runs.append(raw)
            print(
                json.dumps(
                    {
                        "visit_id": visit_id,
                        "stability_status": summary.get("stability_status"),
                        "tokens": summary.get("total_tokens"),
                        "confirmed": summary.get("confirmed_defect_count"),
                        "data_gap": summary.get("data_quality_gap_count"),
                        "rejected": summary.get("rejected_by_system_count"),
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:
            failures.append({"visit_id": visit_id, "error": str(exc)})
            print(f"failed {visit_id}: {exc}")

    summary_by_visit = {_safe_text(row.get("visit_id")): row for row in summaries}
    issues = _normalize_issue_rows(raw_issue_rows, summary_by_visit=summary_by_visit)
    metrics = _summary_metrics(summaries, issues)
    report_status = "completed" if not failures and all(row.get("stability_status") == "provider_stability_pass" for row in summaries) else "failed_provider_unstable"
    payload = {
        "report_status": report_status,
        "script": "run_formal_qc_random10_original_chain_audit.py",
        "mode": "formal_final_fast_screen_full_original_chain_readonly",
        "rule_set_key": "sc_content_full_v1",
        "pack_concurrency": args.pack_concurrency,
        "random_seed": args.random_seed,
        "exclude_visit_ids": sorted(_load_excluded_visit_ids(args)),
        "selected_profiles": selected_profiles,
        "metrics": metrics,
        "summaries": summaries,
        "issues": issues,
        "failures": failures,
        "raw_runs": raw_runs,
    }
    _write_csv(args.summary_csv, summaries)
    _write_json(args.summary_json, payload)
    _write_csv(args.issue_csv, issues)
    _write_json(args.issue_json, {"report_status": report_status, "metrics": metrics, "issues": issues})
    _write_report(
        args.report_md,
        selected_profiles=selected_profiles,
        summaries=summaries,
        issues=issues,
        failures=failures,
        metrics=metrics,
        random_seed=args.random_seed,
    )
    print(f"wrote {args.summary_csv}")
    print(f"wrote {args.issue_csv}")
    print(f"wrote {args.report_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式原链路 final fast_screen_full 随机 10 病历只读质控抽检。")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--visit-ids", default="", help="逗号分隔的 visit_id；传入后跳过随机抽样，按指定病历只读运行。")
    parser.add_argument("--max-scan", type=int, default=80)
    parser.add_argument("--random-seed", type=int, default=20260515)
    parser.add_argument("--exclude-visit-ids", default="", help="逗号分隔的 visit_id 排除列表，用于避免重复抽样。")
    parser.add_argument("--exclude-visit-ids-file", type=Path, help="从既有 summary/issue JSON 中读取 visit_id 并排除。")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--limit-per-bucket", type=int, default=999)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--issue-csv", type=Path, default=ISSUE_CSV)
    parser.add_argument("--issue-json", type=Path, default=ISSUE_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
