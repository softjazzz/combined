from datetime import datetime, timedelta
from typing import Optional, Iterable
import threading
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext

from .settings import get_settings
from .roles import effective_principal, effective_roles
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
    to_encode.setdefault("type", "access")
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str) or not hashed_password:
        return False
    if len(plain_password.encode("utf-8")) > 72:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


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
    if expected_type is not None:
        if expected_type == "access":
            # 兼容历史未携带 type 的合法 access token，明确拒绝 refresh/password_reset 等非 access 令牌
            if token_type is not None and token_type != "access":
                raise _credentials_exception()
        elif token_type != expected_type:
            raise _credentials_exception()
    return payload


def resolve_user_by_subject(subject: str | None) -> Optional[dict]:
    return resolve_auth_store_user_by_subject(subject)


def resolve_current_user_from_token(token: str) -> dict:
    payload = _decode_token(token)
    token_type = payload.get("type")
    if token_type is not None and token_type != "access":
        raise _credentials_exception()
    token_subject: str = payload.get("sub")
    if token_subject is None:
        raise _credentials_exception()

    user = resolve_user_by_subject(token_subject)
    if user is None or user.get("is_active") is False:
        raise _credentials_exception()
    return effective_principal(user)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    cached_user = getattr(request.state, "current_user", None)
    if cached_user is not None:
        return effective_principal(cached_user)
    user = resolve_current_user_from_token(credentials.credentials)
    request.state.current_user = user
    return user


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    cached_user = getattr(request.state, "current_user", None)
    if cached_user is not None:
        return effective_principal(cached_user)
    if credentials is None:
        return None
    user = resolve_current_user_from_token(credentials.credentials)
    request.state.current_user = user
    return user


def require_roles(*roles: str):
    allowed = {r for r in roles}

    async def _checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = set(effective_roles(current_user.get("roles")))
        if not user_roles.intersection({"sync_admin", "super_admin"}) and not user_roles.intersection(allowed):
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
    系统管理员、super_admin 及 sync_admin 超级管理员可访问。
    """
    if "admin" not in effective_roles(current_user.get("roles")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此操作需要系统管理员权限"
        )
    return current_user


def _extract_principal_roles(current_user: dict | None) -> set[str]:
    if not isinstance(current_user, dict):
        return set()
    raw = current_user.get("roles")
    if isinstance(raw, (list, tuple, set)):
        roles = {str(r).strip().lower() for r in raw if str(r).strip()}
    elif isinstance(raw, str) and raw.strip():
        roles = {raw.strip().lower()}
    else:
        roles = set()
    single = current_user.get("role")
    if isinstance(single, str) and single.strip():
        roles.add(single.strip().lower())
    return roles


def is_global_system_admin_principal(
    roles: Iterable[str] | None,
    institute_id: object = None,
) -> bool:
    """判定是否为全局系统管理员：sync_admin / super_admin（不受院区绑定限制），或未绑定院区的 admin。"""
    raw = {str(r).strip().lower() for r in (roles or []) if str(r).strip()}
    expanded = {
        str(r).strip().lower()
        for r in effective_roles(raw)
        if str(r).strip()
    }
    inst = str(institute_id or "").strip()
    return bool((raw | expanded) & {"sync_admin", "super_admin"}) or (
        "admin" in expanded and not inst
    )


def _verify_persistent_global_admin_scope(actor_id: str) -> None:
    """若持久账号表存在该账号，以持久角色与院区绑定为准复核全局范围；DB 异常时 fail-closed 返回 503。"""
    if not actor_id:
        return
    from ..database import connection as db_conn

    session_factory = getattr(db_conn, "SessionLocal", None)
    if session_factory is None:
        return
    from sqlalchemy import select
    from sqlalchemy.exc import OperationalError, SQLAlchemyError
    from ..database.models.v36_reports import SysUser
    from ..services.user_scope_owner import user_owner_options
    from ..services.defect_rectification_service import _effective_persistent_roles

    try:
        with session_factory() as session:
            row = session.execute(
                select(
                    SysUser.id,
                    SysUser.role,
                    SysUser.roles_json,
                    SysUser.institute_id,
                    SysUser.is_active,
                ).where(SysUser.id == actor_id),
                execution_options=user_owner_options(session),
            ).first()
    except OperationalError as exc:
        msg = str(exc).lower()
        # 仅兼容离线 SQLite 单测环境中未建 sys_users 表/列时的回退；其余 DB 故障 fail-closed 返回 503
        if "no such table" in msg or "no such column" in msg:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="账号全局权限复核服务暂不可用",
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="账号全局权限复核服务暂不可用",
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="账号全局权限复核服务暂不可用",
        ) from None
    if row is None:
        return
    _uid, db_role, db_roles_json, db_institute_id, db_is_active = row
    if not db_is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已停用，无权执行全局系统配置操作",
        )
    persistent_roles = _effective_persistent_roles(db_role, db_roles_json)
    if not is_global_system_admin_principal(persistent_roles, db_institute_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅全局系统管理员可执行此操作，绑定院区管理员不可越权操作全局配置",
        )


def verify_global_system_admin(current_user: dict) -> dict:
    """校验全局系统管理员权限：允许 sync_admin / super_admin 或未绑定院区的 admin，拒绝非管理员及绑定院区的普通 admin。"""
    roles = _extract_principal_roles(current_user)
    institute_id = current_user.get("institute_id") if isinstance(current_user, dict) else None
    if not is_global_system_admin_principal(roles, institute_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此操作需要全局系统管理员权限",
        )
    actor_id = str((current_user or {}).get("id") or (current_user or {}).get("user_id") or "").strip()
    _verify_persistent_global_admin_scope(actor_id)
    return current_user


async def require_global_system_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI 依赖：要求当前用户为全局系统管理员（sync_admin / super_admin 或无院区绑定的 admin）。"""
    return verify_global_system_admin(current_user)


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

