"""只对已导入的独立副本刷新Bundle并验收；无质控/模型入口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from pdf_material_copy import digest


def protected_fingerprints(engine, plan):
    """只返回旧Bundle/当前关联任务的散列，不把患者原文写到公共日志。"""
    from app.services.bundles import assembly

    found = {}
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        for table in (*assembly._SCENE_BUNDLE_TABLE.values(), *assembly._DOMAIN_BUNDLE_TABLE.values()):
            for case in plan["copies"]:
                src = case["source_case"]
                value = conn.execute(text(f"SELECT md5(to_jsonb(t)::text) FROM public.{table} t "
                    "WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id"),src).scalars().all()
                found[table+":"+src["sample"]] = value
        ids = sorted({case["item"].get("latest_job_id") for case in plan["copies"]} - {None,""})
        for identifier in ids:
            value = conn.execute(text("SELECT md5(to_jsonb(t)::text) FROM qc.custom_qc_batch_jobs t WHERE id=:id"), {"id":identifier}).scalars().all()
            found["latest_job:"+identifier] = value
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--env-file",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--refresh",action="store_true")
    args = parser.parse_args()
    if ".tmp" not in args.output.resolve().parts or not args.output.parent.name.endswith("-private"):
        raise ValueError("private_output_required")
    load_dotenv(args.env_file, override=True)
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"backend"))
    from app.database.connection import engine, SessionLocal
    from app.services.bundles import assembly
    from app.services.bundles.current_view import load_current_documents
    from app.services.qc_workspace.record_repository import RecordRepository
    from app.services.case_identity import CaseRef
    from app.services.luxian_0609.source_evidence_reader import read_luxian_0609_snapshot_source_rows
    from app.services.validation_material_source import material_source_schema

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    before = protected_fingerprints(engine, plan)
    rows = [dict(institute_id=case["source_case"]["institute_id"],patient_id=case["mapping"]["patient_id"],visit_id=case["mapping"]["visit_id"]) for case in plan["copies"]]
    if args.refresh:
        with engine.connect() as conn:
            if conn.execute(text("SELECT plan_sha256 FROM qc.validation_material_batches WHERE id=:id"),{"id":plan["batch_id"]}).scalar_one() != plan["plan_sha256"]:
                raise ValueError("imported_batch_plan_mismatch")
        result = assembly.refresh_all_bundle_variants_for_rows(rows=rows,policy_version="authorized_pdf_material_copy_v1",
            continue_on_error=False, trigger_source="pdf_material_import")
        print(json.dumps(dict(event="bundles_refreshed",processed_visits=result.get("processed"),model_calls=0,qc_runs=0)),flush=True)
    refs = [CaseRef.from_mapping(row) for row in rows]
    repository = RecordRepository(session_factory=SessionLocal)
    records = repository.collect_records(scope="all",department=None,doctor=None,date_field="admission",start_date=None,end_date=None,keyword=None,record_refs=refs)
    if {CaseRef.from_mapping(record) for record in records} != set(refs):
        raise ValueError("copied_cases_not_executable_by_record_repository")
    repository.hydrate_records_with_medical_text(records)
    checks = []
    for case,row in zip(plan["copies"],rows):
        owner = material_source_schema(default_schema="cdm",**row)
        if owner != plan["storage_schema"]:
            raise ValueError("copy_owner_mismatch")
        view = load_current_documents(**row)
        candidates = [doc for doc in view["documents"] if doc.get("doc_type") == "pdf_candidate"]
        expected_held = [doc for doc in case["documents"] if doc["state"] in ("version_review","held")]
        if len(candidates) != len(expected_held):
            raise ValueError("pdf_review_documents_not_visible")
        evidence_checks = {}
        for table in ("daily_course_record","senior_course_record","inpat_drug_order","inpat_nondrug_order",
                      "bloodtrans_record","discharge_record","death_record","pathology_exam_report"):
            source = read_luxian_0609_snapshot_source_rows(source_key=table,source_schema=None,**row)
            evidence_checks[table] = dict(rows=len(source.rows),truncated=source.truncated)
            if any(doc["candidate_id"] in {str(item.get("document_id")) for item in source.rows} for doc in expected_held):
                raise ValueError("inactive_pdf_candidate_leaked_into_rule_input")
        # 原始PDF字节与逐片段内容逐个核验，不能只看数量。
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            for file in conn.execute(text("SELECT sha256,content FROM qc.validation_material_files WHERE copy_id=:id"),{"id":case["id"]}).mappings():
                if hashlib.sha256(bytes(file["content"])).hexdigest()!=file["sha256"]:
                    raise ValueError("stored_pdf_checksum_mismatch")
            stored = conn.execute(text("SELECT candidate_id,content FROM qc.validation_material_documents WHERE copy_id=:id"),{"id":case["id"]}).mappings().all()
            expected = {doc["candidate_id"]:doc["content"] for doc in case["documents"]}
            if {doc["candidate_id"]:doc["content"] for doc in stored} != expected:
                raise ValueError("stored_pdf_segment_mismatch")
        checks.append(dict(sample=case["source_case"]["sample"],current_documents=len(view["documents"]),review_documents=len(candidates),rule_sources=evidence_checks))
        print(json.dumps(dict(event="case_verified",sample=case["source_case"]["sample"],review_documents=len(candidates),model_calls=0,qc_runs=0)),flush=True)
    after = protected_fingerprints(engine,plan)
    if before != after:
        raise ValueError("original_bundle_or_latest_job_changed_during_finalization")
    if args.refresh:
        with engine.begin() as conn:
            conn.execute(text("UPDATE qc.manual_problem_sample_pool_items SET bundle_status='ready' WHERE pool_id=:pool"),{"pool":plan["target_pool_id"]})
            conn.execute(text("UPDATE qc.manual_problem_sample_pools SET ready_items=27,updated_at=now() WHERE id=:pool"),{"pool":plan["target_pool_id"]})
            conn.execute(text("UPDATE qc.validation_material_batches SET state='ready' WHERE id=:id"),{"id":plan["batch_id"]})
    report = dict(event="verified",cases=len(checks),checks=checks,original_bundle_and_latest_job_unchanged=True,
                  protected_before=digest(before),protected_after=digest(after),model_calls=0,qc_runs=0,
                  ready=True,refreshed=args.refresh)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:value for key,value in report.items() if key!="checks"},ensure_ascii=True),flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 私有完整栈只写入明确的审计目录，不把SQL参数或患者信息输出到公共日志。
        import traceback
        import re
        output_arg = sys.argv[sys.argv.index("--output")+1] if "--output" in sys.argv else None
        if output_arg:
            target = Path(output_arg).resolve()
            if ".tmp" in target.parts and target.parent.name.endswith("-private"):
                target.with_name("finalize-error-private.txt").write_text(traceback.format_exc(),encoding="utf-8")
        code = str(exc) if isinstance(exc,ValueError) and re.fullmatch("[a-z_]+",str(exc)) else None
        print(json.dumps(dict(event="finalization_failed",error_type=type(exc).__name__,code=code,
                              data_already_imported=True,model_calls=0,qc_runs=0)),flush=True)
        raise SystemExit(1) from None
