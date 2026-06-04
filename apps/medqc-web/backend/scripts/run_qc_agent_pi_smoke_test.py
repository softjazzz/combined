#!/usr/bin/env python
"""Smoke test for the isolated Pi Agent QC Agent harness.

This script intentionally avoids importing MedQC backend packages. It only
checks the Python/Pi test environment and calls the local QC Agent chat API
with an access token supplied by environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from importlib import metadata
from typing import Any

import requests


SENSITIVE_KEYS = {
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "structured_context",
    "prompt",
    "examples",
    "internal_data",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal QC Agent chat API smoke test from the Pi Agent test venv."
    )
    parser.add_argument("--visit-id", required=True, help="Local visit_id used by the smoke cases.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8001",
        help="MedQC backend base URL. Default: http://127.0.0.1:8001",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds.")
    return parser.parse_args()


def require_python_311() -> None:
    if sys.version_info < (3, 11):
        print("错误：该 smoke test 必须使用 Python 3.11+ 虚拟环境运行。", file=sys.stderr)
        print(f"当前版本：{sys.version}", file=sys.stderr)
        raise SystemExit(2)
    print(f"Python: {sys.version.split()[0]}")


def package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def print_pi_package_status() -> None:
    pi_agent = package_version("pi-agent")
    pi_agent_core = package_version("pi-agent-core")
    print(f"pi-agent: {pi_agent or '未安装'}")
    print(f"pi-agent-core: {pi_agent_core or '未安装'}")
    if not pi_agent and not pi_agent_core:
        print("错误：未检测到 pi-agent 或 pi-agent-core，请先在 .venv-pi-agent-test 中安装。", file=sys.stderr)
        raise SystemExit(2)


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


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)[:1000]


def call_chat_case(
    *,
    base_url: str,
    token: str,
    timeout: float,
    case_name: str,
    payload: dict[str, Any],
    expected_status: str | set[str],
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/v1/qc-agent/chat"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        print(f"{case_name}: HTTP {response.status_code}", file=sys.stderr)
        print(response.text[:1000], file=sys.stderr)
        raise SystemExit(1)

    data = response.json()
    sensitive_paths = find_sensitive_paths(data)
    if sensitive_paths:
        print(f"{case_name}: 响应包含敏感字段：{', '.join(sensitive_paths)}", file=sys.stderr)
        raise SystemExit(1)

    status = data.get("status")
    expected = {expected_status} if isinstance(expected_status, str) else expected_status
    if status not in expected:
        print(
            f"{case_name}: status={status!r}，预期为 {sorted(expected)!r}。",
            file=sys.stderr,
        )
        print(compact_json(data), file=sys.stderr)
        raise SystemExit(1)

    print(f"{case_name}: OK status={status}")
    return data


def main() -> int:
    args = parse_args()
    require_python_311()
    print_pi_package_status()

    token = os.getenv("MEDQC_ACCESS_TOKEN", "").strip()
    if not token:
        print("未设置 MEDQC_ACCESS_TOKEN，已跳过 API 调用。")
        print("请先登录获取 token 后运行，例如：")
        print("$env:MEDQC_ACCESS_TOKEN = '<access_token>'")
        print("SKIPPED: environment smoke check passed, API smoke requires MEDQC_ACCESS_TOKEN.")
        return 0

    visit_id = str(args.visit_id)
    cases = [
        {
            "case_name": "查房记录质控",
            "payload": {"message": f"对 visit_id={visit_id} 的查房记录做质控"},
            "expected_status": {"completed", "needs_clarification", "needs_confirmation"},
        },
        {
            "case_name": "显式 WR-001 规则质控",
            "payload": {"message": f"用 WR-001 检查 visit_id={visit_id} 的查房记录"},
            "expected_status": {"completed", "needs_clarification", "needs_confirmation"},
        },
        {
            "case_name": "拒绝删除质控结果",
            "payload": {
                "message": "删除这个病人的质控结果",
                "user_context": {"visit_id": visit_id},
            },
            "expected_status": "unsupported",
        },
    ]

    for case in cases:
        call_chat_case(
            base_url=args.base_url,
            token=token,
            timeout=args.timeout,
            case_name=case["case_name"],
            payload=case["payload"],
            expected_status=case["expected_status"],
        )

    print("QC Agent Pi smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
