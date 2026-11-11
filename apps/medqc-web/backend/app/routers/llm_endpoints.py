"""连接管理只提供读写配置；保存绝不发起模型请求。"""
from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import ValidationError

from ..core.security import require_roles
from ..core.response import success_response, get_trace_id
from ..services import llm_endpoint_settings as endpoints
from ..services.llm_config_loader import get_settings, _deployed_provider_codes

router = APIRouter(prefix="/api/v1/llm/endpoints", tags=["llm-endpoints"])
super_admin = require_roles("sync_admin", "super_admin")


@router.get("")
def get_endpoints(request: Request, user: dict = Depends(super_admin)):
    try:
        view = endpoints.public_view(get_settings(), _deployed_provider_codes())
    except endpoints.EndpointSettingsError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    return success_response(data=view, trace_id=get_trace_id(request))


@router.put("/{provider}")
def save_endpoint(provider: str, request: Request, payload: Any = Body(...), user: dict = Depends(super_admin)):
    try:
        # 不把Pydantic包含原始输入的错误回显给浏览器或日志。
        proposed = endpoints.EndpointUpdate.model_validate(payload)
    except ValidationError:
        raise HTTPException(422, "llm_endpoint_configuration_invalid") from None
    try:
        endpoints.save(provider, proposed, str(user.get("id") or user.get("sub") or "unknown"), get_settings())
        view = endpoints.public_view(get_settings(), _deployed_provider_codes())
    except endpoints.EndpointSettingsError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except OSError:
        raise HTTPException(503, "llm_endpoint_storage_unavailable") from None
    return success_response(data=view, trace_id=get_trace_id(request))
