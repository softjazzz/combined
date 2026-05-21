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


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import run_formal_qc_gate_integrated_random10_audit as audit  # noqa: E402
from app.services.llm_config_loader import (  # noqa: E402
    LLMConfigLoader,
    build_adjudicator_runtime_config,
)
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

SUMMARY_CSV = DOCS_DIR / "formal_qc_dual_model_random10_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_dual_model_random10_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_dual_model_random10_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_dual_model_random10_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_dual_model_random10_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_dual_model_random10_quality_review.json"
REPORT_MD = DOCS_DIR / "正式质控双模型random10验证报告.md"
EXPECTED_FIRST_PASS_MODEL = "qwen3.5-35b-a3b"
EXPECTED_ADJUDICATOR_MODEL = "qwen3.6-35b-a3b"
SINGLE_VISIT_ID = "2122521"
INVALID_ENV_ASSIGNMENT_NOTE = (
    "上一轮 PowerShell 命令使用双引号包裹 -Command，外层 PowerShell 提前展开 $env:LLM_ADJUDICATOR_MODEL，"
    "传入 pwsh 后变成无效赋值；该轮结果标记为 invalid_env_assignment，不作为双模型验证结论。"
)

QWEN35_FAILURE_BASELINE_JSON = DOCS_DIR / "formal_qc_rule_prompt_criteria_ab_summary.json"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


async def _minimal_probe(*, label: str, client: SichuanQCLLMClient) -> dict[str, Any]:
    started = time.perf_counter()
    row: dict[str, Any] = {
        "label": label,
        "provider": client.provider_code,
        "model": client.model,
        "model_role": getattr(client, "model_role", ""),
        "model_source": getattr(client, "adjudicator_model_source", "") or client.config_source,
        "provider_error": 0,
        "upstream_http_error": 0,
        "parse_error": 0,
        "timeout": 0,
        "rate_limit": 0,
        "usage_total_tokens": 0,
        "has_choices": False,
        "passed": False,
    }
    try:
        response = await client.generate('请只返回一个 JSON 对象：{"ok":true}，不要输出 Markdown。')
        usage = response.get("_usage_breakdown") if isinstance(response.get("_usage_breakdown"), dict) else {}
        row["usage_total_tokens"] = _safe_int(usage.get("total_tokens") or (response.get("usage") or {}).get("total_tokens"))
        row["has_choices"] = bool(response.get("choices"))
        row["passed"] = bool(row["usage_total_tokens"] > 0 and row["has_choices"])
    except Exception as exc:
        message = str(exc)
        row["provider_error"] = 1
        row["upstream_http_error"] = int("upstream_http_error" in message)
        row["timeout"] = int("timeout" in message.lower())
        row["rate_limit"] = int("rate" in message.lower() and "limit" in message.lower())
        row["error_summary"] = message[:500]
    row["wall_clock_time"] = round(time.perf_counter() - started, 3)
    return row


async def _run_minimal_probes() -> list[dict[str, Any]]:
    first_pass_config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
    if not first_pass_config:
        first_pass_config = {}
    first_pass_client = SichuanQCLLMClient(first_pass_config)
    adjudicator_client = SichuanQCLLMClient(build_adjudicator_runtime_config(first_pass_config))
    return [
        await _minimal_probe(label="first_pass", client=first_pass_client),
        await _minimal_probe(label="adjudicator", client=adjudicator_client),
    ]


def _probe_models_ok(probes: list[dict[str, Any]]) -> bool:
    if len(probes) < 2:
        return False
    return (
        bool(probes[0].get("passed"))
        and bool(probes[1].get("passed"))
        and _safe_text(probes[0].get("model")) == EXPECTED_FIRST_PASS_MODEL
        and _safe_text(probes[1].get("model")) == EXPECTED_ADJUDICATOR_MODEL
    )


def _stability_ok(summary: dict[str, Any], *, missing_after_retry: int = 0) -> bool:
    return (
        _safe_int(summary.get("provider_error_count")) == 0
        and _safe_int(summary.get("provider_connection_error_count")) == 0
        and _safe_int(summary.get("upstream_http_error_count")) == 0
        and _safe_int(summary.get("parse_error_count")) == 0
        and _safe_int(summary.get("timeout_count")) == 0
        and _safe_int(summary.get("rate_limit_count")) == 0
        and _safe_int(summary.get("technical_error_internal_count")) == 0
        and missing_after_retry == 0
    )


def _issue_missing_after_retry_count(issues: list[dict[str, Any]]) -> int:
    return sum(_safe_int(row.get("adjudicator_missing_rule_output_count")) for row in issues)


