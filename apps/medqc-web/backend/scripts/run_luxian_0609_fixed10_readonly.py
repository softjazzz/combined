from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from sqlalchemy import text


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
DEFAULT_CASE_MAP = ROOT / "tmp-lx0609-0426-current-audit" / "private-case-map.json"
EXPECTED_LUXIAN_0609_RULE_IDS = tuple(
    f"LX0609-{number:03d}" for number in range(1, 50)
)
_CASE_LABEL = re.compile(r"case-\d{2}")
_JSON_FIELDS = (
    "structured_context",
    "document_hits",
    "data_quality_flags",
    "source_doc_priority",
)

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def resolve_full_luxian_0609_rule_ids(
    inventory: Sequence[Any] | None = None,
) -> list[str]:
    if inventory is None:
        from app.services.luxian_0609.native_package import (
            load_luxian_0609_dependency_inventory,
        )

        inventory = load_luxian_0609_dependency_inventory()
    rule_ids = [str(getattr(item, "rule_id", "") or "").strip() for item in inventory]
    if tuple(rule_ids) != EXPECTED_LUXIAN_0609_RULE_IDS:
        raise RuntimeError("全49点回归必须显式包含49个客户规则ID，且顺序为LX0609-001..049")
    return rule_ids


def _result_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("evaluation_results", "parsed_evaluation_results", "results"):
        rows = result.get(key)
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)]
    return []


def validate_full_luxian_0609_results(result: Mapping[str, Any]) -> None:
    returned = tuple(
        str(item.get("rule_id") or item.get("rule_code") or "").strip()
        for item in _result_rows(result)
    )
    if returned != EXPECTED_LUXIAN_0609_RULE_IDS:
        raise RuntimeError("LX0609全49点回归结果范围异常：必须返回49个客户规则且顺序一致")


def build_safe_rule_states(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "rule_id": str(item.get("rule_id") or item.get("rule_code") or ""),
            "status": str(item.get("status") or "unknown"),
        }
        for item in rows
    ]


def load_private_case_map(path: Path, *, limit: int) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("病例映射必须是数组")
    cases: list[dict[str, str]] = []
    for item in payload[:limit]:
        if not isinstance(item, Mapping):
            raise RuntimeError("病例映射包含非法行")
        row = {
            key: str(item.get(key) or "").strip()
            for key in ("case_label", "institute_id", "patient_id", "visit_id")
        }
        if not _CASE_LABEL.fullmatch(row["case_label"]) or not all(row.values()):
            raise RuntimeError("病例映射缺少安全标签或查询坐标")
        cases.append(row)
    if len(cases) != limit:
        raise RuntimeError(f"病例映射不足{limit}例")
    return cases


def load_bundle_readonly(case: Mapping[str, str]) -> dict[str, Any]:
    from app.database.connection import engine

    if engine is None:
        raise RuntimeError("DATABASE_URL未配置")
    query = text(
        "SELECT * FROM public.running_record_bundle "
        "WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id "
        "LIMIT 1"
    )
    with engine.connect() as connection:
        row = connection.execute(
            query,
            {
                "institute_id": case["institute_id"],
                "patient_id": case["patient_id"],
                "visit_id": case["visit_id"],
            },
        ).mappings().first()
    if row is None:
        raise RuntimeError("病例bundle不存在")
    bundle = dict(row)
    for key in _JSON_FIELDS:
        value = bundle.get(key)
        if not isinstance(value, str):
            continue
        try:
            bundle[key] = json.loads(value)
        except json.JSONDecodeError:
            bundle[key] = {}
    return bundle


async def evaluate_full_luxian_0609_case(
    *,
    service: Any,
    bundle: dict[str, Any],
    rule_ids: Sequence[str],
    timeout_seconds: float,
) -> dict[str, Any]:
    if tuple(rule_ids) != EXPECTED_LUXIAN_0609_RULE_IDS:
        raise RuntimeError("全49点回归禁止使用空列表或非客户规则范围")
    result = await asyncio.wait_for(
        service.evaluate_running_final_bundle_input(
            bundle=bundle,
            rule_ids=list(rule_ids),
            bucket_strategy="domain_only",
            quality_profile="throughput_v1",
            batch_output_mode="full",
            enable_selective_refine=False,
            use_execution_cache=False,
            rule_set_key="luxian_0609_qc_v1",
        ),
        timeout=timeout_seconds,
    )
    validate_full_luxian_0609_results(result)
    return result


async def run(args: argparse.Namespace) -> int:
    from app.services.sichuan_qc_service import SichuanQCService

    cases = load_private_case_map(Path(args.case_map), limit=int(args.limit))
    rule_ids = resolve_full_luxian_0609_rule_ids()
    service = SichuanQCService()
    failed = 0
    for case in cases:
        started = time.perf_counter()
        try:
            result = await evaluate_full_luxian_0609_case(
                service=service,
                bundle=load_bundle_readonly(case),
                rule_ids=rule_ids,
                timeout_seconds=float(args.timeout_seconds),
            )
            rows = _result_rows(result)
            status_counts = dict(Counter(str(item.get("status") or "unknown") for item in rows))
            token_usage = result.get("token_usage")
            if not isinstance(token_usage, Mapping):
                token_usage = {}
            summary = {
                "case_label": case["case_label"],
                "result_count": len(rows),
                "status_counts": status_counts,
                "rule_states": build_safe_rule_states(rows),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "total_tokens": int(token_usage.get("total_tokens") or 0),
            }
        except Exception as exc:  # noqa: BLE001
            failed += 1
            summary = {
                "case_label": case["case_label"],
                "error_type": type(exc).__name__,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读运行固定病例的LX0609全49点正式入口回归")
    parser.add_argument("--case-map", default=str(DEFAULT_CASE_MAP))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
