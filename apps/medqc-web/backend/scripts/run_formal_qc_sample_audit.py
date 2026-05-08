#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import (  # noqa: E402
    _extract_bundle_documents,
    get_fast_screen_full_rule_ids,
    run_final_fast_screen,
)
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
RELEASE_MR = REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto" / "mr.csv"
SHEET2_MATRIX = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sheet2_exact_review_matrix.csv"
DEFAULT_VISIT_IDS = ["1915580", "2024757", "2246915", "2287309", "2311318"]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate(value: Any, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", _safe_text(value))
    return text[:limit]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _load_visit_keys() -> dict[str, dict[str, str]]:
    return {_safe_text(row.get("visit_id")): row for row in _read_csv_rows(RELEASE_MR) if _safe_text(row.get("visit_id"))}


def _load_sheet2_status() -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in _read_csv_rows(SHEET2_MATRIX):
        visit_id = _safe_text(row.get("visit_id"))
        if not visit_id:
            continue
        item = grouped.setdefault(
            visit_id,
            {
                "sample_ids": [],
                "exact_count": 0,
                "blocked_count": 0,
                "skip_count": 0,
                "statuses": Counter(),
            },
        )
        sample_id = _safe_text(row.get("sheet2_row_id"))
        status = _safe_text(row.get("exact_review_status"))
        if sample_id:
            item["sample_ids"].append(sample_id)
        item["statuses"][status] += 1
        if status == "exact_confirmed":
            item["exact_count"] += 1
        elif status == "blocked_with_reason":
            item["blocked_count"] += 1
        elif status == "skip":
            item["skip_count"] += 1
    for item in grouped.values():
        item["statuses"] = dict(item["statuses"])
    return grouped


def _bundle_profile(bundle: dict[str, Any]) -> dict[str, Any]:
    hits = dict(bundle.get("document_hits") or {})
    source_docs = [dict(item) for item in list(bundle.get("source_documents") or []) if isinstance(item, dict)]
    docs_with_text = [item for item in source_docs if _safe_text(item.get("content"))]
    source_tables = Counter(_safe_text(item.get("source_table")) for item in docs_with_text if _safe_text(item.get("source_table")))
    text = "\n".join(_safe_text(item.get("content")) for item in docs_with_text)
    abnormal_keywords = ["异常", "阳性", "偏高", "偏低", "危急", "感染", "结节", "积液", "梗", "骨折", "肾功", "低钾"]
    abnormal_hit_count = sum(text.count(keyword) for keyword in abnormal_keywords)
    surgery_tables = {
        "mr_surgery",
        "surgery_record",
        "anesthesia_record",
        "presurg_summary",
        "presurg_discussion",
        "postsurg_firstcourse_record",
        "surgery_safecheck_record",
        "surgery_inventory_record",
    }
    return {
        "document_hit_count": sum(1 for value in hits.values() if bool(value)),
        "document_missing_count": sum(1 for value in hits.values() if not bool(value)),
        "document_hits": hits,
        "data_quality_flags": list(bundle.get("data_quality_flags") or []),
        "source_document_count": len(source_docs),
        "source_document_with_text_count": len(docs_with_text),
        "source_tables": dict(source_tables),
        "is_surgery": any(bool(hits.get(table)) for table in surgery_tables),
        "has_consultation": bool(hits.get("consultation_record")),
        "has_blood": bool(hits.get("bloodtrans_record") or hits.get("blood_application")),
        "has_critical_value": bool(hits.get("crisis_value_record")),
        "abnormal_keyword_hit_count": abnormal_hit_count,
        "has_many_exam_lab_abnormal": abnormal_hit_count >= 8,
    }


def _result_counts(results: list[dict[str, Any]]) -> Counter:
    return Counter(_safe_text(item.get("status")) or "unknown" for item in results)


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("metadata")
    return dict(meta) if isinstance(meta, dict) else {}


def _duplicate_flags(items: list[dict[str, Any]]) -> dict[int, bool]:
    normalized: dict[str, list[int]] = defaultdict(list)
    for idx, item in enumerate(items):
        key = "|".join(
            [
                _safe_text(item.get("rule_id")),
                _safe_text(item.get("status")),
                _truncate(item.get("findings"), 120),
                _truncate(item.get("evidence"), 120),
            ]
        )
        normalized[key].append(idx)
    return {idx: len(indexes) > 1 for indexes in normalized.values() for idx in indexes}


def _build_issue_rows(
    *,
    visit_row: dict[str, Any],
    results: list[dict[str, Any]],
    data_quality_flags: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    candidates = [
        dict(item)
        for item in results
        if _safe_text(item.get("status")) in {"non_compliant", "uncertain"}
    ]
    candidates.sort(key=lambda item: (0 if _safe_text(item.get("status")) == "non_compliant" else 1, _safe_text(item.get("rule_id"))))
    candidates = candidates[: max(1, limit)]
    dup_map = _duplicate_flags(candidates)
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates):
        meta = _metadata(item)
        evidence = _safe_text(item.get("evidence"))
        rows.append(
            {
                "visit_id": visit_row["visit_id"],
                "patient_id": visit_row.get("patient_id", ""),
                "patient_name": visit_row.get("patient_name", ""),
                "rule_id": _safe_text(item.get("rule_id")),
                "rule_name": _safe_text(item.get("rule_name")),
                "status": _safe_text(item.get("status")),
                "confidence": item.get("confidence", ""),
                "target_document_type": _safe_text(item.get("target_document_type") or meta.get("target_document_type")),
                "findings": _truncate(item.get("findings")),
                "evidence": _truncate(evidence),
                "suggestion": _truncate(item.get("suggestion")),
                "evidence_verified": "yes" if len(evidence) >= 8 else "no",
                "pack_id": _safe_text(meta.get("pack_id")),
                "data_quality_flags": json.dumps(data_quality_flags, ensure_ascii=False),
                "suspected_duplicate": "yes" if dup_map.get(idx) else "no",
                "review_label": "",
                "review_note": "",
            }
        )
    return rows


async def _run_one_visit(
    *,
    visit_id: str,
    visit_keys: dict[str, dict[str, str]],
    sheet2_status: dict[str, dict[str, Any]],
    pack_concurrency: int,
    issue_limit: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id，无法运行正式质控")

    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    profile = _bundle_profile(bundle)
    qc_service = SichuanQCService()
    result = await run_final_fast_screen(
        qc_service=qc_service,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
        rule_ids=list(get_fast_screen_full_rule_ids()),
        quality_profile="throughput_v1",
        batch_output_mode="minimal",
        pack_concurrency=pack_concurrency,
    )
    results = [dict(item) for item in list(result.get("evaluation_results") or []) if isinstance(item, dict)]
    counts = _result_counts(results)
    token_usage = dict(result.get("token_usage") or {})
    pack_metrics = dict(result.get("pack_metrics") or {})
    sheet2 = sheet2_status.get(visit_id, {})
    summary = {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("name")),
        "sample_ids": ",".join(sheet2.get("sample_ids", [])),
        "sheet2_exact_count": int(sheet2.get("exact_count") or 0),
        "sheet2_blocked_count": int(sheet2.get("blocked_count") or 0),
        "sheet2_skip_count": int(sheet2.get("skip_count") or 0),
        "is_surgery": profile["is_surgery"],
        "has_consultation": profile["has_consultation"],
        "has_blood": profile["has_blood"],
        "has_critical_value": profile["has_critical_value"],
        "has_many_exam_lab_abnormal": profile["has_many_exam_lab_abnormal"],
        "abnormal_keyword_hit_count": profile["abnormal_keyword_hit_count"],
        "bundle_document_hit_count": profile["document_hit_count"],
        "bundle_document_missing_count": profile["document_missing_count"],
        "source_document_count": profile["source_document_count"],
        "source_document_with_text_count": profile["source_document_with_text_count"],
        "llm_call_count": int(pack_metrics.get("total_packs") or 0)
        + int(pack_metrics.get("single_rule_retries") or 0)
        + int(pack_metrics.get("probe_calls") or 0),
        "pack_count": int(pack_metrics.get("total_packs") or 0),
        "wall_clock_time": float(pack_metrics.get("wall_clock_time") or result.get("api_time") or 0.0),
        "total_tokens": int(token_usage.get("total_tokens") or 0),
        "prompt_tokens": int(token_usage.get("prompt_tokens") or 0),
        "completion_tokens": int(token_usage.get("completion_tokens") or 0),
        "non_compliant_count": int(counts.get("non_compliant") or 0),
        "uncertain_count": int(counts.get("uncertain") or 0),
        "compliant_count": int(counts.get("compliant") or 0),
        "not_applicable_count": int(counts.get("not_applicable") or 0),
        "provider_error_count": int(pack_metrics.get("provider_error_count") or 0),
        "timeout_count": int(pack_metrics.get("timeout_count") or 0),
        "rate_limit_count": int(pack_metrics.get("rate_limit_count") or 0),
        "configured_concurrency": int(pack_metrics.get("configured_concurrency") or pack_concurrency),
        "observed_max_concurrency": int(pack_metrics.get("observed_max_concurrency") or 0),
        "slowest_pack": _safe_text(pack_metrics.get("slowest_pack")),
        "slowest_pack_api_time": float(pack_metrics.get("slowest_pack_api_time") or 0.0),
        "data_quality_flags": json.dumps(profile["data_quality_flags"], ensure_ascii=False),
    }
    issue_rows = _build_issue_rows(
        visit_row=summary,
        results=results,
        data_quality_flags=profile["data_quality_flags"],
        limit=issue_limit,
    )
    raw = {
        "summary": summary,
        "issue_rows": issue_rows,
        "pack_metrics": pack_metrics,
        "bundle_profile": profile,
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
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "0.00"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def _as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _write_report(path: Path, summaries: list[dict[str, Any]], issue_rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    count = len(summaries)
    avg_time = sum(float(row.get("wall_clock_time") or 0.0) for row in summaries) / count if count else 0.0
    max_time = max((float(row.get("wall_clock_time") or 0.0) for row in summaries), default=0.0)
    avg_calls = sum(int(row.get("llm_call_count") or 0) for row in summaries) / count if count else 0.0
    provider_errors = sum(_as_int(row.get("provider_error_count")) for row in summaries)
    timeout_errors = sum(_as_int(row.get("timeout_count")) for row in summaries)
    rate_limit_errors = sum(_as_int(row.get("rate_limit_count")) for row in summaries)
    duplicate_count = sum(1 for row in issue_rows if row.get("suspected_duplicate") == "yes")
    evidence_missing = sum(1 for row in issue_rows if row.get("evidence_verified") != "yes")
    surgery_count = sum(1 for row in summaries if _as_bool(row.get("is_surgery")))
    non_surgery_count = sum(1 for row in summaries if not _as_bool(row.get("is_surgery")))
    consult_count = sum(1 for row in summaries if _as_bool(row.get("has_consultation")))
    no_consult_count = sum(1 for row in summaries if not _as_bool(row.get("has_consultation")))
    blood_count = sum(1 for row in summaries if _as_bool(row.get("has_blood")))
    abnormal_count = sum(1 for row in summaries if _as_bool(row.get("has_many_exam_lab_abnormal")))
    can_expand = provider_errors == 0 and timeout_errors == 0 and rate_limit_errors == 0
    lines = [
        "# 正式全量质控小样本抽检报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 抽检范围",
        "",
        f"- 实际完成：{count} 份病历；失败：{len(failures)} 份。",
        f"- 默认链路：正式 final `fast_screen_full`，`pack_concurrency=3`，只读运行，不写业务结果表。",
        f"- 覆盖手术病历：{surgery_count}；非手术病历：{non_surgery_count}；会诊病历：{consult_count}；无会诊病历：{no_consult_count}；输血相关：{blood_count}；检查检验异常较多：{abnormal_count}。",
        "",
        "## 性能与稳定性",
        "",
        f"- 平均耗时：{_format_float(avg_time)}s；最慢耗时：{_format_float(max_time)}s；平均 LLM 调用：{_format_float(avg_calls)} 次。",
        f"- provider_error={provider_errors}，timeout={timeout_errors}，rate_limit={rate_limit_errors}。",
        "",
        "## 结果质量初筛",
        "",
        f"- 导出待人工复核问题：{len(issue_rows)} 条，包含每份病历前 20 条 `non_compliant/uncertain`。",
        f"- evidence 为空或过短：{evidence_missing} 条；疑似重复：{duplicate_count} 条。",
        "- `review_label` 预留给人工填写，可选值：`accurate`、`acceptable`、`false_positive`、`evidence_insufficient`、`duplicate`、`needs_rule_tuning`。",
        "",
        "## 分病历摘要",
        "",
        "| visit_id | 类型覆盖 | wall(s) | tokens | LLM calls | non_compliant | uncertain | provider/rate/timeout |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summaries:
        types = []
        if _as_bool(row.get("is_surgery")):
            types.append("手术")
        else:
            types.append("非手术")
        if _as_bool(row.get("has_consultation")):
            types.append("会诊")
        else:
            types.append("无会诊")
        if _as_bool(row.get("has_blood")):
            types.append("输血")
        if _as_bool(row.get("has_many_exam_lab_abnormal")):
            types.append("异常较多")
        if _as_int(row.get("sheet2_exact_count")) > 0:
            types.append("Sheet2 exact")
        if _as_int(row.get("sheet2_blocked_count")) > 0:
            types.append("Sheet2 blocked")
        lines.append(
            f"| {row.get('visit_id')} | {','.join(types) or '普通'} | {_format_float(row.get('wall_clock_time'))} | {row.get('total_tokens')} | {row.get('llm_call_count')} | {row.get('non_compliant_count')} | {row.get('uncertain_count')} | {row.get('provider_error_count')}/{row.get('rate_limit_count')}/{row.get('timeout_count')} |"
        )
    lines.extend(
        [
            "",
            "## 验收问题回答",
            "",
            f"1. 本轮实际跑了 {count} 份病历，覆盖非手术 {non_surgery_count} 份、手术 {surgery_count} 份、会诊 {consult_count} 份、无会诊 {no_consult_count} 份，并包含 Sheet2 exact 与 blocked 样本。",
            f"2. 平均耗时 {_format_float(avg_time)}s，最慢 {_format_float(max_time)}s，平均 LLM 调用 {_format_float(avg_calls)} 次。",
            "3. `non_compliant/uncertain` 数量见分病历摘要；是否异常需后续医生/质控科在 review CSV 中标注。",
            f"4. evidence 初筛：{len(issue_rows) - evidence_missing}/{len(issue_rows)} 条具备可读 evidence；短证据条目需人工优先复核。",
            f"5. provider/rate limit/timeout 错误合计：{provider_errors}/{rate_limit_errors}/{timeout_errors}。",
            f"6. 疑似重复问题 {duplicate_count} 条；当前仅基于规则+发现+证据文本归一化初筛。",
            "7. 明显误报高风险规则需人工填写 `review_label=false_positive` 后再汇总，不在本轮自动判定。",
            "8. 建议先完成本轮人工标注；若 provider 错误清零且 accurate/acceptable 占比可接受，再扩大到 20 份。",
            "9. 客户现场正式演示建议分两步：可先演示并发运行链路；结果质量演示需等待人工标注与 provider 错误复跑确认。",
        ]
    )
    if not can_expand:
        lines.extend(
            [
                "",
                "## 收口风险",
                "",
                f"- 本轮存在 provider/rate/timeout={provider_errors}/{rate_limit_errors}/{timeout_errors}，不建议直接扩大 20 份或直接做结果质量演示。",
                "- 建议对出现 provider 错误的样本单独复跑一次，确认是偶发 provider 响应异常还是稳定规则/pack 问题。",
            ]
        )
    if failures:
        lines.extend(["", "## 失败样本", ""])
        for failure in failures:
            lines.append(f"- {failure.get('visit_id')}: {failure.get('error')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    visit_ids = [item.strip() for item in args.visit_ids if item.strip()]
    if not visit_ids:
        visit_ids = DEFAULT_VISIT_IDS[: args.limit]
    else:
        visit_ids = visit_ids[: args.limit]
    visit_keys = _load_visit_keys()
    sheet2_status = _load_sheet2_status()

    summaries: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    raw_runs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for visit_id in visit_ids:
        try:
            summary, issues, raw = await _run_one_visit(
                visit_id=visit_id,
                visit_keys=visit_keys,
                sheet2_status=sheet2_status,
                pack_concurrency=args.pack_concurrency,
                issue_limit=args.issue_limit,
            )
            summaries.append(summary)
            issue_rows.extend(issues)
            raw_runs.append(raw)
            print(f"completed {visit_id}: {summary['wall_clock_time']:.2f}s, issues={len(issues)}")
        except Exception as exc:
            failures.append({"visit_id": visit_id, "error": str(exc)})
            print(f"failed {visit_id}: {exc}")

    _write_csv(args.summary_csv, summaries)
    _write_json(args.summary_json, {"runs": summaries, "failures": failures, "raw_runs": raw_runs})
    _write_csv(args.issue_csv, issue_rows)
    _write_json(args.issue_json, {"issues": issue_rows, "review_label_options": REVIEW_LABEL_OPTIONS})
    _write_report(args.report_md, summaries, issue_rows, failures)
    print(f"wrote {args.summary_csv}")
    print(f"wrote {args.issue_csv}")
    print(f"wrote {args.report_md}")


REVIEW_LABEL_OPTIONS = [
    "accurate",
    "acceptable",
    "false_positive",
    "evidence_insufficient",
    "duplicate",
    "needs_rule_tuning",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式 final fast_screen_full 小样本只读抽检。")
    parser.add_argument("--visit-id", dest="visit_ids", action="append", default=[], help="可重复传入；默认使用内置候选样本。")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--issue-limit", type=int, default=20)
    parser.add_argument("--summary-csv", type=Path, default=DOCS_DIR / "formal_qc_sample_run_summary.csv")
    parser.add_argument("--summary-json", type=Path, default=DOCS_DIR / "formal_qc_sample_run_summary.json")
    parser.add_argument("--issue-csv", type=Path, default=DOCS_DIR / "formal_qc_sample_issue_review.csv")
    parser.add_argument("--issue-json", type=Path, default=DOCS_DIR / "formal_qc_sample_issue_review.json")
    parser.add_argument("--report-md", type=Path, default=DOCS_DIR / "正式全量质控小样本抽检报告.md")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
