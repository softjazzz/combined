"""临床读取来源设置；同步链路与读取来源分别配置。"""
from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.audit import audit_event
from ..core.response import success_response
from ..core.security import get_current_user
from ..database import clinical_connection
from ..database.connection import SessionLocal
from ..services import clinical_sources as sources
from ..services.data_pipeline_settings import PipelineError
from .data_pipelines import require_pipeline_admin

router = APIRouter(prefix="/api/v1/clinical-sources", tags=["clinical-sources"])


@router.get("/options")
def options(_user: dict = Depends(get_current_user)):
    try:
        value = sources.configuration()
        return success_response(data={"default_source": value.default_source, "sources": [
            {"id": "legacy_pg", "name": value.legacy_name, "enabled": value.legacy_enabled},
            {"id": "independent_cdm", "name": value.cdm.name, "enabled": value.cdm.enabled},
        ]})
    except PipelineError as error:
        raise HTTPException(error.status, error.code) from None


@router.get("")
def configuration(_actor: dict = Depends(require_pipeline_admin)):
    try:
        return success_response(data=sources.configuration().model_dump())
    except PipelineError as error:
        raise HTTPException(error.status, error.code) from None


@router.put("")
def configure(value: sources.SourceSettings, request: Request, actor: dict = Depends(require_pipeline_admin)):
    try:
        if SessionLocal is None:
            raise PipelineError("clinical_source_configuration_unavailable")
        with SessionLocal() as session:
            saved = sources.save(session, value, actor["id"])
    except PipelineError as error:
        raise HTTPException(error.status, error.code) from None
    except Exception:
        raise HTTPException(503, "clinical_source_configuration_unavailable") from None
    audit_event(request, action="clinical.sources.configure", resource="clinical-sources", outcome="success",
                details={"version": saved.version, "default_source": saved.default_source})
    return success_response(data=saved.model_dump())


@router.post("/check")
def check(value: sources.SourceSettings, _actor: dict = Depends(require_pipeline_admin)):
    # 用户明确点击才连接；不保存设置，不读取患者正文，不做DDL。
    try:
        selection = sources.snapshot(value, "independent_cdm", allow_disabled=True)
        with clinical_connection.selected(selection):
            engine = clinical_connection.get_engine()
            with engine.connect() as connection:
                from ..services.clinical_source_contract import inspect_source
                report = inspect_source(connection)
        # 预检报告逐项列出缺表、缺列、权限、空表；不替代发布就绪门禁。
        return success_response(data={"connected": True, **report})
    except PipelineError as error:
        raise HTTPException(error.status, error.code) from None
    except Exception:
        raise HTTPException(503, "clinical_source_connection_unavailable") from None
