#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import inspect as sa_inspect, text  # noqa: E402

from app.database.connection import engine  # noqa: E402
from app.database.connection import Base  # noqa: E402
from app.database.models import cdm as _cdm_models  # noqa: F401,E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
OUTPUT_DIR = DOCS_DIR / "surgery_level_catalog"
CATALOG_CSV = OUTPUT_DIR / "surgery_level_catalog.csv"
PREVIOUS_NAME_PROBE_CSV = OUTPUT_DIR / "surgery_level_catalog_match_probe.csv"

FIELD_PROBE_CSV = OUTPUT_DIR / "surgery_code_field_probe.csv"
FIELD_PROBE_JSON = OUTPUT_DIR / "surgery_code_field_probe.json"
MATCH_PROBE_CSV = OUTPUT_DIR / "surgery_level_code_match_probe.csv"
MATCH_PROBE_JSON = OUTPUT_DIR / "surgery_level_code_match_probe.json"
REPORT_MD = OUTPUT_DIR / "手术分级目录编码优先匹配报告.md"

RELEASE_CSV_ROOTS = [
    REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto",
    REPO_ROOT / "release" / "0426" / "0426",
]

SURGERY_TABLES = [
    "mr_surgery",
    "surgery_application",
    "surgery_record",
    "surgery_inform_consent",
    "surgery_inventory_record",
    "presurg_summary",
    "presurg_discussion",
    "postsurg_firstcourse_record",
    "surgery_safecheck_record",
    "surgery_risk_assessment",
    "anesthesia_record",
    "postane_surveil_record",
]

CODE_FIELD_HINTS = {
    "surgery_code",
    "operation_code",
    "procedure_code",
    "icd9_code",
    "icd9_cm3",
    "planned_operation_code",
}
ID_FIELD_HINTS = {
    "surgery_id",
    "operation_id",
    "procedure_id",
}
NAME_FIELD_HINTS = {
    "surgery_name",
    "operation_name",
    "procedure_name",
    "planned_operation_name",
}
NAME_EXCLUDE_PATTERNS = re.compile(r"(room|dept|department|physician|doctor|nurse|sign)", re.IGNORECASE)
CODE_EXCLUDE_PATTERNS = re.compile(
    r"(physician|doctor|nurse|surgeon|anesthesiologist|submitter|modifier|order|document|application|dept|patient)",
    re.IGNORECASE,
)
SURGERY_RELATED_RULES = {
    "SC-083",
    "SC-097",
    "SC-099",
    "SC-100",
    "SC-101",
    "SC-105",
    "SC-107",
}
SURGERY_TEXT_PATTERN = re.compile(r"手术|术前|术后|麻醉|植入|取材|病理|SC-083|SC-097|SC-099|SC-100|SC-101")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "items", "issues", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _normalize_name(value: Any) -> str:
    text_value = unicodedata.normalize("NFKC", _safe_text(value))
    text_value = re.sub(r"[\s　]+", "", text_value)
    text_value = re.sub(r"[，,。；;：:、/\\（）()\[\]【】<>《》\"'“”‘’·]", "", text_value)
    text_value = text_value.upper()
    text_value = re.sub(r"(手术)$", "术", text_value)
    return text_value


def _normalize_code(value: Any) -> str:
    text_value = unicodedata.normalize("NFKC", _safe_text(value))
    text_value = re.sub(r"[\s　]+", "", text_value).upper()
    return text_value


def _compact_code(value: Any) -> str:
    code = _normalize_code(value)
    return re.sub(r"[^0-9A-Z]", "", code)


def _zero_relaxed_code(value: Any) -> str:
    code = _normalize_code(value)
    parts = re.split(r"([.\-X])", code)
    relaxed: list[str] = []
    for part in parts:
        if part.isdigit():
            relaxed.append(str(int(part)) if part else part)
        else:
            relaxed.append(part)
    return "".join(relaxed)


def _is_code_candidate(column_name: str) -> bool:
    name = column_name.lower()
    if name in CODE_FIELD_HINTS:
        return True
    if name in ID_FIELD_HINTS:
        return True
    if CODE_EXCLUDE_PATTERNS.search(name):
        return False
    return (
        ("surgery" in name or "operation" in name or "procedure" in name or "icd9" in name)
        and (name.endswith("_code") or name.endswith("_id") or "code" in name)
    )


