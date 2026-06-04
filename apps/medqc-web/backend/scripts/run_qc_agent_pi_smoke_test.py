#!/usr/bin/env python
"""External QC Agent regression harness for the isolated Pi Agent test venv.

The harness deliberately avoids importing MedQC backend packages. It follows a
small agents/workflow/run style structure, while using requests as the stable
transport to call the local MedQC QC Agent chat API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import requests


APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = APP_ROOT / "docs" / "0602"
CHAT_PATH = "/api/v1/qc-agent/chat"
LOGIN_PATH = "/api/v1/auth/login"
VALID_STATUSES = {"completed", "needs_clarification", "needs_confirmation", "unsupported"}
SENSITIVE_KEYS = {
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "structured_context",
    "prompt",
    "examples",
    "internal_data",
    "raw_llm_output",
}


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    message: str
    expected_statuses: set[str]
    required_plan_tools_when_completed: set[str] = field(default_factory=set)
    skip_reason: str | None = None


@dataclass
class HarnessEnvironment:
    python_version: str
    pi_agent_installed: str | None
    pi_agent_core_installed: str | None
    requests_installed: str | None
    orchestration_mode: str


@dataclass
class AuthContext:
    token: str | None
    auth_mode: str
    login_attempted: bool = False
    masked_account: str | None = None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run QC Agent regression cases from the isolated Pi Agent test venv."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8001",
        help="MedQC backend base URL. Default: http://127.0.0.1:8001",
    )
    parser.add_argument("--visit-id", help="Local visit_id used by visit-scoped regression cases.")
    parser.add_argument("--patient-name", help="Optional patient name for search-style regression case.")
    parser.add_argument("--department", help="Optional department for search-style regression case.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Report output directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--env-check", action="store_true", help="Only check Python/Pi/request environment.")
    parser.add_argument("--case", help="Run only one case id.")
    parser.add_argument("--login-account", help="Optional login account used when MEDQC_ACCESS_TOKEN is absent.")
    parser.add_argument("--login-password", help="Optional login password used when MEDQC_ACCESS_TOKEN is absent.")
    parser.add_argument("--no-auto-login", action="store_true", help="Disable login fallback when MEDQC_ACCESS_TOKEN is absent.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds.")
    return parser.parse_args()


def package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def inspect_environment() -> HarnessEnvironment:
    if sys.version_info < (3, 11):
        print("错误：该 harness 必须使用 Python 3.11+ 虚拟环境运行。", file=sys.stderr)
        print(f"当前版本：{sys.version}", file=sys.stderr)
        raise SystemExit(2)

    return HarnessEnvironment(
        python_version=sys.version.split()[0],
        pi_agent_installed=package_version("pi-agent"),
        pi_agent_core_installed=package_version("pi-agent-core"),
        requests_installed=package_version("requests"),
        orchestration_mode="requests_fallback",
    )


def print_environment(environment: HarnessEnvironment) -> None:
    print(f"Python: {environment.python_version}")
    print(f"pi-agent: {environment.pi_agent_installed or '未安装'}")
    print(f"pi-agent-core: {environment.pi_agent_core_installed or '未安装'}")
    print(f"requests: {environment.requests_installed or '未安装'}")
    print(f"orchestration_mode: {environment.orchestration_mode}")
    if not environment.pi_agent_installed and not environment.pi_agent_core_installed:
        print("错误：未检测到 pi-agent 或 pi-agent-core，请先在 .venv-pi-agent-test 中安装。", file=sys.stderr)
        raise SystemExit(2)
    if not environment.requests_installed:
        print("错误：未检测到 requests，请先在 .venv-pi-agent-test 中安装。", file=sys.stderr)
        raise SystemExit(2)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mask_account(account: str | None) -> str | None:
    if not account:
        return None
    account = account.strip()
    if not account:
        return None
    if "@" in account:
        name, domain = account.split("@", 1)
        if not name:
            return f"***@{domain}"
        return f"{name[0]}***@{domain}"
    if len(account) <= 2:
        return account[0] + "***"
    return f"{account[0]}***{account[-1]}"


def sanitize_auth_message(message: str, account: str | None = None, password: str | None = None) -> str:
    sanitized = str(message)
    if password:
        sanitized = sanitized.replace(password, "***")
    if account:
        sanitized = sanitized.replace(account, mask_account(account) or "***")
    return sanitized[:300]


def extract_access_token(response_data: dict[str, Any]) -> str | None:
    for key in ("access_token", "token"):
        value = response_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    data = response_data.get("data")
    if isinstance(data, dict):
        for key in ("access_token", "token"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def login_for_token(base_url: str, account: str, password: str, timeout: float) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}{LOGIN_PATH}",
        json={"account": account, "password": password},
        timeout=timeout,
    )
    if response.status_code >= 400:
        try:
            response_data = response.json()
            message = response_data.get("message") or response_data.get("detail") or response_data.get("error") or ""
        except ValueError:
            message = response.text
        safe_message = sanitize_auth_message(str(message), account=account, password=password)
        raise RuntimeError(f"login HTTP {response.status_code}: {safe_message}")

    try:
        response_data = response.json()
    except ValueError as exc:
        raise RuntimeError("login response is not JSON") from exc

    token = extract_access_token(response_data)
    if not token:
        raise RuntimeError("login response does not contain a supported token field")
    return token


def resolve_auth(args: argparse.Namespace, *, allow_login: bool) -> AuthContext:
    env_token = os.getenv("MEDQC_ACCESS_TOKEN", "").strip()
    if env_token:
        return AuthContext(token=env_token, auth_mode="env_token")

    if args.no_auto_login or not allow_login:
        return AuthContext(token=None, auth_mode="missing")

    credential_source = None
    account = None
    password = None
    if args.login_account and args.login_password:
        credential_source = "auto_login_args"
        account = args.login_account
        password = args.login_password
    else:
        env_account = os.getenv("MEDQC_LOGIN_ACCOUNT", "").strip()
        env_password = os.getenv("MEDQC_LOGIN_PASSWORD", "")
        if env_account and env_password:
            credential_source = "auto_login_env"
            account = env_account
            password = env_password

    if not credential_source or not account or not password:
        return AuthContext(token=None, auth_mode="missing")

    masked = mask_account(account)
    try:
        token = login_for_token(args.base_url, account, password, args.timeout)
    except Exception as exc:  # noqa: BLE001 - report sanitized auth failure.
        return AuthContext(
            token=None,
            auth_mode="failed",
            login_attempted=True,
            masked_account=masked,
            error=sanitize_auth_message(str(exc), account=account, password=password),
        )
    return AuthContext(
        token=token,
        auth_mode=credential_source,
        login_attempted=True,
        masked_account=masked,
    )


def find_sensitive_paths(value: Any, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            if key in SENSITIVE_KEYS:
                paths.append(key_path)
            paths.extend(find_sensitive_paths(item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(find_sensitive_paths(item, f"{path}[{index}]"))
    return paths


def extract_plan_tools(response_data: dict[str, Any]) -> list[str]:
    plan = response_data.get("plan")
    if not isinstance(plan, list):
        return []

    tools: list[str] = []
    for step in plan:
        if not isinstance(step, dict):
            continue
        for key in ("tool_name", "tool", "name", "step"):
            value = step.get(key)
            if isinstance(value, str) and value:
                tools.append(value)
                break
    return tools


def extract_warnings(response_data: dict[str, Any]) -> list[str]:
    warnings = response_data.get("warnings")
    if isinstance(warnings, list):
        return [str(item) for item in warnings[:20]]
    if isinstance(warnings, str) and warnings:
        return [warnings]

    result = response_data.get("result")
    if isinstance(result, dict):
        result_warnings = result.get("warnings")
        if isinstance(result_warnings, list):
            return [str(item) for item in result_warnings[:20]]
        if isinstance(result_warnings, str) and result_warnings:
            return [result_warnings]
    return []


def extract_rule_ids(response_data: dict[str, Any]) -> list[str]:
    intent = response_data.get("parsed_intent")
    if not isinstance(intent, dict):
        return []
    rule_ids = intent.get("rule_ids")
    if isinstance(rule_ids, list):
        return [str(rule_id) for rule_id in rule_ids]
    return []


def summarize_response(response_data: dict[str, Any]) -> dict[str, Any]:
    result = response_data.get("result")
    parsed_intent = response_data.get("parsed_intent")
    qc_summary = result.get("qc_summary") if isinstance(result, dict) else None
    selected_rules = result.get("selected_rules") if isinstance(result, dict) else None
    skipped_rules = result.get("skipped_rules") if isinstance(result, dict) else None
    candidates = response_data.get("candidates")
    intent_summary = None
    if isinstance(parsed_intent, dict):
        rule_ids = parsed_intent.get("rule_ids")
        intent_summary = {
            "document_alias": parsed_intent.get("document_alias"),
            "document_type": parsed_intent.get("document_type"),
            "qc_point_type": parsed_intent.get("qc_point_type"),
            "rule_ids": rule_ids if isinstance(rule_ids, list) else [],
            "has_visit_id": bool(parsed_intent.get("visit_id")),
            "has_patient_id": bool(parsed_intent.get("patient_id")),
            "has_patient_name": bool(parsed_intent.get("patient_name")),
            "has_department": bool(parsed_intent.get("department")),
        }

    return {
        "status": response_data.get("status"),
        "trace_id": response_data.get("trace_id") or response_data.get("run_id"),
        "parsed_intent_summary": intent_summary,
        "qc_summary": qc_summary if isinstance(qc_summary, dict) else None,
        "selected_rule_count": len(selected_rules) if isinstance(selected_rules, list) else None,
        "skipped_rule_count": len(skipped_rules) if isinstance(skipped_rules, list) else None,
        "candidate_count": len(candidates) if isinstance(candidates, list) else None,
    }


def build_cases(args: argparse.Namespace) -> list[RegressionCase]:
    visit_id = str(args.visit_id) if args.visit_id else "<visit_id>"
    cases = [
        RegressionCase(
            case_id="direct_ward_round_qc",
            message=f"对 visit_id={visit_id} 的查房记录做质控",
            expected_statuses={"completed", "needs_clarification"},
            required_plan_tools_when_completed={
                "get_record_context",
                "select_record_documents",
                "resolve_rule_scope",
                "run_document_qc",
            },
        ),
        RegressionCase(
            case_id="explicit_rule_id_qc",
            message=f"用 WR-001 检查 visit_id={visit_id} 的查房记录",
            expected_statuses={"completed", "needs_clarification"},
            required_plan_tools_when_completed={"run_document_qc"},
        ),
        RegressionCase(
            case_id="unsupported_write_intent",
            message="删除这个病人的质控结果",
            expected_statuses={"unsupported"},
        ),
        RegressionCase(
            case_id="discharge_record_qc",
            message=f"对 visit_id={visit_id} 的出院记录做完整性质控",
            expected_statuses=VALID_STATUSES,
        ),
        RegressionCase(
            case_id="vague_request",
            message="帮我看看这个病人有没有问题",
            expected_statuses={"needs_clarification", "needs_confirmation"},
        ),
    ]

    if args.patient_name and args.department:
        cases.append(
            RegressionCase(
                case_id="patient_search_qc",
                message=f"对{args.department}{args.patient_name}的查房记录做质控",
                expected_statuses={"completed", "needs_clarification", "needs_confirmation"},
            )
        )
    else:
        cases.append(
            RegressionCase(
                case_id="patient_search_qc",
                message="",
                expected_statuses=set(),
                skip_reason="未提供 --patient-name 和 --department，跳过搜索类测试。",
            )
        )

    if args.case:
        return [case for case in cases if case.case_id == args.case]
    return cases


def result_template(case: RegressionCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "message": case.message,
        "status": "skipped" if case.skip_reason else None,
        "passed": False,
        "skipped": bool(case.skip_reason),
        "warnings": [case.skip_reason] if case.skip_reason else [],
        "plan_tools": [],
        "sensitive_leak_found": False,
        "sensitive_paths": [],
        "error": None,
        "response_summary": None,
    }


def evaluate_case(case: RegressionCase, response_data: dict[str, Any]) -> dict[str, Any]:
    result = result_template(case)
    status = response_data.get("status")
    plan_tools = extract_plan_tools(response_data)
    warnings = extract_warnings(response_data)
    sensitive_paths = find_sensitive_paths(response_data)
    errors: list[str] = []

    result.update(
        {
            "status": status,
            "warnings": warnings,
            "plan_tools": plan_tools,
            "sensitive_leak_found": bool(sensitive_paths),
            "sensitive_paths": sensitive_paths,
            "response_summary": summarize_response(response_data),
        }
    )

    if sensitive_paths:
        errors.append(f"响应包含敏感字段：{', '.join(sensitive_paths)}")
    if status not in case.expected_statuses:
        errors.append(f"status={status!r} 不在预期范围 {sorted(case.expected_statuses)!r}")
    if case.case_id == "unsupported_write_intent" and status != "unsupported":
        errors.append("写入/删除意图未被拒绝为 unsupported")
    if case.case_id == "vague_request" and status == "completed" and "run_document_qc" in plan_tools:
        errors.append("模糊请求直接执行了 run_document_qc")
    if case.case_id == "explicit_rule_id_qc":
        rule_ids = extract_rule_ids(response_data)
        if status == "completed" and "WR-001" not in rule_ids:
            errors.append("显式 rule_id WR-001 未出现在 parsed_intent.rule_ids")
    if status == "completed":
        missing_tools = sorted(case.required_plan_tools_when_completed.difference(plan_tools))
        if missing_tools:
            errors.append(f"completed 但 plan 缺少必要工具：{', '.join(missing_tools)}")

    if status in {"needs_clarification", "needs_confirmation"} and not errors:
        result["warnings"] = warnings + [f"{status} 在病历不明确或文书缺失时允许通过。"]

    result["passed"] = not errors
    result["error"] = "; ".join(errors) if errors else None
    return result


def call_chat(base_url: str, token: str, timeout: float, message: str, visit_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message}
    if visit_id:
        payload["user_context"] = {"visit_id": str(visit_id)}

    response = requests.post(
        f"{base_url.rstrip('/')}{CHAT_PATH}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=timeout,
    )

    if response.status_code == 401:
        raise PermissionError("HTTP 401：请设置有效的 MEDQC_ACCESS_TOKEN。")
    if response.status_code >= 500:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    if response.status_code >= 400:
        try:
            data = response.json()
        except ValueError:
            data = {"status": "http_error", "detail": response.text[:500]}
        data["_http_status"] = response.status_code
        return data
    return response.json()


def run_cases(args: argparse.Namespace, cases: list[RegressionCase], auth: AuthContext) -> list[dict[str, Any]]:
    if args.env_check:
        return [
            {
                "case_id": "env_check",
                "message": "",
                "status": "skipped",
                "passed": True,
                "skipped": True,
                "warnings": ["--env-check 模式仅检查 Python/Pi/request 环境，未调用 API。"],
                "plan_tools": [],
                "sensitive_leak_found": False,
                "sensitive_paths": [],
                "error": None,
                "response_summary": None,
            }
        ]

    if not args.visit_id:
        raise SystemExit("错误：除非使用 --env-check，否则必须提供 --visit-id。")

    if not auth.token:
        auth_warning = "未设置 MEDQC_ACCESS_TOKEN，API 回归测试已跳过。"
        auth_error = "missing MEDQC_ACCESS_TOKEN"
        if auth.auth_mode == "failed":
            auth_warning = "自动登录失败，API 回归测试已跳过。"
            auth_error = auth.error or "auto login failed"
        return [
            {
                "case_id": "env_check",
                "message": "",
                "status": "skipped",
                "passed": True,
                "skipped": True,
                "warnings": ["Python/Pi/request 环境检查已通过，未调用 API。"],
                "plan_tools": [],
                "sensitive_leak_found": False,
                "sensitive_paths": [],
                "error": None,
                "response_summary": None,
            },
            {
                "case_id": "api_auth",
                "message": "",
                "status": "skipped",
                "passed": False,
                "skipped": True,
                "warnings": [
                    auth_warning,
                    "可通过 MEDQC_ACCESS_TOKEN 或 --login-account/--login-password 提供认证。",
                ],
                "plan_tools": [],
                "sensitive_leak_found": False,
                "sensitive_paths": [],
                "error": auth_error,
                "response_summary": None,
            }
        ]

    results: list[dict[str, Any]] = []
    for case in cases:
        case_result = result_template(case)
        if case.skip_reason:
            case_result["passed"] = True
            results.append(case_result)
            print(f"{case.case_id}: SKIPPED - {case.skip_reason}")
            continue

        try:
            response_data = call_chat(
                base_url=args.base_url,
                token=auth.token,
                timeout=args.timeout,
                message=case.message,
                visit_id=args.visit_id,
            )
            case_result = evaluate_case(case, response_data)
        except PermissionError as exc:
            case_result.update({"status": "failed", "error": str(exc), "passed": False})
        except requests.RequestException as exc:
            case_result.update({"status": "failed", "error": f"请求失败：{exc}", "passed": False})
        except Exception as exc:  # noqa: BLE001 - harness should capture case-level failures.
            case_result.update(
                {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "passed": False,
                    "warnings": [traceback.format_exc(limit=3)],
                }
            )

        results.append(case_result)
        outcome = "PASS" if case_result["passed"] else "FAIL"
        print(f"{case.case_id}: {outcome} status={case_result.get('status')}")

        if isinstance(case_result.get("error"), str) and "HTTP 401" in case_result["error"]:
            break
    return results


def build_summary(case_results: list[dict[str, Any]]) -> dict[str, int]:
    total = len(case_results)
    skipped = sum(1 for item in case_results if item.get("skipped"))
    passed = sum(1 for item in case_results if item.get("passed") and not item.get("skipped"))
    failed = sum(1 for item in case_results if not item.get("passed") and not item.get("skipped"))
    return {"total": total, "passed": passed, "failed": failed, "skipped": skipped}


def build_report(
    args: argparse.Namespace,
    environment: HarnessEnvironment,
    auth: AuthContext,
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "python_version": environment.python_version,
        "pi_agent_installed": environment.pi_agent_installed,
        "pi_agent_core_installed": environment.pi_agent_core_installed,
        "requests_installed": environment.requests_installed,
        "orchestration_mode": environment.orchestration_mode,
        "base_url": args.base_url,
        "visit_id": args.visit_id,
        "auth_mode": auth.auth_mode,
        "login_attempted": auth.login_attempted,
        "masked_account": auth.masked_account,
        "patient_name_provided": bool(args.patient_name),
        "department_provided": bool(args.department),
        "case_results": case_results,
        "summary": build_summary(case_results),
    }


def write_json_report(report: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "qc_agent_pi_regression_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def write_markdown_report(report: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "qc_agent_pi_regression_report.md"
    lines = [
        "# QC Agent Pi 回归测试报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- Python：{report['python_version']}",
        f"- pi-agent：{report['pi_agent_installed'] or '未安装'}",
        f"- pi-agent-core：{report['pi_agent_core_installed'] or '未安装'}",
        f"- requests：{report['requests_installed'] or '未安装'}",
        f"- 编排模式：{report['orchestration_mode']}",
        f"- 认证模式：{report['auth_mode']}",
        f"- 已尝试登录：{'是' if report['login_attempted'] else '否'}",
        f"- 登录账号：{report['masked_account'] or '未记录'}",
        f"- API：{report['base_url']}{CHAT_PATH}",
        f"- visit_id：{report['visit_id'] or '未提供'}",
        "",
        "## 汇总",
        "",
        f"- 总数：{report['summary']['total']}",
        f"- 通过：{report['summary']['passed']}",
        f"- 失败：{report['summary']['failed']}",
        f"- 跳过：{report['summary']['skipped']}",
        "",
        "## 用例结果",
        "",
        "| case_id | status | passed | plan_tools | warnings | error |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for result in report["case_results"]:
        warnings = "<br>".join(str(item).replace("|", "\\|") for item in result.get("warnings", [])[:5])
        plan_tools = ", ".join(result.get("plan_tools") or [])
        error = str(result.get("error") or "").replace("|", "\\|")
        lines.append(
            "| {case_id} | {status} | {passed} | {plan_tools} | {warnings} | {error} |".format(
                case_id=result.get("case_id"),
                status=result.get("status"),
                passed="是" if result.get("passed") else "否",
                plan_tools=plan_tools,
                warnings=warnings,
                error=error,
            )
        )

    lines.extend(
        [
            "",
            "## 安全说明",
            "",
            "- 脚本不导入 MedQC 后端 app 包，只作为外部 HTTP client 调用 QC Agent chat API。",
            "- token 仅从 MEDQC_ACCESS_TOKEN 环境变量读取，报告和控制台都不输出 token。",
            "- JSON/Markdown 报告只保存裁剪后的响应摘要，不保存完整 API 响应。",
            "- 每个用例都会递归扫描 sensitive keys：medical_text、record_content、documents、bundle、structured_context、prompt、examples、internal_data、raw_llm_output。",
            "- 当前 Pi 包用于独立测试环境校验；由于 Pi Agent API 尚未接入生产后端，本轮编排模式为 requests_fallback。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def main() -> int:
    args = parse_args()
    environment = inspect_environment()
    print_environment(environment)

    cases = build_cases(args)
    if args.case and not cases:
        print(f"错误：未知 case id：{args.case}", file=sys.stderr)
        return 2

    auth = resolve_auth(args, allow_login=not args.env_check)
    print(f"auth_mode: {auth.auth_mode}")
    if auth.login_attempted:
        print(f"login_attempted: true, account: {auth.masked_account or 'masked'}")
    case_results = run_cases(args, cases, auth)
    output_dir = Path(args.output_dir).resolve()
    report = build_report(args, environment, auth, case_results)
    json_path = write_json_report(report, output_dir)
    markdown_path = write_markdown_report(report, output_dir)

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")

    summary = report["summary"]
    print(f"summary: total={summary['total']} passed={summary['passed']} failed={summary['failed']} skipped={summary['skipped']}")
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
