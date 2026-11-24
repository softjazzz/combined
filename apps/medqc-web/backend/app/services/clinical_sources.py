"""临床来源配置及任务冻结；业务连接和凭据所有者不变。"""

from contextlib import contextmanager
from functools import wraps
import json
import os
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.engine import URL

from ..core.clinical_defaults import (
    CDM_PROFILE_NAME, INDEPENDENT_CDM, LEGACY_PG, LEGACY_SOURCE_NAME, get_clinical_defaults,
)
from ..database import clinical_connection as clinical
from .data_pipeline_settings import PipelineError
from .clinical_source_policy import fixed_cdm

NAMESPACE, KEY = "clinical", "sources_v1"
TASK_KEY = "clinical_source"
IDS = {LEGACY_PG, INDEPENDENT_CDM}
_FIXED_SETTINGS = {"default_source": INDEPENDENT_CDM, "legacy_enabled": False}
WORKSPACE_METADATA_GET_PATHS = frozenset({
    "/api/v1/qc/sichuan/workspace/rule-sets",
    "/api/v1/qc/sichuan/workspace/batch-jobs",
    # 仅按已保存任务与脱敏记录引用读取反馈；/all 会补查当前病例，不在此列。
    "/api/v1/qc/sichuan/workspace/result-feedback-demo",
})


class CDMProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(
        default_factory=lambda: get_clinical_defaults().cdm_profile_name,
        min_length=1, max_length=100, validate_default=True, json_schema_extra={"default": CDM_PROFILE_NAME},
    )
    enabled: bool = False
    host: str = Field(default="127.0.0.1", min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.:-]+$")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(default="medqc_sync_cdm", min_length=1, max_length=63, pattern=r"^[A-Za-z0-9_\-]+$")
    username: str = Field(default="", max_length=63, pattern=r"^[A-Za-z0-9_\-]*$")


class SourceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(default=0, ge=0)
    default_source: Literal["legacy_pg", "independent_cdm"] = Field(
        default_factory=lambda: get_clinical_defaults().compat_source, validate_default=True,
        json_schema_extra={"default": LEGACY_PG},
    )
    legacy_name: str = Field(default=LEGACY_SOURCE_NAME, min_length=1, max_length=100)
    legacy_enabled: bool = True
    cdm: CDMProfile = Field(default_factory=CDMProfile)


def load(session) -> tuple[SourceSettings, str | None]:
    row = session.execute(text("SELECT payload_json FROM qc.sync_config_registry WHERE namespace=:n AND config_key=:k"), {"n": NAMESPACE, "k": KEY}).first()
    if row is None:
        return SourceSettings(), None
    try:
        return SourceSettings.model_validate(json.loads(row[0])), row[0]
    except (ValueError, TypeError):
        raise PipelineError("clinical_source_configuration_invalid") from None


def legacy_snapshot() -> dict:
    return {"id": LEGACY_PG, "version": 0, "name": LEGACY_SOURCE_NAME, "binding": ""}


def snapshot(settings: SourceSettings, source_id: str, *, allow_disabled=False) -> dict:
    if source_id not in IDS:
        raise PipelineError("unknown_clinical_source", 422)
    if source_id == "legacy_pg":
        if fixed_cdm():
            raise PipelineError("ordinary_source_fixed_donghua_cdm", 409)
        if not settings.legacy_enabled and not allow_disabled:
            raise PipelineError("clinical_source_disabled", 409)
        return {**legacy_snapshot(), "version": settings.version, "name": settings.legacy_name}
    profile = settings.cdm
    if not profile.enabled and not allow_disabled:
        raise PipelineError("clinical_source_disabled", 409)
    if not profile.username:
        raise PipelineError("clinical_source_username_required", 422)
    # 凭据只通过部署提供的专用passfile，不存入配置或任务，也不使用同步服务密钥。
    passfile = os.getenv("CDM_PGPASSFILE", "").strip()
    if not passfile:
        raise PipelineError("clinical_source_credentials_unavailable", 503)
    url = URL.create("postgresql+psycopg2", username=profile.username, host=profile.host, port=profile.port, database=profile.database).render_as_string(hide_password=True)
    clinical._engine(url, passfile)  # 仅静态构造；不checkout连接。
    binding = clinical.build_source_binding(profile.host, profile.port, profile.database, profile.username)
    return {"id": source_id, "version": settings.version, "name": profile.name, "binding": binding, "url": url}