def _is_name_candidate(column_name: str) -> bool:
    name = column_name.lower()
    if NAME_EXCLUDE_PATTERNS.search(name):
        return False
    return name in NAME_FIELD_HINTS or (
        ("surgery" in name or "operation" in name or "procedure" in name)
        and ("name" in name or "title" in name)
    )


def _table_columns_from_orm(table_name: str) -> list[str]:
    table = Base.metadata.tables.get(table_name)
    if not table:
        return []
    return [column.name for column in table.columns]


def _release_csv_path(table_name: str) -> Path | None:
    for root in RELEASE_CSV_ROOTS:
        path = root / f"{table_name}.csv"
        if path.exists():
            return path
    return None


def _db_table_schema(table_name: str) -> tuple[str, list[str]] | None:
    if engine is None:
        return None
    inspector = sa_inspect(engine)
    for schema in ("cdm", "public", None):
        try:
            if not inspector.has_table(table_name, schema=schema):
                continue
            columns = [column["name"] for column in inspector.get_columns(table_name, schema=schema)]
            return (schema or "", columns)
        except Exception:
            continue
    return None


def _qualified_table(schema: str, table_name: str) -> str:
    if schema:
        return f'"{schema}"."{table_name}"'
    return f'"{table_name}"'


def _count_non_empty_db(schema: str, table_name: str, fields: list[str]) -> int | None:
    if not fields or engine is None:
        return None
    clauses = [f"NULLIF(BTRIM(COALESCE(CAST(\"{field}\" AS TEXT), '')), '') IS NOT NULL" for field in fields]
    sql = f"SELECT COUNT(*) FROM {_qualified_table(schema, table_name)} WHERE {' OR '.join(clauses)}"
    try:
        with engine.connect() as conn:
            return int(conn.execute(text(sql)).scalar() or 0)
    except Exception:
        return None


def _sample_values_db(schema: str, table_name: str, fields: list[str], limit: int = 5) -> list[dict[str, Any]]:
    if not fields or engine is None:
        return []
    selected = ["visit_id"] + fields
    select_sql = ", ".join(f'"{field}"' for field in selected)
    clauses = [f"NULLIF(BTRIM(COALESCE(CAST(\"{field}\" AS TEXT), '')), '') IS NOT NULL" for field in fields]
    sql = f"SELECT {select_sql} FROM {_qualified_table(schema, table_name)} WHERE {' OR '.join(clauses)} LIMIT {limit}"
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _field_probe_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_counter: Counter[str] = Counter()
    for table_name in SURGERY_TABLES:
        db_info = _db_table_schema(table_name)
        release_path = _release_csv_path(table_name)
        if db_info:
            schema, columns = db_info
            local_schema = schema or "search_path"
            source = "local_pg"
        elif release_path:
            release_rows = _read_csv(release_path)
            columns = list(release_rows[0].keys()) if release_rows else []
            local_schema = "release_csv"
            source = str(release_path.relative_to(REPO_ROOT))
        else:
            columns = _table_columns_from_orm(table_name)
            local_schema = "orm_only"
            source = "orm_model"

        code_fields = [column for column in columns if _is_code_candidate(column)]
        name_fields = [column for column in columns if _is_name_candidate(column)]
        match_code_fields = [field for field in code_fields if field.lower() not in ID_FIELD_HINTS]
        if not match_code_fields:
            match_code_fields = code_fields
        code_rows: int | None = None
        match_code_rows: int | None = None
        name_rows: int | None = None
        sample_values: list[dict[str, Any]] = []
        if db_info:
            schema, _columns = db_info
            code_rows = _count_non_empty_db(schema, table_name, code_fields)
            match_code_rows = _count_non_empty_db(schema, table_name, match_code_fields)
            name_rows = _count_non_empty_db(schema, table_name, name_fields)
            sample_values = _sample_values_db(schema, table_name, list(dict.fromkeys(code_fields + name_fields)))
        elif release_path:
            release_rows = _read_csv(release_path)
            code_rows = sum(
                1 for row in release_rows if any(_safe_text(row.get(field)) for field in code_fields)
            )
            match_code_rows = sum(
                1 for row in release_rows if any(_safe_text(row.get(field)) for field in match_code_fields)
            )
            name_rows = sum(
                1 for row in release_rows if any(_safe_text(row.get(field)) for field in name_fields)
            )
            for row in release_rows:
                if any(_safe_text(row.get(field)) for field in code_fields + name_fields):
                    sample_values.append({field: row.get(field, "") for field in ["visit_id"] + code_fields + name_fields})
                if len(sample_values) >= 5:
                    break

        source_counter[local_schema] += 1
        rows.append(
            {
                "table_name": table_name,
                "local_schema": local_schema,
                "data_source": source,
                "code_field_candidates": "|".join(code_fields),
                "match_code_field_candidates": "|".join(match_code_fields),
                "name_field_candidates": "|".join(name_fields),
                "rows_with_code_count": "" if code_rows is None else code_rows,
                "rows_with_match_code_count": "" if match_code_rows is None else match_code_rows,
                "rows_with_name_count": "" if name_rows is None else name_rows,
                "sample_values": json.dumps(sample_values, ensure_ascii=False),
            }
        )
    return rows, {"source_counter": dict(source_counter)}


