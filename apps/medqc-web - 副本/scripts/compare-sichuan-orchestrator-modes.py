#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比四川规则执行链：/evaluate 与 /evaluate-fast（当前都应走 orchestrator）。

用途：
1. 回归检查两条入口在同一输入下的规则判定是否一致；
2. 输出 token/耗时/执行器分布，便于持续优化观察。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import requests


@dataclass
class EndpointResult:
    endpoint: str
    status_code: int
    payload: Dict[str, Any]


def _read_text(args: argparse.Namespace) -> str:
    if args.medical_text_file:
        with open(args.medical_text_file, "r", encoding="utf-8") as fp:
            return fp.read()
    return args.medical_text


def _login(base_url: str, email: str, password: str) -> str:
    response = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(f"登录失败: {response.status_code} {response.text[:300]}")
    token = ((response.json().get("data") or {}).get("access_token") or "").strip()
    if not token:
        raise RuntimeError("登录成功但 access_token 为空")
    return token


def _post(
    base_url: str,
    endpoint: str,
    token: str,
    payload: Dict[str, Any],
) -> EndpointResult:
    response = requests.post(
        f"{base_url}{endpoint}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=180,
    )
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    return EndpointResult(endpoint=endpoint, status_code=response.status_code, payload=body)


def _index_by_rule(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    output: Dict[str, Dict[str, Any]] = {}
    for item in items:
        rule_id = str(item.get("rule_id") or "").strip()
        if not rule_id:
            continue
        output[rule_id] = item
    return output


def _extract_eval_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload.get("evaluation_results"), list):
        return payload.get("evaluation_results") or []
    return []


def _extract_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    summary = payload.get("evaluation_summary") or {}
    perf = payload.get("performance_metrics") or {}
    token_usage = perf.get("token_usage")
    if token_usage is None:
        token_usage = (payload.get("token_usage") or {}).get("total_tokens")
    processing_time = perf.get("processing_time")
    if processing_time is None:
        processing_time = perf.get("api_time")
    if processing_time is None:
        processing_time = payload.get("api_time")
    return {
        "mode": payload.get("mode"),
        "total_rules": summary.get("total_rules") or payload.get("total_rules"),
        "issues_found": summary.get("issues_found"),
        "compliance_rate": summary.get("compliance_rate"),
        "token_usage": token_usage,
        "processing_time": processing_time,
        "executor_breakdown": payload.get("executor_breakdown") or summary.get("executor_breakdown"),
        "cache_breakdown": payload.get("cache_breakdown") or summary.get("cache_breakdown"),
    }


def _compare_rules(
    evaluate_items: List[Dict[str, Any]],
    evaluate_fast_items: List[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, Any]]]:
    left = _index_by_rule(evaluate_items)
    right = _index_by_rule(evaluate_fast_items)
    rule_ids = sorted(set(left.keys()) | set(right.keys()))
    diffs: List[Dict[str, Any]] = []
    for rule_id in rule_ids:
        lv = left.get(rule_id) or {}
        rv = right.get(rule_id) or {}
        l_status = lv.get("status")
        r_status = rv.get("status")
        l_comp = lv.get("is_compliant")
        r_comp = rv.get("is_compliant")
        if l_status != r_status or l_comp != r_comp:
            diffs.append(
                {
                    "rule_id": rule_id,
                    "evaluate": {"status": l_status, "is_compliant": l_comp},
                    "evaluate_fast": {"status": r_status, "is_compliant": r_comp},
                }
            )
    return len(diffs) == 0, diffs


def main() -> int:
    parser = argparse.ArgumentParser(description="对比 /evaluate 与 /evaluate-fast 输出一致性")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--email", default="admin@medqc.com")
    parser.add_argument("--password", default="admin888")
    parser.add_argument("--document-id", default="compare-orchestrator-001")
    parser.add_argument("--document-type", default="入院记录")
    parser.add_argument(
        "--rule-ids",
        default="SC-001,SC-002",
        help="逗号分隔 rule_id 列表",
    )
    parser.add_argument(
        "--medical-text",
        default="入院记录：患者于2026-04-10入院，主诉腹痛，医师签名：张三。",
    )
    parser.add_argument("--medical-text-file", default="")
    args = parser.parse_args()

    medical_text = _read_text(args)
    rule_ids = [item.strip() for item in str(args.rule_ids).split(",") if item.strip()]
    if not rule_ids:
        print("ERROR: rule_ids 不能为空", file=sys.stderr)
        return 2

    request_payload = {
        "document_id": args.document_id,
        "document_content": medical_text,
        "document_type": args.document_type,
        "rule_ids": rule_ids,
    }

    try:
        token = _login(args.base_url.rstrip("/"), args.email, args.password)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    evaluate = _post(args.base_url.rstrip("/"), "/api/v1/qc/sichuan/evaluate", token, request_payload)
    evaluate_fast = _post(
        args.base_url.rstrip("/"),
        "/api/v1/qc/sichuan/evaluate-fast",
        token,
        request_payload,
    )

    if evaluate.status_code != 200 or evaluate_fast.status_code != 200:
        print(
            json.dumps(
                {
                    "ok": False,
                    "evaluate_status": evaluate.status_code,
                    "evaluate_fast_status": evaluate_fast.status_code,
                    "evaluate_payload": evaluate.payload,
                    "evaluate_fast_payload": evaluate_fast.payload,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    eval_items = _extract_eval_items(evaluate.payload)
    fast_items = _extract_eval_items(evaluate_fast.payload)
    matched, diffs = _compare_rules(eval_items, fast_items)

    output = {
        "ok": matched,
        "metrics": {
            "evaluate": _extract_metrics(evaluate.payload),
            "evaluate_fast": _extract_metrics(evaluate_fast.payload),
        },
        "rule_diff_count": len(diffs),
        "rule_diffs": diffs,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
