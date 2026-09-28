from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Iterable
import threading
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext

from .settings import get_settings
from ..services.auth_store import resolve_user_by_subject as resolve_auth_store_user_by_subject


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

_RESET_TOKEN_TTL_MINUTES = 15
_used_reset_jti: dict[str, float] = {}
_reset_jti_lock = threading.Lock()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def issue_login_token_pair(user: Mapping[str, Any]) -> dict[str, Any]:
    """签发密码登录与扫码登录共用的访问/刷新令牌合同。"""
    settings = get_settings()
    user_id = str(user.get("id") or "").strip()
    token_sub = str(user.get("email") or "").strip().lower()
    if not user_id or not token_sub:
        raise ValueError("用户缺少令牌签发身份")
    access_token = create_access_token(
        data={"sub": token_sub, "uid": user_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_access_token(
        data={"sub": token_sub, "uid": user_id, "type": "refresh"},
        expires_delta=timedelta(days=7),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_token(token: str, *, expected_type: Optional[str] = None) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise _credentials_exception()
    token_type = payload.get("type")
    if expected_type is not None and token_type != expected_type:
        raise _credentials_exception()
    return payload


def resolve_user_by_subject(subject: str | None) -> Optional[dict]:
    return resolve_auth_store_user_by_subject(subject)


def resolve_current_user_from_token(token: str) -> dict:
    payload = _decode_token(token)
    # 兼容历史无 type 的访问令牌，但刷新/重置令牌不得用作 Bearer 访问资源。
    if payload.get("type") not in (None, "access"):
        raise _credentials_exception()
    token_subject: str = payload.get("sub")
    if token_subject is None:
        raise _credentials_exception()

    user = resolve_user_by_subject(token_subject)
    if user is None:
        raise _credentials_exception()
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    cached_user = getattr(request.state, "current_user", None)
    if cached_user is not None:
        return cached_user
    user = resolve_current_user_from_token(credentials.credentials)
    request.state.current_user = user
    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    cached_user = getattr(request.state, "current_user", None)
    if cached_user is not None:
        return cached_user
    if credentials is None:
        return None
    user = resolve_current_user_from_token(credentials.credentials)
    request.state.current_user = user
    return user


def require_roles(*roles: str):
    allowed = {r for r in roles}

    async def _checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = {str(r) for r in current_user.get("roles", [])}
        if not user_roles.intersection(allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要角色之一: {', '.join(sorted(allowed))}",
            )
        return current_user

    return _checker


def require_any_role(roles: Iterable[str]):
    return require_roles(*list(roles))


async def require_admin(current_user: dict = Depends(get_current_user)):
    """
    验证当前用户是否为系统管理员
    只有角色中包含 'admin' 的用户才能访问
    """
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此操作需要系统管理员权限"
        )
    return current_user


def create_password_reset_token(email: str, expires_minutes: int = _RESET_TOKEN_TTL_MINUTES) -> str:
    ttl = max(1, int(expires_minutes))
    jti = f"pwdreset-{datetime.utcnow().timestamp()}-{email}"
    return create_access_token(
        data={"sub": email, "type": "password_reset", "jti": jti},
        expires_delta=timedelta(minutes=ttl),
    )


def verify_password_reset_token(token: str) -> tuple[str, str]:
    payload = _decode_token(token, expected_type="password_reset")
    email = payload.get("sub")
    jti = payload.get("jti")
    if not email or not jti:
        raise _credentials_exception()
    return str(email), str(jti)


def _cleanup_used_reset_jti(now_ts: float) -> None:
    expired = [k for k, v in _used_reset_jti.items() if v <= now_ts]
    for key in expired:
        _used_reset_jti.pop(key, None)


def consume_password_reset_jti(jti: str, ttl_seconds: int = 3600) -> bool:
    """
    One-time token protection.
    Returns True on first consume; False when token was already consumed.
    """
    now_ts = datetime.utcnow().timestamp()
    with _reset_jti_lock:
        _cleanup_used_reset_jti(now_ts)
        if jti in _used_reset_jti:
            return False
        _used_reset_jti[jti] = now_ts + max(60, int(ttl_seconds))
        return True