def _load_catalog() -> dict[str, Any]:
    rows = _read_csv(CATALOG_CSV)
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_compact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_zero_relaxed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        row["code_norm"] = _normalize_code(row.get("surgery_code"))
        row["code_compact"] = _compact_code(row.get("surgery_code"))
        row["code_zero_relaxed"] = _zero_relaxed_code(row.get("surgery_code"))
        row["name_norm"] = _normalize_name(row.get("surgery_name"))
        if row["code_norm"]:
            by_code[row["code_norm"]].append(row)
        if row["code_compact"]:
            by_compact[row["code_compact"]].append(row)
        if row["code_zero_relaxed"]:
            by_zero_relaxed[row["code_zero_relaxed"]].append(row)
        if row["name_norm"]:
            by_name[row["name_norm"]].append(row)
    return {
        "rows": rows,
        "by_code": by_code,
        "by_compact": by_compact,
        "by_zero_relaxed": by_zero_relaxed,
        "by_name": by_name,
    }


def _best_level(rows: list[dict[str, Any]]) -> str:
    levels = [_safe_text(row.get("surgery_level")) for row in rows if _safe_text(row.get("surgery_level"))]
    if not levels:
        return ""
    return str(max(int(level) for level in levels if level.isdigit()))


def _pick_catalog_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return sorted(rows, key=lambda row: (row.get("surgery_level") != "4", row.get("surgery_code", "")))[0]


def _match_by_code(code: str, catalog: dict[str, Any]) -> dict[str, Any] | None:
    norm = _normalize_code(code)
    if not norm:
        return None
    exact = catalog["by_code"].get(norm)
    if exact:
        row = _pick_catalog_row(exact)
        return {
            "matched_catalog_code": row.get("surgery_code", ""),
            "matched_catalog_name": row.get("surgery_name", ""),
            "matched_level": row.get("surgery_level", ""),
            "match_type": "code_exact",
            "match_confidence": 1.0,
            "source_page": row.get("source_page", ""),
            "review_status": "matched_by_code",
        }
    zero_relaxed = catalog["by_zero_relaxed"].get(_zero_relaxed_code(code))
    compact = catalog["by_compact"].get(_compact_code(code))
    normalized = zero_relaxed or compact
    if normalized:
        row = _pick_catalog_row(normalized)
        return {
            "matched_catalog_code": row.get("surgery_code", ""),
            "matched_catalog_name": row.get("surgery_name", ""),
            "matched_level": row.get("surgery_level", ""),
            "match_type": "code_normalized",
            "match_confidence": 0.96,
            "source_page": row.get("source_page", ""),
            "review_status": "matched_by_code",
        }

    candidates: list[dict[str, Any]] = []
    compact_code = _compact_code(code)
    for catalog_row in catalog["rows"]:
        catalog_compact = catalog_row.get("code_compact", "")
        if not compact_code or not catalog_compact:
            continue
        if len(compact_code) < 4 or len(catalog_compact) < 4:
            continue
        if compact_code.startswith(catalog_compact) or catalog_compact.startswith(compact_code):
            candidates.append(catalog_row)
    if candidates:
        row = _pick_catalog_row(candidates)
        return {
            "matched_catalog_code": row.get("surgery_code", ""),
            "matched_catalog_name": row.get("surgery_name", ""),
            "matched_level": row.get("surgery_level", ""),
            "match_type": "code_prefix_ext",
            "match_confidence": 0.85,
            "source_page": row.get("source_page", ""),
            "review_status": "probable_level4" if row.get("surgery_level") == "4" else "needs_review",
        }
    return None


