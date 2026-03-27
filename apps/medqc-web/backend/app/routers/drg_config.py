from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.drg import config_service

router = APIRouter()


def _drg_router():
    from . import drg as drg_router

    return drg_router


class GrouperConfigPayload(BaseModel):
    region: str
    engine: str
    baseRate: float
    hospitalCoefficient: float
    regionCoefficient: float
    effectiveDate: str
    lowRateThreshold: int
    highRateThreshold: int
    enableCCMCC: bool = True
    enableAutoSuggestion: bool = True


class SaveConfigRequest(BaseModel):
    config: GrouperConfigPayload
    operator: str
    change_summary: str


class PublishConfigRequest(BaseModel):
    operator: str
    change_summary: str


class RollbackConfigRequest(BaseModel):
    version_id: str
    operator: str
    change_summary: str


class ConsistencySample(BaseModel):
    case_key: Optional[str] = None
    admission_id: Optional[str] = None
    hospital_group: Optional[str] = None
    insurance_group: Optional[str] = None


class ConsistencyCheckRequest(BaseModel):
    operator: str
    version_id: Optional[str] = None
    samples: List[ConsistencySample]


@router.get("/config/current")
async def get_grouper_config_current() -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    return {"success": True, "data": config_service.get_current_config(store)}


@router.put("/config")
async def save_grouper_config(payload: SaveConfigRequest) -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    saved = config_service.save_draft_config(
        store,
        config=payload.config.model_dump(),
        operator=payload.operator,
        change_summary=payload.change_summary,
    )
    return {"success": True, "data": saved, "message": "配置草稿已保存"}


@router.post("/config/publish")
async def publish_grouper_config(payload: PublishConfigRequest) -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    version = config_service.publish_config(
        store,
        operator=payload.operator,
        change_summary=payload.change_summary,
    )
    return {"success": True, "data": version, "message": "配置发布成功"}


@router.get("/config/versions")
async def list_grouper_config_versions(limit: int = Query(20, ge=1, le=200)) -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    return {"success": True, "data": config_service.list_versions(store, limit=limit)}


@router.get("/config/versions/{version_id}")
async def get_grouper_config_version_detail(version_id: str) -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    try:
        detail = config_service.get_version_detail(store, version_id=version_id)
    except config_service.DRGConfigVersionNotFoundError:
        raise HTTPException(status_code=404, detail="版本不存在")
    return {"success": True, "data": detail}


@router.post("/config/rollback")
async def rollback_grouper_config(payload: RollbackConfigRequest) -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    try:
        result = config_service.rollback_config(
            store,
            version_id=payload.version_id,
            operator=payload.operator,
            change_summary=payload.change_summary,
        )
    except config_service.DRGConfigVersionNotFoundError:
        raise HTTPException(status_code=404, detail="目标版本不存在")
    return {"success": True, "data": result, "message": "版本回滚成功"}


@router.get("/config/audit-logs")
async def list_grouper_config_audit_logs(limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    return {"success": True, "data": config_service.list_audit_logs(store, limit=limit)}


@router.post("/config/consistency-check")
async def run_grouper_consistency_check(payload: ConsistencyCheckRequest) -> Dict[str, Any]:
    store = _drg_router().get_drg_config_store()
    report = config_service.run_consistency_check(
        store,
        samples=[sample.model_dump() for sample in payload.samples],
        operator=payload.operator,
        version_id=payload.version_id,
    )
    return {"success": True, "data": report}

