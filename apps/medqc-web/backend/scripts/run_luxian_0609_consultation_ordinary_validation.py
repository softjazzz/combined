"""只读选择普通单条会诊验证队列；标准输出永远不包含病历原文或三坐标。"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import DB_SCHEMA_MODE
from app.services.bundles import assembly as bundle_assembly
from scripts.build_luxian_0609_golden_ledger import canonical_digest


SELECTOR_VERSION = "lx0609-consultation-ordinary-v1"
CONDITION_VERSION = "single-consultation-row-nonreconsult-v1"
_CASE_COUNT = 20
_RECONSULTATION_RE = re.compile(r"(?:再次请会诊|再会诊)")
_REQUIRED_ROW_FIELDS = {
    "institute_id",
    "patient_id",
    "visit_id",
    "document_id",
    "record_time",
    "record_content",
    "has_daily_or_senior",
}


class OrdinarySelectorContractError(ValueError):
    """普通会诊验证队列无法稳定构造时的非回显错误。"""


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _coordinates(row: Mapping[str, Any]) -> tuple[str, str, str]:
    coordinates = tuple(
        str(row.get(field) or "").strip()
        for field in ("institute_id", "patient_id", "visit_id")
    )
    if any(not value or len(value) > 256 for value in coordinates):
        raise OrdinarySelectorContractError("invalid source row")
    return coordinates


def _coordinate_hash(row: Mapping[str, Any]) -> str:
    institute_id, patient_id, visit_id = _coordinates(row)
    return canonical_digest(
        {
            "domain": "lx0609-consultation-ordinary-coordinate-v1",
            "scene": "running",
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
        }
    )


def _consult_row_hash(row: Mapping[str, Any]) -> str:
    document_id = str(row.get("document_id") or "").strip()
    record_time = _normalized_text(row.get("record_time"))
    content = _normalized_text(row.get("record_content"))
    if not content:
        raise OrdinarySelectorContractError("invalid source row")
    return canonical_digest(
        {
            "domain": "lx0609-consultation-ordinary-row-v1",
            "document_id": document_id,
            "record_time": record_time,
            "record_content": content,
        }
    )


def select_ordinary_consultation_cases(
    rows: Sequence[Mapping[str, Any]],
    *,
    schema_mode: str,
    snapshot_as_of: str,
) -> dict[str, Any]:
    """从内部行选择固定20例；返回值仅含不可逆摘要。"""

    normalized_schema_mode = str(schema_mode or "").strip().lower()
    normalized_as_of = str(snapshot_as_of or "").strip()
    if normalized_schema_mode not in {"single", "split"}:
        raise OrdinarySelectorContractError("invalid selector context")
    try:
        if date.fromisoformat(normalized_as_of).isoformat() != normalized_as_of:
            raise ValueError
    except ValueError as exc:
        raise OrdinarySelectorContractError("invalid selector context") from exc

    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    seen_row_signatures: set[tuple[tuple[str, str, str], str]] = set()
    for row in rows:
        if not isinstance(row, Mapping) or not _REQUIRED_ROW_FIELDS.issubset(row):
            raise OrdinarySelectorContractError("invalid source row")
        coordinates = _coordinates(row)
        row_hash = _consult_row_hash(row)
        signature = (coordinates, row_hash)
        if signature in seen_row_signatures:
            raise OrdinarySelectorContractError("duplicate source row")
        seen_row_signatures.add(signature)
        grouped.setdefault(coordinates, []).append(row)

    candidates: list[dict[str, str]] = []
    for consultation_rows in grouped.values():
        if len(consultation_rows) != 1:
            continue
        row = consultation_rows[0]
        raw_content = str(row.get("record_content") or "").strip()
        if len(raw_content) < 80 or _RECONSULTATION_RE.search(raw_content):
            continue
        if not bool(row.get("has_daily_or_senior")):
            continue
        candidates.append(
            {
                "coordinate_hash": _coordinate_hash(row),
                "consult_row_hash": _consult_row_hash(row),
            }
        )

    candidates.sort(key=lambda item: (item["coordinate_hash"], item["consult_row_hash"]))
    if len(candidates) < _CASE_COUNT:
        raise OrdinarySelectorContractError("insufficient ordinary consultation cases")
    selected = candidates[:_CASE_COUNT]
    if len({item["coordinate_hash"] for item in selected}) != _CASE_COUNT:
        raise OrdinarySelectorContractError("duplicate selected coordinate")
    safe_cases = [
        {
            "case_label": f"case-{index:02d}",
            "coordinate_hash": item["coordinate_hash"],
            "consult_row_hash": item["consult_row_hash"],
        }
        for index, item in enumerate(selected, start=1)
    ]
    selector_fingerprint = canonical_digest(
        {
            "domain": "lx0609-consultation-ordinary-selector-fingerprint-v1",
            "selector_version": SELECTOR_VERSION,
            "condition_version": CONDITION_VERSION,
            "schema_mode": normalized_schema_mode,
            "snapshot_as_of": normalized_as_of,
            "cases": [
                {
                    "case_ref": item["case_label"],
                    "coordinate_hash": item["coordinate_hash"],
                    "consult_row_hash": item["consult_row_hash"],
                }
                for item in safe_cases
            ],
        }
    )
    return {
        "selector_version": SELECTOR_VERSION,
        "condition_version": CONDITION_VERSION,
        "cases": safe_cases,
        "selector_fingerprint": selector_fingerprint,
    }


def _require_columns(schema: str, table_name: str, required: set[str]) -> None:
    columns = set(bundle_assembly._get_table_columns(schema, table_name))
    if not required.issubset(columns):
        raise OrdinarySelectorContractError("required source columns unavailable")


def read_ordinary_consultation_source_rows(*, limit_rows: int = 5000) -> list[dict[str, Any]]:
    """唯一的数据库入口：可信标识符+三表 EXISTS 的参数化只读查询。"""

    if not isinstance(limit_rows, int) or not 20 <= limit_rows <= 10000:
        raise OrdinarySelectorContractError("invalid source limit")
    schema = bundle_assembly._default_source_schema()
    engine = bundle_assembly.engine
    if engine is None:
        raise OrdinarySelectorContractError("database unavailable")
    coordinate_columns = {"institute_id", "patient_id", "visit_id"}
    _require_columns(schema, "consultation_record", coordinate_columns | {"document_id", "record_time", "record_content"})
    _require_columns(schema, "daily_course_record", coordinate_columns)
    _require_columns(schema, "senior_course_record", coordinate_columns)

    q = bundle_assembly._quote_ident
    qualified = bundle_assembly._qualified_table
    join_predicate = " AND ".join(
        f"{q('consult')}.{q(field)} = {q('bundle')}.{q(field)}"
        for field in ("institute_id", "patient_id", "visit_id")
    )
    daily_predicate = " AND ".join(
        f"{q('daily')}.{q(field)} = {q('bundle')}.{q(field)}"
        for field in ("institute_id", "patient_id", "visit_id")
    )
    senior_predicate = " AND ".join(
        f"{q('senior')}.{q(field)} = {q('bundle')}.{q(field)}"
        for field in ("institute_id", "patient_id", "visit_id")
    )
    sql = (
        f"SELECT {q('bundle')}.{q('institute_id')} AS {q('institute_id')}, "
        f"{q('bundle')}.{q('patient_id')} AS {q('patient_id')}, "
        f"{q('bundle')}.{q('visit_id')} AS {q('visit_id')}, "
        f"{q('consult')}.{q('document_id')} AS {q('document_id')}, "
        f"{q('consult')}.{q('record_time')} AS {q('record_time')}, "
        f"{q('consult')}.{q('record_content')} AS {q('record_content')}, "
        f"(EXISTS (SELECT 1 FROM {qualified(schema, 'daily_course_record')} AS {q('daily')} "
        f"WHERE {daily_predicate}) OR EXISTS (SELECT 1 FROM {qualified(schema, 'senior_course_record')} "
        f"AS {q('senior')} WHERE {senior_predicate})) AS {q('has_daily_or_senior')} "
        f"FROM {qualified('public', 'running_record_bundle')} AS {q('bundle')} "
        f"JOIN {qualified(schema, 'consultation_record')} AS {q('consult')} ON {join_predicate} "
        f"ORDER BY {q('bundle')}.{q('institute_id')}, {q('bundle')}.{q('patient_id')}, "
        f"{q('bundle')}.{q('visit_id')}, {q('consult')}.{q('document_id')} LIMIT :limit_rows"
    )
    with engine.connect() as connection:
        rows = connection.execute(bundle_assembly.text(sql), {"limit_rows": limit_rows}).mappings().all()
    return [dict(row) for row in rows]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读构造LX0609普通会诊20例验证队列")
    parser.add_argument("--snapshot-as-of", required=True)
    parser.add_argument("--limit-rows", type=int, default=5000)
    args = parser.parse_args(argv)
    payload = select_ordinary_consultation_cases(
        read_ordinary_consultation_source_rows(limit_rows=args.limit_rows),
        schema_mode=str(DB_SCHEMA_MODE or "").strip().lower() or "single",
        snapshot_as_of=args.snapshot_as_of,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
