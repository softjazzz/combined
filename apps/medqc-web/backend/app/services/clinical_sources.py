"""临床来源配置及任务冻结；业务连接和凭据所有者不变。"""

from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import os
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.engine import URL

from ..database import clinical_connection as clinical
from .data_pipeline_settings import PipelineError

NAMESPACE, KEY = "clinical", "sources_v1"
TASK_KEY = "clinical_source"
IDS = {"legacy_pg", "independent_cdm"}


class CDMProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(default="服务器CDM", min_length=1, max_length=100)
    enabled: bool = False
    host: str = Field(default="127.0.0.1", min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.:-]+$")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(default="medqc_sync_cdm", min_length=1, max_length=63, pattern=r"^[A-Za-z0-9_\-]+$")
    username: str = Field(default="", max_length=63, pattern=r"^[A-Za-z0-9_\-]*$")


class SourceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(default=0, ge=0)
    default_source: Literal["legacy_pg", "independent_cdm"] = "legacy_pg"
    legacy_name: str = Field(default="原有数据源", min_length=1, max_length=100)
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
    return {"id": "legacy_pg", "version": 0, "name": "原有数据源", "binding": ""}


def snapshot(settings: SourceSettings, source_id: str, *, allow_disabled=False) -> dict:
    if source_id not in IDS:
        raise PipelineError("unknown_clinical_source", 422)
    if source_id == "legacy_pg":
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
    identity = [profile.host, profile.port, profile.database, profile.username, "cdm"]
    binding = "cdm-read-v1:" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    return {"id": source_id, "version": settings.version, "name": profile.name, "binding": binding, "url": url}


def save(session, proposed: SourceSettings, actor: str) -> SourceSettings:
    current, raw = load(session)
    if proposed.version != current.version:
        raise PipelineError("clinical_source_configuration_changed", 409)
    if not proposed.legacy_enabled and not proposed.cdm.enabled:
        raise PipelineError("at_least_one_clinical_source_required", 422)
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
            return SourceSettings()
        raise PipelineError("clinical_source_configuration_unavailable")
    try:
        with SessionLocal() as session:
            return load(session)[0]
    except PipelineError:
        raise
    except Exception:
        raise PipelineError("clinical_source_configuration_unavailable") from None


def prepare_request(request: Request) -> None:
    paths = ("/api/medical-records", "/api/v1/medical-records", "/api/v1/records", "/api/v1/emr", "/api/v1/qc/sichuan/workspace")
    # 样本集和其它业务API仍属业务库，不让全局默认改变1026或管理操作。
    path = request.url.path
    job_detail = "/workspace/batch-jobs/" in path
    if job_detail or not path.startswith(paths):
        request.state.clinical_source = legacy_snapshot()
        return
    # 停用旧普通病例入口不能让已登记的1026副本/历史展示不可读。
    from .validation_material_source import is_material_copy, material_source_schema
    identity = {key: request.query_params.get(key) or request.path_params.get(key) or ""
                for key in ("institute_id", "patient_id", "visit_id")}
    if request.method == "GET" and is_material_copy(identity["patient_id"], identity["visit_id"]):
        try:
            if not all(identity.values()):
                raise ValueError
            material_source_schema(default_schema="cdm", **identity)
        except Exception:
            raise HTTPException(422, "clinical_material_identity_unavailable") from None
        request.state.clinical_source = legacy_snapshot()
        return
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
            # 无显式来源的旧详情链接保留原库；新病历池先解析默认源再携带显式来源。
            default = settings.default_source if path.endswith("/workstation") or request.method == "POST" else "legacy_pg"
            request.state.clinical_source = snapshot(settings, header or query or default)
        if request.state.clinical_source["id"] == "independent_cdm" and "medical-records/" in path:
            suffix = path.split("medical-records/", 1)[1]
            supported = ("workstation", "list", "departments", "stats", "frontpage/", "frontpage-by-mr/",
                         "frontpage-sheet/", "diagnoses/", "surgeries/", "cost/", "record-content/", "documents/")
            if request.method != "GET" or not suffix.startswith(supported):
                raise PipelineError("clinical_source_operation_not_supported", 422)
        if request.state.clinical_source["id"] == "independent_cdm" and path.startswith("/api/v1/records"):
            raise PipelineError("clinical_source_legacy_record_api_not_supported", 422)

    except PipelineError as error:
        raise HTTPException(error.status, error.code) from None
    except clinical.ClinicalSourceConfigurationError:
        raise HTTPException(503, "clinical_source_configuration_invalid") from None


async def bind_request(request: Request):
    with clinical.selected(getattr(request.state, "clinical_source", legacy_snapshot())):
        yield


def source_for_saved_job(request: Request, job_id: str) -> dict:
    """历史文书读取只接受已保存任务的服务端来源，不能由URL提交端点或凭据。"""
    from ..database.connection import SessionLocal
    if SessionLocal is None or len(job_id) > 128:
        raise PipelineError("clinical_source_job_unavailable", 503)
    try:
        with SessionLocal() as session:
            row = session.execute(text("SELECT created_by,filters_json FROM qc.custom_qc_batch_jobs WHERE id=:id"), {"id": job_id}).first()
        if row is None:
            raise PipelineError("clinical_source_job_not_found", 404)
        actor = getattr(request.state, "current_user", {})
        if row[0] != actor.get("id") and not set(actor.get("roles") or []) & {"admin", "sync_admin", "super_admin", "qc_manager", "qc_staff", "doctor"}:
            raise PipelineError("clinical_source_job_forbidden", 403)
        filters = json.loads(row[1] or "{}")
        selection = saved_snapshot(filters)
        if TASK_KEY in filters:
            identity = tuple(request.query_params.get(k) or request.path_params.get(k) or "" for k in ("institute_id", "patient_id", "visit_id"))
            refs = filters.get("record_refs") or []
            if not all(identity) or identity not in {
                tuple(str(ref.get(k) or "") for k in ("institute_id", "patient_id", "visit_id")) for ref in refs if isinstance(ref, dict)
            }:
                raise PipelineError("clinical_source_job_case_mismatch", 403)
        return selection
    except PipelineError:
        raise
    except Exception:
        raise PipelineError("clinical_source_job_unavailable", 503) from None


def freeze(filters: dict) -> None:
    source = clinical.current_selection() or legacy_snapshot()
    refs = filters.get("record_refs") or []
    refs = [ref for ref in refs if isinstance(ref, dict)] if isinstance(refs, list) else []
    if filters.get("sample_pool_id") or (refs and all(str(ref.get("patient_id", "")).startswith("pdfp_") and str(ref.get("visit_id", "")).startswith("pdfv_") for ref in refs)):
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
        expected = "cdm-read-v1:" + hashlib.sha256(json.dumps([parsed.host, parsed.port or 5432, parsed.database, parsed.username, "cdm"]).encode()).hexdigest()
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
            return await function(job_id, workspace=workspace, **kwargs)
    return run


@contextmanager
def request_selection(request: Request):
    with clinical.selected(getattr(request.state, "clinical_source", legacy_snapshot())):
        yield