def save(session, proposed: SourceSettings, actor: str) -> SourceSettings:
    current, raw = load(session)
    if fixed_cdm():
        proposed = proposed.model_copy(update=_FIXED_SETTINGS)
    if proposed.version != current.version:
        raise PipelineError("clinical_source_configuration_changed", 409)
    if not fixed_cdm() and not proposed.legacy_enabled and not proposed.cdm.enabled:
        raise PipelineError("at_least_one_clinical_source_required", 422)
    if not fixed_cdm():
        snapshot(proposed, proposed.default_source)
    if proposed.cdm.enabled:
        snapshot(proposed, "independent_cdm")
    saved = proposed.model_copy(update={"version": current.version + 1})
    params = dict(n=NAMESPACE, k=KEY, value=saved.model_dump_json(), actor=actor)
    if raw is None:
        query = "INSERT INTO qc.sync_config_registry(namespace,config_key,payload_json,updated_by,source,change_reason,updated_at) VALUES(:n,:k,:value,:actor,'clinical_sources','configure clinical sources',CURRENT_TIMESTAMP) ON CONFLICT(namespace,config_key) DO NOTHING"
    else:
        params["old"] = raw
        query = "UPDATE qc.sync_config_registry SET payload_json=:value,updated_by=:actor,updated_at=CURRENT_TIMESTAMP WHERE namespace=:n AND config_key=:k AND payload_json=:old"
    if session.execute(text(query), params).rowcount != 1:
        raise PipelineError("clinical_source_configuration_changed", 409)
    session.commit()
    return saved


def configuration() -> SourceSettings:
    from ..database.connection import SessionLocal
    if SessionLocal is None:
        if os.getenv("ENV", "development").lower() not in {"prod", "production"}:
            return SourceSettings(**_FIXED_SETTINGS) if fixed_cdm() else SourceSettings()
        raise PipelineError("clinical_source_configuration_unavailable")
    try:
        with SessionLocal() as session:
            value = load(session)[0]
            return value.model_copy(update=_FIXED_SETTINGS) if fixed_cdm() else value
    except PipelineError:
        raise
    except Exception:
        raise PipelineError("clinical_source_configuration_unavailable") from None


def _registered_local_case(ref: dict) -> bool:
    from .validation_material_source import is_material_copy, material_source_schema
    keys = ("institute_id", "patient_id", "visit_id")
    if not all(ref.get(key) for key in keys):
        raise PipelineError("clinical_material_identity_incomplete", 422)
    identity = {key: str(ref[key]) for key in keys}
    if is_material_copy(identity["patient_id"], identity["visit_id"]):
        material_source_schema(default_schema="cdm", **identity)
        return True
    if identity["institute_id"] != "CUSTOMER_TEST":
        return False
    from ..database.connection import SessionLocal, DB_SCHEMA_MODE
    if SessionLocal is None:
        raise PipelineError("clinical_material_registration_unavailable")
    schema = "qc" if str(DB_SCHEMA_MODE).lower()=="split" else "public"
    with SessionLocal() as session:
        found = session.execute(text(f"SELECT 1 FROM {schema}.manual_problem_sample_pool_items WHERE pool_id=:pool AND matched_institute_id=:institute_id AND matched_patient_id=:patient_id AND matched_visit_id=:visit_id LIMIT 1"), {**identity, "pool":"customer-created-test-records-v1"}).first()
    if found is None:
        raise PipelineError("clinical_material_identity_not_registered", 422)
    return True


def _local_material_filters(filters: dict) -> bool:
    refs = filters.get("record_refs")
    if not isinstance(refs,list) or not refs:
        return False
    local = [_registered_local_case(ref) for ref in refs if isinstance(ref,dict)]
    if len(local)!=len(refs) or any(local) and not all(local):
        raise PipelineError("clinical_material_mixed_sources",422)
    return bool(local) and all(local)