async def _run_single_visit_gate(*, pack_concurrency: int) -> dict[str, Any]:
    visit_keys = audit._load_visit_keys()
    rules_by_id = audit._load_rules_by_id()
    summary, issues, raw = await audit._run_one_visit_full(
        visit_id=SINGLE_VISIT_ID,
        visit_keys=visit_keys,
        rules_by_id=rules_by_id,
        pack_concurrency=pack_concurrency,
    )
    summary = audit._apply_stability_counts(summary, raw)
    missing_after_retry = _issue_missing_after_retry_count(issues)
    first_pass_model = _safe_text(summary.get("first_pass_model"))
    adjudicator_model = _safe_text(summary.get("adjudicator_model"))
    model_ok = (
        first_pass_model == EXPECTED_FIRST_PASS_MODEL
        and adjudicator_model == EXPECTED_ADJUDICATOR_MODEL
    )
    stability_ok = _stability_ok(summary, missing_after_retry=missing_after_retry)
    return {
        "visit_id": SINGLE_VISIT_ID,
        "passed": bool(model_ok and stability_ok),
        "model_ok": bool(model_ok),
        "stability_ok": bool(stability_ok),
        "first_pass_model": first_pass_model,
        "adjudicator_model": adjudicator_model,
        "adjudicator_model_source": _safe_text(summary.get("adjudicator_model_source")),
        "missing_rule_after_retry": missing_after_retry,
        "provider_error_count": _safe_int(summary.get("provider_error_count")),
        "provider_connection_error_count": _safe_int(summary.get("provider_connection_error_count")),
        "upstream_http_error_count": _safe_int(summary.get("upstream_http_error_count")),
        "parse_error_count": _safe_int(summary.get("parse_error_count")),
        "timeout_count": _safe_int(summary.get("timeout_count")),
        "rate_limit_count": _safe_int(summary.get("rate_limit_count")),
        "technical_error_internal_count": _safe_int(summary.get("technical_error_internal_count")),
        "total_tokens": _safe_int(summary.get("total_tokens")),
        "llm_call_count": _safe_int(summary.get("llm_call_count")),
        "wall_clock_time": round(_safe_float(summary.get("wall_clock_time")), 3),
    }


def _quality_keep_rate(quality_payload: dict[str, Any]) -> tuple[int, int, float]:
    summary = quality_payload.get("summary") if isinstance(quality_payload.get("summary"), dict) else {}
    counts = summary.get("confirmed_review_counts") if isinstance(summary.get("confirmed_review_counts"), dict) else {}
    confirmed = _safe_int(summary.get("confirmed_total") or summary.get("confirmed_defect"))
    keep = _safe_int(counts.get("keep") or counts.get("confirmed_keep"))
    if not confirmed:
        reviews = quality_payload.get("reviews") if isinstance(quality_payload.get("reviews"), list) else []
        confirmed = len([row for row in reviews if row.get("review_scope") == "confirmed_full"])
    return confirmed, keep, round(keep / confirmed, 4) if confirmed else 0.0


def _rule_status(issue_payload: dict[str, Any], *, visit_id: str, rule_id: str) -> str:
    issues = issue_payload.get("issues") if isinstance(issue_payload.get("issues"), list) else []
    for row in issues:
        if _safe_text(row.get("visit_id")) == visit_id and _safe_text(row.get("rule_id")).upper() == rule_id:
            return _safe_text(row.get("display_status"))
    return "not_in_issue_review"


