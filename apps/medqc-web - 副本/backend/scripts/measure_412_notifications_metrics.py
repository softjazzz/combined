from __future__ import annotations

import json
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import create_app
from app.routers import notifications as notifications_router


@dataclass
class FakeResp:
    data: List[Dict[str, Any]]
    count: int


class FakeQuery:
    def __init__(self):
        self._ops: List[Tuple[str, Any]] = []

    def select(self, *args, **kwargs):
        self._ops.append(("select", (args, kwargs)))
        return self

    def eq(self, *args, **kwargs):
        self._ops.append(("eq", (args, kwargs)))
        return self

    def gte(self, *args, **kwargs):
        self._ops.append(("gte", (args, kwargs)))
        return self

    def lt(self, *args, **kwargs):
        self._ops.append(("lt", (args, kwargs)))
        return self

    def order(self, *args, **kwargs):
        self._ops.append(("order", (args, kwargs)))
        return self

    def limit(self, *args, **kwargs):
        self._ops.append(("limit", (args, kwargs)))
        return self

    def range(self, *args, **kwargs):
        self._ops.append(("range", (args, kwargs)))
        return self


class FakeSupabase:
    def table(self, _name: str):
        return FakeQuery()


def generate_notifications(rows: int = 480) -> List[Dict[str, Any]]:
    random.seed(20260323)
    base = datetime(2026, 3, 23, 8, 0, 0)
    types = ["defect_urge", "task_assign", "remediation", "system"]
    severities = ["info", "warning", "critical"]
    departments = ["内科", "外科", "骨科", "儿科", "ICU"]

    items: List[Dict[str, Any]] = []
    for i in range(rows):
        typ = types[i % len(types)]
        sev = severities[i % len(severities)]
        dept = departments[i % len(departments)]
        rec_no = f"R{(i % 120) + 1:03d}"
        ts = base + timedelta(seconds=i * 17)
        items.append(
            {
                "id": f"N{i + 1:04d}",
                "recipient_id": "u-metrics",
                "type": typ,
                "severity": sev,
                "department": dept,
                "record_id": rec_no,
                "title": f"{typ}-title",
                "content": f"{typ} content {i + 1}",
                "created_at": ts.isoformat() + "Z",
                "is_read": (i % 5 == 0),
            }
        )
    return items


def _overview_key(item: Dict[str, Any]) -> str:
    return f"{item.get('type','general')}|{item.get('severity','info')}|{item.get('department','未分科室')}|{item.get('record_id','')}"


def build_expected_aggregate(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    expected: Dict[str, Dict[str, Any]] = {}
    for row in items:
        key = _overview_key(row)
        if key not in expected:
            expected[key] = {"occurrence_count": 0, "unread_count": 0}
        expected[key]["occurrence_count"] += 1
        if not bool(row.get("is_read")):
            expected[key]["unread_count"] += 1
    return expected


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p
    lower = int(idx)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    frac = idx - lower
    return ordered[lower] * (1 - frac) + ordered[upper] * frac


def main() -> None:
    rows = generate_notifications()
    expected = build_expected_aggregate(rows)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-metrics"}

    notifications_router._ensure_db = lambda: FakeSupabase()  # type: ignore[attr-defined]

    async def fake_async_execute(_query):
        return FakeResp(data=rows, count=len(rows))

    notifications_router.async_execute = fake_async_execute  # type: ignore[assignment]

    durations_ms: List[float] = []
    final_payload: Dict[str, Any] = {}

    with TestClient(app) as client:
        for _ in range(120):
            start = time.perf_counter()
            resp = client.get("/api/v1/notifications/overview?date=2026-03-23")
            elapsed = (time.perf_counter() - start) * 1000
            durations_ms.append(elapsed)
            if resp.status_code != 200:
                raise RuntimeError(f"overview api failed: {resp.status_code}")
            final_payload = resp.json()

    items = final_payload.get("data", {}).get("items", [])
    total_items = len(items)
    jump_ready = 0
    unread_match = 0
    total_checks = 0

    for item in items:
        key = _overview_key(item)
        if item.get("record_id") and item.get("source_notification_ids"):
            jump_ready += 1
        expected_item = expected.get(key)
        if expected_item:
            total_checks += 1
            if int(item.get("unread_count", 0)) == int(expected_item["unread_count"]):
                unread_match += 1

    p95_ms = percentile(durations_ms, 0.95)
    jump_success_rate = (jump_ready / total_items * 100) if total_items else 0.0
    unread_accuracy = (unread_match / total_checks * 100) if total_checks else 0.0

    result = {
        "date": "2026-03-23",
        "dataset_size": len(rows),
        "overview_items": total_items,
        "p95_latency_ms": round(p95_ms, 2),
        "jump_success_rate_percent": round(jump_success_rate, 2),
        "unread_accuracy_percent": round(unread_accuracy, 2),
        "thresholds": {
            "p95_latency_ms": 60000,
            "jump_success_rate_percent": 99,
            "unread_accuracy_percent": 99,
        },
        "passed": {
            "p95_latency": p95_ms <= 60000,
            "jump_success_rate": jump_success_rate >= 99,
            "unread_accuracy": unread_accuracy >= 99,
        },
        "raw_summary": {
            "mean_latency_ms": round(statistics.mean(durations_ms), 2),
            "min_latency_ms": round(min(durations_ms), 2),
            "max_latency_ms": round(max(durations_ms), 2),
            "samples": len(durations_ms),
        },
        "note": "jump_success_rate 使用脚本口径：可定位病历且具备 source_notification_ids 的概览项占比。",
    }

    out_dir = Path(__file__).resolve().parents[2] / "docs" / "acceptance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "2026-03-23-4.1.2-metrics.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