def ordinary_snapshot():
    return snapshot(configuration(), INDEPENDENT_CDM)


async def prepare_task_material_request(request: Request) -> None:
    """认证后仅为明确登记的PDF任务绑定来源，不改变普通病例默认源。"""
    if request.method != "POST" or request.url.path != "/api/v1/qc/sichuan/workspace/batch-jobs":
        return
    try:
        payload = await request.json()
    except ValueError:
        return  # 请求体合同仍交由路由校验。
    refs = payload.get("record_refs") if isinstance(payload, dict) else None
    from .validation_material_source import is_material_copy
    if not isinstance(refs, list) or not any(
        isinstance(ref, dict) and is_material_copy(ref.get("patient_id", ""), ref.get("visit_id", "")) for ref in refs
    ):
        return
    try:
        if not refs or any(not isinstance(ref, dict) or not all(isinstance(ref.get(k), str) and ref[k].strip()
                for k in ("institute_id", "patient_id", "visit_id"))
                or not is_material_copy(ref["patient_id"], ref["visit_id"]) for ref in refs):
            raise ValueError("invalid_or_mixed")
        from starlette.concurrency import run_in_threadpool
        if not await run_in_threadpool(_local_material_filters, {"record_refs": refs}):
            raise ValueError("unregistered")
    except (ValueError, PipelineError):
        raise HTTPException(422, "clinical_material_identity_not_registered") from None
    if any(value not in (None, "legacy_pg") for value in (
        request.headers.get("x-clinical-source"), request.query_params.get("source_id")
    )):
        raise HTTPException(422, "clinical_source_selection_conflict")
    request.state.registered_pdf_task_source = legacy_snapshot()