def _split_name_components(name: str) -> list[str]:
    raw = _safe_text(name)
    parts = re.split(r"[+＋、,/，,；;]", raw)
    values = [raw] + [part for part in parts if part and part != raw]
    return list(dict.fromkeys(_normalize_name(value) for value in values if _normalize_name(value)))


def _match_by_name(name: str, catalog: dict[str, Any]) -> dict[str, Any] | None:
    components = _split_name_components(name)
    for component in components:
        exact = catalog["by_name"].get(component)
        if exact:
            row = _pick_catalog_row(exact)
            return {
                "matched_catalog_code": row.get("surgery_code", ""),
                "matched_catalog_name": row.get("surgery_name", ""),
                "matched_level": row.get("surgery_level", ""),
                "match_type": "name_exact_candidate",
                "match_confidence": 0.78,
                "source_page": row.get("source_page", ""),
                "review_status": "needs_review_name_only",
            }
    best: tuple[int, dict[str, Any]] | None = None
    for component in components:
        if len(component) < 4:
            continue
        for catalog_row in catalog["rows"]:
            catalog_name = catalog_row.get("name_norm", "")
            if len(catalog_name) < 4:
                continue
            if component in catalog_name or catalog_name in component:
                score = min(len(component), len(catalog_name))
                if best is None or score > best[0]:
                    best = (score, catalog_row)
    if best:
        row = best[1]
        return {
            "matched_catalog_code": row.get("surgery_code", ""),
            "matched_catalog_name": row.get("surgery_name", ""),
            "matched_level": row.get("surgery_level", ""),
            "match_type": "name_contains_candidate",
            "match_confidence": 0.62,
            "source_page": row.get("source_page", ""),
            "review_status": "needs_review_name_only",
        }
    return None


def _load_previous_probe_visits() -> dict[str, dict[str, Any]]:
    visits: dict[str, dict[str, Any]] = {}
    for row in _read_csv(PREVIOUS_NAME_PROBE_CSV):
        visit_id = _safe_text(row.get("visit_id"))
        if not visit_id:
            continue
        visits.setdefault(visit_id, {})
        visits[visit_id].update(
            {
                "patient_name": row.get("patient_name", ""),
                "sample_source": "previous_surgery_name_probe",
            }
        )
    return visits


def _load_issue_visit_candidates() -> dict[str, dict[str, Any]]:
    visits: dict[str, dict[str, Any]] = {}
    issue_files = [
        DOCS_DIR / "formal_qc_random10_original_chain_issue_review.json",
        DOCS_DIR / "formal_qc_random10_batch2_original_chain_issue_review.json",
        DOCS_DIR / "formal_qc_random10_batch3_original_chain_issue_review.json",
        DOCS_DIR / "formal_qc_random10_original_chain_issue_review.csv",
        DOCS_DIR / "formal_qc_random10_batch2_original_chain_issue_review.csv",
        DOCS_DIR / "formal_qc_random10_batch3_original_chain_issue_review.csv",
    ]
    for path in issue_files:
        rows = _read_json_rows(path) if path.suffix == ".json" else _read_csv(path)
        for row in rows:
            visit_id = _safe_text(row.get("visit_id"))
            if not visit_id:
                continue
            rule_id = _safe_text(row.get("rule_id")).upper()
            combined = " ".join(_safe_text(row.get(key)) for key in ("rule_name", "conclusion", "findings", "evidence", "suggestion"))
            if rule_id not in SURGERY_RELATED_RULES and not SURGERY_TEXT_PATTERN.search(combined):
                continue
            visits.setdefault(visit_id, {})
            visits[visit_id].update(
                {
                    "patient_name": row.get("patient_name", visits[visit_id].get("patient_name", "")),
                    "department": row.get("department", visits[visit_id].get("department", "")),
                    "sample_source": "random10_surgery_related_issue",
                }
            )
    return visits


