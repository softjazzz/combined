"""业务只读依赖清单；不把物理表/空表当作已完成发布的证明。"""
from __future__ import annotations

from sqlalchemy import text

KEYS = ("institute_id", "patient_id", "visit_id")
# 对应目录、Bundle全部领域、RecordRepository以及LX0609来源。
# 虚拟exam_lab_order复用inpat_nondrug_order，诊断子表有已存在的父文书/diagnosis回退。
TABLES = tuple("""
admission_record admission_record_diagnosis anesthesia_record blood_application bloodtrans_record
consent_form consultation_record crisis_value_record daily_course_record death_discussion death_record
diagnosis diffcase_discussion_record discharge_record discharge_record_diagnosis docpat_commu_record
exam_item exam_item_report exam_master patient_information first_course_record first_course_record_diagnosis handoff_record handover_record
inpat_bill_item inpat_drug_order inpat_nondrug_order inpat_prescription inpat_prescription_item inpat_registration
labtest_item_report labtest_master medical_insurance_settlement medical_insurance_settlement_cost medical_order
mr mr_bloodtrans mr_cost mr_diagnosis mr_surgery newborn_record pathology_exam_master pathology_exam_report
physician_change_event postane_surveil_record postsurg_firstcourse_record preane_surveil_record presurg_discussion
presurg_summary rescue_record senior_course_record summary_record surgery_application surgery_inform_consent
surgery_inventory_record surgery_record surgery_risk_assessment surgery_safecheck_record transfer_in_record transfer_out_record
""".split())
OPTIONAL = frozenset(("patient_information", "exam_item", "exam_master", "inpat_registration", "physician_change_event", "medical_order", "consent_form",
    "medical_insurance_settlement", "medical_insurance_settlement_cost", "inpat_prescription", "inpat_prescription_item",
    "admission_record_diagnosis", "first_course_record_diagnosis", "discharge_record_diagnosis", "mr_diagnosis"))
REQUIRED_COLUMNS = {
    "patient_information": ("institute_id", "patient_id"),
    "admission_record": (*KEYS, "document_id", "record_content", "admission_datetime"),
    "discharge_record": (*KEYS, "document_id", "record_content", "admission_date", "discharge_date"),
    "daily_course_record": (*KEYS, "document_id", "record_content"),
    "exam_item_report": (*KEYS, "document_id", "record_content"),
    "labtest_item_report": (*KEYS, "document_id", "record_content"),
    "diagnosis": (*KEYS, "diagnosis_name"),
}


def inspect_source(connection, *, check_rows=True):
    """逐个固定名字访问pg_catalog；无权限的表也不会从清单中消失。"""
    rows = []
    readonly = connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
    exists = connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='cdm')")).scalar_one()
    if not exists:
        return {"ok":False,"read_only":readonly,"schema":"cdm","dependencies":[
            {"table":name,"required":name not in OPTIONAL,"status":"table_missing","missing_columns":[],"publication":"unconfirmed"} for name in TABLES],
            "publication_ready":None,"capture_requires_controlled_window":True,"account_read_only":False}
    schema_usage = connection.execute(text("SELECT has_schema_privilege(current_user,'cdm','USAGE')")).scalar_one()
    readonly_account = connection.execute(text("""
        SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
          AND NOT has_schema_privilege(current_user,'cdm','CREATE')
          AND NOT has_database_privilege(current_user,current_database(),'CREATE')
        FROM pg_roles WHERE rolname=current_user
    """)).scalar_one()
    for name in TABLES:
        metadata = connection.execute(text("""
            SELECT c.oid, has_table_privilege(current_user,c.oid,'SELECT') AS readable,
              has_table_privilege(current_user,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AS writable,
              ARRAY(SELECT a.attname FROM pg_attribute a WHERE a.attrelid=c.oid
                AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum) AS columns
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='cdm' AND c.relname=:name AND c.relkind IN ('r','p','v','m','f')
        """), {"name": name}).mappings().one_or_none()
        item = {"table": name, "required": name not in OPTIONAL, "publication": "unconfirmed"}
        if metadata is None:
            item.update(status="table_missing", missing_columns=[])
        else:
            missing = sorted(set(REQUIRED_COLUMNS.get(name, KEYS)) - set(metadata["columns"]))
            if not schema_usage or not metadata["readable"]:
                status = "select_denied"
            elif metadata["writable"]:
                status = "write_privilege_forbidden"
            elif missing:
                status = "columns_missing"
            else:
                status = "structure_ready"
                if check_rows:
                    # 固定白名单；仅EXISTS，不读取正文，不输出标识。
                    present = connection.execute(text(f'SELECT EXISTS(SELECT 1 FROM cdm."{name}" LIMIT 1)')).scalar_one()
                    status = "rows_present" if present else "zero_rows"
            item.update(status=status, missing_columns=missing)
        rows.append(item)
    bad = [r for r in rows if r["status"] not in {"structure_ready", "rows_present", "zero_rows"}
           and (r["required"] or r["status"] != "table_missing")]
    return {"ok": readonly and readonly_account and not bad, "read_only": readonly, "schema": "cdm", "dependencies": rows,
            "publication_ready": None, "capture_requires_controlled_window": True, "account_read_only": readonly_account}
