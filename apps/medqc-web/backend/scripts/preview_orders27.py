"""27例药品/非药品医嘱只读对账；只保存差异元数据，不保存药名或正文。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import zipfile

import preview_order_time_fill as check


TABLES = ("inpat_drug_order", "inpat_nondrug_order")
COMMON = {
    "visit_type": ("visit_type",), "group_id": ("group_id",),
    "repeat_indicator": ("repeat_indicator",), "inpat_no": ("inpat_no", "inpatno"),
    "dept_name": ("dept_name",), "order_status": ("order_status", "status"),
    "prescribed_datetime": ("prescribed_datetime", "prescribed_time"),
    "planned_start_datetime": ("planned_start_datetime", "planned_start_time"),
    "planned_end_datetime": ("planned_end_datetime", "planned_end_time"),
    "reviewed_datetime": ("reviewed_datetime", "reviewed_time"),
    "carried_datetime": ("carried_datetime", "carried_time"),
    "canceled_datetime": ("canceled_datetime", "canceled_time"),
    "is_deleted": ("is_deleted", "is_delete"),
}
DRUG = {
    "drug_type": ("drug_type",), "drug_code": ("drug_code",),
    "generic_name": ("generic_name", "drug_name", "order_item_name", "order_item"),
    "brand_name": ("brand_name",), "cfda_id": ("cfda_id",), "firm": ("firm",),
    "drug_specification": ("drug_specification", "specification"),
    "drug_frequency": ("drug_frequency", "frequency"),
    "drug_apply_method": ("drug_apply_method", "route"),
    "single_dose": ("single_dose", "dose", "dosage"),
    "single_dose_unit": ("single_dose_unit", "dose_unit"),
    "dose_form": ("dose_form",), "medication_duration": ("medication_duration",),
}
NONDRUG = {
    "application_id": ("application_id",), "order_type": ("order_type",),
    "order_name": ("order_name", "item_name", "order_item_name", "order_item"),
    "quantity": ("quantity",), "quantity_unit": ("quantity_unit",), "frequency": ("frequency",),
}


def mapping(table):
    return {**COMMON, **(DRUG if table == TABLES[0] else NONDRUG)}


def blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def canonical(row, fields):
    result = {"order_id": str(row.get("order_id") or "").strip()}
    for name, aliases in fields.items():
        present = [a for a in aliases if a in row]
        if present:
            result[name] = next((row[a] for a in present if not blank(row[a])), row[present[0]])
    return result


def comparable(field, value):
    if blank(value):
        return None
    if field.endswith("_datetime"):
        return check.parse_time(value)
    return str(value).strip()


def field_difference(field, source, local, source_has_column, local_has_column):
    if not source_has_column:
        return "source_column_absent"
    if not local_has_column:
        return "local_column_absent_with_source_value" if not blank(source) else "local_column_absent_source_empty"
    try:
        left, right = comparable(field, source), comparable(field, local)
    except (ValueError, check.PreviewError):
        return "invalid_time_needs_review"
    if left == right:
        return None
    if left is None:
        return "source_empty_keep_local"
    if right is None:
        return "local_empty_source_has_value"
    return "nonempty_conflict"


def scope_cases(raw):
    expected = {f"C{n:02d}" for n in range(1, 28)}
    if not isinstance(raw, list) or len(raw) != 27 or {c.get("sample") for c in raw} != expected:
        raise check.PreviewError("expected_27_cases")
    for case in raw:
        if case.get("institute_id") != "泸县人民医院":
            raise check.PreviewError("unexpected_case_institution")
        if any(not isinstance(case.get(k), str) or not case[k].strip() for k in ("patient_id", "visit_id")):
            raise check.PreviewError("invalid_case_identity")
    if len({(c["patient_id"], c["visit_id"]) for c in raw}) != 27:
        raise check.PreviewError("duplicate_case_identity")
    return sorted(raw, key=lambda c: c["sample"])


def table_columns(conn, schema, table):
    with conn.cursor() as cursor:
        cursor.execute("SELECT column_name,data_type FROM information_schema.columns "
                       "WHERE table_schema=%s AND table_name=%s", (schema, table))
        return dict(cursor.fetchall())


def read_case(conn, schema, table, cols, institute, case):
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor

    if not set(check.KEYS).issubset(cols):
        raise check.PreviewError("table_or_identity_columns_missing:" + schema + "." + table)
    selected = {"order_id"}
    for aliases in mapping(table).values():
        selected.update(set(aliases) & cols)
    # 不 SELECT *，不读取姓名、提交人、医师姓名或医嘱正文。
    query = sql.SQL("SELECT {} FROM {}.{} WHERE institute_id=%s AND patient_id=%s AND visit_id=%s").format(
        sql.SQL(", ").join(map(sql.Identifier, sorted(selected))), sql.Identifier(schema), sql.Identifier(table),
    )
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query, (institute, case["patient_id"], case["visit_id"]))
        rows = [canonical(dict(row), mapping(table)) for row in cursor.fetchall()]
        same_case = len(rows)
        if not rows:
            cursor.execute(sql.SQL("SELECT count(*) FROM {}.{} WHERE patient_id=%s AND visit_id=%s").format(
                sql.Identifier(schema), sql.Identifier(table)), (case["patient_id"], case["visit_id"]))
            same_case = cursor.fetchone()[0]
    return rows, same_case


def index_rows(rows):
    result = defaultdict(list)
    for row in rows:
        result[row["order_id"]].append(row)
    return result


def row_token(sample, order_id):
    return "ord_" + hashlib.sha256((sample + "\0" + order_id).encode("utf-8")).hexdigest()[:20]


def names(row):
    return {"".join(str(row.get(k) or "").split()) for k in ("generic_name", "brand_name", "order_name")
            if not blank(row.get(k))}


def identity_issues(table, source, local):
    if table == TABLES[0]:
        return check.identity_checks(source, local)
    problems = []
    if not names(source) or not names(local):
        problems.append("order_name_unavailable")
    elif not names(source).intersection(names(local)):
        problems.append("order_name_conflict")
    for name in ("prescribed_datetime", "planned_start_datetime"):
        if not blank(source.get(name)) and not blank(local.get(name)):
            if comparable(name, source[name]) != comparable(name, local[name]):
                problems.append(name + "_conflict")
    return problems


def candidate_index(rows_by_table):
    """仅为不同编号提供待核实线索，不据此合并或认定等价。"""
    result = defaultdict(set)
    for table, rows in rows_by_table.items():
        for row in rows:
            if not row["order_id"] or blank(row.get("prescribed_datetime")):
                continue
            try:
                when = comparable("prescribed_datetime", row["prescribed_datetime"])
            except (ValueError, check.PreviewError):
                continue
            for name in names(row):
                result[(when, name)].add((table, row["order_id"]))
    return result


def analyze_case(sample, source, local, schemas, emit_detail):
    source_indexes = {t: index_rows(source[t]) for t in TABLES}
    local_indexes = {t: index_rows(local[t]) for t in TABLES}
    candidates = candidate_index(local)
    summaries = []
    for table in TABLES:
        other = TABLES[1] if table == TABLES[0] else TABLES[0]
        si, li = source_indexes[table], local_indexes[table]
        counts, fields = Counter(), Counter()
        for order_id in sorted(set(si) | set(li)):
            sr, lr = si.get(order_id, []), li.get(order_id, [])
            token = row_token(sample, order_id)
            event = {"sample": sample, "table": table, "order_token": token}
            if not order_id or len(sr) > 1 or len(lr) > 1:
                counts["ambiguous_id_groups"] += 1
                emit_detail({**event, "kind": "empty_or_duplicate_id", "source_rows": len(sr), "local_rows": len(lr)})
                continue
            if source_indexes[other].get(order_id) or local_indexes[other].get(order_id):
                counts["cross_table_id_groups"] += 1
                emit_detail({**event, "kind": "cross_table_id_needs_review", "source_same_table_rows": len(sr),
                             "local_same_table_rows": len(lr), "source_other_table_rows": len(source_indexes[other].get(order_id, [])),
                             "local_other_table_rows": len(local_indexes[other].get(order_id, []))})
                continue
            if not sr:
                counts["local_only_unmatched_id"] += 1
                emit_detail({**event, "kind": "local_only_keep_no_delete"})
                continue
            if not lr:
                counts["source_only_unmatched_id"] += 1
                found = set()
                try:
                    when = comparable("prescribed_datetime", sr[0].get("prescribed_datetime"))
                    for name in names(sr[0]):
                        found.update(candidates.get((when, name), set()))
                except (ValueError, check.PreviewError):
                    pass
                if found:
                    counts["possible_rebuilt_id_groups"] += 1
                emit_detail({**event, "kind": "source_only_not_confirmed_missing", "candidate_count": len(found),
                             "candidate_tokens": sorted({row_token(sample, oid) for _, oid in found})[:5],
                             "source_status_available": not blank(sr[0].get("order_status"))})
                continue
            counts["same_table_unique_pairs"] += 1
            try:
                issues = identity_issues(table, sr[0], lr[0])
            except (ValueError, check.PreviewError):
                issues = ["invalid_identity_time"]
            if issues:
                counts["identity_issue_pairs"] += 1
                emit_detail({**event, "kind": "identity_needs_review", "reasons": issues})
            changed = False
            for field, aliases in mapping(table).items():
                source_has = bool(set(aliases) & schemas[("source", table)])
                local_has = field in schemas[("local", table)]
                kind = field_difference(field, sr[0].get(field), lr[0].get(field), source_has, local_has)
                # schema 级缺列已统一记录，逐行只记源端确实有值的目标缺列。
                if kind in {None, "source_column_absent", "local_column_absent_source_empty"}:
                    continue
                if field in {"generic_name", "brand_name"} and not issues and kind == "nonempty_conflict":
                    kind = "name_representation_difference"
                changed = True
                fields[(field, kind)] += 1
                detail = {**event, "kind": kind, "field": field, "identity_checks_passed": not issues}
                if field.endswith("_datetime") and kind != "invalid_time_needs_review":
                    detail.update(source_time=check.time_text(sr[0].get(field)), local_time=check.time_text(lr[0].get(field)))
                emit_detail(detail)
            counts["pairs_with_differences" if changed else "pairs_equal_in_compared_fields"] += 1
        summaries.append({"sample": sample, "table": table, "source_rows": len(source[table]),
                          "local_rows": len(local[table]), "counts": dict(counts),
                          "field_differences": [{"field": f, "kind": k, "rows": n} for (f, k), n in sorted(fields.items())]})
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--scope", type=Path, default=Path(__file__).with_name("cases27-private.json"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    backend, scope_path, output_dir = args.backend.resolve(), args.scope.resolve(), args.output_dir.resolve()
    logging.disable(logging.CRITICAL)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_dir = output_dir / ("orders27-preview-" + stamp)
    report_dir.mkdir(parents=True, exist_ok=False)
    source_conn = local_conn = None
    phase = "configuration"
    def emit(event, **data):
        print(json.dumps({"event": event, **data}, ensure_ascii=True), flush=True)
    try:
        cases = scope_cases(json.loads(scope_path.read_text(encoding="utf-8-sig")))
        local_dsn, source_dsn = check.connection_dsns(backend)
        emit("scope", cases=27, tables=list(TABLES), database_writes=0, model_calls=0)
        phase = "connect_homology"
        source_conn = check.connect_readonly(source_dsn)
        phase = "connect_local"
        local_conn = check.connect_readonly(local_dsn)
        schemas, schema_report = {}, []
        for side, conn, schema in (("source", source_conn, "graph3_homology"), ("local", local_conn, "cdm")):
            for table in TABLES:
                column_types = table_columns(conn, schema, table)
                cols = set(column_types)
                if not set(check.KEYS).issubset(cols):
                    raise check.PreviewError("table_or_identity_columns_missing:" + side + "." + table)
                schemas[(side, table)] = cols
                used = {"order_id"} | {a for aliases in mapping(table).values() for a in aliases}
                schema_report.append({"side": side, "table": table, "physical_columns": sorted(cols),
                                      "column_types": column_types,
                                      "field_aliases": mapping(table),
                                      "compared_fields": sorted(mapping(table)),
                                      "uncompared_columns": sorted(cols - used - set(check.KEYS)),
                                      "missing_canonical_fields": sorted(f for f in mapping(table) if f not in cols),
                                      "source_fields_with_no_alias": sorted(f for f, aliases in mapping(table).items() if not set(aliases) & cols)})
        summaries, mapping_warnings = [], []
        with (report_dir / "differences.jsonl").open("x", encoding="utf-8", newline="\n") as details:
            def emit_detail(value):
                details.write(json.dumps(value, ensure_ascii=False) + "\n")
            for case in cases:
                phase = "compare_" + case["sample"]
                source, local = {}, {}
                for side, conn, schema, institute, store in (
                    ("source", source_conn, "graph3_homology", "机构号", source),
                    ("local", local_conn, "cdm", case["institute_id"], local),
                ):
                    for table in TABLES:
                        rows, same_case = read_case(conn, schema, table, schemas[(side, table)], institute, case)
                        store[table] = rows
                        if not rows and same_case:
                            mapping_warnings.append({"sample": case["sample"], "side": side, "table": table,
                                                     "same_patient_visit_rows": same_case, "kind": "institution_mapping_needs_review"})
                compared = analyze_case(case["sample"], source, local, schemas, emit_detail)
                if not any(source.values()) or not any(local.values()):
                    mapping_warnings.append({"sample": case["sample"], "kind": "empty_side_requires_coverage_review",
                                             "source_rows": sum(map(len, source.values())),
                                             "local_rows": sum(map(len, local.values()))})
                summaries.extend(compared)
                combined = Counter()
                for entry in compared:
                    combined.update(entry["counts"])
                emit("case", sample=case["sample"], source_rows=sum(map(len, source.values())),
                     local_rows=sum(map(len, local.values())), counts=dict(combined))
        source_conn.rollback()
        local_conn.rollback()
        totals = Counter()
        for item in summaries:
            totals.update(item["counts"])
        manifest = {"complete": True, "cases": 27, "tables": list(TABLES), "captured_at_utc": stamp,
                    "transactions": "REPEATABLE READ READ ONLY on both databases; not a shared cross-database snapshot",
                    "database_writes": 0, "model_calls": 0, "totals": dict(totals),
                    "mapping_warnings": mapping_warnings,
                    "scope_note": "Compared curated order fields only. Unmatched IDs are not proven lost rows. No automatic fill plan or source switch."}
        for filename, payload in (("summary.json", summaries), ("schema.json", schema_report), ("manifest.json", manifest)):
            with (report_dir / filename).open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        archive = report_dir.with_suffix(".zip")
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as package:
            for path in sorted(report_dir.iterdir()):
                package.write(path, path.name)
        with zipfile.ZipFile(archive) as package:
            if package.testzip() is not None:
                raise check.PreviewError("report_archive_crc_failed")
        emit("done", complete=True, report=str(archive), totals=dict(totals),
             mapping_warnings=len(mapping_warnings), database_writes=0, model_calls=0)
        return 0
    except Exception as exc:
        emit("error", complete=False, phase=phase, error_type=type(exc).__name__,
             code=str(exc) if isinstance(exc, check.PreviewError) else None,
             sqlstate=getattr(exc, "pgcode", None), database_writes=0, model_calls=0)
        return 1
    finally:
        for conn in (source_conn, local_conn):
            if conn is not None:
                conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
