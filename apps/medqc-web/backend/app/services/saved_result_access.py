"""保存结果入口的机构授权；账号角色与机构只取持久 owner。"""

import json

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from .defect_rectification_service import RectificationError, _person


# 泸县人民医院账号查看「机构号」病例时须核验东华单院的归属证据，投递代次与接口由现场核定。
# 旧快照缺少账本元数据时，仅在已核定的 CDM 绑定上核对现行回执；归属无法核验时拒绝访问。
_DONGHUA_EPOCH = "7cecd40f-047d-4458-b964-8741d0ea7399"
_DONGHUA_BINDING = "cdm-read-v1:d6426d946c655b24ec8ad3915e7441e7cb5033dd69c7397a70c7431f5a3dea08"
_DONGHUA_TABLES = ("admission_record", "discharge_record")
_COORDINATES = ("institute_id", "patient_id", "visit_id")


def saved_result_institute_scope(actor_id: str) -> str | None:
    """None 仅表示持久账号具有全局角色，不以请求中的角色或机构兜底。"""
    from ..database.connection import SessionLocal

    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(403, "缺少可信账号身份")
    try:
        if SessionLocal is None:
            raise RuntimeError("account_store_unavailable")
        with SessionLocal() as session:
            actor = _person(session, actor_id.strip())
        # 与既有报表的 admin/sync_admin 全局范围一致，保留本入口原有 super_admin。
        if actor["roles"] & {"admin", "sync_admin", "super_admin"}:
            return None
        if "qc_manager" not in actor["roles"]:
            raise HTTPException(403, "无权读取质控结果")
        scope = actor["institute_id"]
        if not isinstance(scope, str) or not scope.strip() or scope != scope.strip():
            raise HTTPException(403, "账号缺少可信机构范围")
        return scope
    except RectificationError:
        raise HTTPException(403, "账号或机构权限无效") from None
    except HTTPException:
        raise
    except Exception:
        # 数据库异常不回显连接串、SQL或账号内部信息，也不按请求角色兜底。
        raise HTTPException(503, "账号机构权限来源暂不可用") from None


def check_saved_result_institute(scope: str | None, institute_id: str) -> None:
    if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
        raise HTTPException(403, "缺少可信病历机构范围")
    if scope is not None and scope != institute_id:
        raise HTTPException(403, "无权读取其他机构质控结果")


def require_saved_result_institute(actor_id: str, institute_id: str) -> None:
    check_saved_result_institute(saved_result_institute_scope(actor_id), institute_id)


def result_view_needs_donghua_proof(actor_id: str, institute_id: str) -> bool:
    """只有查看结果可以使用已确认的东华单院来源，其他操作沿用各自的权限。"""
    return scope_needs_donghua_result_proof(saved_result_institute_scope(actor_id), institute_id)


def scope_needs_donghua_result_proof(scope: str | None, institute_id: str) -> bool:
    if scope == "泸县人民医院" and institute_id == "机构号":
        return True
    check_saved_result_institute(scope, institute_id)
    return False


def _saved_job_material_owner(session, jobs, job_id, identity):
    from ..database.clinical_connection import ClinicalSourceConfigurationError
    from .clinical_sources import saved_snapshot
    from .material_job_lineage import resolve_material_job_id

    def lookup(key):
        return session.execute(select(
            jobs.c.id, jobs.c.created_by, jobs.c.parent_job_id, jobs.c.job_kind,
            jobs.c.child_job_ids_json, jobs.c.filters_json,
        ).where(jobs.c.id == key)).mappings().one_or_none()

    row = lookup(job_id)
    try:
        filters = json.loads(row["filters_json"]) if row else {}
        if not isinstance(filters, dict) or not any(
            isinstance(ref, dict) and tuple(ref.get(k) for k in _COORDINATES) == identity
            for ref in filters.get("record_refs", ())
        ):
            raise ValueError
        return saved_snapshot(filters), resolve_material_job_id(row, lookup)
    except (ValueError, TypeError, KeyError, ClinicalSourceConfigurationError):
        raise HTTPException(403, "缺少可核验的历史结果机构归属") from None


def require_selected_donghua_job(session, jobs, job_id, identity):
    from ..database import clinical_connection as clinical

    source, material_job = _saved_job_material_owner(session, jobs, job_id, identity)
    if source["id"] != "independent_cdm":
        raise HTTPException(403, "缺少可核验的历史结果机构归属")
    with clinical.selected(source):
        return require_donghua_frozen_result(material_job, identity, source["binding"])


def selected_history_material_is_available(session, jobs, job_id, identity, *, require_donghua_proof):
    """从原作业谱系读取冻结材料，缺失或不能核验时跳过该轮。"""
    from ..database import clinical_connection as clinical
    from . import case_material_snapshot as material

    try:
        if require_donghua_proof:
            return bool(require_selected_donghua_job(session, jobs, job_id, identity))
        source, material_job = _saved_job_material_owner(session, jobs, job_id, identity)
        with clinical.selected(source):
            snapshot = material.load(material_job, identity)
        schema = snapshot.get("schema") if snapshot else None
        return bool(isinstance(schema, str) and schema
                    and (source["id"] != "independent_cdm" or schema == "cdm"))
    except HTTPException as error:
        if error.status_code not in {403, 503}:
            raise
        return False
    except material.MaterialSnapshotError:
        return False


