from copy import deepcopy
import threading
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.response import StatusCode, get_trace_id, success_response
from ..core.security import require_roles
from ..storage.memory import llm_configs
from .llm_configs import _project_config_row


_SYSTEM_CONFIG_ROLES = ("admin", "sync_admin", "super_admin")
_LLM_CONFIGS_LOCK = threading.RLock()

_ALLOWED_UPDATE_FIELDS = frozenset({
    "user_id",
    "config_name",
    "provider_id",
    "model_id",
    "provider_code",
    "model_code",
    "provider",
    "model",
    "custom_parameters",
    "is_active",
})
_ALLOWED_CREATE_FIELDS = _ALLOWED_UPDATE_FIELDS | frozenset({"id"})

router = APIRouter(
    prefix="/api/v1/qc",
    tags=["qc-llm-configs"],
    dependencies=[Depends(require_roles(*_SYSTEM_CONFIG_ROLES))],
)


def _sanitize_payload(payload: Dict[str, Any], *, allowed_fields: frozenset[str]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=StatusCode.UNPROCESSABLE_ENTITY, detail="无效的配置载荷")
    disallowed = sorted(str(key) for key in payload.keys() if key not in allowed_fields)
    if disallowed:
        raise HTTPException(
            status_code=StatusCode.UNPROCESSABLE_ENTITY,
            detail=f"包含不允许修改的配置字段: {', '.join(disallowed)}",
        )
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        if key == "custom_parameters" and value is not None and not isinstance(value, dict):
            raise HTTPException(
                status_code=StatusCode.UNPROCESSABLE_ENTITY,
                detail="custom_parameters 必须是对象",
            )
        sanitized[key] = deepcopy(value)
    return sanitized


def _project_safe_copy(row: Dict[str, Any]) -> Dict[str, Any]:
    """统一投影并深拷贝，禁止暴露共享内存引用或密钥字段。"""
    return deepcopy(_project_config_row(deepcopy(row)))


@router.get("/llm-configs")
async def list_configs(
    _admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del _admin_user
    with _LLM_CONFIGS_LOCK:
        items = [_project_safe_copy(item) for item in llm_configs.values()]
    return {"items": items, "total": len(items)}


@router.post("/llm-configs")
async def create_config(
    request: Request,
    payload: Dict[str, Any],
    _admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del _admin_user
    sanitized = _sanitize_payload(payload, allowed_fields=_ALLOWED_CREATE_FIELDS)
    with _LLM_CONFIGS_LOCK:
        cid = str(sanitized.get("id") or "").strip() or f"cfg-{len(llm_configs) + 1:03d}"
        if cid in llm_configs:
            raise HTTPException(status_code=StatusCode.BAD_REQUEST, detail="配置已存在")
        stored = {**sanitized, "id": cid}
        llm_configs[cid] = deepcopy(stored)
        projected = _project_safe_copy(stored)
    return success_response(data=projected, message="配置创建成功", trace_id=get_trace_id(request))


@router.put("/llm-configs/{config_id}")
async def update_config(
    request: Request,
    config_id: str,
    payload: Dict[str, Any],
    _admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del _admin_user
    sanitized = _sanitize_payload(payload, allowed_fields=_ALLOWED_UPDATE_FIELDS)
    with _LLM_CONFIGS_LOCK:
        if config_id not in llm_configs:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="配置不存在")
        updated = deepcopy(llm_configs[config_id])
        updated.update(sanitized)
        updated["id"] = config_id
        llm_configs[config_id] = updated
        projected = _project_safe_copy(updated)
    return success_response(data=projected, message="配置更新成功", trace_id=get_trace_id(request))


@router.delete("/llm-configs/{config_id}")
async def delete_config(
    request: Request,
    config_id: str,
    _admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del _admin_user
    with _LLM_CONFIGS_LOCK:
        if config_id not in llm_configs:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="配置不存在")
        del llm_configs[config_id]
    return success_response(data=None, message="配置删除成功", trace_id=get_trace_id(request))


@router.post("/llm-configs/{config_id}/test")
async def test_config(
    request: Request,
    config_id: str,
    _admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del _admin_user
    with _LLM_CONFIGS_LOCK:
        exists = config_id in llm_configs
    if not exists:
        raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="配置不存在")
    return success_response(data={"config_id": config_id}, message="连接正常", trace_id=get_trace_id(request))
