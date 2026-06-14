from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

CATALOG_PATH = DOCS_DIR / "luxian_0609_formal_rule_catalog.json"
GOLDEN_CASES_PATH = DOCS_DIR / "泸县0609质控点-golden-cases.json"
EVAL_PATH = DOCS_DIR / "luxian_0609_qc_eval.json"
CANDIDATE_COVERAGE_PATH = DOCS_DIR / "luxian_0609_candidate_coverage.json"
REVIEW_QUEUE_QUALITY_PATH = DOCS_DIR / "luxian_0609_review_queue_quality.json"
READINESS_DASHBOARD_PATH = DOCS_DIR / "luxian_0609_readiness_dashboard.json"
FORMAL_WORK_PACKAGES_PATH = DOCS_DIR / "luxian_0609_formal_launch_work_packages.json"
CUSTOMER_SAMPLE_PAGE_EVIDENCE_PATH = DOCS_DIR / "luxian_0609_customer_sample_page_evidence.json"

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_release_gate.json"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-正式版发布闸门报告.md"

RULE_SOURCE_PATHS = (
    ROOT / "backend" / "app" / "data" / "sichuan_rules_146.json",
    ROOT / "backend" / "app" / "data" / "custom_rules_33.json",
    ROOT / "backend" / "app" / "data" / "customer_rules_luxian_v1.json",
)
PROGRAMMATIC_EXECUTOR_PATH = ROOT / "backend" / "app" / "services" / "programmatic_rule_executor.py"

CASE_TYPES = ("positive", "negative", "boundary")
EXPECTED_RULE_COUNT = 49

REQUIRED_IMPLEMENTATION_STATUSES = {"formal_ready"}
BLOCKING_IMPLEMENTATION_STATUSES = {
    "needs_evidence_hardening",
    "needs_cross_document",
    "needs_data_linkage",
    "needs_rule_implementation",
}


def load_executable_rule_ids() -> set[str]:
    rule_ids: set[str] = set()
    for path in RULE_SOURCE_PATHS:
        if not path.exists():
            continue
        data = load_json(path, [])
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            for key in ("rule_id", "ruleId", "id", "code", "rule_code"):
                rule_id = normalize(item.get(key)).upper()
                if rule_id:
                    rule_ids.add(rule_id)
                    break
    if PROGRAMMATIC_EXECUTOR_PATH.exists():
        import re

        text = PROGRAMMATIC_EXECUTOR_PATH.read_text(encoding="utf-8")
        rule_ids.update(match.upper() for match in re.findall(r'"([A-Z]+-\d+)"\s*:\s*ProgrammaticRuleSpec\(', text))
    return rule_ids


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str:
    return str(value or "").strip()


def status_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(normalize(row.get(key)) or "unknown" for row in rows))


def summarize_catalog() -> dict[str, Any]:
    rows = load_json(CATALOG_PATH, [])
    if not isinstance(rows, list):
        rows = []
    executable_rule_ids = load_executable_rule_ids()
    implementation_status = status_counts(rows, "implementation_status")
    missing_required_fields: list[dict[str, Any]] = []
    missing_executable_rule_ids: list[dict[str, Any]] = []
    required_fields = (
        "qc_point_id",
        "source_index",
        "customer_text",
        "standardized_rule",
        "rule_basis",
        "evidence_summary_template",
        "suggestion_template",
        "allowed_result_statuses",
    )
    for row in rows:
        missing = [field for field in required_fields if row.get(field) in (None, "", [])]
        allowed_statuses = set(row.get("allowed_result_statuses") or [])
        for required_status in ("hit", "not_hit", "data_quality_gap"):
            if required_status not in allowed_statuses:
                missing.append(f"allowed_result_statuses.{required_status}")
        if missing:
            missing_required_fields.append(
                {
                    "qc_point_id": row.get("qc_point_id"),
                    "missing": missing,
                }
            )
        row_rule_ids = [normalize(rule_id).upper() for rule_id in (row.get("rule_ids") or []) if normalize(rule_id)]
        missing_rule_ids = [rule_id for rule_id in row_rule_ids if rule_id not in executable_rule_ids]
        if missing_rule_ids:
            missing_executable_rule_ids.append(
                {
                    "qc_point_id": row.get("qc_point_id"),
                    "missing_rule_ids": missing_rule_ids,
                }
            )
    blocking_rules = [
        {
            "qc_point_id": row.get("qc_point_id"),
            "implementation_status": row.get("implementation_status"),
            "customer_text": row.get("customer_text"),
        }
        for row in rows
        if normalize(row.get("implementation_status")) in BLOCKING_IMPLEMENTATION_STATUSES
    ]
    return {
        "rule_count": len(rows),
        "implementation_status": implementation_status,
        "missing_required_field_count": len(missing_required_fields),
        "missing_required_fields": missing_required_fields[:20],
        "executable_rule_id_count": len(executable_rule_ids),
        "missing_executable_rule_id_count": len(missing_executable_rule_ids),
        "missing_executable_rule_ids": missing_executable_rule_ids[:20],
        "blocking_rule_count": len(blocking_rules),
        "blocking_rules": blocking_rules[:20],
    }