def prepare_request(request: Request) -> None:
    paths = (
        "/api/medical-records",
        "/api/v1/medical-records",
        "/api/v1/records",
        "/api/v1/emr",
        "/api/v1/qc/sichuan/workspace",
        "/api/v1/workstation",
    )
    # 样本集和其它业务API仍属业务库，不让全局默认改变1026或管理操作。
    path = request.url.path
    if request.method == "POST" and path == "/api/v1/qc/sichuan/workspace/batch-jobs" and getattr(request.state, "registered_pdf_task_source", None):
        request.state.clinical_source = request.state.registered_pdf_task_source
        return
    if request.method == "GET" and path in WORKSPACE_METADATA_GET_PATHS:
        header = request.headers.get("x-clinical-source")
        query = request.query_params.get("source_id")
        if header and query and header != query:
            raise HTTPException(422, "clinical_source_selection_conflict")
        if (header or query) and (header or query) not in IDS:
            raise HTTPException(422, "unknown_clinical_source")
        # 仅业务目录、账号历史列表与已保存反馈，不以旧库替代停用CDM。
        request.state.clinical_source = legacy_snapshot()
        return
    job_detail = "/workspace/batch-jobs/" in path
    if job_detail or not path.startswith(paths):
        request.state.clinical_source = legacy_snapshot()
        return
    # 停用旧普通病例入口不能让已登记的1026副本/历史展示不可读。
    from .validation_material_source import is_material_copy, material_source_schema
    identity = {key: request.query_params.get(key) or request.path_params.get(key) or ""
                for key in ("institute_id", "patient_id", "visit_id")}
    # 最新结果接口的 record_id 明确定义为就诊号，仅在这一条路由归一化。
    record_id = request.path_params.get("record_id")
    if (request.method == "GET" and record_id
            and path == f"/api/v1/qc/sichuan/workspace/records/{record_id}/latest-result"):
        if identity["visit_id"] and identity["visit_id"] != record_id:
            raise HTTPException(422, "clinical_material_identity_unavailable")
        identity["visit_id"] = record_id
    if request.method == "GET" and is_material_copy(identity["patient_id"], identity["visit_id"]):
        job_id = request.query_params.get("job_id") if path.startswith("/api/v1/emr/") else None
        if not all(identity.values()):
            raise HTTPException(422, "clinical_material_identity_unavailable")
        if not job_id:
            try:
                material_source_schema(default_schema="cdm", **identity)
            except Exception:
                raise HTTPException(422, "clinical_material_identity_unavailable") from None
        if job_id:
            selection = source_for_saved_job(request, job_id)
            if selection["id"] != "legacy_pg":
                raise HTTPException(409, "clinical_material_job_source_mismatch")
            # 历史原文必须来自该任务材料；缺失时由 bind_request 明确拒绝，
            # 不能把当前登记副本冒充历史。已保存结果仍可只读显示缺失标记。
        request.state.clinical_source = legacy_snapshot()
        return
    if fixed_cdm() and request.method=="GET" and identity["institute_id"]=="CUSTOMER_TEST" and not request.query_params.get("job_id"):
        try:
            if _registered_local_case(identity):
                request.state.clinical_source=legacy_snapshot()
                return
        except (PipelineError,ValueError):
            raise HTTPException(422,"clinical_material_identity_not_registered") from None
    try:
        header = request.headers.get("x-clinical-source")
        query = request.query_params.get("source_id")
        if header and query and header != query:
            raise PipelineError("clinical_source_selection_conflict", 422)
        job_id = request.query_params.get("job_id") if path.startswith("/api/v1/emr/") else None
        if job_id:
            selection = source_for_saved_job(request, job_id)
            if (header or query) and (header or query) != selection["id"]:
                raise PipelineError("clinical_source_selection_conflict", 409)
            request.state.clinical_source = selection
        else:
            settings = configuration()
            # 单源部署不允许旧链接切回原库；兼容模式仅供保留原部署与隔离回归。
            if fixed_cdm():
                if (header or query) not in (None, INDEPENDENT_CDM):
                    raise PipelineError("ordinary_source_fixed_donghua_cdm",409)
                if (
                    path.startswith("/api/v1/workstation")
                    and not (header or query)
                    and not settings.cdm.enabled
                ):
                    request.state.clinical_source = legacy_snapshot()
                    return
                default = INDEPENDENT_CDM
            else:
                default = (
                    settings.default_source
                    if path.endswith("/workstation")
                    or path.startswith("/api/v1/workstation")
                    or request.method == "POST"
                    else LEGACY_PG
                )
            request.state.clinical_source = snapshot(settings, header or query or default)
        if request.state.clinical_source["id"] == "independent_cdm" and "medical-records/" in path:
            suffix = path.split("medical-records/", 1)[1]
            supported = ("workstation", "list", "departments", "stats", "frontpage/", "frontpage-by-mr/",
                         "frontpage-sheet/", "diagnoses/", "surgeries/", "cost/", "record-content/", "documents/")
            workstation_summary = path == "/api/medical-records/workstation/qc-summary" and request.method == "POST"
            if not workstation_summary and (request.method != "GET" or not suffix.startswith(supported)):
                raise PipelineError("clinical_source_operation_not_supported", 422)
        if request.state.clinical_source["id"] == "independent_cdm" and path.startswith("/api/v1/records"):
            raise PipelineError("clinical_source_legacy_record_api_not_supported", 422)

    except PipelineError as error:
        raise HTTPException(error.status, error.code) from None
    except clinical.ClinicalSourceConfigurationError:
        raise HTTPException(503, "clinical_source_configuration_invalid") from None


async def bind_request(request: Request):
    from . import case_material_snapshot as materials
    with clinical.selected(getattr(request.state, "clinical_source", legacy_snapshot())):
        frozen = None
        root_job = getattr(request.state, "material_root_job_id", "")
        if root_job:
            identity = tuple(request.query_params.get(key) or request.path_params.get(key) or "" for key in ("institute_id", "patient_id", "visit_id"))
            try:
                frozen = getattr(request.state, "verified_history_material", None)
                if frozen is None:
                    frozen = materials.load(root_job, identity)
                if frozen is None:
                    raise HTTPException(409, "historical_material_snapshot_not_retained")
                if request.query_params.get("source_view") == "current":
                    raise HTTPException(409, "historical_and_current_material_views_conflict")
            except materials.MaterialSnapshotError:
                raise HTTPException(409, "historical_material_snapshot_unavailable") from None
        with materials.activate(frozen):
            yield


