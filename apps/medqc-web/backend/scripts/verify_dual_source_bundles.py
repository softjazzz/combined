"""独立子进程调用客户机已安装的Bundle刷新与读回；不启动应用或质控任务。"""

import contextlib
import io
import json
import logging
from pathlib import Path
import sys


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
    result = {"event": "bundle_result", "ok": False, "model_calls": 0, "qc_tasks_started": 0}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from dotenv import load_dotenv
            load_dotenv(backend / ".env", override=True)
            from app.services.bundles import assembly
            stats = assembly.refresh_all_bundle_variants_for_rows(
                rows=request["cases"], scenes=("running", "final"), policy_version="dual-source-small-acceptance")
            failed = sum(int(value.get("failed", 0)) for group in (stats.get("scenes", {}), stats.get("domains", {})) for value in group.values())
            if failed:
                raise ValueError("bundle_refresh_failed")
            from sqlalchemy import text
            from app.services.document_assembly.assembler import assemble_document
            inventory_tables = ("running_record_bundle", "final_record_bundle", *assembly._DOMAIN_BUNDLE_TABLE.values())
            checked = 0
            with assembly.engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                for case in request["cases"]:
                    documents = []
                    params = {key: case[key] for key in ("institute_id", "patient_id", "visit_id")}
                    predicate = "institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id"
                    for table in inventory_tables:
                        payload = connection.execute(text('SELECT source_documents FROM public."' + table + '" WHERE ' + predicate), params).scalar()
                        if isinstance(payload, str):
                            payload = json.loads(payload)
                        documents.extend(payload or [])
                    for table in request["tables"]:
                        if table.startswith("inpat_"):
                            continue
                        qualified = assembly._qualified_table(assembly._default_source_schema(), table)
                        rows = connection.execute(text('SELECT * FROM ' + qualified + ' WHERE ' + predicate), params).mappings().all()
                        for row in rows:
                            sections = [str(row.get(field) or "") for field in (
                                "record_content", "admission_condition", "treatment_course", "discharge_condition",
                                "discharge_order", "death_reason", "diagnosis", "surgery_process") if row.get(field)]
                            if not sections:
                                continue
                            document_id = assemble_document(table, dict(row)).document_id
                            check_document(table, document_id, sections, documents)
                            checked += 1
            result.update(ok=True, counts=stats, checked_documents=checked)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, code="bundle_refresh_or_content_verification_failed")
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