def summarize_golden_cases() -> dict[str, Any]:
    data = load_json(GOLDEN_CASES_PATH, {"rules": []})
    rows = data.get("rules") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []
    missing_by_rule: list[dict[str, Any]] = []
    rules_with_all_case_types = 0
    case_type_totals = Counter()
    total_cases = 0
    for row in rows:
        qc_point_id = normalize(row.get("qc_point_id"))
        cases = row.get("cases") if isinstance(row.get("cases"), dict) else {}
        counts = {case_type: len(cases.get(case_type) or []) for case_type in CASE_TYPES}
        for case_type, count in counts.items():
            case_type_totals[case_type] += count
            total_cases += count
        missing = [case_type for case_type, count in counts.items() if count <= 0]
        if missing:
            missing_by_rule.append(
                {
                    "qc_point_id": qc_point_id,
                    "missing_case_types": missing,
                }
            )
        else:
            rules_with_all_case_types += 1
    return {
        "rule_count": len(rows),
        "total_cases": total_cases,
        "case_type_totals": dict(case_type_totals),
        "rules_with_all_case_types": rules_with_all_case_types,
        "rules_missing_case_types": len(missing_by_rule),
        "missing_by_rule": missing_by_rule[:20],
    }


def summarize_eval() -> dict[str, Any]:
    data = load_json(EVAL_PATH, {"summary": {}, "results": []})
    summary = data.get("summary") if isinstance(data, dict) else {}
    results = data.get("results") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(results, list):
        results = []
    launch_status = summary.get("launch_status")
    if not isinstance(launch_status, dict):
        launch_status = status_counts(results, "launch_status")
    failed_rules = [
        {
            "qc_point_id": row.get("qc_point_id"),
            "launch_status": row.get("launch_status"),
            "precision": row.get("precision"),
            "recall": row.get("recall"),
            "not_ready_reasons": row.get("not_ready_reasons") or [],
        }
        for row in results
        if normalize(row.get("launch_status")) != "formal_candidate"
    ]
    return {
        "rule_count": summary.get("rule_count", len(results)),
        "launch_status": launch_status,
        "rules_with_all_case_types": summary.get("rules_with_all_case_types", 0),
        "rules_missing_case_types": summary.get("rules_missing_case_types", 0),
        "failed_rule_count": len(failed_rules),
        "failed_rules": failed_rules[:20],
    }


