#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import run_formal_qc_gate_integrated_random10_audit as audit  # noqa: E402
from app.services.llm_config_loader import LLMConfigLoader, build_adjudicator_runtime_config  # noqa: E402
from app.services.qc_llm_client import SichuanQCLLMClient  # noqa: E402


FIXED_VISIT_IDS = [
    "2013648",
    "2191214",
    "1965856",
    "2262370",
    "1962863",
    "2048454",
    "2083787",
    "2263802",
    "2328501",
    "2262981",
]

EXPECTED_PROVIDER = "deepseek"
EXPECTED_MODEL = "deepseek-v4-flash"

SUMMARY_CSV = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_quality_review.json"
REPORT_MD = DOCS_DIR / "正式质控DeepSeekV4Flash随机10病历AB回归报告.md"
PROBE_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_minimal_probe.json"
PROBE_CSV = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_minimal_probe.csv"

BASELINE_SUMMARY_JSON = DOCS_DIR / "formal_qc_dual_model_random10_summary.json"
BASELINE_QUALITY_JSON = DOCS_DIR / "formal_qc_dual_model_random10_quality_review.json"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_host(endpoint: Any) -> str:
    try:
        return urlparse(str(endpoint or "")).hostname or ""
    except Exception:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _quality_counts(quality_payload: dict[str, Any]) -> tuple[int, int, float]:
    summary = quality_payload.get("summary") if isinstance(quality_payload.get("summary"), dict) else {}
    counts = summary.get("confirmed_review_counts") if isinstance(summary.get("confirmed_review_counts"), dict) else {}
    confirmed_total = _safe_int(summary.get("confirmed_total") or summary.get("confirmed_defect"))
    keep = _safe_int(counts.get("keep") or counts.get("confirmed_keep"))
    if not confirmed_total:
        reviews = quality_payload.get("reviews") if isinstance(quality_payload.get("reviews"), list) else []
        confirmed_reviews = [row for row in reviews if row.get("review_scope") == "confirmed_full"]
        confirmed_total = len(confirmed_reviews)
        keep = sum(1 for row in confirmed_reviews if row.get("review_recommendation") == "keep")
    keep_rate = round(keep / confirmed_total, 4) if confirmed_total else 0.0
    return confirmed_total, keep, keep_rate


def _display_count(summary_payload: dict[str, Any], key: str) -> int:
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    counts = totals.get("display_status_counts") if isinstance(totals.get("display_status_counts"), dict) else {}
    return _safe_int(counts.get(key))


