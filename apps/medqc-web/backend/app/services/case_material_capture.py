"""一次病历短只读事务；捕获既有投影和读合同，不新增临床判断。"""
from __future__ import annotations

import builtins
import logging
import time
from traceback import walk_tb

from sqlalchemy import exc as sqlalchemy_errors, inspect

from . import case_material_snapshot as material
from ..database import clinical_connection as clinical

logger = logging.getLogger(__name__)


def _log_capture_failure(stage, error):
    # 只取可信基类名。异常消息、动态异常类名和堆栈源码都可能携带病历或连接参数。
    error_type = next(
        cls.__name__ for cls in type(error).__mro__
        if vars(builtins).get(cls.__name__) is cls or vars(sqlalchemy_errors).get(cls.__name__) is cls
    )
    owner, line = "case_material_capture", None
    for frame, number in walk_tb(error.__traceback__):
        module = frame.f_globals.get("__name__")
        if module in {__name__, material.__name__, f"{__package__}.automatic_material_scope"}:
            owner, line = module.rsplit(".", 1)[-1], number
            if stage == "source_read" and frame.f_code.co_name in {"validate_read_contract", "validate_table_identity"}:
                stage = "source_validation"
    logger.error("material_capture_failed stage=%s type=%s owner=%s line=%s", stage, error_type, owner, line)


def capture(*, identity, cancellation_check=None, after_table_read=None):
    from .bundles import assembly, current_view, emr_view
    from .luxian_0609 import source_evidence_reader as reader
    from .luxian_0609.clinical_material_policy import CLINICAL_MATERIAL_POLICY_VERSION, clinical_source_keys
    from .sample_programmatic_evidence import capture_programmatic_sources, _SOURCE_TABLES
    from .validation_material_source import material_source_schema, is_material_copy

    pdf_copy = is_material_copy(identity[1], identity[2])
    coordinates = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
    # 副本登记与正文必须来自同一个一致性事务，不能先用缓存或另一连接解析schema。
    schema = None if pdf_copy else material_source_schema(default_schema=assembly._default_source_schema(), **coordinates)
    engine = assembly.engine if pdf_copy else assembly._source_engine(schema)
    if engine is None:
        raise material.MaterialSnapshotError("material_source_unavailable")
    state = {"protocol": material.PROTOCOL, "identity": list(identity), "binding": material.source_binding(identity),
             "schema": schema, "columns": {}, "tables": {}, "queries": {},
             "clinical_material_policy": CLINICAL_MATERIAL_POLICY_VERSION}
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
            state.update(engine=engine, connection=connection)
            if pdf_copy:
                from .validation_material_source import capture_validation_material
                with material.recording(state):
                    state["validation_material"] = capture_validation_material(connection, identity)
                schema = state["validation_material"]["schema"]
                state["schema"] = schema
            state["read_contract"] = {"schema": schema, "read_only": True,
                                      "isolation_level": "REPEATABLE READ",
                                      "identity_columns": list(coordinates)}
            if pdf_copy:
                state["read_contract"]["table_identity_columns"] = {}
            if clinical.configured() and schema == "cdm":
                from .clinical_source_contract import inspect_source
                from .automatic_material_scope import PROTOCOL, validate_read_contract
                report = inspect_source(connection, check_rows=False, primary_documents_only=True)
                source_statuses = validate_read_contract(report)
                state["read_contract"]["source_report"] = report
                state["automatic_material"] = {"protocol": PROTOCOL, "sources": {}}
            from . import daily_material_projection as daily, primary_material_projection as primary
            if not pdf_copy and primary.enabled():
                if not clinical.configured() or schema != "cdm":
                    raise material.MaterialSnapshotError("primary_material_independent_cdm_required")
                primary.capture_into(state, connection, identity)
            elif not pdf_copy and daily.enabled():
                if not clinical.configured() or schema != "cdm":
                    raise material.MaterialSnapshotError("daily_material_independent_cdm_required")
                state["daily_material_manifest"] = daily.read_manifest(connection, identity)
            with material.recording(state):
                limits = assembly._material_limits_for_variants(scenes=tuple(assembly._SCENE_DOC_PRIORITY), domains=tuple(assembly._DOMAIN_DOC_PRIORITY))
                names = set(limits) | set(reader._NATIVE_SOURCE_FIELDS) | set(_SOURCE_TABLES) | {"mr", "mr_diagnosis", "mr_cost", "mr_surgery", "diagnosis", "inpat_registration"}
                names = set(clinical_source_keys(names))
                inspector = inspect(connection)
                # 目录元数据也来自本事务；缺表不与权限错误混为一谈。
                for table in sorted(names):
                    check()
                    state["columns"][table] = tuple(column["name"] for column in inspector.get_columns(table, schema=schema)) if inspector.has_table(table, schema=schema) else ()
                    if pdf_copy and state["columns"][table]:
                        from .clinical_source_contract import material_identity_columns
                        material.validate_table_identity(table, state["columns"][table], identity, ())
                        state["read_contract"]["table_identity_columns"][table] = list(material_identity_columns(table, state["columns"][table]))
                for table in sorted(names):
                    check()
                    status = source_statuses.get(table, "structure_ready") if "automatic_material" in state else "structure_ready"
                    # 不对缺列来源执行不完整 SQL；其他来源仍在本事务捕获。
                    rows = [] if status == "columns_missing" and primary.scope(table) is None else assembly._select_records(schema=schema, table=table, **coordinates, limit=10001)
                    if len(rows) >= 10001:
                        raise material.MaterialSnapshotError("material_table_capacity_exceeded")
                    if pdf_copy and state["columns"][table]:
                        material.validate_table_identity(table, state["columns"][table], identity, rows)
                    state["tables"][table] = rows
                    if "automatic_material" in state:
                        from .automatic_material_scope import describe_source
                        state["automatic_material"]["sources"][table] = describe_source(
                            state["columns"][table], rows,
                            status if state["columns"][table] else "table_missing")
                    if after_table_read:
                        after_table_read(table)
                if "automatic_material" in state:
                    from .cdm_publication_evidence import read_publication
                    publication = read_publication(connection, state["tables"])
                    state["automatic_material"]["publication"] = publication
                    for table, scope in state["automatic_material"]["sources"].items():
                        scope["publication_evidence"] = publication["rows"].get(table, [])
                        scope["publication_metadata_status"] = publication["status"]
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
                    for key in clinical_source_keys(keys):
                        check()
                        try:
                            function(source_key=key, **arguments)
                        except (reader.SourceEvidenceUnavailable, reader.SourceEvidenceQueryError, reader.SourceEvidenceTruncated):
                            pass
                # 调用原投影owner，历史文书直接使用该固定渲染材料而非最新公共Bundle。
                state["documents"] = current_view._assemble_current_documents(**coordinates)
                from .sichuan_qc_service import SichuanQCService
                # 辅助查询也必须保存缺口回执；不能因缺诊断字段中断其他材料，
                # 也不能跳过捕获后让相关规则回查当前库。权限/连接/身份异常仍抛出。
                try:
                    diagnosis = SichuanQCService._resolve_primary_diagnosis_context(**coordinates)
                except reader.SourceEvidenceUnavailable:
                    diagnosis = None
                if diagnosis:
                    departments = {str(row.get("dept_name") or "").strip() for row in state["tables"].get("first_course_record", ())}
                    for department in sorted(departments - {""}):
                        check()
                        # 复用原有最多10份的同病种对照，不新选队列、不改变相似度规则。
                        try:
                            SichuanQCService._load_same_disease_first_course_candidates(
                                institute_id=identity[0],current_patient_id=identity[1],current_visit_id=identity[2],
                                dept_name=department,diagnosis_code=str(diagnosis.get("diagnosis_code") or ""),
                                diagnosis_name=str(diagnosis.get("diagnosis_name") or ""),limit=10)
                        except reader.SourceEvidenceUnavailable:
                            pass  # material_query已保存该调用的缺口，其他文书继续捕获。
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
    stage = "source_read"
    try:
        captured = capture(identity=identity, cancellation_check=cancellation_check)
        stage = "snapshot_persist"
        return material.persist(job_id, captured)
    except material.MaterialSnapshotError:
        raise
    except Exception as error:
        if type(error).__name__ == "QCJobCancelled":
            raise
        _log_capture_failure(stage, error)
        raise material.MaterialSnapshotError("material_capture_failed") from None


