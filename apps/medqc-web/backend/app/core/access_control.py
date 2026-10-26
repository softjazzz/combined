from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from .security import optional_security, resolve_current_user_from_token


PUBLIC_EXACT_PATHS = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/api/v1/health",
    "/api/v1/runtime-build",
    "/api/v1/ready",
    "/api/v1/metrics",
    "/api/v1/metrics/prometheus",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/registration-departments",
    "/api/v1/auth/registration-status",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/logout",
    # 仅绕过应用级认证：准生产路由会先检查关闭开关，开启后再自行认证。
    "/api/v1/qc/luxian-0609/preproduction/evaluate",
}

_DEFERRED_ROUTE_AUTH_PATH = "/api/v1/qc/luxian-0609/preproduction/evaluate"

PUBLIC_PREFIX_PATHS = {
    "/docs/",
    "/redoc/",
    "/api/v1/demo/",
}


def is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIX_PATHS)


async def enforce_default_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
):
    """
    Default-deny authentication strategy:
    - All endpoints require auth unless explicitly listed as public.
    - Public endpoints may still accept bearer token to hydrate request.state.current_user.
    """
    path = request.url.path
    if request.method == "OPTIONS" or is_public_path(path):
        # 该入口必须保证开关关闭时零认证存储访问；令牌由路由在开关开启后解析。
        if path == _DEFERRED_ROUTE_AUTH_PATH:
            return
        if credentials is not None:
            try:
                request.state.current_user = resolve_current_user_from_token(credentials.credentials)
            except HTTPException:
                # Keep public endpoints resilient to stale/invalid tokens.
                pass
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.current_user = resolve_current_user_from_token(credentials.credentials)
    from ..services.doctor_case_scope import enforce_doctor_case_access

    await enforce_doctor_case_access(request, request.state.current_user)