def _read_release_rows(table_name: str, visit_ids: set[str] | None = None, limit: int | None = None) -> list[dict[str, str]]:
    path = _release_csv_path(table_name)
    if not path:
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if visit_ids is not None and _safe_text(row.get("visit_id")) not in visit_ids:
                continue
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    return rows


def _db_fetch_rows(table_name: str, visit_ids: set[str] | None, fields: list[str], limit: int | None = None) -> list[dict[str, Any]]:
    db_info = _db_table_schema(table_name)
    if not db_info or engine is None:
        return []
    schema, columns = db_info
    selected = [field for field in ["visit_id", "patient_id", "name", "dept_name", "admission_dept_name", "discharge_dept_name"] + fields if field in columns]
    if "visit_id" not in selected:
        return []
    select_sql = ", ".join(f'"{field}"' for field in dict.fromkeys(selected))
    where_sql = ""
    params: dict[str, Any] = {}
    if visit_ids:
        params["visit_ids"] = list(visit_ids)
        where_sql = ' WHERE CAST("visit_id" AS TEXT) = ANY(:visit_ids)'
    limit_sql = f" LIMIT {int(limit)}" if limit else ""
    sql = f"SELECT {select_sql} FROM {_qualified_table(schema, table_name)}{where_sql}{limit_sql}"
    try:
        with engine.connect() as conn:
            return [dict(row) for row in conn.execute(text(sql), params).mappings().all()]
    except Exception:
        return []


def _source_rows_for_table(table_name: str, visit_ids: set[str]) -> tuple[list[dict[str, Any]], str, list[str], list[str]]:
    db_info = _db_table_schema(table_name)
    columns = db_info[1] if db_info else []
    source = "local_pg" if db_info else ""
    if not columns:
        path = _release_csv_path(table_name)
        release_rows = _read_release_rows(table_name, visit_ids)
        columns = list(release_rows[0].keys()) if release_rows else []
        source = str(path.relative_to(REPO_ROOT)) if path else "missing"
    code_fields = [column for column in columns if _is_code_candidate(column)]
    name_fields = [column for column in columns if _is_name_candidate(column)]
    fields = list(dict.fromkeys(code_fields + name_fields))
    rows = _db_fetch_rows(table_name, visit_ids, fields) if db_info else []
    if not rows:
        rows = _read_release_rows(table_name, visit_ids)
        if rows and not source.startswith("release"):
            path = _release_csv_path(table_name)
            source = str(path.relative_to(REPO_ROOT)) if path else source
    return rows, source, code_fields, name_fields


def _supplement_mr_surgery_visits(existing_visit_ids: set[str], max_count: int = 20) -> dict[str, dict[str, Any]]:
    rows, _source, _code_fields, _name_fields = _source_rows_for_table("mr_surgery", set())
    supplemented: dict[str, dict[str, Any]] = {}
    for row in rows:
        visit_id = _safe_text(row.get("visit_id"))
        if not visit_id or visit_id in existing_visit_ids or visit_id in supplemented:
            continue
        if not _safe_text(row.get("surgery_code")) and not _safe_text(row.get("surgery_name")):
            continue
        supplemented[visit_id] = {
            "patient_name": row.get("name", ""),
            "department": row.get("dept_name") or row.get("admission_dept_name") or row.get("discharge_dept_name") or "",
            "sample_source": "supplement_mr_surgery_distribution",
        }
        if len(supplemented) >= max_count:
            break
    return supplemented


def _build_visit_context() -> dict[str, dict[str, Any]]:
    visits = _load_previous_probe_visits()
    for visit_id, meta in _load_issue_visit_candidates().items():
        visits.setdefault(visit_id, {})
        visits[visit_id].update({key: value for key, value in meta.items() if value})
    visits.update(_supplement_mr_surgery_visits(set(visits), 20))
    return visits


