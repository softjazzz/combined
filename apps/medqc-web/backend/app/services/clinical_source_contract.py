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



def read_columns(name, columns):
    """复用正式投影和ORM映射；返回实际会引用的列，不扩大到所有别名。"""
    available = set(columns)
    if name == "patient_information" and "visit_id" not in available:
        # 两键主索引不会进入三键文书取材；本轮只有EXISTS/身份键权限探针。
        # 若未来增加真实消费者或visit_id，仍走下方实际投影检查，不能永久豁免。
        required = set(REQUIRED_COLUMNS[name])
        return required, required & available
    from .bundles import assembly
    from .sample_programmatic_evidence import _SOURCE_TABLES
    from .luxian_0609 import source_evidence_reader as reader
    from ..database.models import cdm
    available = set(columns)
    full_rows = set(_SOURCE_TABLES) | {"mr", "diagnosis", "mr_surgery", "mr_cost"}
    orm = {"mr": cdm.MedicalRecordFrontpage, "diagnosis": cdm.Diagnosis,
           "mr_surgery": cdm.MrSurgery, "mr_cost": cdm.MrCost,
           "admission_record": cdm.AdmissionRecord, "discharge_record": cdm.DischargeRecord,
           "first_course_record": cdm.FirstCourseRecord, "inpat_registration": cdm.InpatRegistration}
    required = set(REQUIRED_COLUMNS.get(name, KEYS))
    if name in orm:
        required.update(column.name for column in orm[name].__table__.columns)
    selected = set(available) if name in full_rows else assembly.source_projection_columns(name, available)
    selected.update(set(reader._NATIVE_SOURCE_FIELDS.get(name, ())) & available)
    selected.update(set(reader._SNAPSHOT_SOURCE_FIELDS.get(name, ())) & available)
    selected.update(set((*assembly._ORDER_COLUMNS_PRIORITY, "document_id", "pathology_exam_id", "pathology_id",
                         "diagnosis_id", "order_id", "record_time", "report_datetime", "surgery_begin_datetime",
                         "surgery_begin_time", "transfution_datetime")) & available)
    return required, selected | (required & available)


def inspect_source(connection, *, check_rows=True):
    """逐个固定名字访问pg_catalog；无权限的表也不会从清单中消失。"""
    rows = []
    readonly = connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
    exists = connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='cdm')")).scalar_one()
    if not exists:
        return {"ok":False,"read_only":readonly,"schema":"cdm","dependencies":[
            {"table":name,"required":name not in OPTIONAL,"status":"table_missing","missing_columns":[],"publication":"unconfirmed"} for name in TABLES],
            "publication_ready":None,"capture_requires_controlled_window":False,"account_read_only":False}
    schema_usage = connection.execute(text("SELECT has_schema_privilege(current_user,'cdm','USAGE')")).scalar_one()
    # 先枚举可 SET 的身份（含当前身份），再展开该身份立即继承的能力。
    # SET 和 USAGE 各自已经包含传递关系；不能只对当前账号分别取二者并集。
    capability_roles = connection.execute(text("""
        SELECT DISTINCT effective.oid
        FROM pg_roles switched JOIN pg_roles effective
          ON pg_has_role(switched.oid,effective.oid,'USAGE')
        WHERE pg_has_role(current_user,switched.oid,'SET')
    """)).scalars().all()
    readonly_account = connection.execute(text("""
        SELECT NOT EXISTS (
          SELECT 1 FROM pg_roles r WHERE r.oid = ANY(:capability_roles)
          AND (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls
            OR has_schema_privilege(r.oid,'cdm','CREATE')
            OR has_database_privilege(r.oid,current_database(),'CREATE')
            OR r.oid IN (
              SELECT nspowner FROM pg_namespace WHERE nspname='cdm'
              UNION SELECT datdba FROM pg_database WHERE datname=current_database()
              UNION SELECT c.relowner FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='cdm'
              UNION SELECT p.proowner FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='cdm'
            ))
        )
    """), {"capability_roles": capability_roles}).scalar_one()
    for name in TABLES:
        metadata = connection.execute(text("""
            SELECT c.oid, (c.relowner = ANY(:capability_roles)) AS owns_object,
              has_table_privilege(current_user,c.oid,'SELECT') AS readable,
              EXISTS(SELECT 1 FROM pg_roles r WHERE r.oid = ANY(:capability_roles) AND
                (has_table_privilege(r.oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                 OR has_any_column_privilege(r.oid,c.oid,'INSERT,UPDATE,REFERENCES'))) AS writable,
              ARRAY(SELECT a.attname FROM pg_attribute a WHERE a.attrelid=c.oid
                AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum) AS columns
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='cdm' AND c.relname=:name AND c.relkind IN ('r','p','v','m','f')
        """), {"name": name, "capability_roles": capability_roles}).mappings().one_or_none()
        item = {"table": name, "required": name not in OPTIONAL, "publication": "unconfirmed"}
        if metadata is None:
            item.update(status="table_missing", missing_columns=[])
        else:
            required, selected = read_columns(name, metadata["columns"])
            missing = sorted(required - set(metadata["columns"]))
            denied = []
            if not metadata["readable"]:
                denied = [column for column in sorted(selected) if not connection.execute(text(
                    "SELECT has_column_privilege(current_user,:oid,:column,'SELECT')"
                ), {"oid": metadata["oid"], "column": column}).scalar_one()]
            item.update(read_columns=sorted(selected), denied_columns=denied, owns_object=metadata["owns_object"])
            if not schema_usage or denied:
                status = "select_denied"
            elif metadata["owns_object"]:
                status = "object_ownership_forbidden"
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
            "publication_ready": None, "capture_requires_controlled_window": False, "account_read_only": readonly_account}
