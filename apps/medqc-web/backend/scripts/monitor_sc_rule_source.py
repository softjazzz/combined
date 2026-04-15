#!/usr/bin/env python3
"""
持续监控四川规则来源：
- 轮询 /api/v1/qc/sichuan/rules/source
- 当 sc_source != pg_governance 时立即告警

示例：
  python monitor_sc_rule_source.py --base-url http://127.0.0.1:8001 --interval 30
  python monitor_sc_rule_source.py --once
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib import request, error


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_source(url: str, timeout: int) -> dict[str, Any]:
    req = request.Request(url=url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("响应体缺少 data 字段")
    return data


def _run_once(base_url: str, timeout: int, expected_source: str) -> int:
    target = f"{base_url.rstrip('/')}/api/v1/qc/sichuan/rules/source"
    try:
        data = _fetch_source(target, timeout=timeout)
    except error.HTTPError as exc:
        print(f"[{_now_iso()}] ERROR http={exc.code} url={target}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"[{_now_iso()}] ERROR fetch_failed={exc}", file=sys.stderr)
        return 3

    source = str(data.get("sc_source") or "").strip()
    healthy = source == expected_source
    msg = (
        f"[{_now_iso()}] source={source or 'unknown'} expected={expected_source} "
        f"healthy={str(healthy).lower()} sc_rule_count={int(data.get('sc_rule_count') or 0)} "
        f"checksum={str(data.get('sc_checksum') or '')[:12]}"
    )
    if healthy:
        print(msg)
        return 0
    print(f"{msg} ALERT=SC_RULE_SOURCE_MISMATCH", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor SC rule source health.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001", help="backend base url")
    parser.add_argument("--interval", type=int, default=60, help="poll interval seconds")
    parser.add_argument("--timeout", type=int, default=8, help="request timeout seconds")
    parser.add_argument("--expected-source", default="pg_governance", help="expected sc_source value")
    parser.add_argument("--once", action="store_true", help="run once and exit")
    args = parser.parse_args()

    if args.once:
        return _run_once(args.base_url, args.timeout, args.expected_source)

    interval = max(10, int(args.interval or 60))
    while True:
        code = _run_once(args.base_url, args.timeout, args.expected_source)
        if code not in (0, 2):
            # 网络/接口故障直接标红，但继续巡检
            pass
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
