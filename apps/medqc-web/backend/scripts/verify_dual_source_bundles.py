"""独立子进程调用客户机已安装的Bundle刷新与读回；不启动应用或质控任务。"""

import contextlib
import io
import json
import logging
from pathlib import Path
import sys
import traceback


def inventory_expression(columns):
    if "source_documents" in columns:
        return "source_documents"
    if "structured_context" in columns:
        return "structured_context -> 'document_inventory'"
    raise ValueError("bundle_inventory_column_missing")


def refresh_if_requested(assembly, request):
    if request.get("refresh", True) is False:
        return {}
    return assembly.refresh_all_bundle_variants_for_rows(
        rows=request["cases"], scenes=("running", "final"), policy_version="dual-source-small-acceptance")


def source_sections(row):
    return [str(row[field]) for field in (
        "record_content", "admission_condition", "treatment_course", "discharge_condition",
        "discharge_order", "death_reason", "diagnosis", "surgery_process")
        if row.get(field) and str(row[field]).strip() not in {"[]", "{}", "null"}]


def check_required_documents(checks, required):
    fields = ("sample", "table", "document_id")
    found = {tuple(check.get(field) for field in fields) for check in checks if check.get("bundle_content_verified")}
    if any(tuple(doc.get(field) for field in fields) not in found for doc in required):
        raise ValueError("expected_document_missing")


def check_document(table, document_id, sections, documents):
    matches = [doc for doc in documents if doc.get("source_table") == table
               and str(doc.get("document_id")) == str(document_id)]
    if not document_id or not matches:
        raise ValueError("bundle_document_missing")
    body = "".join(str(doc.get("content") or "") for doc in matches)
    if any("".join(section.split()) not in "".join(body.split()) for section in sections):
        raise ValueError("bundle_content_incomplete")


def main():
    request = json.load(sys.stdin)
    backend = Path(request["backend"])
    sys.path.insert(0, str(backend))
    logging.disable(logging.CRITICAL)
    result = {"event": "bundle_result", "ok": False, "model_calls": 0, "qc_tasks_started": 0,
              "refresh_requested": request.get("refresh", True) is not False, "checks": []}
    if not result["refresh_requested"]:
        result["database_writes"] = 0
    phase, context, stats = "load_config", {}, {}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from dotenv import load_dotenv
            load_dotenv(backend / ".env", override=True)
            from app.services.bundles import assembly
            phase = "refresh"
            stats = refresh_if_requested(assembly, request)
            failed = sum(int(value.get("failed", 0)) for group in (stats.get("scenes", {}), stats.get("domains", {})) for value in group.values())
            if failed:
                raise ValueError("bundle_refresh_failed")
            from sqlalchemy import text
            from app.services.document_assembly.assembler import assemble_document
            inventory_tables = ("running_record_bundle", "final_record_bundle", *assembly._DOMAIN_BUNDLE_TABLE.values())
            checked = 0
            with assembly.engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                phase = "bundle_schema"
                columns = connection.execute(text(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND column_name IN ('source_documents','structured_context')"
                )).all()
                expressions = {table: inventory_expression({column for name, column in columns if name == table})
                               for table in inventory_tables}
                for case in request["cases"]:
                    documents = []
                    params = {key: case[key] for key in ("institute_id", "patient_id", "visit_id")}
                    predicate = "institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id"
                    for table in inventory_tables:
                        phase, context = "read_bundle_inventory", {"sample": case.get("sample"), "table": table}
                        stored = connection.execute(text('SELECT ' + expressions[table] + ' AS inventory FROM public."' + table + '" WHERE ' + predicate), params).first()
                        if stored is None:
                            raise ValueError("bundle_row_missing")
                        payload = stored[0]
                        if isinstance(payload, str):
                            payload = json.loads(payload)
                        if payload is not None and (not isinstance(payload, list) or any(not isinstance(doc, dict) for doc in payload)):
                            raise ValueError("bundle_inventory_shape_invalid")
                        documents.extend(payload or [])
                    for table in request["tables"]:
                        if table.startswith("inpat_"):
                            continue
                        phase, context = "read_source_rows", {"sample": case.get("sample"), "table": table}
                        qualified = assembly._qualified_table(assembly._default_source_schema(), table)
                        rows = connection.execute(text('SELECT * FROM ' + qualified + ' WHERE ' + predicate), params).mappings().all()
                        for row in rows:
                            sections = source_sections(row)
                            if not sections:
                                continue
                            document_id = assemble_document(table, dict(row)).document_id
                            phase = "compare_document"
                            check_document(table, document_id, sections, documents)
                            checked += 1
                            result["checks"].append({**context, "document_id": document_id,
                                                     "nonempty_sections": len(sections), "bundle_content_verified": True})
            phase, context = "expected_documents", {}
            check_required_documents(result["checks"], request.get("required_documents", []))
            result.update(ok=True, counts=stats, checked_documents=checked)
    except Exception as exc:
        safe_codes = {"bundle_refresh_failed", "bundle_inventory_column_missing", "bundle_row_missing",
                      "bundle_inventory_shape_invalid", "bundle_document_missing", "bundle_content_incomplete",
                      "expected_document_missing"}
        code = str(exc) if isinstance(exc, ValueError) and str(exc) in safe_codes else "bundle_refresh_or_content_verification_failed"
        result.update(error_type=type(exc).__name__, code=code, phase=phase, context=context, counts=stats,
                      sqlstate=getattr(getattr(exc, "orig", exc), "pgcode", None),
                      locations=[{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                                 for f in traceback.extract_tb(exc.__traceback__)[-3:]])
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