def _record_match_rows(visits: dict[str, dict[str, Any]], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    visit_ids = set(visits)
    detail_rows: list[dict[str, Any]] = []
    for table_name in SURGERY_TABLES:
        source_rows, data_source, code_fields, name_fields = _source_rows_for_table(table_name, visit_ids)
        if not source_rows:
            continue
        match_code_fields = [field for field in code_fields if field.lower() not in ID_FIELD_HINTS]
        # Fields like mr_surgery.surgery_id are record identifiers in this CDM, not ICD procedure codes.
        # Keep them in the field probe, but do not let them create false code_unmatched decisions when a
        # real surgery_code/planned_operation_code field is available.
        if not match_code_fields:
            match_code_fields = code_fields
        for source_row in source_rows:
            visit_id = _safe_text(source_row.get("visit_id"))
            if not visit_id:
                continue
            code_values = [(_safe_text(source_row.get(field)), field) for field in match_code_fields if _safe_text(source_row.get(field))]
            name_values = [(_safe_text(source_row.get(field)), field) for field in name_fields if _safe_text(source_row.get(field))]
            if not code_values and not name_values:
                continue
            if not visits.get(visit_id):
                visits[visit_id] = {}
            patient_name = _safe_text(visits.get(visit_id, {}).get("patient_name") or source_row.get("name"))
            department = _safe_text(
                visits.get(visit_id, {}).get("department")
                or source_row.get("dept_name")
                or source_row.get("admission_dept_name")
                or source_row.get("discharge_dept_name")
            )
            matched = False
            for code_value, code_field in code_values:
                match = _match_by_code(code_value, catalog)
                row = {
                    "visit_id": visit_id,
                    "patient_name": patient_name,
                    "department": department,
                    "sample_source": visits.get(visit_id, {}).get("sample_source", ""),
                    "table_name": table_name,
                    "data_source": data_source,
                    "surgery_code_field": code_field,
                    "surgery_code": code_value,
                    "surgery_name_field": "",
                    "surgery_name": name_values[0][0] if name_values else "",
                }
                if match:
                    row.update(match)
                    row["notes"] = "编码优先匹配。"
                else:
                    row.update(
                        {
                            "matched_catalog_code": "",
                            "matched_catalog_name": "",
                            "matched_level": "",
                            "match_type": "code_unmatched",
                            "match_confidence": 0,
                            "source_page": "",
                            "review_status": "code_unmatched",
                            "notes": "本地手术编码未命中 catalog，后续只能作为 data_gap_code_unmatched。"
                        }
                    )
                detail_rows.append(row)
                matched = True
            if not matched:
                for name_value, name_field in name_values:
                    match = _match_by_name(name_value, catalog)
                    row = {
                        "visit_id": visit_id,
                        "patient_name": patient_name,
                        "department": department,
                        "sample_source": visits.get(visit_id, {}).get("sample_source", ""),
                        "table_name": table_name,
                        "data_source": data_source,
                        "surgery_code_field": "",
                        "surgery_code": "",
                        "surgery_name_field": name_field,
                        "surgery_name": name_value,
                    }
                    if match:
                        row.update(match)
                        row["notes"] = "无编码或编码不可用，名称仅作为人工核查候选。"
                    else:
                        row.update(
                            {
                                "matched_catalog_code": "",
                                "matched_catalog_name": "",
                                "matched_level": "",
                                "match_type": "name_no_match",
                                "match_confidence": 0,
                                "source_page": "",
                                "review_status": "needs_review_name_only",
                                "notes": "无编码，名称也未命中 catalog。"
                            }
                        )
                    detail_rows.append(row)
    return _attach_visit_applicability(detail_rows)


def _attach_visit_applicability(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_safe_text(row.get("visit_id"))].append(row)

    visit_summary: dict[str, dict[str, str]] = {}
    for visit_id, visit_rows in grouped.items():
        code_rows = [row for row in visit_rows if _safe_text(row.get("surgery_code"))]
        exact_level4 = [
            row for row in code_rows
            if row.get("match_type") in {"code_exact", "code_normalized"} and row.get("matched_level") == "4"
        ]
        exact_level_rows = [
            row for row in code_rows
            if row.get("match_type") in {"code_exact", "code_normalized"} and _safe_text(row.get("matched_level")).isdigit()
        ]
        prefix_level4 = [
            row for row in code_rows
            if row.get("match_type") == "code_prefix_ext" and row.get("matched_level") == "4"
        ]
        code_unmatched = [row for row in code_rows if row.get("match_type") == "code_unmatched"]
        code_missing = not code_rows
        name_candidates = [row for row in visit_rows if str(row.get("match_type", "")).startswith("name_")]

        if exact_level4:
            summary = {
                "visit_surgery_level": "4",
                "sc083_applicability": "applicable_level4_by_code",
                "visit_review_status": "matched_by_code",
            }
        elif prefix_level4:
            summary = {
                "visit_surgery_level": "probable_4",
                "sc083_applicability": "needs_review_code_prefix_ext",
                "visit_review_status": "needs_review",
            }
        elif code_rows and not code_unmatched and exact_level_rows and max(int(row["matched_level"]) for row in exact_level_rows) <= 3:
            summary = {
                "visit_surgery_level": "<=3",
                "sc083_applicability": "not_applicable_level3_by_code",
                "visit_review_status": "matched_by_code",
            }
        elif code_unmatched:
            summary = {
                "visit_surgery_level": "unknown",
                "sc083_applicability": "data_gap_code_unmatched",
                "visit_review_status": "needs_review",
            }
        elif code_missing and name_candidates:
            summary = {
                "visit_surgery_level": "unknown",
                "sc083_applicability": "needs_review_name_only",
                "visit_review_status": "needs_review",
            }
        else:
            summary = {
                "visit_surgery_level": "unknown",
                "sc083_applicability": "data_gap_code_missing",
                "visit_review_status": "needs_review",
            }
        visit_summary[visit_id] = summary

    for row in rows:
        row.update(visit_summary.get(_safe_text(row.get("visit_id")), {}))
    rows.sort(key=lambda row: (_safe_text(row.get("visit_id")), _safe_text(row.get("table_name")), _safe_text(row.get("surgery_code")), _safe_text(row.get("surgery_name"))))
    return rows


def _counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_safe_text(row.get(key)) or "(empty)" for row in rows))


