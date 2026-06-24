#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database.connection import engine  # noqa: E402


def _columns(inspector: Any, table_name: str) -> set[str]:
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def _table_names(inspector: Any) -> set[str]:
    names = set(inspector.get_table_names())
    for schema in ("cdm", "public"):
        try:
            names.update(inspector.get_table_names(schema=schema))
        except Exception:
            continue
    return names


def _exists(conn: Any, sql: str, params: dict[str, Any]) -> bool:
    try:
        return bool(conn.execute(text(sql), params).first())
    except Exception:
        return False


def _first_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def select_candidates(limit: int) -> list[dict[str, Any]]:
    if engine is None:
        raise RuntimeError("DATABASE_URL 未配置，无法读取本机 CDM 候选")

    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = _table_names(inspector)
        if "mr" not in tables:
            raise RuntimeError("本机 CDM 未发现 mr 表")

        mr_cols = _columns(inspector, "mr")
        select_cols = [
            "patient_id",
            "visit_id",
            "mr_no" if "mr_no" in mr_cols else "'' AS mr_no",
            "admission_dept_name" if "admission_dept_name" in mr_cols else "'' AS admission_dept_name",
            "discharge_dept_name" if "discharge_dept_name" in mr_cols else "'' AS discharge_dept_name",
            "abo_blood_code" if "abo_blood_code" in mr_cols else "'' AS abo_blood_code",
            "rh_blood_code" if "rh_blood_code" in mr_cols else "'' AS rh_blood_code",
            "allergy_sign" if "allergy_sign" in mr_cols else "'' AS allergy_sign",
        ]
        rows = conn.execute(
            text(
                "SELECT "
                + ", ".join(select_cols)
                + " FROM mr WHERE patient_id IS NOT NULL AND visit_id IS NOT NULL LIMIT :limit_rows"
            ),
            {"limit_rows": max(1, limit)},
        ).mappings().all()

        has_surgery_table = "mr_surgery" in tables
        has_diag_table = "diagnosis" in tables
        has_cost_table = "mr_cost" in tables
        candidates: list[dict[str, Any]] = []
        for row_proxy in rows:
            row = dict(row_proxy)
            patient_id = str(row.get("patient_id") or "").strip()
            visit_id = str(row.get("visit_id") or "").strip()
            if not patient_id or not visit_id:
                continue

            has_surgery = (
                has_surgery_table
                and _exists(
                    conn,
                    "SELECT 1 FROM mr_surgery WHERE patient_id = :patient_id AND visit_id = :visit_id LIMIT 1",
                    {"patient_id": patient_id, "visit_id": visit_id},
                )
            )
            has_tcm = (
                has_diag_table
                and _exists(
                    conn,
                    "SELECT 1 FROM diagnosis "
                    "WHERE patient_id = :patient_id AND visit_id = :visit_id "
                    "AND (diagnosis_name LIKE '%中医%' OR diagnosis_type LIKE '%中医%') LIMIT 1",
                    {"patient_id": patient_id, "visit_id": visit_id},
                )
            )
            has_cost = (
                has_cost_table
                and _exists(
                    conn,
                    "SELECT 1 FROM mr_cost WHERE patient_id = :patient_id AND visit_id = :visit_id LIMIT 1",
                    {"patient_id": patient_id, "visit_id": visit_id},
                )
            )

            candidates.append(
                {
                    "visit_id": visit_id,
                    "patient_id": patient_id,
                    "mr_no": _first_value(row, "mr_no"),
                    "dept": _first_value(row, "discharge_dept_name", "admission_dept_name"),
                    "has_surgery": has_surgery,
                    "has_tcm_diagnosis": has_tcm,
                    "has_cost": has_cost,
                    "has_blood_type": bool(_first_value(row, "abo_blood_code", "rh_blood_code")),
                    "has_allergy_sign": bool(_first_value(row, "allergy_sign")),
                }
            )
        return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="只读筛选病案首页生成演示候选，不输出完整病历正文")
    parser.add_argument("--limit", type=int, default=30, help="最多读取候选数量")
    args = parser.parse_args()

    candidates = select_candidates(args.limit)
    print(json.dumps(candidates, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
