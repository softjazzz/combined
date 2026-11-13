"""一次病历短只读事务；捕获既有投影和读合同，不新增临床判断。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import time

from sqlalchemy import inspect

from . import case_material_snapshot as material
from ..database import clinical_connection as clinical


def capture(*, identity, cancellation_check=None, after_table_read=None):
    from .bundles import assembly, current_view, emr_view
    from .luxian_0609 import source_evidence_reader as reader
    from .sample_programmatic_evidence import capture_programmatic_sources, _SOURCE_TABLES
    from .validation_material_source import material_source_schema, is_material_copy

    if is_material_copy(identity[1], identity[2]):
        raise material.MaterialSnapshotError("pdf_case_material_snapshot_not_supported")
    if clinical.configured():
        try:
            until = datetime.fromisoformat(os.environ.get("QC_CDM_CAPTURE_WINDOW_UNTIL", "").replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if until.tzinfo is None or not now < until <= now + timedelta(hours=24):
                raise ValueError
        except ValueError:
            raise material.MaterialSnapshotError("cdm_publication_window_unconfirmed") from None
    coordinates = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
    schema = material_source_schema(default_schema=assembly._default_source_schema(), **coordinates)
    engine = assembly._source_engine(schema)
    if engine is None:
        raise material.MaterialSnapshotError("material_source_unavailable")
    state = {"protocol": material.PROTOCOL, "identity": list(identity), "binding": clinical.source_binding(),
             "schema": schema, "columns": {}, "tables": {}, "queries": {}}
    started = time.monotonic()
    last_cancel_check = 0.0

    def check():
        nonlocal last_cancel_check
        if cancellation_check and time.monotonic() - last_cancel_check >= 0.25:
            last_cancel_check = time.monotonic()
            if cancellation_check():
                raise material.MaterialSnapshotError("material_capture_cancelled")
        if time.monotonic() - started > 60:
            raise material.MaterialSnapshotError("material_capture_timeout")

    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout=10000")
            if clinical.configured() and schema == "cdm":
                from .clinical_source_contract import inspect_source
                if not inspect_source(connection, check_rows=False)["ok"]:
                    raise material.MaterialSnapshotError("material_source_contract_incomplete")
            from . import daily_material_projection as daily
            if daily.enabled():
                if not clinical.configured() or schema != "cdm":
                    raise material.MaterialSnapshotError("daily_material_independent_cdm_required")
                state["daily_material_manifest"] = daily.read_manifest(connection, identity)
            state.update(engine=engine, connection=connection)
            with material.recording(state):
                limits = assembly._material_limits_for_variants(scenes=tuple(assembly._SCENE_DOC_PRIORITY), domains=tuple(assembly._DOMAIN_DOC_PRIORITY))
                names = set(limits) | set(reader._NATIVE_SOURCE_FIELDS) | set(_SOURCE_TABLES) | {"mr", "mr_diagnosis", "mr_cost", "mr_surgery", "diagnosis", "inpat_registration"}
                inspector = inspect(connection)
                # 目录元数据也来自本事务；缺表不与权限错误混为一谈。
                for table in sorted(names):
                    check()
                    state["columns"][table] = tuple(column["name"] for column in inspector.get_columns(table, schema=schema)) if inspector.has_table(table, schema=schema) else ()
                for table in sorted(names):
                    check()
                    rows = assembly._select_records(schema=schema, table=table, **coordinates, limit=10001)
                    if len(rows) >= 10001:
                        raise material.MaterialSnapshotError("material_table_capacity_exceeded")
                    state["tables"][table] = rows
                    if after_table_read:
                        after_table_read(table)
                # 旧程序取证需要完整结构化行，不能以Bundle文本投影代替。
                state["programmatic_sources"] = capture_programmatic_sources(state, check)
                arguments = {**coordinates, "source_schema": schema}
                functions = (
                    reader.read_luxian_0609_course_round_timeline,
                    reader.has_luxian_0609_current_visit_unstable_order,
                    reader.read_luxian_0609_severity_order_rows,
                    reader.read_luxian_0609_exam_lab_order_rows,
                    reader.read_luxian_0609_rescue_order_rows,
                    reader.read_luxian_0609_discharge_horizon_rows,
                )
                for function in functions:
                    check()
                    try:
                        function(**arguments)
                    except (reader.SourceEvidenceUnavailable, reader.SourceEvidenceQueryError, reader.SourceEvidenceTruncated):
                        pass
                for function, keys in (
                    (reader.read_luxian_0609_snapshot_source_rows, tuple(reader._SNAPSHOT_SOURCE_FIELDS)),
                    (reader.read_luxian_0609_native_source_rows, tuple(reader._NATIVE_SOURCE_FIELDS)),
                    (reader.read_luxian_0609_runtime_source_rows, ("surgery_record", "mr_surgery", "presurg_summary", "surgery_safecheck_record")),
                ):
                    for key in keys:
                        check()
                        try:
                            function(source_key=key, **arguments)
                        except (reader.SourceEvidenceUnavailable, reader.SourceEvidenceQueryError, reader.SourceEvidenceTruncated):
                            pass
                # 调用原投影owner，历史文书直接使用该固定渲染材料而非最新公共Bundle。
                state["documents"] = current_view._assemble_current_documents(**coordinates)
                from .sichuan_qc_service import SichuanQCService
                diagnosis = SichuanQCService._resolve_primary_diagnosis_context(**coordinates)
                if diagnosis:
                    departments = {str(row.get("dept_name") or "").strip() for row in state["tables"].get("first_course_record", ())}
                    for department in sorted(departments - {""}):
                        check()
                        # 复用原有最多10份的同病种对照，不新选队列、不改变相似度规则。
                        SichuanQCService._load_same_disease_first_course_candidates(
                            institute_id=identity[0],current_patient_id=identity[1],current_visit_id=identity[2],
                            dept_name=department,diagnosis_code=str(diagnosis.get("diagnosis_code") or ""),
                            diagnosis_name=str(diagnosis.get("diagnosis_name") or ""),limit=10)
                state["domain_names"] = list(emr_view._DOMAIN_LOAD_ORDER)
                check()
            state.pop("engine")
            state.pop("connection")
    # 此处没有源库事务/连接；后续持久化和模型执行不会持有源事务。
    return state


def obtain(job_id, identity, *, retry=False, cancellation_check=None):
    existing = material.load(job_id, identity)
    if existing is not None:
        return existing
    if retry:
        raise material.MaterialSnapshotError("original_task_material_not_retained")
    try:
        return material.persist(job_id, capture(identity=identity, cancellation_check=cancellation_check))
    except material.MaterialSnapshotError:
        raise
    except Exception as error:
        if type(error).__name__ == "QCJobCancelled":
            raise
        raise material.MaterialSnapshotError("material_capture_failed") from None
