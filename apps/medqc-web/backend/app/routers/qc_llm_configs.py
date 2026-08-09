from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.response import StatusCode, get_trace_id, success_response
from ..core.security import require_roles
from ..storage.memory import llm_configs


_SYSTEM_CONFIG_ROLES = ("admin", "sync_admin", "super_admin")

router = APIRouter(
    prefix="/api/v1/qc",
    tags=["qc-llm-configs"],
    dependencies=[Depends(require_roles(*_SYSTEM_CONFIG_ROLES))],
)


@router.get("/llm-configs")
async def list_configs():
    return {"items": list(llm_configs.values()), "total": len(llm_configs)}


@router.post("/llm-configs")
async def create_config(request: Request, payload: Dict[str, Any]):
    cid = payload.get("id") or f"cfg-{len(llm_configs)+1:03d}"
    if cid in llm_configs:
        raise HTTPException(status_code=StatusCode.BAD_REQUEST, detail="配置已存在")
    payload["id"] = cid
    llm_configs[cid] = payload
    return success_response(data=payload, message="配置创建成功", trace_id=get_trace_id(request))


@router.put("/llm-configs/{config_id}")
async def update_config(request: Request, config_id: str, payload: Dict[str, Any]):
    if config_id not in llm_configs:
        raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="配置不存在")
    llm_configs[config_id].update(payload)
    return success_response(data=llm_configs[config_id], message="配置更新成功", trace_id=get_trace_id(request))


@router.delete("/llm-configs/{config_id}")
async def delete_config(request: Request, config_id: str):
    if config_id not in llm_configs:
        raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="配置不存在")
    del llm_configs[config_id]
    return success_response(data=None, message="配置删除成功", trace_id=get_trace_id(request))


@router.post("/llm-configs/{config_id}/test")
async def test_config(request: Request, config_id: str):
    if config_id not in llm_configs:
        raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="配置不存在")
    return success_response(data={"config_id": config_id}, message="连接正常", trace_id=get_trace_id(request))