def require_donghua_frozen_result(job_id: str, identity: tuple, binding: str) -> dict:
    """返回已核验的同一份冻结材料，供历史文书直接读取。"""
    from . import case_material_snapshot as material
    from .cdm_publication_evidence import target_hash

    denied = HTTPException(403, "缺少可核验的历史结果机构归属")
    try:
        state = material.load(job_id, identity)
    except material.MaterialSnapshotError:
        raise denied from None
    if (not state or state.get("schema") != "cdm" or state.get("binding") != binding
            or state.get("identity") != list(identity) or identity[0] != "机构号"):
        raise denied
    automatic = state.get("automatic_material")
    publication = automatic.get("publication") if isinstance(automatic, dict) else None
    if not isinstance(publication, dict) or not isinstance(publication.get("rows"), dict):
        raise denied
    digest = target_hash(dict(zip(_COORDINATES, identity)))
    if publication.get("status") in {"metadata_permission_unconfirmed", "metadata_unavailable",
                                     "metadata_contract_unconfirmed"}:
        # 旧快照可能没有操作账本的列权限。仅对专属院区已绑定的基础表核对归属，
        # 当前投递回执只用于决定谁可查看；历史结果与正文始终取自原任务。
        if (binding == _DONGHUA_BINDING and publication["rows"] == {}
                and _verify_donghua_delivery_owner(state, identity, digest)):
            return state
        raise denied
    if publication.get("status") != "metadata_available":
        raise denied
    verified = False
    for table in _DONGHUA_TABLES:
        entries = publication["rows"].get(table, [])
        if not isinstance(entries, list):
            raise denied
        for entry in entries:
            if not isinstance(entry, dict):
                raise denied
            if entry.get("status") != "receipt_verified":
                continue
            receipt, operation = entry.get("receipt") or {}, entry.get("operation") or {}
            if (not isinstance(receipt, dict) or not isinstance(operation, dict)
                    or entry.get("target_key_hash") != digest or receipt.get("target_key_hash") != digest
                    or receipt.get("source_epoch") != _DONGHUA_EPOCH or operation.get("source_epoch") != _DONGHUA_EPOCH
                    or operation.get("interface_name") != "web." + table):
                raise denied
            verified = True
    if not verified:
        raise denied
    return state


def _verify_donghua_delivery_owner(state, identity, digest):
    from ..database import clinical_connection as clinical

    tables = state.get("tables")
    if not isinstance(tables, dict):
        return False
    interfaces = set()
    for table in _DONGHUA_TABLES:
        rows = tables.get(table, [])
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or tuple(row.get(k) for k in _COORDINATES) != identity
            for row in rows
        ):
            return False
        if rows:
            interfaces.add("web." + table)
    if not interfaces or clinical.source_binding() != _DONGHUA_BINDING:
        return False
    try:
        engine = clinical.get_engine()
        if engine is None:
            return False
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql("SET LOCAL statement_timeout=3000")
                records = conn.execute(text("""
                    SELECT r.interface_name, r.source_epoch, r.generation,
                           (c.source_epoch=r.source_epoch AND c.activation=r.activation
                            AND c.mapping_hash=r.mapping_hash) AS matches_contract
                    FROM sync_delivery.receipt r LEFT JOIN sync_delivery.contract c
                      ON c.interface_name=r.interface_name
                    WHERE r.target_key_hash=:digest
                      AND r.interface_name IN ('web.admission_record','web.discharge_record')
                    LIMIT 3
                """), {"digest": digest}).mappings().all()
    except (SQLAlchemyError, clinical.ClinicalSourceConfigurationError):
        raise HTTPException(503, "机构归属回执暂不可核验") from None
    seen = set()
    for record in records:
        interface = record["interface_name"]
        if (interface in seen or str(record["source_epoch"]) != _DONGHUA_EPOCH
                or record["matches_contract"] is not True or not record["generation"] or record["generation"] < 1):
            return False
        seen.add(interface)
    return bool(seen & interfaces)


def require_retry_record_institutes(actor_id: str, record_refs: object) -> None:
    """每次重试重新读取账号权限；旧任务创建者身份不等于当前机构授权。"""
    scope = saved_result_institute_scope(actor_id)
    if not isinstance(record_refs, list) or not record_refs:
        raise HTTPException(403, "重试任务缺少可信病历范围")
    for ref in record_refs:
        if not isinstance(ref, dict) or not all(isinstance(ref.get(key), str) and ref[key].strip()
                for key in ("institute_id", "patient_id", "visit_id")):
            raise HTTPException(403, "重试任务缺少可信病历范围")
        check_saved_result_institute(scope, ref["institute_id"])
