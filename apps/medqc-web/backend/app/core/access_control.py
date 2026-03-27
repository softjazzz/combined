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
    "/api/v1/ready",
    "/api/v1/metrics",
    "/api/v1/metrics/prometheus",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/logout",
}

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