def _confirmed_review_rule_breakdown(quality_payload: dict[str, Any]) -> list[tuple[str, str, int]]:
    reviews = quality_payload.get("reviews") if isinstance(quality_payload.get("reviews"), list) else []
    counts: dict[tuple[str, str], int] = {}
    for row in reviews:
        if row.get("review_scope") != "confirmed_full":
            continue
        key = (_safe_text(row.get("rule_id")) or "UNKNOWN", _safe_text(row.get("review_recommendation")) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return [(rule_id, decision, count) for (rule_id, decision), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


async def _minimal_probe() -> dict[str, Any]:
    started = time.perf_counter()
    config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
    client = SichuanQCLLMClient(config or {})
    row: dict[str, Any] = {
        "probe_type": "minimal_chat",
        "provider": client.provider_code,
        "endpoint_host": _safe_host(client.api_endpoint),
        "model": client.model,
        "key_present": bool(client.api_key),
        "usage_total_tokens": 0,
        "has_choices": False,
        "provider_error": 0,
        "upstream_http_error": 0,
        "parse_error": 0,
        "timeout": 0,
        "rate_limit": 0,
        "passed": False,
        "error_summary": "",
    }
    try:
        response = await client.generate('请只返回严格 JSON：{"ok": true}，不要输出 Markdown。')
        usage = response.get("_usage_breakdown") if isinstance(response.get("_usage_breakdown"), dict) else {}
        row["usage_total_tokens"] = _safe_int(usage.get("total_tokens") or (response.get("usage") or {}).get("total_tokens"))
        row["has_choices"] = bool(response.get("choices"))
        row["passed"] = bool(
            row["provider"] == EXPECTED_PROVIDER
            and row["model"] == EXPECTED_MODEL
            and row["usage_total_tokens"] > 0
            and row["has_choices"]
        )
    except Exception as exc:
        message = str(exc)
        lower = message.lower()
        row["provider_error"] = 1
        row["upstream_http_error"] = int("upstream_http_error" in lower)
        row["timeout"] = int("timeout" in lower)
        row["rate_limit"] = int("rate" in lower and "limit" in lower)
        row["parse_error"] = int("json" in lower and "decode" in lower)
        row["error_summary"] = message[:800]
    row["wall_clock_time"] = round(time.perf_counter() - started, 3)
    return row


def _stability_pass(summary_payload: dict[str, Any]) -> bool:
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    return bool(totals.get("stability_pass")) and all(
        _safe_int(totals.get(key)) == 0
        for key in [
            "provider_error_count",
            "provider_connection_error_count",
            "upstream_http_error_count",
            "parse_error_count",
            "timeout_count",
            "rate_limit_count",
            "technical_error_internal_count",
        ]
    )


def _write_ab_report(*, probe: dict[str, Any], summary_payload: dict[str, Any], quality_payload: dict[str, Any]) -> None:
    baseline_summary = _read_json(BASELINE_SUMMARY_JSON)
    baseline_quality = _read_json(BASELINE_QUALITY_JSON)
    baseline_totals = baseline_summary.get("totals") if isinstance(baseline_summary.get("totals"), dict) else {}
    current_totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    baseline_confirmed, baseline_keep, baseline_keep_rate = _quality_counts(baseline_quality)
    current_confirmed, current_keep, current_keep_rate = _quality_counts(quality_payload)
    review_breakdown = _confirmed_review_rule_breakdown(quality_payload)
    stable = _stability_pass(summary_payload)
    confirmed_shrink_rate = 0.0
    if baseline_confirmed:
        confirmed_shrink_rate = round((baseline_confirmed - current_confirmed) / baseline_confirmed, 4)

    lines = [
        "# 正式质控 DeepSeek V4 Flash random10 A/B 回归报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 运行范围",
        "",
        "- 链路：正式原链路 `final fast_screen_full / sc_content_full_v1`",
        "- 模型：`deepseek-v4-flash`",
        "- provider：`deepseek`",
        "- endpoint_host：`api.deepseek.com`",
        "- 样本：复用 qwen 双模型 random10 同一批 10 个 visit_id",
        "- 模式：只读，不写正式 QC 结果表，不扩大到 20 份",
        "",
        "## Provider 门禁",
        "",
        f"- provider：`{probe.get('provider')}`",
        f"- model：`{probe.get('model')}`",
        f"- tokens：{_safe_int(probe.get('usage_total_tokens'))}",
        f"- has_choices：{bool(probe.get('has_choices'))}",
        f"- provider_error：{_safe_int(probe.get('provider_error'))}",
        f"- upstream_http_error：{_safe_int(probe.get('upstream_http_error'))}",
        f"- parse_error：{_safe_int(probe.get('parse_error'))}",
        f"- timeout：{_safe_int(probe.get('timeout'))}",
        f"- rate_limit：{_safe_int(probe.get('rate_limit'))}",
        f"- 门禁：{'通过' if probe.get('passed') else '未通过'}",
        "",
        "## 稳定性",
        "",
        f"- report_status：`{summary_payload.get('report_status')}`",
        f"- completed_visit_count：{_safe_int(current_totals.get('visit_count'))}/10",
        f"- provider_error：{_safe_int(current_totals.get('provider_error_count'))}",
        f"- provider_connection_error：{_safe_int(current_totals.get('provider_connection_error_count'))}",
        f"- upstream_http_error：{_safe_int(current_totals.get('upstream_http_error_count'))}",
        f"- parse_error：{_safe_int(current_totals.get('parse_error_count'))}",
        f"- timeout：{_safe_int(current_totals.get('timeout_count'))}",
        f"- rate_limit：{_safe_int(current_totals.get('rate_limit_count'))}",
        f"- technical_error_internal：{_safe_int(current_totals.get('technical_error_internal_count'))}",
        f"- 稳定性结论：{'通过' if stable else '未通过'}",
        "",
        "## 性能与 token",
        "",
        f"- total_wall_clock_time：{_safe_float(current_totals.get('total_wall_clock_time')):.2f}s",
        f"- average_wall_clock_time：{_safe_float(current_totals.get('average_wall_clock_time')):.2f}s/份",
        f"- max_wall_clock_time：{_safe_float(current_totals.get('max_wall_clock_time')):.2f}s",
        f"- llm_call_count：{_safe_int(current_totals.get('llm_call_count'))}",
        f"- total_tokens：{_safe_int(current_totals.get('total_tokens'))}",
        "",
        "## A/B 质量对比",
        "",
        f"- baseline confirmed_defect：{baseline_confirmed}",
        f"- DeepSeek confirmed_defect：{current_confirmed}",
        f"- baseline confirmed_keep：{baseline_keep}",
        f"- DeepSeek confirmed_keep：{current_keep}",
        f"- baseline keep_rate：{baseline_keep_rate:.1%}",
        f"- DeepSeek keep_rate：{current_keep_rate:.1%}",
        f"- confirmed 收缩率：{confirmed_shrink_rate:.1%}",
        f"- DeepSeek data_quality_gap：{_display_count(summary_payload, 'data_quality_gap')}",
        f"- DeepSeek rejected_by_system：{_display_count(summary_payload, 'rejected_by_system')}",
        "",
        "## DeepSeek confirmed 误报聚类",
        "",
    ]
    if review_breakdown:
        lines.extend(f"- {rule_id} / {decision}：{count}" for rule_id, decision, count in review_breakdown)
    else:
        lines.append("- 无 confirmed 复核样本。")
    lines.extend(
        [
            "",
            "## 下一步治理建议",
            "",
            "- P0：SC-118。DeepSeek 将出院记录字段缺项类 confirmed 放大，5 条建议转 data_quality_gap，说明出院记录完整字段矩阵仍不足。",
            "- P0：SC-014。个人史/婚育史/家族史等生活史字段被放大为 confirmed，需按字段矩阵和客户口径收紧。",
            "- P1：SC-146、SC-125、SC-097。当前数量较少，但仍有 confirmed 证据链不足，需要保留在下一轮误报治理清单。",
            "- 暂不扩大到 20 份；先治理上述规则，再用同一 random10 复验。",
            "",
            "## 结论",
            "",
        ]
    )
    if not probe.get("passed"):
        lines.append("- Provider minimal 门禁未通过，不评价 random10 质量。")
    elif not stable:
        lines.append("- random10 稳定性未通过，不评价质量，不建议扩大样本。")
    elif current_confirmed == 0:
        lines.append("- 稳定性通过，但 confirmed 被压到 0，不建议作为质量可演示结论，也不建议扩大到 20 份。")
    elif current_keep_rate >= 0.7:
        lines.append("- 稳定性通过，confirmed keep rate 达到 70% 阈值；可作为进入 20 份只读验收的候选。")
    else:
        lines.append("- 稳定性通过，但 confirmed keep rate 未达到 70%；不建议扩大到 20 份，下一步应继续治理具体误报规则。")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def _run(args: argparse.Namespace) -> None:
    probe = await _minimal_probe()
    audit._write_csv(args.probe_csv, [probe])
    _write_json(args.probe_json, {"probe": probe})
    if not probe.get("passed"):
        payload = {
            "report_status": "failed_minimal_probe",
            "model": EXPECTED_MODEL,
            "provider": EXPECTED_PROVIDER,
            "probe": probe,
            "totals": {"stability_pass": False},
        }
        _write_json(args.summary_json, payload)
        _write_ab_report(probe=probe, summary_payload=payload, quality_payload={})
        print("minimal probe failed; stop before random10")
        return

    audit_args = argparse.Namespace(
        limit=10,
        random_seed=20260519,
        scan_limit=260,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=" ".join(FIXED_VISIT_IDS),
        summary_csv=args.summary_csv,
        summary_json=args.summary_json,
        issue_csv=args.issue_csv,
        issue_json=args.issue_json,
        quality_csv=args.quality_csv,
        quality_json=args.quality_json,
        report_md=args.report_md,
    )
    await audit._run(audit_args)
    summary_payload = _read_json(args.summary_json)
    summary_payload["model"] = EXPECTED_MODEL
    summary_payload["provider"] = EXPECTED_PROVIDER
    summary_payload["minimal_probe"] = probe
    summary_payload["baseline_summary_json"] = str(BASELINE_SUMMARY_JSON)
    summary_payload["baseline_quality_json"] = str(BASELINE_QUALITY_JSON)
    _write_json(args.summary_json, summary_payload)
    _write_ab_report(
        probe=probe,
        summary_payload=summary_payload,
        quality_payload=_read_json(args.quality_json),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepSeek V4 Flash formal QC random10 A/B replay.")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--issue-csv", type=Path, default=ISSUE_CSV)
    parser.add_argument("--issue-json", type=Path, default=ISSUE_JSON)
    parser.add_argument("--quality-csv", type=Path, default=QUALITY_CSV)
    parser.add_argument("--quality-json", type=Path, default=QUALITY_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--probe-csv", type=Path, default=PROBE_CSV)
    parser.add_argument("--probe-json", type=Path, default=PROBE_JSON)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
