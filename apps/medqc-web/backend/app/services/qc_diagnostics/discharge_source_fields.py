"""在服务进程内核对出院文书取数字段；只读，不执行规则或构造模型客户端。"""

from datetime import datetime, timezone

from sqlalchemy import bindparam, text

from ..bundles import assembly
from ..luxian_0609 import source_evidence_reader as reader
from ..luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from ..luxian_0609.extended_document.discharge_documentation import _discharge_record_completion_time
from ..luxian_0609.native_extended_document_execution import _source_rows


FIELDS = ("chief_physician_sign_datetime", "v2_schema")


def _present(value):
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _layer_check(rows, raw):
    matches = [row for row in rows if row.get("document_id") == raw["document_id"]]
    if len(matches) != 1:
        return {"matched_rows": len(matches), "passed": False}
    row = matches[0]
    fields = {
        field: {"readable": field in row, "matches_pg": field in row and row[field] == raw.get(field)}
        for field in FIELDS
    }
    clocks = {
        field: row.get(field) == raw.get(field)
        for field in reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS
    }
    # 以移除新增证据后的原始行作为时间基线，避免两侧同时误用签署时间却被判一致。
    original_clock_fields = {key: value for key, value in raw.items() if key not in FIELDS}
    selected_clock_matches = (
        reader.authoritative_document_time_value(row)
        == reader.authoritative_document_time_value(original_clock_fields)
    )
    completion_clock_matches = (
        _discharge_record_completion_time(row)
        == _discharge_record_completion_time(original_clock_fields)
    )
    return {
        "matched_rows": 1,
        "fields": fields,
        "record_submit_unchanged": all(clocks.values()),
        "document_time_present": _present(reader.authoritative_document_time_value(row)),
        "completion_time_present": _discharge_record_completion_time(row) is not None,
        "passed": all(all(check.values()) for check in fields.values())
        and all(clocks.values()) and selected_clock_matches and completion_clock_matches,
    }


def check_discharge_source_fields(*, pool_id: str, row_numbers: list[int]) -> dict:
    """范围由样本集内行号确定；返回长度及一致性，绝不返回姓名、正文或原始JSON。"""
    if not 1 <= len(row_numbers) <= 6 or len(set(row_numbers)) != len(row_numbers):
        raise ValueError("invalid_scope")
    engine = assembly.engine
    if engine is None:
        raise RuntimeError("source_unavailable")
    scope_sql = text(
        "SELECT row_no, matched_institute_id, matched_patient_id, matched_visit_id "
        "FROM qc.manual_problem_sample_pool_items "
        "WHERE pool_id=:pool_id AND row_no IN :row_numbers ORDER BY row_no"
    ).bindparams(bindparam("row_numbers", expanding=True))
    schema = assembly._default_source_schema()
    columns = set(assembly._get_table_columns(schema, "discharge_record"))
    selected = [field for field in ("document_id", *FIELDS, *reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS)
                if field in columns]
    if "document_id" not in selected:
        raise RuntimeError("source_unavailable")
    raw_sql = text(
        "SELECT " + ", ".join(assembly._quote_ident(field) for field in selected)
        + " FROM " + assembly._qualified_table(schema, "discharge_record")
        + " WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id"
        + " LIMIT 101"
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        scope = connection.execute(scope_sql, {"pool_id": pool_id, "row_numbers": row_numbers}).mappings().all()
        if len(scope) != len(row_numbers):
            raise LookupError("scope_not_found")
        results = []
        for item in scope:
            coords = {field: str(item.get("matched_" + field) or "").strip()
                      for field in ("institute_id", "patient_id", "visit_id")}
            if not all(coords.values()):
                raise LookupError("scope_not_matched")
            raw_rows = connection.execute(raw_sql, coords).mappings().all()
            if len(raw_rows) > 100:
                raise RuntimeError("source_truncated")
            kwargs = dict(source_key="discharge_record", source_schema=schema, **coords)
            native = reader.read_luxian_0609_native_source_rows(**kwargs)
            snapshot = reader.read_luxian_0609_snapshot_source_rows(**kwargs)
            session = build_luxian_0609_evidence_read_session(
                selected_rule_ids=("LX0609-08-01-01",), source_schema=schema,
                created_at=datetime.now(timezone.utc).isoformat(), **coords,
            )
            materials = session.materials.rows("discharge_record")
            executor, error = _source_rows(session.materials, "discharge_record")
            if snapshot.truncated or error:
                raise RuntimeError("source_unavailable")
            documents = []
            for raw in raw_rows:
                layers = {name: _layer_check(rows, raw) for name, rows in (
                    ("native", native), ("snapshot", snapshot.rows),
                    ("material", materials), ("executor_input", executor),
                )}
                documents.append({
                    "signed_time_present": _present(raw.get(FIELDS[0])),
                    "json_present": _present(raw.get(FIELDS[1])),
                    "json_characters": len(raw.get(FIELDS[1]) or ""),
                    "record_time_present": any(_present(raw.get(f)) for f in ("record_time", "record_datetime")),
                    "submit_time_present": any(_present(raw.get(f)) for f in ("submit_time", "submit_datetime")),
                    "layers": layers,
                    "passed": all(layer["passed"] for layer in layers.values()),
                })
            results.append({"row_no": item["row_no"], "documents": documents,
                            "passed": bool(documents) and all(doc["passed"] for doc in documents)})
    return {"read_only": True, "source_key": "discharge_record", "results": results,
            "passed": all(item["passed"] for item in results)
            and FIELDS[0] not in reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
            "signed_time_is_document_clock": FIELDS[0] in reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS,
            "model_calls": 0, "qc_tasks_started": 0, "database_writes": 0}