def summarize_candidate_coverage() -> dict[str, Any]:
    data = load_json(CANDIDATE_COVERAGE_PATH, {"summary": {}})
    summary = data.get("summary") if isinstance(data, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    return {
        "rule_count": summary.get("rule_count", 0),
        "formal_cases_ready": summary.get("formal_cases_ready", 0),
        "ready_for_review": summary.get("ready_for_review", 0),
        "partial_candidates": summary.get("partial_candidates", 0),
        "no_candidates": summary.get("no_candidates", 0),
        "total_candidates": summary.get("total_candidates", 0),
        "pending_candidates": summary.get("pending_candidates", 0),
        "accepted_candidates": summary.get("accepted_candidates", 0),
        "rejected_candidates": summary.get("rejected_candidates", 0),
        "coverage_status_counts": summary.get("coverage_status_counts") or {},
    }


def summarize_review_queue_quality() -> dict[str, Any]:
    data = load_json(REVIEW_QUEUE_QUALITY_PATH, {"summary": {}, "errors": []})
    summary = data.get("summary") if isinstance(data, dict) else {}
    errors = data.get("errors") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(errors, list):
        errors = []
    return {
        "row_count": summary.get("row_count", 0),
        "error_count": summary.get("error_count", len(errors)),
        "status_counts": summary.get("status_counts") or {},
        "case_type_counts": summary.get("case_type_counts") or {},
        "accepted_rule_count": summary.get("accepted_rule_count", 0),
        "errors": errors[:20],
    }


def summarize_readiness_dashboard() -> dict[str, Any]:
    data = load_json(READINESS_DASHBOARD_PATH, {"summary": {}})
    summary = data.get("summary") if isinstance(data, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    return {
        "rule_count": summary.get("rule_count", 0),
        "stage_summary": summary.get("stage_summary") or {},
        "implementation_status": summary.get("implementation_status") or {},
        "rules_with_all_case_types": summary.get("rules_with_all_case_types", 0),
        "rules_with_review_candidates": summary.get("rules_with_review_candidates", 0),
        "rules_with_ready_evidence_pack": summary.get("rules_with_ready_evidence_pack", 0),
        "formal_candidates": summary.get("formal_candidates", 0),
    }


def summarize_customer_sample_page_evidence() -> dict[str, Any]:
    data = load_json(CUSTOMER_SAMPLE_PAGE_EVIDENCE_PATH, {"summary": {}, "blocking": []})
    summary = data.get("summary") if isinstance(data, dict) else {}
    blocking = data.get("blocking") if isinstance(data, dict) else []
    capabilities = data.get("capabilities") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(blocking, list):
        blocking = []
    if not isinstance(capabilities, list):
        capabilities = []
    return {
        "exists": CUSTOMER_SAMPLE_PAGE_EVIDENCE_PATH.exists(),
        "page_verified": bool(summary.get("page_verified")),
        "capability_count": summary.get("capability_count", len(capabilities)),
        "status_counts": summary.get("status_counts") or {},
        "passed_capabilities": summary.get("passed_capabilities", 0),
        "partial_capabilities": summary.get("partial_capabilities", 0),
        "failed_capabilities": summary.get("failed_capabilities", 0),
        "blocking_count": summary.get("blocking_count", len(blocking)),
        "blocking": blocking[:20],
    }


def summarize_formal_work_packages() -> dict[str, Any]:
    data = load_json(FORMAL_WORK_PACKAGES_PATH, {"summary": {}, "packages": []})
    summary = data.get("summary") if isinstance(data, dict) else {}
    packages = data.get("packages") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(packages, list):
        packages = []
    missing_task_packages: list[dict[str, Any]] = []
    for item in packages:
        if not isinstance(item, dict):
            continue
        missing = [
            field
            for field in ("implementation_tasks", "evidence_tasks", "sample_tasks", "evaluation_tasks", "page_validation_tasks", "acceptance_gate")
            if not item.get(field)
        ]
        if missing:
            missing_task_packages.append({"qc_point_id": item.get("qc_point_id"), "missing": missing})
    return {
        "package_count": summary.get("package_count", len(packages)),
        "phase_counts": summary.get("phase_counts") or {},
        "priority_counts": summary.get("priority_counts") or {},
        "missing_task_package_count": len(missing_task_packages),
        "missing_task_packages": missing_task_packages[:20],
    }


def check(status: str, key: str, title: str, message: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "status": status,
        "message": message,
        "evidence": evidence or {},
    }


def build_gate() -> dict[str, Any]:
    catalog = summarize_catalog()
    golden = summarize_golden_cases()
    evaluation = summarize_eval()
    candidate_coverage = summarize_candidate_coverage()
    review_queue_quality = summarize_review_queue_quality()
    readiness = summarize_readiness_dashboard()
    formal_work_packages = summarize_formal_work_packages()
    customer_sample_page = summarize_customer_sample_page_evidence()

    checks: list[dict[str, Any]] = []

    catalog_complete = (
        catalog["rule_count"] == EXPECTED_RULE_COUNT
        and catalog["missing_required_field_count"] == 0
        and catalog["missing_executable_rule_id_count"] == 0
    )
    checks.append(
        check(
            "pass" if catalog_complete else "fail",
            "catalog_complete",
            "规则目录完整",
            "49 条质控点均有正式上线字段。" if catalog_complete else "规则目录数量或字段不完整。",
            {
                "rule_count": catalog["rule_count"],
                "missing_required_field_count": catalog["missing_required_field_count"],
                "missing_executable_rule_id_count": catalog["missing_executable_rule_id_count"],
                "executable_rule_id_count": catalog["executable_rule_id_count"],
            },
        )
    )

    implementation_ready = (
        catalog["rule_count"] == EXPECTED_RULE_COUNT
        and catalog["blocking_rule_count"] == 0
        and set(catalog["implementation_status"]).issubset(REQUIRED_IMPLEMENTATION_STATUSES)
    )
    checks.append(
        check(
            "pass" if implementation_ready else "fail",
            "implementation_ready",
            "规则实现可执行",
            "所有规则均达到 formal_ready。" if implementation_ready else "仍有规则处于待补强、跨文书、数据联查或待实现状态。",
            {
                "implementation_status": catalog["implementation_status"],
                "blocking_rule_count": catalog["blocking_rule_count"],
            },
        )
    )

    golden_ready = (
        golden["rule_count"] == EXPECTED_RULE_COUNT
        and golden["rules_with_all_case_types"] == EXPECTED_RULE_COUNT
        and golden["total_cases"] >= EXPECTED_RULE_COUNT * len(CASE_TYPES)
    )
    checks.append(
        check(
            "pass" if golden_ready else "fail",
            "golden_cases_ready",
            "Golden cases 齐备",
            "每条规则都有阳性、阴性、边界样本。" if golden_ready else "Golden cases 尚未补齐，不能计算可信准确性。",
            {
                "rules_with_all_case_types": golden["rules_with_all_case_types"],
                "rules_missing_case_types": golden["rules_missing_case_types"],
                "case_type_totals": golden["case_type_totals"],
            },
        )
    )

    review_queue_clean = review_queue_quality["error_count"] == 0
    checks.append(
        check(
            "pass" if review_queue_clean else "fail",
            "review_queue_quality",
            "人工复核队列质量",
            "复核队列结构校验通过。" if review_queue_clean else "复核队列存在结构或状态错误。",
            {
                "row_count": review_queue_quality["row_count"],
                "error_count": review_queue_quality["error_count"],
                "status_counts": review_queue_quality["status_counts"],
            },
        )
    )

    work_packages_ready = (
        formal_work_packages["package_count"] == EXPECTED_RULE_COUNT
        and formal_work_packages["missing_task_package_count"] == 0
    )
    checks.append(
        check(
            "pass" if work_packages_ready else "fail",
            "formal_work_packages_ready",
            "正式上线工作包齐备",
            "49 条质控点均已拆成实现、证据、样本、评估和页面验收任务。"
            if work_packages_ready
            else "正式上线工作包缺失或任务字段不完整。",
            {
                "package_count": formal_work_packages["package_count"],
                "phase_counts": formal_work_packages["phase_counts"],
                "priority_counts": formal_work_packages["priority_counts"],
                "missing_task_package_count": formal_work_packages["missing_task_package_count"],
            },
        )
    )

    review_completed = (
        review_queue_quality["row_count"] > 0
        and review_queue_quality["status_counts"].get("pending", 0) == 0
        and review_queue_quality["accepted_rule_count"] == EXPECTED_RULE_COUNT
    )
    checks.append(
        check(
            "pass" if review_completed else "fail",
            "review_completed",
            "人工复核完成",
            "候选样本已完成复核并覆盖全部规则。" if review_completed else "候选样本仍未完成复核或未覆盖全部规则。",
            {
                "row_count": review_queue_quality["row_count"],
                "accepted_rule_count": review_queue_quality["accepted_rule_count"],
                "status_counts": review_queue_quality["status_counts"],
            },
        )
    )

    candidates_ready = (
        candidate_coverage["formal_cases_ready"] == EXPECTED_RULE_COUNT
        and candidate_coverage["partial_candidates"] == 0
        and candidate_coverage["no_candidates"] == 0
    )
    checks.append(
        check(
            "pass" if candidates_ready else "fail",
            "candidate_coverage",
            "样本覆盖完整",
            "49 条规则均具备可用正式样本。" if candidates_ready else "仍有规则缺候选样本或候选样本不完整。",
            {
                "formal_cases_ready": candidate_coverage["formal_cases_ready"],
                "ready_for_review": candidate_coverage["ready_for_review"],
                "partial_candidates": candidate_coverage["partial_candidates"],
                "no_candidates": candidate_coverage["no_candidates"],
                "total_candidates": candidate_coverage["total_candidates"],
            },
        )
    )

    eval_ready = (
        evaluation["rule_count"] == EXPECTED_RULE_COUNT
        and evaluation["failed_rule_count"] == 0
        and evaluation["launch_status"].get("formal_candidate", 0) == EXPECTED_RULE_COUNT
    )
    checks.append(
        check(
            "pass" if eval_ready else "fail",
            "accuracy_evaluation",
            "准确性评估达标",
            "全部规则达到发布候选标准。" if eval_ready else "评估结果仍未达到发布候选标准。",
            {
                "launch_status": evaluation["launch_status"],
                "failed_rule_count": evaluation["failed_rule_count"],
                "rules_with_all_case_types": evaluation["rules_with_all_case_types"],
            },
        )
    )

    frontend_verified = customer_sample_page["exists"] and customer_sample_page["page_verified"]
    checks.append(
        check(
            "pass" if frontend_verified else ("fail" if customer_sample_page["exists"] else "unverified"),
            "customer_sample_page_verified",
            "样本验证页面闭环",
            "客户样本验证页面闭环已通过页面证据检查。"
            if frontend_verified
            else (
                "页面已有部分证据，但仍缺少完整闭环验收能力。"
                if customer_sample_page["exists"]
                else "尚未提供页面级自动化或人工验收证据，需验证规则集选择、任务执行、结果展示和证据跳转。"
            ),
            {
                "target_page": "/workstation-v4/customer-sample-validation",
                "expected_rule_set": "luxian_0609_qc_v1",
                "evidence_file": str(CUSTOMER_SAMPLE_PAGE_EVIDENCE_PATH),
                "capability_count": customer_sample_page["capability_count"],
                "status_counts": customer_sample_page["status_counts"],
                "blocking_count": customer_sample_page["blocking_count"],
            },
        )
    )

    release_ready = all(item["status"] == "pass" for item in checks) and frontend_verified
    blockers = [
        {
            "key": item["key"],
            "title": item["title"],
            "message": item["message"],
            "evidence": item["evidence"],
        }
        for item in checks
        if item["status"] in {"fail", "unverified"}
    ]

    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "model": "qwen3.5-35b-a3b",
        "release_ready": release_ready,
        "summary": {
            "rule_count": EXPECTED_RULE_COUNT,
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
            "unverified_checks": sum(1 for item in checks if item["status"] == "unverified"),
            "blocking_count": len(blockers),
        },
        "checks": checks,
        "blockers": blockers,
        "inputs": {
            "catalog": str(CATALOG_PATH),
            "golden_cases": str(GOLDEN_CASES_PATH),
            "evaluation": str(EVAL_PATH),
            "candidate_coverage": str(CANDIDATE_COVERAGE_PATH),
            "review_queue_quality": str(REVIEW_QUEUE_QUALITY_PATH),
            "readiness_dashboard": str(READINESS_DASHBOARD_PATH),
            "formal_work_packages": str(FORMAL_WORK_PACKAGES_PATH),
            "customer_sample_page_evidence": str(CUSTOMER_SAMPLE_PAGE_EVIDENCE_PATH),
        },
        "evidence": {
            "catalog": catalog,
            "golden_cases": golden,
            "evaluation": evaluation,
            "candidate_coverage": candidate_coverage,
            "review_queue_quality": review_queue_quality,
            "readiness_dashboard": readiness,
            "formal_work_packages": formal_work_packages,
            "customer_sample_page": customer_sample_page,
        },
    }


def format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_markdown(gate: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 泸县0609质控点-正式版发布闸门报告")
    lines.append("")
    lines.append(f"- 规则集：`{gate['rule_set_key']}`")
    lines.append(f"- 模型：`{gate['model']}`")
    lines.append(f"- 结论：{'可以发布' if gate['release_ready'] else '暂不能发布'}")
    lines.append(
        f"- 检查项：通过 {gate['summary']['passed_checks']}，失败 {gate['summary']['failed_checks']}，未验证 {gate['summary']['unverified_checks']}"
    )
    lines.append("")
    lines.append("## 闸门检查")
    lines.append("")
    lines.append("| 检查项 | 状态 | 说明 | 关键证据 |")
    lines.append("| --- | --- | --- | --- |")
    for item in gate["checks"]:
        evidence = item.get("evidence") or {}
        evidence_text = "<br>".join(
            f"{key}: {format_value(value)}"
            for key, value in evidence.items()
            if key in {
                "rule_count",
                "missing_required_field_count",
                "missing_executable_rule_id_count",
                "executable_rule_id_count",
                "implementation_status",
                "blocking_rule_count",
                "rules_with_all_case_types",
                "rules_missing_case_types",
                "case_type_totals",
                "row_count",
                "error_count",
                "status_counts",
                "accepted_rule_count",
                "package_count",
                "phase_counts",
                "priority_counts",
                "missing_task_package_count",
                "formal_cases_ready",
                "ready_for_review",
                "partial_candidates",
                "no_candidates",
                "total_candidates",
                "launch_status",
                "failed_rule_count",
                "target_page",
                "expected_rule_set",
                "evidence_file",
                "capability_count",
            }
        )
        lines.append(f"| {item['title']} | {item['status']} | {item['message']} | {evidence_text} |")
    lines.append("")
    lines.append("## 当前阻塞")
    lines.append("")
    if gate["blockers"]:
        for index, blocker in enumerate(gate["blockers"], start=1):
            lines.append(f"{index}. **{blocker['title']}**：{blocker['message']}")
    else:
        lines.append("无。")
    lines.append("")
    lines.append("## 下一步")
    lines.append("")
    lines.append("1. 先完成人工复核：从 P0 复核表开始，确认阳性、阴性、边界样本。")
    lines.append("2. 将已接受样本导入 golden cases，并重新运行准确性评估。")
    lines.append("3. 对 `needs_cross_document`、`needs_data_linkage`、`needs_rule_implementation` 规则补齐执行链路。")
    lines.append("4. 在客户样本验证页面验证规则集选择、批量执行、结果证据和详情跳转。")
    lines.append("5. 重新运行本闸门，全部通过后再切换为正式上线规则集。")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Luxian 0609 QC release gate.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown reports.")
    parser.add_argument("--no-fail", action="store_true", help="Always exit 0, even when release gate fails.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = build_gate()
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
        OUTPUT_MD_PATH.write_text(build_markdown(gate), encoding="utf-8")
    print(
        json.dumps(
            {
                "release_ready": gate["release_ready"],
                "summary": gate["summary"],
                "blockers": [blocker["key"] for blocker in gate["blockers"]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.no_fail:
        return 0
    return 0 if gate["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
