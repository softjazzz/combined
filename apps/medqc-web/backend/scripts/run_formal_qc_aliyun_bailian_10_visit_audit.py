#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
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
os.chdir(BACKEND_ROOT)

from diagnose_formal_qc_provider_failures import _classify_error  # noqa: E402
from run_formal_qc_three_visit_adjudicated_audit import (  # noqa: E402
    _read_csv_rows,
    _run_one_visit,
    _safe_float,
    _safe_int,
    _safe_text,
    _write_csv,
    _write_json,
    _load_rules_by_id,
    _load_visit_keys,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
MATRIX_PATH = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sheet2_exact_review_matrix.csv"
DEFAULT_VISIT_IDS = [
    "1915580",  # blocked, surgery, consultation
    "2024757",  # blocked, non-surgery, consultation
    "2287309",  # blocked, surgery, consultation
    "2246915",  # blocked, surgery, consultation
    "1883111",  # exact, non-surgery, no consultation
    "1966656",  # blocked, surgery, consultation
    "2311318",  # blocked, surgery, consultation
    "2207717",  # exact, non-surgery, consultation
    "1870471",  # exact, surgery, consultation
    "2268187",  # blocked, non-surgery, consultation
]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load_sheet2_status() -> dict[str, dict[str, Any]]:
    rows = _read_csv_rows(MATRIX_PATH)
    by_visit: dict[str, dict[str, Any]] = {}
    for row in rows:
        visit_id = _safe_text(row.get("visit_id"))
        if not visit_id:
            continue
        item = by_visit.setdefault(
            visit_id,
            {
                "sheet2_row_ids": [],
                "sheet2_status_counts": Counter(),
                "sheet2_rule_ids": [],
            },
        )
        item["sheet2_row_ids"].append(_safe_text(row.get("sheet2_row_id")))
        item["sheet2_status_counts"][_safe_text(row.get("exact_review_status")) or "blank"] += 1
        rid = _safe_text(row.get("primary_rule_id"))
        if rid:
            item["sheet2_rule_ids"].append(rid)
    result: dict[str, dict[str, Any]] = {}
    for visit_id, item in by_visit.items():
        result[visit_id] = {
            "sheet2_row_ids": ",".join(item["sheet2_row_ids"]),
            "sheet2_status_counts": _json(dict(item["sheet2_status_counts"])),
            "sheet2_rule_ids": ",".join(dict.fromkeys(item["sheet2_rule_ids"])),
        }
    return result


def _failure_counts_from_pack_metrics(pack_metrics: dict[str, Any]) -> dict[str, int]:
    counts = {
        "provider_error_count": 0,
        "upstream_http_error_count": 0,
        "parse_error_count": 0,
        "provider_connection_error_count": 0,
        "timeout_count": 0,
        "rate_limit_count": 0,
    }
    for diagnostic in list(pack_metrics.get("pack_diagnostics") or []):
        if not isinstance(diagnostic, dict):
            continue
        raw_error = _safe_text(diagnostic.get("raw_error_summary") or diagnostic.get("pack_retry_reason"))
        classified = _classify_error(raw_error)
        counts["upstream_http_error_count"] += classified["upstream_http_error_count"]
        counts["parse_error_count"] += classified["parse_error_count"]
        counts["provider_connection_error_count"] += classified["provider_connection_error_count"]
        counts["timeout_count"] += max(_safe_int(diagnostic.get("timeout_count")), classified["timeout_count"])
        counts["rate_limit_count"] += max(_safe_int(diagnostic.get("rate_limit_count")), classified["rate_limit_count"])
        if classified["upstream_http_error_count"] or classified["parse_error_count"]:
            counts["provider_error_count"] += classified["provider_connection_error_count"]
        else:
            counts["provider_error_count"] += max(
                _safe_int(diagnostic.get("provider_error_count")),
                classified["provider_connection_error_count"],
            )
    return counts


def _apply_gate(summary: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    pack_metrics = dict(raw.get("pack_metrics") or {})
    counts = _failure_counts_from_pack_metrics(pack_metrics)
    for key, value in counts.items():
        summary[key] = value
    failed = any(
        _safe_int(summary.get(key)) > 0
        for key in (
            "provider_error_count",
            "upstream_http_error_count",
            "parse_error_count",
            "timeout_count",
            "rate_limit_count",
            "technical_error_internal_count",
        )
    )
    summary["stability_status"] = "failed_provider_unstable" if failed else "provider_stability_pass"
    return summary


def _write_report(
    path: Path,
    *,
    summaries: list[dict[str, Any]],
    issue_rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    failed = [
        row
        for row in summaries
        if _safe_text(row.get("stability_status")) != "provider_stability_pass"
    ]
    provider_error = sum(_safe_int(row.get("provider_error_count")) for row in summaries)
    upstream = sum(_safe_int(row.get("upstream_http_error_count")) for row in summaries)
    parse = sum(_safe_int(row.get("parse_error_count")) for row in summaries)
    timeout = sum(_safe_int(row.get("timeout_count")) for row in summaries)
    rate_limit = sum(_safe_int(row.get("rate_limit_count")) for row in summaries)
    technical = sum(_safe_int(row.get("technical_error_internal_count")) for row in summaries)
    report_status = "failed_provider_unstable" if failed or failures else "provider_stability_pass"
    confirmed = [row for row in issue_rows if row.get("display_status") == "confirmed_defect"]
    rejected = [row for row in issue_rows if row.get("display_status") == "rejected_by_system"]
    data_gap = [row for row in issue_rows if row.get("display_status") == "data_quality_gap"]
    avg_wall = sum(_safe_float(row.get("wall_clock_time")) for row in summaries) / len(summaries) if summaries else 0
    avg_tokens = sum(_safe_int(row.get("total_tokens")) for row in summaries) / len(summaries) if summaries else 0

    lines = [
        "# 正式质控 10 病历阿里云百炼只读抽检报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 稳定性门禁",
        "",
        f"- report_status：`{report_status}`。",
        "- provider：`alibaba / dashscope`；规则集：`sc_content_full_v1`；`pack_concurrency=3`。",
        "- 只读运行，不写医生整改/正式质控业务结果表。",
        f"- provider_error={provider_error}，upstream_http_error={upstream}，parse_error={parse}，timeout={timeout}，rate_limit={rate_limit}，technical_error_internal={technical}。",
        f"- 平均 wall_clock_time={avg_wall:.2f}s；平均 tokens={avg_tokens:.0f}。",
        "",
    ]
    if report_status != "provider_stability_pass":
        lines.extend(
            [
                "## 质量结论",
                "",
                "- 本轮稳定性门禁失败，不做质量结论，不建议扩大样本。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## 质量复核摘要",
                "",
                f"- confirmed_defect：{len(confirmed)} 条。",
                f"- data_quality_gap：{len(data_gap)} 条。",
                f"- rejected_by_system：{len(rejected)} 条。",
                "- 本轮 provider 稳定性通过，可以进入质量复核；但 confirmed/rejected 仍需按明细抽查证据和二审 reason/quote。",
                "",
            ]
        )
    lines.extend(
        [
            "## 分病历结果",
            "",
            "| visit_id | patient | dept | Sheet2 | surgery | consult | wall(s) | model(s) | tokens | llm_calls | provider | upstream | parse | timeout | rate | technical | confirmed | data_gap | rejected |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summaries:
        lines.append(
            "| {visit_id} | {patient_name} | {department} | `{sheet2}` | {surgery} | {consult} | {wall:.2f} | {model:.2f} | {tokens} | {calls} | {provider} | {upstream} | {parse} | {timeout} | {rate} | {technical} | {confirmed} | {data_gap} | {rejected} |".format(
                visit_id=row.get("visit_id", ""),
                patient_name=row.get("patient_name", ""),
                department=row.get("department", ""),
                sheet2=row.get("sheet2_status_counts", "{}"),
                surgery=row.get("is_surgery", ""),
                consult=row.get("has_consultation", ""),
                wall=_safe_float(row.get("wall_clock_time")),
                model=_safe_float(row.get("total_processing_time")),
                tokens=row.get("total_tokens", 0),
                calls=row.get("llm_call_count", 0),
                provider=row.get("provider_error_count", 0),
                upstream=row.get("upstream_http_error_count", 0),
                parse=row.get("parse_error_count", 0),
                timeout=row.get("timeout_count", 0),
                rate=row.get("rate_limit_count", 0),
                technical=row.get("technical_error_internal_count", 0),
                confirmed=row.get("confirmed_defect_count", 0),
                data_gap=row.get("data_quality_gap_count", 0),
                rejected=row.get("rejected_by_system_count", 0),
            )
        )
    lines.extend(["", "## confirmed_defect 明细", ""])
    for row in confirmed:
        lines.append(
            "- `{visit_id}` `{rule_id}` {rule_name}：{findings}；quote={quote}；reason={reason}".format(
                visit_id=row.get("visit_id", ""),
                rule_id=row.get("rule_id", ""),
                rule_name=row.get("rule_name", ""),
                findings=_safe_text(row.get("findings"))[:180],
                quote=_safe_text(row.get("adjudicator_supporting_quote"))[:180],
                reason=_safe_text(row.get("adjudicator_reason"))[:180],
            )
        )
    lines.extend(["", "## rejected_by_system 抽样复核清单", ""])
    for row in rejected[:40]:
        lines.append(
            "- `{visit_id}` `{rule_id}` {rule_name}：auto={auto}；reason={reason}".format(
                visit_id=row.get("visit_id", ""),
                rule_id=row.get("rule_id", ""),
                rule_name=row.get("rule_name", ""),
                auto=row.get("auto_quality_label", ""),
                reason=_safe_text(row.get("adjudicator_reason") or row.get("postprocess_reason"))[:220],
            )
        )
    if failures:
        lines.extend(["", "## 运行失败", ""])
        for row in failures:
            lines.append(f"- `{row.get('visit_id')}`：{row.get('error')}")
    lines.extend(
        [
            "",
            "## 是否可以继续 10 份之后的扩展",
            "",
            "- 本报告只回答 10 份稳定性和初步质量复核，不自动进入 20 份。",
            "- 若需扩大到 20 份，应先人工抽查 confirmed_defect 和 rejected_by_system 明细，确认没有系统性误报/误驳回。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    visit_ids = [item.strip() for item in args.visit_ids if item.strip()] or DEFAULT_VISIT_IDS
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    sheet2_status = _load_sheet2_status()
    summaries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    raw_runs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for visit_id in visit_ids[: args.limit]:
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
                    }
                )
            summaries.append(summary)
            issues.extend(issue_rows)
            raw_runs.append(raw)
            print(
                json.dumps(
                    {
                        "visit_id": visit_id,
                        "stability_status": summary["stability_status"],
                        "provider_error": summary.get("provider_error_count"),
                        "upstream_http_error": summary.get("upstream_http_error_count"),
                        "parse_error": summary.get("parse_error_count"),
                        "technical": summary.get("technical_error_internal_count"),
                        "tokens": summary.get("total_tokens"),
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:
            failures.append({"visit_id": visit_id, "error": str(exc)})
            print(f"failed {visit_id}: {exc}")

    report_status = (
        "provider_stability_pass"
        if summaries
        and not failures
        and all(row.get("stability_status") == "provider_stability_pass" for row in summaries)
        else "failed_provider_unstable"
    )
    payload = {
        "report_status": report_status,
        "provider": "alibaba",
        "endpoint_host": "dashscope.aliyuncs.com",
        "pack_concurrency": args.pack_concurrency,
        "summaries": summaries,
        "issues": issues,
        "failures": failures,
        "raw_runs": raw_runs,
    }
    _write_csv(args.summary_csv, summaries)
    _write_json(args.summary_json, payload)
    _write_csv(args.issue_csv, issues)
    _write_json(args.issue_json, {"report_status": report_status, "issues": issues})
    _write_report(args.report_md, summaries=summaries, issue_rows=issues, failures=failures)
    print(f"wrote {args.summary_csv}")
    print(f"wrote {args.issue_csv}")
    print(f"wrote {args.report_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式 final fast_screen_full 阿里云百炼 10 病历只读抽检。")
    parser.add_argument("--visit-id", dest="visit_ids", action="append", default=[])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--limit-per-bucket", type=int, default=50)
    parser.add_argument("--summary-csv", type=Path, default=DOCS_DIR / "formal_qc_aliyun_bailian_10_visit_run_summary.csv")
    parser.add_argument("--summary-json", type=Path, default=DOCS_DIR / "formal_qc_aliyun_bailian_10_visit_run_summary.json")
    parser.add_argument("--issue-csv", type=Path, default=DOCS_DIR / "formal_qc_aliyun_bailian_10_visit_issue_review.csv")
    parser.add_argument("--issue-json", type=Path, default=DOCS_DIR / "formal_qc_aliyun_bailian_10_visit_issue_review.json")
    parser.add_argument("--report-md", type=Path, default=DOCS_DIR / "正式质控阿里云百炼10病历只读抽检报告.md")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