def _saved_history_needs_source_proof(session, actor_id: str, identity: tuple[str, str, str], selection: dict) -> bool:
    """先核对持久账号；本院质控管理员的占位机构还须核验本任务冻结来源。"""
    from .defect_rectification_service import _person, RectificationError
    from .saved_result_access import check_saved_result_institute, scope_needs_donghua_result_proof

    try:
        person = _person(session, actor_id)
    except RectificationError:
        raise HTTPException(403, "账号或机构权限无效") from None
    except Exception:
        raise HTTPException(503, "账号机构权限来源暂不可用") from None
    roles = person["roles"]
    if roles & {"admin", "sync_admin", "super_admin"}:
        return False
    institute_id = person["institute_id"]
    if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
        raise HTTPException(403, "账号缺少可信机构范围")
    if "qc_manager" in roles and selection["id"] == "independent_cdm":
        return scope_needs_donghua_result_proof(institute_id, identity[0])
    check_saved_result_institute(institute_id, identity[0])
    if roles & {"qc_manager", "qc_staff"}:
        return False
    if "doctor" in roles:
        from ..database.connection import SessionLocal
        from .doctor_case_scope import resolve_doctor_case_scope

        # prepare_request 先于外层医生门禁；按已保存来源执行同一个个人范围owner。
        with clinical.selected(selection):
            scope = resolve_doctor_case_scope(actor_id, session_factory=SessionLocal)
        if scope is not None:
            scope.require_case(*identity)
            return False
    raise HTTPException(403, "无权读取该任务病历材料")


def source_for_saved_job(request: Request, job_id: str) -> dict:
    """历史文书读取只接受已保存任务的服务端来源，不能由URL提交端点或凭据。"""
    from ..database.connection import SessionLocal
    if SessionLocal is None or len(job_id) > 128:
        raise PipelineError("clinical_source_job_unavailable", 503)
    try:
        with SessionLocal() as session:
            def lookup(saved_job_id):
                return session.execute(text(
                    "SELECT id,created_by,filters_json,parent_job_id,job_kind,child_job_ids_json "
                    "FROM qc.custom_qc_batch_jobs WHERE id=:id"
                ), {"id": saved_job_id}).mappings().first()
            row = lookup(job_id)
            if row is None:
                raise PipelineError("clinical_source_job_not_found", 404)
            actor = getattr(request.state, "current_user", {})
            filters = json.loads(row["filters_json"] or "{}")
            selection = saved_snapshot(filters)
            identity = tuple(request.query_params.get(k) or request.path_params.get(k) or "" for k in ("institute_id", "patient_id", "visit_id"))
            refs = filters.get("record_refs")
            # 无来源标记的旧任务也须有可信保存引用，不能借创建者身份读取任意材料。
            if not all(identity) or not isinstance(refs, list) or identity not in {
                tuple(str(ref.get(k) or "") for k in ("institute_id", "patient_id", "visit_id")) for ref in refs if isinstance(ref, dict)
            }:
                raise PipelineError("clinical_source_job_case_mismatch", 403)
            needs_proof = _saved_history_needs_source_proof(session, str(actor.get("id") or ""), identity, selection)
            from .material_job_lineage import resolve_material_job_id
            try:
                material_job_id = resolve_material_job_id(row, lookup)
            except ValueError:
                raise PipelineError("clinical_source_job_lineage_invalid", 409) from None
        if needs_proof:
            if request.method != "GET" or request.url.path not in {
                f"/api/v1/emr/{identity[2]}/documents", f"/api/v1/emr/{identity[2]}/render",
            }:
                raise HTTPException(403, "无权读取该任务病历材料")
            from .saved_result_access import require_donghua_frozen_result
            with clinical.selected(selection):
                request.state.verified_history_material = require_donghua_frozen_result(
                    material_job_id, identity, selection["binding"]
                )
        request.state.material_root_job_id = material_job_id
        return selection
    except PipelineError:
        raise
    except HTTPException:
        raise
    except Exception:
        raise PipelineError("clinical_source_job_unavailable", 503) from None