def _report(
    field_rows: list[dict[str, Any]],
    match_rows: list[dict[str, Any]],
    *,
    field_meta: dict[str, Any],
) -> str:
    code_tables = [
        row for row in field_rows
        if _safe_text(row.get("match_code_field_candidates")) and _safe_text(row.get("rows_with_match_code_count")) not in {"", "0"}
    ]
    name_tables = [
        row for row in field_rows
        if _safe_text(row.get("name_field_candidates")) and _safe_text(row.get("rows_with_name_count")) not in {"", "0"}
    ]
    visit_ids = sorted({_safe_text(row.get("visit_id")) for row in match_rows if _safe_text(row.get("visit_id"))})
    code_rows = [row for row in match_rows if _safe_text(row.get("surgery_code"))]
    visits_with_code = sorted({_safe_text(row.get("visit_id")) for row in code_rows if _safe_text(row.get("visit_id"))})
    sc083_2214679 = [row for row in match_rows if _safe_text(row.get("visit_id")) == "2214679"]
    match_type_counts = _counter(match_rows, "match_type")
    applicability_counts = _counter(
        list({row.get("visit_id"): row for row in match_rows}.values()),
        "sc083_applicability",
    )

    def table_line(row: dict[str, Any]) -> str:
        return (
            f"- `{row['table_name']}`（{row['local_schema']}）："
            f"编码候选 `{row['code_field_candidates'] or '-'}`，"
            f"匹配用编码 `{row['match_code_field_candidates'] or '-'}`，"
            f"名称字段 `{row['name_field_candidates'] or '-'}`，"
            f"匹配用编码非空 {row['rows_with_match_code_count'] or 0}，名称非空 {row['rows_with_name_count'] or 0}"
        )

    sc083_lines = []
    for row in sc083_2214679:
        sc083_lines.append(
            f"- {row.get('table_name')}：code={row.get('surgery_code') or '-'}，"
            f"name={row.get('surgery_name') or '-'}，match={row.get('match_type')}，"
            f"level={row.get('matched_level') or '-'}，applicability={row.get('sc083_applicability')}"
        )
    if not sc083_lines:
        sc083_lines.append("- 未在本轮样本/本地手术表中找到 visit_id=2214679 的手术编码行。")

    return "\n".join(
        [
            "# 手术分级目录编码优先匹配报告",
            "",
            "## 输入与边界",
            "- 本轮只读使用已生成的手术分级 catalog，不接入 SC-083，不写数据库，不改正式质控主链路。",
            "- 匹配策略为 code-first：`code_exact/code_normalized` 是强证据，`code_prefix_ext` 只作为需复核候选，名称匹配只作为人工核查辅助。",
            f"- 字段探查来源分布：`{json.dumps(field_meta.get('source_counter', {}), ensure_ascii=False)}`。",
            "",
            "## 手术编码字段覆盖",
            f"- 探查表数：{len(field_rows)}。",
            f"- 有非空编码候选的表数：{len(code_tables)}。",
            f"- 有非空名称候选的表数：{len(name_tables)}。",
            "- 说明：`surgery_id/operation_id/procedure_id` 会保留在字段探查中，但当同表存在 `surgery_code/planned_operation_code` 时，不作为 catalog 匹配依据，避免把记录号误判为手术编码。",
            *(table_line(row) for row in field_rows),
            "",
            "## 匹配评估统计",
            f"- 评估 visit 数：{len(visit_ids)}。",
            f"- 手术候选行数：{len(match_rows)}。",
            f"- 有编码行数：{len(code_rows)}。",
            f"- 本轮样本手术编码覆盖率：{len(visits_with_code)}/{len(visit_ids)}（{(len(visits_with_code) / len(visit_ids) * 100 if visit_ids else 0):.1f}%）。",
            f"- match_type 分布：`{json.dumps(match_type_counts, ensure_ascii=False)}`。",
            f"- SC-083 applicability 分布：`{json.dumps(applicability_counts, ensure_ascii=False)}`。",
            "",
            "## SC-083 样本 2214679",
            *sc083_lines,
            "- 结论：只有 `code_exact/code_normalized` 命中 catalog 四级时，才可作为 SC-083 适用性强证据；如果只有名称候选或编码缺失，应进入 data_quality_gap / needs_review。",
            "",
            "## 后续接入建议",
            "- confirmed 条件必须包含 `matched_level=4` 且 `match_type in {code_exact, code_normalized}`。",
            "- `code_prefix_ext` 需要人工确认或小范围白名单后才能升级为强证据。",
            "- `name_*_candidate` 不得作为 confirmed 依据，只能辅助人工核查。",
            "- `code_missing/code_unmatched` 应输出数据缺口，说明缺手术编码或目录未覆盖。",
            "- `matched_level<=3` 应作为 SC-083 不适用或系统驳回依据。",
            "",
            "## 产物",
            f"- `{FIELD_PROBE_CSV.relative_to(REPO_ROOT)}`",
            f"- `{FIELD_PROBE_JSON.relative_to(REPO_ROOT)}`",
            f"- `{MATCH_PROBE_CSV.relative_to(REPO_ROOT)}`",
            f"- `{MATCH_PROBE_JSON.relative_to(REPO_ROOT)}`",
        ]
    ) + "\n"


