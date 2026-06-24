#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.fast_screen_qc import get_fast_screen_pack_definitions, run_final_fast_screen  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
RELEASE_MR = REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto" / "mr.csv"
DEFAULT_RULE_IDS = [
    "SC-004",
    "SC-007",
    "SC-008",
    "SC-009",
    "SC-010",
    "SC-011",
    "SC-012",
    "SC-013",
    "SC-014",
    "SC-015",
    "SC-016",
    "SC-018",
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate(value: Any, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", _safe_text(value))[:limit]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _visit_keys(visit_id: str) -> dict[str, str]:
    for row in _read_csv_rows(RELEASE_MR):
        if _safe_text(row.get("visit_id")) == _safe_text(visit_id):
            return {
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_id": _safe_text(row.get("patient_id")),
                "institute_id": _safe_text(row.get("institute_id")),
                "patient_name": _safe_text(row.get("name")),
            }
    return {"visit_id": visit_id, "patient_id": "", "institute_id": "", "patient_name": ""}


def _parse_rule_ids(value: str) -> list[str]:
    return [item.strip().upper() for item in str(value or "").split(",") if item.strip()]


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("metadata")
    return dict(meta) if isinstance(meta, dict) else {}


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(_safe_text(item.get("status")) or "unknown" for item in rows))


async def _run_attempt(
    *,
    attempt_no: int,
    visit_id: str,
    institute_id: str,
    patient_id: str,
    rule_ids: list[str],
    pack_concurrency: int,
) -> dict[str, Any]:
    started = datetime.now().isoformat(timespec="seconds")
    start = time.perf_counter()
    result: dict[str, Any] = {}
    error = ""
    try:
        result = await run_final_fast_screen(
            qc_service=SichuanQCService(),
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema="cdm",
            rule_ids=rule_ids,
            quality_profile="throughput_v1",
            batch_output_mode="minimal",
            pack_concurrency=pack_concurrency,
        )
    except Exception as exc:
        error = str(exc)
    finished = datetime.now().isoformat(timespec="seconds")
    wall = max(0.0, time.perf_counter() - start)
    token_usage = dict(result.get("token_usage") or {})
    pack_metrics = dict(result.get("pack_metrics") or {})
    rows = [dict(item) for item in list(result.get("evaluation_results") or []) if isinstance(item, dict)]
    technical_error_rows = [
        row
        for row in rows
        if "批量执行异常" in _safe_text(row.get("findings"))
        or (_safe_text(row.get("status")) == "uncertain" and float(row.get("confidence") or 0.0) == 0.0 and not _safe_text(row.get("evidence")))
    ]
    provider_error_count = int(pack_metrics.get("provider_error_count") or 0)
    if error:
        provider_error_count += 1
    return {
        "attempt_no": attempt_no,
        "started_at": started,
        "finished_at": finished,
        "wall_clock_time": wall,
        "provider_error_count": provider_error_count,
        "timeout_count": int(pack_metrics.get("timeout_count") or 0),
        "rate_limit_count": int(pack_metrics.get("rate_limit_count") or 0),
        "raw_error_summary": error or "; ".join(sorted({_safe_text(row.get("findings")) for row in technical_error_rows if _safe_text(row.get("findings"))})),
        "tokens": int(token_usage.get("total_tokens") or 0),
        "prompt_tokens": int(token_usage.get("prompt_tokens") or 0),
        "completion_tokens": int(token_usage.get("completion_tokens") or 0),
        "api_time": float(result.get("api_time") or pack_metrics.get("sum_pack_api_time") or 0.0),
        "status_count": _status_counts(rows),
        "pack_metrics": pack_metrics,
        "rule_results": [
            {
                "attempt_no": attempt_no,
                "rule_id": _safe_text(row.get("rule_id")),
                "rule_name": _safe_text(row.get("rule_name")),
                "status": _safe_text(row.get("status")),
                "confidence": row.get("confidence", ""),
                "target_document_type": _safe_text(row.get("target_document_type") or _metadata(row).get("target_document_type")),
                "findings": _truncate(row.get("findings")),
                "evidence": _truncate(row.get("evidence")),
                "evidence_verified": "yes" if len(_safe_text(row.get("evidence"))) >= 8 else "no",
                "suggestion": _truncate(row.get("suggestion")),
                "pack_id": _safe_text(_metadata(row).get("pack_id")),
            }
            for row in rows
        ],
    }


def _write_csv(path: Path, attempts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for attempt in attempts:
        for item in attempt.get("rule_results") or []:
            row = {
                "attempt_no": attempt["attempt_no"],
                "started_at": attempt["started_at"],
                "finished_at": attempt["finished_at"],
                "wall_clock_time": attempt["wall_clock_time"],
                "provider_error_count": attempt["provider_error_count"],
                "timeout_count": attempt["timeout_count"],
                "rate_limit_count": attempt["rate_limit_count"],
                "raw_error_summary": attempt["raw_error_summary"],
                "tokens": attempt["tokens"],
                "api_time": attempt["api_time"],
                "status_count": json.dumps(attempt["status_count"], ensure_ascii=False),
            }
            row.update(item)
            rows.append(row)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_conclusion(path: Path, payload: dict[str, Any]) -> None:
    attempts = list(payload.get("attempts") or [])
    successful = [item for item in attempts if int(item.get("provider_error_count") or 0) == 0]
    final = successful[-1] if successful else (attempts[-1] if attempts else {})
    status_count = dict(final.get("status_count") or {})
    affected_rules = ", ".join(payload.get("rule_ids") or [])
    lines = [
        "# 2246915 provider异常失败pack复跑结论",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 原异常来源",
        "",
        "- 小样本正式质控抽检中，`visit_id=2246915` 出现 `provider_error=3`。",
        "- 质量治理中 12 条 `technical_error` 均来自入院记录相关规则包批量执行异常后降级为 `uncertain`。",
        f"- 受影响规则：{affected_rules}。",
        "",
        "## 复跑范围",
        "",
        f"- 本轮只读重跑指定规则，不写 `qc_results/qc_defects`，不改规则、prompt、Sheet2 或原始抽检文件。",
        f"- 实际命中的 pack：{', '.join(payload.get('pack_ids') or [])}。",
        f"- 最大尝试次数：{payload.get('max_attempts')}；pack_concurrency={payload.get('pack_concurrency')}。",
        "",
        "## 复跑结果",
        "",
    ]
    if successful:
        lines.extend(
            [
                "- 复跑成功：至少一次 attempt 的 `provider_error_count=0`。",
                "- 结论：原异常更像偶发 provider/批量响应问题，重跑可恢复。",
                f"- 最终状态分布：{json.dumps(status_count, ensure_ascii=False)}。",
                "- 12 条 technical_error 可在人工复核视角中解除，但是否为正式缺陷仍需按 evidence 和后处理准入策略判断。",
            ]
        )
    else:
        lines.extend(
            [
                "- 复跑失败：所有 attempt 仍存在 provider_error。",
                f"- 最终状态分布：{json.dumps(status_count, ensure_ascii=False)}。",
                "- 结论：需要在正式链路中考虑 pack 级自动重试 1 次，并将技术异常从缺陷清单分层展示。",
            ]
        )
    lines.extend(["", "## 分次明细", ""])
    for attempt in attempts:
        lines.append(
            f"- attempt {attempt.get('attempt_no')}: wall={float(attempt.get('wall_clock_time') or 0.0):.2f}s, provider={attempt.get('provider_error_count')}, timeout={attempt.get('timeout_count')}, rate_limit={attempt.get('rate_limit_count')}, tokens={attempt.get('tokens')}, status={json.dumps(attempt.get('status_count') or {}, ensure_ascii=False)}"
        )
    lines.extend(
        [
            "",
            "## 对演示结论的影响",
            "",
            "- 技术链路仍可演示。",
            "- 结果质量演示仍不建议直接推进；需要先落地后处理分层，避免 provider_error/数据缺口混入医生缺陷清单。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    rule_ids = _parse_rule_ids(args.rule_ids) or DEFAULT_RULE_IDS
    visit = _visit_keys(args.visit_id)
    if not (_safe_text(visit.get("patient_id")) and _safe_text(visit.get("institute_id"))):
        raise SystemExit(f"无法从 release mr.csv 推断 visit_id={args.visit_id} 的 patient_id/institute_id")
    packs = get_fast_screen_pack_definitions(rule_ids)
    pack_ids = [pack.pack_id for pack in packs]
    if args.pack_id:
        requested = _safe_text(args.pack_id)
        if requested not in pack_ids:
            print(f"warning: requested pack_id={requested} not in actual packs {pack_ids}; 按 rule_ids 实际命中 pack 重跑。")
    attempts: list[dict[str, Any]] = []
    for attempt_no in range(1, max(1, int(args.max_attempts)) + 1):
        attempt = await _run_attempt(
            attempt_no=attempt_no,
            visit_id=args.visit_id,
            institute_id=visit["institute_id"],
            patient_id=visit["patient_id"],
            rule_ids=rule_ids,
            pack_concurrency=args.pack_concurrency,
        )
        attempts.append(attempt)
        if int(attempt.get("provider_error_count") or 0) == 0:
            break
    payload = {
        "visit": visit,
        "scene": args.scene,
        "rule_ids": rule_ids,
        "requested_pack_id": args.pack_id,
        "pack_ids": pack_ids,
        "pack_concurrency": args.pack_concurrency,
        "max_attempts": args.max_attempts,
        "attempts": attempts,
    }
    _write_json(args.output_json, payload)
    _write_csv(args.output_csv, attempts)
    _write_conclusion(args.conclusion_md, payload)
    print(json.dumps({"attempts": len(attempts), "pack_ids": pack_ids, "final_status": attempts[-1].get("status_count") if attempts else {}}, ensure_ascii=False, indent=2))
    print(f"wrote: {args.output_json}")
    print(f"wrote: {args.output_csv}")
    print(f"wrote: {args.conclusion_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读重跑正式 fast_screen 失败 pack。")
    parser.add_argument("--visit-id", default="2246915")
    parser.add_argument("--rule-ids", default=",".join(DEFAULT_RULE_IDS))
    parser.add_argument("--pack-id", default="admission_content_core")
    parser.add_argument("--scene", choices=["final"], default="final")
    parser.add_argument("--pack-concurrency", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--output-json", type=Path, default=DOCS_DIR / "formal_qc_2246915_failed_pack_rerun.json")
    parser.add_argument("--output-csv", type=Path, default=DOCS_DIR / "formal_qc_2246915_failed_pack_rerun.csv")
    parser.add_argument("--conclusion-md", type=Path, default=DOCS_DIR / "2246915-provider异常失败pack复跑结论.md")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
