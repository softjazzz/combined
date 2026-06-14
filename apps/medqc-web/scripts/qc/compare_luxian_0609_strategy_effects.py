from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS = (
    ROOT / ".runtime-logs" / "qc-pack-poc" / "luxian_0609_pack_strategy_20260613-090704.json",
    ROOT / ".runtime-logs" / "qc-pack-poc" / "luxian_0609_pack_strategy_20260613-091115.json",
    ROOT / ".runtime-logs" / "qc-pack-poc" / "luxian_0609_pack_strategy_20260613-091530.json",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_map(strategy_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _safe_text(item.get("rule_id")): dict(item)
        for item in list(strategy_summary.get("rule_results") or [])
        if _safe_text(item.get("rule_id"))
    }


def _decision_key(item: dict[str, Any] | None) -> tuple[str, bool]:
    if not item:
        return ("missing", False)
    return (_safe_text(item.get("status")) or "unknown", bool(item.get("is_compliant") is True))


def _clip(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def analyze_report(report: dict[str, Any], left: str, right: str) -> dict[str, Any]:
    strategies = dict(report.get("strategies") or {})
    left_summary = dict(strategies.get(left) or {})
    right_summary = dict(strategies.get(right) or {})
    left_map = _result_map(left_summary)
    right_map = _result_map(right_summary)
    rule_ids = sorted(set(left_map) | set(right_map))
    differences: list[dict[str, Any]] = []
    same_counter: Counter[str] = Counter()
    diff_counter: Counter[str] = Counter()

    for rule_id in rule_ids:
        left_item = left_map.get(rule_id)
        right_item = right_map.get(rule_id)
        left_decision = _decision_key(left_item)
        right_decision = _decision_key(right_item)
        if left_decision == right_decision:
            same_counter[left_decision[0]] += 1
            continue
        diff_counter[f"{left_decision[0]} -> {right_decision[0]}"] += 1
        differences.append(
            {
                "visit_id": report.get("visit_id"),
                "rule_id": rule_id,
                "rule_name": _safe_text((left_item or right_item or {}).get("rule_name")),
                f"{left}_status": left_decision[0],
                f"{left}_is_compliant": left_decision[1],
                f"{left}_confidence": (left_item or {}).get("confidence"),
                f"{left}_findings": _clip((left_item or {}).get("findings")),
                f"{left}_evidence": _clip((left_item or {}).get("evidence")),
                f"{right}_status": right_decision[0],
                f"{right}_is_compliant": right_decision[1],
                f"{right}_confidence": (right_item or {}).get("confidence"),
                f"{right}_findings": _clip((right_item or {}).get("findings")),
                f"{right}_evidence": _clip((right_item or {}).get("evidence")),
            }
        )

    return {
        "visit_id": report.get("visit_id"),
        "patient_name": (report.get("record") or {}).get("patient_name"),
        "department": (report.get("record") or {}).get("department"),
        "left": left,
        "right": right,
        "left_metrics": {
            key: left_summary.get(key)
            for key in ("elapsed_ms", "tokens", "fallback_pack_count", "pack_count", "final_result_count", "terminal_status_count")
        },
        "right_metrics": {
            key: right_summary.get(key)
            for key in ("elapsed_ms", "tokens", "fallback_pack_count", "pack_count", "final_result_count", "terminal_status_count")
        },
        "same_decision_count": sum(same_counter.values()),
        "different_decision_count": len(differences),
        "difference_distribution": dict(diff_counter),
        "differences": differences,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 泸县0609质控策略效果差异复核清单")
    lines.append("")
    lines.append(f"- 生成时间：{report.get('generated_at')}")
    lines.append(f"- 对比策略：`{report.get('left')}` vs `{report.get('right')}`")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append("| 病历 | 科室 | 相同结论 | 不同结论 | baseline耗时/token | domain耗时/token | 差异分布 |")
    lines.append("| --- | --- | ---: | ---: | --- | --- | --- |")
    for item in report.get("reports") or []:
        left_metrics = item.get("left_metrics") or {}
        right_metrics = item.get("right_metrics") or {}
        lines.append(
            "| "
            f"{item.get('visit_id')} {item.get('patient_name') or ''} | {item.get('department') or ''} | "
            f"{item.get('same_decision_count')} | {item.get('different_decision_count')} | "
            f"{left_metrics.get('elapsed_ms')}/{left_metrics.get('tokens')} | "
            f"{right_metrics.get('elapsed_ms')}/{right_metrics.get('tokens')} | "
            f"`{json.dumps(item.get('difference_distribution') or {}, ensure_ascii=False)}` |"
        )
    lines.append("")
    lines.append("## 待人工复核差异")
    lines.append("")
    for item in report.get("reports") or []:
        lines.append(f"### {item.get('visit_id')} {item.get('patient_name') or ''} / {item.get('department') or ''}")
        lines.append("")
        differences = list(item.get("differences") or [])
        if not differences:
            lines.append("- 无策略结论差异。")
            lines.append("")
            continue
        lines.append("| 规则 | 名称 | baseline | domain_family_max5 | baseline依据 | domain依据 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for diff in differences:
            lines.append(
                "| "
                f"{diff.get('rule_id')} | {_clip(diff.get('rule_name'), 32)} | "
                f"{diff.get('baseline_current_status')} / {diff.get('baseline_current_confidence')} | "
                f"{diff.get('domain_family_max5_status')} / {diff.get('domain_family_max5_confidence')} | "
                f"{_clip(diff.get('baseline_current_findings') or diff.get('baseline_current_evidence'), 90)} | "
                f"{_clip(diff.get('domain_family_max5_findings') or diff.get('domain_family_max5_evidence'), 90)} |"
            )
        lines.append("")
    lines.append("## 复核口径")
    lines.append("")
    lines.append("- 优先人工复核两策略结论不同的规则。")
    lines.append("- 重点判断：是否误报、漏报、不适用误判、证据不足。")
    lines.append("- 如果 baseline 与 domain_family 结论不同，以源文书证据为准，不以模型置信度为准。")
    return "\n".join(lines) + "\n"


def write_outputs(data: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"luxian_0609_strategy_effect_compare_{stamp}.json"
    md_path = output_dir / f"luxian_0609_strategy_effect_compare_{stamp}.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="对比泸县0609不同分桶策略的规则级效果差异")
    parser.add_argument("--reports", nargs="*", default=[str(path) for path in DEFAULT_REPORTS])
    parser.add_argument("--left", default="baseline_current")
    parser.add_argument("--right", default="domain_family_max5")
    parser.add_argument("--output-dir", default=str(ROOT / ".runtime-logs" / "qc-pack-poc"))
    args = parser.parse_args()

    report_paths = [Path(item) for item in args.reports]
    analyses = [analyze_report(_load_json(path), args.left, args.right) for path in report_paths]
    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "left": args.left,
        "right": args.right,
        "source_reports": [str(path) for path in report_paths],
        "reports": analyses,
    }
    json_path, md_path = write_outputs(output, Path(args.output_dir))
    print(f"Effect JSON: {json_path}")
    print(f"Effect Markdown: {md_path}")
    for item in analyses:
        print(
            f"{item.get('visit_id')}: same={item.get('same_decision_count')} "
            f"diff={item.get('different_decision_count')} "
            f"distribution={item.get('difference_distribution')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