def run() -> dict[str, Any]:
    if not CATALOG_CSV.exists():
        raise FileNotFoundError(f"catalog not found: {CATALOG_CSV}")
    field_rows, field_meta = _field_probe_rows()
    catalog = _load_catalog()
    visits = _build_visit_context()
    match_rows = _record_match_rows(visits, catalog)
    _write_csv(FIELD_PROBE_CSV, field_rows)
    _write_json(FIELD_PROBE_JSON, {"rows": field_rows, "metadata": field_meta})
    _write_csv(MATCH_PROBE_CSV, match_rows)
    _write_json(MATCH_PROBE_JSON, {"rows": match_rows, "summary": {
        "visit_count": len({_safe_text(row.get("visit_id")) for row in match_rows if _safe_text(row.get("visit_id"))}),
        "row_count": len(match_rows),
        "match_type_counts": _counter(match_rows, "match_type"),
        "sc083_applicability_counts": _counter(
            list({row.get("visit_id"): row for row in match_rows}.values()),
            "sc083_applicability",
        ),
    }})
    REPORT_MD.write_text(_report(field_rows, match_rows, field_meta=field_meta), encoding="utf-8")
    return {
        "field_probe_rows": len(field_rows),
        "match_probe_rows": len(match_rows),
        "output_dir": str(OUTPUT_DIR),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe surgery-level catalog code-first matching without writing DB.")
    parser.parse_args()
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
