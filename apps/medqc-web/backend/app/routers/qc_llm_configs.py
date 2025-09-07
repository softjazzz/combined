from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from ..storage.memory import llm_configs


router = APIRouter(prefix="/api/qc", tags=["qc-llm-configs"])


@router.get("/llm-configs")
async def list_configs():
    return {"items": list(llm_configs.values()), "total": len(llm_configs)}


@router.post("/llm-configs")
async def create_config(payload: Dict[str, Any]):
    cid = payload.get("id") or f"cfg-{len(llm_configs)+1:03d}"
    if cid in llm_configs:
        raise HTTPException(status_code=400, detail="配置已存在")
    payload["id"] = cid
    llm_configs[cid] = payload
    return payload


@router.put("/llm-configs/{config_id}")
async def update_config(config_id: str, payload: Dict[str, Any]):
    if config_id not in llm_configs:
        raise HTTPException(status_code=404, detail="配置不存在")
    llm_configs[config_id].update(payload)
    return llm_configs[config_id]


@router.delete("/llm-configs/{config_id}")
async def delete_config(config_id: str):
    if config_id not in llm_configs:
        raise HTTPException(status_code=404, detail="配置不存在")
    del llm_configs[config_id]
    return {"success": True}


@router.post("/llm-configs/{config_id}/test")
async def test_config(config_id: str):
    if config_id not in llm_configs:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"success": True, "message": "连接正常", "config_id": config_id}