def pdf_retry_materials(job, lookup):
    """PDF重试准入只依赖已保存任务链、可信三键及原快照，不查询当前登记。"""
    from .material_job_lineage import MaterialLineageError

    try:
        return _pdf_retry_materials(job, lookup)
    except MaterialLineageError:
        # 不暴露内部链字段；仅转换解析器自身的合同拒绝，不吞任意ValueError。
        raise material.MaterialSnapshotError("material_retry_lineage_invalid") from None


def _pdf_retry_materials(job, lookup):
    from .material_job_lineage import _filters, _refs, resolve_material_job_id
    from .qc_workspace.failed_rule_retry import FAILED_RULE_RETRY_FILTER_KEY, FAILED_RULE_RETRY_SCHEMA_VERSION
    from .validation_material_source import is_material_copy, material_source_schema

    filters, _ = _filters(job)
    retry_scope = filters.get(FAILED_RULE_RETRY_FILTER_KEY)
    failed_retry = isinstance(retry_scope, dict) and retry_scope.get("schema_version") == FAILED_RULE_RETRY_SCHEMA_VERSION
    if filters.get("retry_lineage") is None and not failed_retry:
        return None
    raw_refs = filters.get("record_refs") or []
    if not any(isinstance(ref, dict) and is_material_copy(ref.get("patient_id", ""), ref.get("visit_id", "")) for ref in raw_refs):
        return None
    accepted = _refs(filters)
    from .clinical_sources import saved_snapshot
    if saved_snapshot(filters)["id"] != "legacy_pg":
        raise material.MaterialSnapshotError("material_identity_or_source_mismatch")
    selected = _refs(retry_scope) if failed_retry else accepted
    if not selected.issubset(accepted) or not all(
        patient.startswith("pdfp_") and visit.startswith("pdfv_") for _, patient, visit in accepted
    ):
        raise material.MaterialSnapshotError("material_identity_or_source_mismatch")
    owner = resolve_material_job_id(job, lookup)
    result = {}
    for identity in sorted(selected):
        frozen = material.load(owner, identity)
        if frozen is None:
            raise material.MaterialSnapshotError("original_task_material_not_retained")
        # 冻结登记也必须是该完整身份/schema；只存在同名任务文件并不足够。
        with material.activate(frozen):
            material_source_schema(default_schema=frozen["schema"], requested_schema=frozen["schema"],
                                   **dict(zip(("institute_id", "patient_id", "visit_id"), identity)))
        result[identity] = frozen
    return result
