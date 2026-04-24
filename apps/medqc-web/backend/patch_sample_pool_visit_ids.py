"""
为历史样本池批量回填 visit_id。

用途：
1. 当前主链路已切换为“只按 visit_id 匹配/同步”
2. 历史样本池中仍存在把 visit_id 放到“住院号”列、或 raw_payload_json.visit_id 为空的情况
3. 本脚本用于一次性把当前池子的 visit_id 补回 raw_payload_json，避免重新导入

说明：
- 优先使用本地已匹配出的 matched_visit_id
- 对尚未匹配的样本，使用历史标识（mr_no）去远端 public.mr 查询
- 若同一标识命中多条远端记录，按最近一次住院/更新时间选择最新记录
- 这是迁移脚本，不改变运行时“只按 visit_id”的规则
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.services.custom_qc_sample_pool_service import (
    _candidate_recency_key,
    _choose_scored_candidate,
    _remote_column_exists,
    _safe_json_loads,
    _safe_text,
)
from app.services.etl_sync import get_remote_db_url, load_db_config


def _load_pool_items(pool_id: str) -> List[Dict[str, Any]]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL 未配置")
    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT
                  id,
                  row_no,
                  mr_no,
                  matched_visit_id,
                  raw_payload_json
                FROM qc.manual_problem_sample_pool_items
                WHERE pool_id = :pool_id
                ORDER BY row_no
                """
            ),
            {"pool_id": pool_id},
        ).mappings().all()
    return [dict(row) for row in rows]


def _load_remote_lookup(identifiers: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    remote_url = get_remote_db_url()
    if not remote_url:
        raise RuntimeError("REMOTE_DB_URL 未配置，无法回填 visit_id")
    cfg = load_db_config()
    remote_schema = str(cfg.get("remote_schema") or "public").strip() or "public"
    lookup_map: Dict[str, List[Dict[str, Any]]] = {}

    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        admission_expr = "NULL AS admission_datetime"
        discharge_expr = "NULL AS discharge_datetime"
        update_expr = "NULL AS update_time"

        if _remote_column_exists(cursor, remote_schema, "mr", "admission_datetime"):
            admission_expr = "admission_datetime AS admission_datetime"
        elif _remote_column_exists(cursor, remote_schema, "mr", "admission_time"):
            admission_expr = "admission_time AS admission_datetime"

        if _remote_column_exists(cursor, remote_schema, "mr", "discharge_datetime"):
            discharge_expr = "discharge_datetime AS discharge_datetime"
        elif _remote_column_exists(cursor, remote_schema, "mr", "discharge_time"):
            discharge_expr = "discharge_time AS discharge_datetime"

        if _remote_column_exists(cursor, remote_schema, "mr", "update_time"):
            update_expr = "update_time AS update_time"
        elif _remote_column_exists(cursor, remote_schema, "mr", "last_modified_time"):
            update_expr = "last_modified_time AS update_time"
        elif _remote_column_exists(cursor, remote_schema, "mr", "mr_time"):
            update_expr = "mr_time AS update_time"

        chunk_size = 200
        for start in range(0, len(identifiers), chunk_size):
            chunk = identifiers[start : start + chunk_size]
            placeholders = ", ".join(["%s"] * len(chunk))
            sql = f"""
                SELECT
                  patient_id::text AS patient_id,
                  visit_id::text AS visit_id,
                  COALESCE(mr_no::text, '') AS mr_no,
                  COALESCE(inpat_no::text, '') AS inpat_no,
                  {admission_expr},
                  {discharge_expr},
                  {update_expr}
                FROM {remote_schema}.mr
                WHERE COALESCE(mr_no::text, '') IN ({placeholders})
                   OR COALESCE(inpat_no::text, '') IN ({placeholders})
                   OR COALESCE(visit_id::text, '') IN ({placeholders})
            """
            params = chunk + chunk + chunk
            cursor.execute(sql, params)
            for row in cursor.fetchall() or []:
                candidate = dict(row)
                for key in (candidate.get("mr_no"), candidate.get("inpat_no"), candidate.get("visit_id")):
                    lookup_key = _safe_text(key)
                    if lookup_key:
                        lookup_map.setdefault(lookup_key, []).append(candidate)
    finally:
        cursor.close()
        conn.close()
    return lookup_map


def _pick_visit_id(candidates: List[Dict[str, Any]]) -> str:
    if not candidates:
        return ""
    chosen = _choose_scored_candidate(
        [(0, candidate) for candidate in candidates],
        get_recency_key=lambda candidate: _candidate_recency_key(
            admission_value=candidate.get("admission_datetime"),
            discharge_value=candidate.get("discharge_datetime"),
            update_value=candidate.get("update_time"),
            visit_id=candidate.get("visit_id"),
        ),
    )
    return _safe_text(chosen.get("visit_id")) if isinstance(chosen, dict) else ""


def _update_pool_item_visit_id(*, item_id: str, raw_payload: Dict[str, Any], visit_id: str, dry_run: bool) -> None:
    payload = dict(raw_payload or {})
    payload["visit_id"] = visit_id
    if dry_run:
        return
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL 未配置")
    with SessionLocal() as session:
        session.execute(
            text(
                """
                UPDATE qc.manual_problem_sample_pool_items
                SET raw_payload_json = :raw_payload_json,
                    updated_at = now()
                WHERE id = :item_id
                """
            ),
            {
                "item_id": item_id,
                "raw_payload_json": json.dumps(payload, ensure_ascii=False),
            },
        )
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="为历史样本池批量回填 visit_id")
    parser.add_argument("--pool-id", required=True, help="样本池 ID")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写库")
    args = parser.parse_args()

    rows = _load_pool_items(args.pool_id)
    lookup_ids = sorted({_safe_text(row.get("mr_no")) for row in rows if _safe_text(row.get("mr_no"))})
    remote_lookup = _load_remote_lookup(lookup_ids) if lookup_ids else {}

    updated = 0
    skipped = 0
    unresolved: List[Dict[str, Any]] = []
    for row in rows:
        raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
        existing_visit_id = _safe_text(raw_payload.get("visit_id") if isinstance(raw_payload, dict) else "")
        if existing_visit_id:
            skipped += 1
            continue

        visit_id = _safe_text(row.get("matched_visit_id"))
        if not visit_id:
            legacy_identifier = _safe_text(row.get("mr_no"))
            visit_id = _pick_visit_id(remote_lookup.get(legacy_identifier, []))

        if not visit_id:
            unresolved.append(
                {
                    "row_no": row.get("row_no"),
                    "mr_no": _safe_text(row.get("mr_no")),
                }
            )
            continue

        _update_pool_item_visit_id(
            item_id=_safe_text(row.get("id")),
            raw_payload=raw_payload if isinstance(raw_payload, dict) else {},
            visit_id=visit_id,
            dry_run=args.dry_run,
        )
        updated += 1

    print(json.dumps(
        {
            "pool_id": args.pool_id,
            "dry_run": args.dry_run,
            "total_rows": len(rows),
            "updated_rows": updated,
            "skipped_rows": skipped,
            "unresolved_rows": len(unresolved),
            "unresolved_samples": unresolved[:20],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
