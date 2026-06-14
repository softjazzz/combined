#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
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
os.chdir(BACKEND_ROOT)

from app.services.qc_result_adjudicator import (  # noqa: E402
    _extract_json_object,
    _extract_llm_content,
)
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
INPUT_ISSUE_JSON = DOCS_DIR / "formal_qc_random10_original_chain_issue_review.json"
INPUT_ISSUE_CSV = DOCS_DIR / "formal_qc_random10_original_chain_issue_review.csv"
INPUT_SUMMARY_JSON = DOCS_DIR / "formal_qc_random10_original_chain_run_summary.json"
OUTPUT_CSV = DOCS_DIR / "formal_qc_random10_confirmed_second_pass_review.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_random10_confirmed_second_pass_review.json"
REPORT_MD = DOCS_DIR / "正式原链路随机10病历confirmed二轮复核报告.md"

ALLOWED_SECOND_PASS_STATUSES = {
    "confirmed_defect",
    "data_quality_gap",
    "rejected_by_system",
    "technical_error_internal",
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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _normalize_status(value: Any) -> str:
    status = _safe_text(value).lower()
    return status if status in ALLOWED_SECOND_PASS_STATUSES else "technical_error_internal"


def _evidence_strength(row: dict[str, Any], second_status: str) -> str:
    evidence = _safe_text(row.get("original_evidence"))
    quote = _safe_text(row.get("supporting_quote"))
    reason = _safe_text(row.get("second_pass_reason"))
    if second_status == "confirmed_defect" and len(evidence) >= 80 and len(quote) >= 30 and len(reason) >= 20:
        return "strong"
    if len(evidence) >= 40 or len(quote) >= 20:
        return "medium"
    return "weak"


def _rule_applicability(status: str, reason: str) -> str:
    text = _safe_text(reason)
    if status == "rejected_by_system" and any(term in text for term in ("不适用", "规则不成立", "触发不成立", "男性不应要求月经史")):
        return "not_applicable"
    if status == "data_quality_gap":
        return "unclear"
    if status == "technical_error_internal":
        return "unclear"
    return "applicable"


def _downgrade_reason(first_status: str, second_status: str, reason: str) -> str:
    if second_status == first_status:
        return ""
    if second_status == "data_quality_gap":
        return "二轮认为证据链不足或缺完整上下文，不能直接确认。"
    if second_status == "rejected_by_system":
        return "二轮认为规则不适用、证据与结论不匹配或存在反证。"
    if second_status == "technical_error_internal":
        return "二轮 provider 或解析异常，不能作为确认缺陷。"
    return _truncate(reason, 300)


def _candidate_payload(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "index": index,
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "rule_id": _safe_text(row.get("rule_id")),
        "rule_name": _safe_text(row.get("rule_name")),
        "original_conclusion": _truncate(row.get("conclusion"), 700),
        "original_evidence": _truncate(row.get("evidence"), 900),
        "supporting_quote": _truncate(row.get("supporting_quote"), 700),
        "source_quote": _truncate(row.get("source_quote"), 700),
        "document_type": _safe_text(row.get("document_type")),
        "evidence_family": _safe_text(row.get("evidence_family")),
        "rule_pack": _safe_text(row.get("rule_pack")),
        "severity": _safe_text(row.get("severity")),
        "confidence": row.get("confidence"),
        "postprocess_reason": _truncate(row.get("postprocess_reason") or row.get("adjudicator_reason"), 800),
        "auto_screening": {
            "evidence_too_short": bool(row.get("evidence_too_short")),
            "quote_missing": bool(row.get("quote_missing")),
            "rule_applicability_risk": bool(row.get("rule_applicability_risk")),
            "possible_false_positive": bool(row.get("possible_false_positive")),
            "data_gap_likely_sync_or_bundle": bool(row.get("data_gap_likely_sync_or_bundle")),
            "needs_manual_review_reason": _truncate(row.get("needs_manual_review_reason"), 500),
        },
    }


def _build_prompt(candidates: list[dict[str, Any]]) -> str:
    payload = json.dumps({"items": candidates}, ensure_ascii=False, indent=2)
    return f"""你是正式病历质控 confirmed_defect 二轮准入复核器。第一轮 fast_screen_full 保持高召回，你只复核已经被第一轮判为 confirmed_defect 的项目，目标是降低误报。

只能输出 JSON，不要输出 Markdown。不得输出“待人工复核”“qc_review_candidate”“needs_review”。

终态只能是：
- confirmed_defect：规则适用，缺陷要件成立，original_evidence / supporting_quote 能直接支撑缺陷，可展示给质控员/医生。
- data_quality_gap：缺完整文书上下文、缺报告单、缺医嘱、缺执行清单、缺跨文书对照，不能归责医生。
- rejected_by_system：规则不适用、已有反证、证据与结论不匹配、结论过度推断。
- technical_error_internal：输入不可解析或你无法完成裁决。

通用准入门槛：
- 证据太短、只有记录时间、只有标题、只有模板空字段、只有截断片段，不得 confirmed_defect。
- 只有 supporting_quote 能直接证明规则核心缺陷时，才可 confirmed_defect。
- 缺全文上下文或跨文书对照时，优先 data_quality_gap。
- 规则不适用、已有反证或只是轻微书写省略时，rejected_by_system。

重点规则约束：
1. SC-008 / SC-010：不得因为主诉较短就认为不能导出诊断；“5小时余” vs “5小前”这类省略/错字不能直接 confirmed，必须有实质性时间、部位、症状、诊断逻辑冲突。
2. SC-014 / SC-015：必须确认完整入院记录中对应字段缺失或明显不全；男性病历不应要求月经史；“具体不详”是否算缺陷要谨慎，细节不足优先 data_quality_gap 或 rejected_by_system。
3. SC-036：必须同时有明确异常报告和后续缺少分析/处理意见；如果后文已有“循环稳定/继续观察/调整治疗/复查”等处理语义，不得 confirmed；缺原报告或缺后续病程上下文时 data_quality_gap。
4. SC-097：不能只凭空字段片段 confirmed；必须确认完整手术记录关键字段确实缺失；“术中诊断:”或“切口愈合等级:”等短片段优先 data_quality_gap。
5. SC-118 / SC-121 / SC-123：SC-118 必须看到完整字段缺失；SC-123 必须先确认存在出院带药，“无出院带药”不等于“出院带药不详细”；生活方式/随访医嘱不能按出院带药不详细 confirmed；出院带药存在且缺给药途径/天数/剂量且 quote 清楚时才可 confirmed。

输出格式：
{{
  "items": [
    {{
      "index": 0,
      "rule_id": "SC-xxx",
      "second_pass_status": "confirmed_defect|data_quality_gap|rejected_by_system|technical_error_internal",
      "second_pass_reason": "裁决理由",
      "supporting_quote": "最能支撑二轮裁决的短引用；没有则为空",
      "evidence_strength": "strong|medium|weak",
      "rule_applicability": "applicable|not_applicable|unclear"
    }}
  ]
}}

待复核项目：
{payload}
"""


def _extract_items(response: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    content = _extract_llm_content(response)
    payload = _extract_json_object(content)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return [], _truncate(content, 500)
    return [dict(item) for item in items if isinstance(item, dict)], ""


async def _call_second_pass(candidates: list[dict[str, Any]], *, batch_size: int) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    qc_service = SichuanQCService()
    if not await qc_service.reload_config():
        raise RuntimeError("无法加载 LLM 运行时配置")
    outputs: list[dict[str, Any]] = []
    parse_error = 0
    provider_error = 0
    error_summary = ""
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        prompt = _build_prompt(batch)
        try:
            response = await qc_service.client.generate(prompt)
        except Exception as exc:
            provider_error += 1
            error_summary = _truncate(str(exc), 500)
            for item in batch:
                outputs.append(
                    {
                        "index": item["index"],
                        "rule_id": item.get("rule_id", ""),
                        "second_pass_status": "technical_error_internal",
                        "second_pass_reason": f"二轮 provider 调用失败：{error_summary}",
                        "supporting_quote": "",
                        "evidence_strength": "weak",
                        "rule_applicability": "unclear",
                    }
                )
            continue
        items, parse_message = _extract_items(response)
        by_index = {}
        for item in items:
            try:
                by_index[int(item.get("index"))] = item
            except Exception:
                continue
        if parse_message or len(by_index) < len(batch):
            parse_error += 1
        for candidate in batch:
            idx = int(candidate["index"])
            item = by_index.get(idx)
            if not item:
                outputs.append(
                    {
                        "index": idx,
                        "rule_id": candidate.get("rule_id", ""),
                        "second_pass_status": "technical_error_internal",
                        "second_pass_reason": f"二轮输出缺失或解析失败：{parse_message}",
                        "supporting_quote": "",
                        "evidence_strength": "weak",
                        "rule_applicability": "unclear",
                    }
                )
                continue
            status = _normalize_status(item.get("second_pass_status"))
            reason = _safe_text(item.get("second_pass_reason")) or "二轮未给出理由。"
            quote = _safe_text(item.get("supporting_quote"))
            outputs.append(
                {
                    "index": idx,
                    "rule_id": _safe_text(item.get("rule_id") or candidate.get("rule_id")),
                    "second_pass_status": status,
                    "second_pass_reason": reason,
                    "supporting_quote": quote,
                    "evidence_strength": _safe_text(item.get("evidence_strength")) or "weak",
                    "rule_applicability": _safe_text(item.get("rule_applicability")) or _rule_applicability(status, reason),
                }
            )
    stats = {
        "provider_error": provider_error,
        "timeout": 0,
        "parse_error": parse_error,
        "model_tokens": _safe_int(getattr(qc_service.client, "total_tokens", 0)),
    }
    return outputs, stats, error_summary


def _build_rows(confirmed: list[dict[str, Any]], adjudicated: list[dict[str, Any]], stats: dict[str, int]) -> list[dict[str, Any]]:
    by_index = {int(item.get("index")): item for item in adjudicated}
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(confirmed):
        second = by_index.get(index) or {}
        second_status = _normalize_status(second.get("second_pass_status"))
        reason = _safe_text(second.get("second_pass_reason"))
        first_status = _safe_text(item.get("display_status"))
        strength = _safe_text(second.get("evidence_strength")) or _evidence_strength(
            {
                "original_evidence": item.get("evidence"),
                "supporting_quote": second.get("supporting_quote") or item.get("supporting_quote"),
                "second_pass_reason": reason,
            },
            second_status,
        )
        applicability = _safe_text(second.get("rule_applicability")) or _rule_applicability(second_status, reason)
        rows.append(
            {
                "visit_id": item.get("visit_id", ""),
                "patient_name": item.get("patient_name", ""),
                "rule_id": item.get("rule_id", ""),
                "rule_name": item.get("rule_name", ""),
                "first_pass_status": first_status,
                "second_pass_status": second_status,
                "second_pass_reason": reason,
                "original_conclusion": item.get("conclusion", ""),
                "original_evidence": item.get("evidence", ""),
                "supporting_quote": second.get("supporting_quote") or item.get("supporting_quote", ""),
                "downgrade_reason": _downgrade_reason(first_status, second_status, reason),
                "evidence_strength": strength if strength in {"strong", "medium", "weak"} else "weak",
                "rule_applicability": applicability if applicability in {"applicable", "not_applicable", "unclear"} else "unclear",
                "final_recommendation": second_status,
                "provider_error": stats["provider_error"],
                "timeout": stats["timeout"],
                "parse_error": stats["parse_error"],
                "model_tokens": stats["model_tokens"],
                "first_pass_evidence_too_short": item.get("evidence_too_short", ""),
                "first_pass_quote_missing": item.get("quote_missing", ""),
                "first_pass_possible_false_positive": item.get("possible_false_positive", ""),
                "first_pass_data_gap_likely_sync_or_bundle": item.get("data_gap_likely_sync_or_bundle", ""),
                "first_pass_needs_manual_review_reason": item.get("needs_manual_review_reason", ""),
            }
        )
    return rows


def _write_report(path: Path, rows: list[dict[str, Any]], *, stats: dict[str, int]) -> None:
    counts = Counter(row["second_pass_status"] for row in rows)
    rule_false_positive = Counter(
        row["rule_id"]
        for row in rows
        if row["second_pass_status"] in {"data_quality_gap", "rejected_by_system"}
    )
    lines = [
        "# 正式原链路随机10病历 confirmed 二轮复核报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 范围",
        "",
        "- 本轮只读取随机10病历原正式链路 issue_review 中的 first-pass `confirmed_defect`。",
        "- 不重跑 84 条正式质控，不使用 structured evidence POC，不写业务表，不接页面。",
        "- 第二轮 LLM 只允许输出 confirmed_defect / data_quality_gap / rejected_by_system / technical_error_internal。",
        "",
        "## 结果",
        "",
        f"- first-pass confirmed_defect：{len(rows)}。",
        f"- 二轮保留 confirmed_defect：{counts['confirmed_defect']}。",
        f"- 二轮降级 data_quality_gap：{counts['data_quality_gap']}。",
        f"- 二轮驳回 rejected_by_system：{counts['rejected_by_system']}。",
        f"- technical_error_internal：{counts['technical_error_internal']}。",
        f"- provider_error={stats['provider_error']}，timeout={stats['timeout']}，parse_error={stats['parse_error']}，model_tokens={stats['model_tokens']}。",
        "",
        "## 误报高频规则",
        "",
    ]
    for rule_id, count in rule_false_positive.most_common():
        lines.append(f"- `{rule_id}`：{count}")
    lines.extend(["", "## 逐条复核", ""])
    for row in rows:
        lines.append(
            f"- `{row['visit_id']}` `{row['rule_id']}` {row['rule_name']}：{row['first_pass_status']} -> {row['second_pass_status']}；strength={row['evidence_strength']}；reason={_truncate(row['second_pass_reason'], 220)}"
        )
    lines.extend(["", "## 是否建议接入正式链路", ""])
    if stats["provider_error"] or stats["parse_error"] or stats["timeout"]:
        lines.append("- 不建议直接接入；需先保证二轮 provider 和 JSON 输出稳定。")
    elif counts["confirmed_defect"] < len(rows):
        lines.append("- 建议作为 feature flag / 旁路 gate 继续验证：二轮显著降低 first-pass confirmed 数量，但需人工复核确认是否过严。")
    else:
        lines.append("- 二轮未降低 confirmed 数量，当前价值有限；建议先优化 prompt 或证据输入。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    payload = _read_json(args.input_issue_json)
    issues = [dict(item) for item in payload.get("issues", []) if isinstance(item, dict)]
    confirmed = [item for item in issues if _safe_text(item.get("display_status")) == "confirmed_defect"]
    candidates = [_candidate_payload(item, index) for index, item in enumerate(confirmed)]
    adjudicated, stats, _ = await _call_second_pass(candidates, batch_size=args.batch_size)
    rows = _build_rows(confirmed, adjudicated, stats)
    counts = dict(Counter(row["second_pass_status"] for row in rows))
    result_payload = {
        "input_issue_json": str(args.input_issue_json),
        "input_summary_json": str(args.input_summary_json),
        "first_pass_confirmed_count": len(confirmed),
        "second_pass_counts": counts,
        "provider_error": stats["provider_error"],
        "timeout": stats["timeout"],
        "parse_error": stats["parse_error"],
        "model_tokens": stats["model_tokens"],
        "rows": rows,
    }
    _write_csv(args.output_csv, rows)
    _write_json(args.output_json, result_payload)
    _write_report(args.report_md, rows, stats=stats)
    print(json.dumps({k: result_payload[k] for k in ["first_pass_confirmed_count", "second_pass_counts", "provider_error", "timeout", "parse_error", "model_tokens"]}, ensure_ascii=False))
    print(f"wrote {args.output_csv}")
    print(f"wrote {args.report_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式原链路随机10病历 confirmed_defect 二轮 LLM 准入复核。")
    parser.add_argument("--input-issue-json", type=Path, default=INPUT_ISSUE_JSON)
    parser.add_argument("--input-issue-csv", type=Path, default=INPUT_ISSUE_CSV)
    parser.add_argument("--input-summary-json", type=Path, default=INPUT_SUMMARY_JSON)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--batch-size", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