def _write_dual_model_report(
    *,
    probes: list[dict[str, Any]],
    single_visit_gate: dict[str, Any] | None = None,
    summary_payload: dict[str, Any],
    quality_payload: dict[str, Any],
    issue_payload: dict[str, Any],
) -> None:
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    display_counts = totals.get("display_status_counts") if isinstance(totals.get("display_status_counts"), dict) else {}
    confirmed_total, confirmed_keep, keep_rate = _quality_keep_rate(quality_payload)
    qwen35_baseline = _read_json(QWEN35_FAILURE_BASELINE_JSON)
    baseline_totals = qwen35_baseline.get("totals") if isinstance(qwen35_baseline.get("totals"), dict) else {}
    stable = bool(totals.get("stability_pass"))
    probe_pass = all(bool(row.get("passed")) for row in probes)
    first_pass_model = _safe_text((probes[0] if probes else {}).get("model"))
    adjudicator_model = _safe_text((probes[1] if len(probes) > 1 else {}).get("model"))
    lines = [
        "# 正式质控双模型 random10 只读验证报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 模型配置",
        f"- 一审模型：`{first_pass_model}`",
        f"- 二审模型：`{adjudicator_model}`",
        "- 策略：一审 fast_screen/pack 初筛使用 qwen3.5，二审 adjudicator 使用 qwen3.6。",
        "- 本轮只读运行，不写正式 QC 结果表，不扩大到 20 份。",
        f"- 无效前序结果说明：{INVALID_ENV_ASSIGNMENT_NOTE}",
        "",
        "## Minimal Probe",
    ]
    for row in probes:
        lines.append(
            "- {label}: model={model}, tokens={tokens}, passed={passed}, provider_error={provider_error}, "
            "upstream_http_error={upstream}, parse_error={parse}, timeout={timeout}, rate_limit={rate}".format(
                label=row.get("label"),
                model=row.get("model"),
                tokens=row.get("usage_total_tokens"),
                passed=row.get("passed"),
                provider_error=row.get("provider_error"),
                upstream=row.get("upstream_http_error"),
                parse=row.get("parse_error"),
                timeout=row.get("timeout"),
                rate=row.get("rate_limit"),
            )
        )
    single_visit_gate = single_visit_gate or {}
    lines.extend(
        [
            "",
            "## 2122521 单病历双模型门禁",
            f"- 状态：{'通过' if single_visit_gate.get('passed') else '未通过/未运行'}",
            f"- 一审模型：`{single_visit_gate.get('first_pass_model', '')}`",
            f"- 二审模型：`{single_visit_gate.get('adjudicator_model', '')}`",
            f"- adjudicator_model_source：`{single_visit_gate.get('adjudicator_model_source', '')}`",
            f"- technical_error_internal：{_safe_int(single_visit_gate.get('technical_error_internal_count'))}",
            f"- missing_rule_after_retry：{_safe_int(single_visit_gate.get('missing_rule_after_retry'))}",
            f"- total_tokens：{_safe_int(single_visit_gate.get('total_tokens'))}",
            "",
            "## 稳定性",
            f"- probe 门禁：{'通过' if probe_pass else '未通过'}",
            f"- random10 状态：`{summary_payload.get('report_status')}`",
            f"- 完成病历数：{_safe_int(totals.get('visit_count'))}/10",
            f"- provider_error：{_safe_int(totals.get('provider_error_count'))}",
            f"- provider_connection_error：{_safe_int(totals.get('provider_connection_error_count'))}",
            f"- upstream_http_error：{_safe_int(totals.get('upstream_http_error_count'))}",
            f"- parse_error：{_safe_int(totals.get('parse_error_count'))}",
            f"- timeout：{_safe_int(totals.get('timeout_count'))}",
            f"- rate_limit：{_safe_int(totals.get('rate_limit_count'))}",
            f"- technical_error_internal：{_safe_int(totals.get('technical_error_internal_count'))}",
            f"- 稳定性结论：{'通过' if stable else '未通过'}",
            "",
            "## 性能与成本",
            f"- 总耗时：{_safe_float(totals.get('total_wall_clock_time')):.2f}s",
            f"- 平均耗时：{_safe_float(totals.get('average_wall_clock_time')):.2f}s/份",
            f"- 最慢耗时：{_safe_float(totals.get('max_wall_clock_time')):.2f}s",
            f"- LLM 调用数：{_safe_int(totals.get('llm_call_count'))}",
            f"- 一审调用数：{_safe_int(totals.get('first_pass_llm_call_count'))}",
            f"- 二审调用数：{_safe_int(totals.get('adjudicator_llm_call_count'))}",
            f"- total_tokens：{_safe_int(totals.get('total_tokens'))}",
            f"- 一审 tokens：{_safe_int(totals.get('first_pass_total_tokens'))}",
            f"- 二审 tokens：{_safe_int(totals.get('adjudicator_total_tokens'))}",
            "",
            "## 结果分层",
            f"- confirmed_defect：{_safe_int(display_counts.get('confirmed_defect'))}",
            f"- data_quality_gap：{_safe_int(display_counts.get('data_quality_gap'))}",
            f"- rejected_by_system：{_safe_int(display_counts.get('rejected_by_system'))}",
            f"- technical_error_internal：{_safe_int(display_counts.get('technical_error_internal'))}",
            "",
            "## 质量参考",
            f"- confirmed 复核 keep：{confirmed_keep}/{confirmed_total}",
            f"- keep rate：{keep_rate:.1%}",
            f"- 2262370 / SC-118 状态：{_rule_status(issue_payload, visit_id='2262370', rule_id='SC-118')}",
            f"- 2328501 / SC-121 状态：{_rule_status(issue_payload, visit_id='2328501', rule_id='SC-121')}",
            "",
            "## 对比 qwen3.5 全链路失败基线",
            f"- qwen3.5 全链路完成数：{_safe_int(baseline_totals.get('visit_count'))}/10",
            f"- qwen3.5 全链路 technical_error_internal：{_safe_int(baseline_totals.get('technical_error_internal_count'))}",
            f"- qwen3.5 全链路稳定性：{bool(baseline_totals.get('stability_pass'))}",
            "",
            "## 结论",
        ]
    )
    if not probe_pass:
        lines.append("- minimal probe 未通过，不允许继续 random10 或质量结论。")
    elif single_visit_gate and not single_visit_gate.get("passed"):
        lines.append("- 2122521 单病历双模型门禁未通过，不允许继续 random10 或质量结论。")
    elif not stable:
        lines.append("- 双模型 random10 稳定性未通过，不建议扩大到 20 份或页面演示。")
    else:
        lines.append("- 双模型 random10 稳定性通过，说明 qwen3.5 一审 + qwen3.6 二审可恢复二审输出完整性。")
        if keep_rate >= 0.7 and confirmed_total >= 3:
            lines.append("- confirmed 质量达到阶段目标，可建议进入 20 份只读验收。")
            lines.append("- 页面演示可作为候选，但仍建议先完成 20 份只读验收。")
        else:
            lines.append("- confirmed 质量仍未达到 70% 阈值，不建议直接扩大到 20 份。")
            lines.append("- 暂不建议页面演示；下一步应继续治理 confirmed 低 keep 规则，而不是扩大样本。")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def _run(args: argparse.Namespace) -> None:
    probes = await _run_minimal_probes()
    audit._write_csv(args.probe_csv, probes)
    _write_json(args.probe_json, {"probes": probes})
    if not _probe_models_ok(probes):
        _write_json(
            args.summary_json,
            {
                "report_status": "failed_minimal_probe_or_model_mismatch",
                "invalid_previous_result": "invalid_env_assignment",
                "invalid_previous_result_reason": INVALID_ENV_ASSIGNMENT_NOTE,
                "probes": probes,
                "totals": {"stability_pass": False},
            },
        )
        _write_dual_model_report(
            probes=probes,
            single_visit_gate={},
            summary_payload=_read_json(args.summary_json),
            quality_payload={},
            issue_payload={},
        )
        print("minimal probe failed; stop before random10")
        return

    single_visit_gate = await _run_single_visit_gate(pack_concurrency=args.pack_concurrency)
    if not single_visit_gate.get("passed"):
        _write_json(
            args.summary_json,
            {
                "report_status": "failed_single_visit_dual_model_gate",
                "invalid_previous_result": "invalid_env_assignment",
                "invalid_previous_result_reason": INVALID_ENV_ASSIGNMENT_NOTE,
                "probes": probes,
                "single_visit_gate": single_visit_gate,
                "totals": {"stability_pass": False},
            },
        )
        _write_dual_model_report(
            probes=probes,
            single_visit_gate=single_visit_gate,
            summary_payload=_read_json(args.summary_json),
            quality_payload={},
            issue_payload={},
        )
        print("single visit dual-model gate failed; stop before random10")
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
    summary_payload["dual_model_probes"] = probes
    summary_payload["single_visit_gate"] = single_visit_gate
    summary_payload["invalid_previous_result"] = "invalid_env_assignment"
    summary_payload["invalid_previous_result_reason"] = INVALID_ENV_ASSIGNMENT_NOTE
    summary_payload["first_pass_model"] = probes[0].get("model") if probes else ""
    summary_payload["adjudicator_model"] = probes[1].get("model") if len(probes) > 1 else ""
    _write_json(args.summary_json, summary_payload)
    _write_dual_model_report(
        probes=probes,
        single_visit_gate=single_visit_gate,
        summary_payload=summary_payload,
        quality_payload=_read_json(args.quality_json),
        issue_payload=_read_json(args.issue_json),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式质控一审/二审双模型 random10 只读验证。")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--issue-csv", type=Path, default=ISSUE_CSV)
    parser.add_argument("--issue-json", type=Path, default=ISSUE_JSON)
    parser.add_argument("--quality-csv", type=Path, default=QUALITY_CSV)
    parser.add_argument("--quality-json", type=Path, default=QUALITY_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--probe-csv", type=Path, default=DOCS_DIR / "formal_qc_dual_model_minimal_probe.csv")
    parser.add_argument("--probe-json", type=Path, default=DOCS_DIR / "formal_qc_dual_model_minimal_probe.json")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