def freeze(filters: dict) -> None:
    if fixed_cdm():
        local_material = _local_material_filters(filters)
        source = legacy_snapshot() if local_material else (
            clinical.current_selection() or ordinary_snapshot())
        if source["id"]=="legacy_pg" and not local_material:
            source=ordinary_snapshot()
    else:
        source = clinical.current_selection() or legacy_snapshot()
    refs = filters.get("record_refs") or []
    refs = [ref for ref in refs if isinstance(ref, dict)] if isinstance(refs, list) else []
    if not fixed_cdm() and (filters.get("sample_pool_id") or (refs and all(str(ref.get("patient_id", "")).startswith("pdfp_") and str(ref.get("visit_id", "")).startswith("pdfv_") for ref in refs))):
        source = legacy_snapshot()
    existing = filters.get(TASK_KEY)
    if existing is not None and existing != source:
        raise ValueError("clinical_source_task_override_forbidden")
    filters[TASK_KEY] = dict(source)


def saved_snapshot(filters: dict) -> dict:
    value = filters.get(TASK_KEY)
    if value is None:
        return legacy_snapshot()  # 老任务固定旧源，绝不按当前默认重新解释。
    if not isinstance(value, dict) or value.get("id") not in IDS:
        raise ValueError("invalid_saved_clinical_source")
    if value["id"] == "legacy_pg" and value.get("binding") != "":
        raise ValueError("invalid_saved_clinical_source")
    if value["id"] == "independent_cdm":
        parsed = clinical._url(value.get("url", ""))
        expected = clinical.build_source_binding(parsed.host, parsed.port, parsed.database, parsed.username)
        if parsed.password or value.get("binding") != expected:
            raise ValueError("invalid_saved_clinical_source")
    return dict(value)


def job_matches(filters: dict, patient_id: str = "", visit_id: str = "") -> bool:
    from .validation_material_source import is_material_copy
    active = clinical.current_selection()
    if active is None:
        return True  # 无请求上下文的兼容/维护工具保持既有API合同。
    binding = "" if is_material_copy(patient_id, visit_id) else active["binding"]
    return saved_snapshot(filters)["binding"] == binding


def bound_job(function):
    @wraps(function)
    async def run(job_id, *, workspace, **kwargs):
        job = workspace.get_batch_job_for_processing(job_id=job_id)
        try:
            source = saved_snapshot((job or {}).get("filters") or {})
        except (ValueError, clinical.ClinicalSourceConfigurationError):
            # 只终结读取时仍排队的同一份快照，不改运行尝试或已有结果。
            raw = (job or {}).get("_claim_filters_json")
            if raw is not None and job.get("status") == "queued":
                workspace.fail_batch_job(job_id=job_id, error_message="clinical_source_snapshot_invalid",
                    queued_only=True, expected_queued_filters_json=raw)
            return None
        with clinical.selected(source):
            if fixed_cdm() and source["id"] == "legacy_pg":
                from .case_material_capture import pdf_retry_materials
                from .case_material_snapshot import MaterialSnapshotError
                try:
                    retry_materials = pdf_retry_materials(job or {}, lambda source_id: workspace.get_batch_job_for_processing(job_id=source_id))
                except MaterialSnapshotError as error:
                    # worker尚未认领；只终结同一排队快照，迟到错误不得覆盖新尝试或终态。
                    from .material_admission import safe_material_failure
                    failure = safe_material_failure(str(error))
                    raw = (job or {}).get("_claim_filters_json")
                    if raw is not None and job.get("status") == "queued":
                        workspace.fail_batch_job(
                            job_id=job_id, error_message=failure["code"], queued_only=True,
                            expected_queued_filters_json=raw,
                            execution_error={"reason_code": failure["code"], "retryable": False},
                        )
                    return None
                if retry_materials is None and not _local_material_filters((job or {}).get("filters") or {}):
                    # 历史普通旧源任务保持原状；不自动执行、不改绑或改写其状态。
                    return None
            return await function(job_id, workspace=workspace, **kwargs)
    return run


@contextmanager
def request_selection(request: Request):
    source=getattr(request.state,"clinical_source",None)
    if source is None:
        source=ordinary_snapshot() if fixed_cdm() else legacy_snapshot()
    with clinical.selected(source):
        yield
