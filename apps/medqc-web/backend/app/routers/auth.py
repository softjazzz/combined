from datetime import timedelta
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from pydantic import EmailStr

from ..core.response import success_response, get_trace_id
from ..schemas.auth import UserUpdate, LoginRequest, RefreshTokenRequest
from ..schemas.registration import RegistrationCreate, RegistrationStatusQuery
from ..core.rate_limit import enforce_rate_limit
from ..core.settings import get_settings
from ..core.roles import effective_roles
from ..core.security import (
    create_access_token,
    create_password_reset_token,
    consume_password_reset_jti,
    get_current_user,
    get_password_hash,
    verify_password_reset_token,
    verify_password,
)
from ..services.auth_store import (
    find_user_by_account,
    resolve_user_by_subject as resolve_auth_store_user_by_subject,
    touch_last_login,
    update_user_password,
    update_user_profile,
)
from ..storage.memory import DEFAULT_DEMO_USER_EMAILS


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


async def _registration_call(method, *args):
    from starlette.concurrency import run_in_threadpool
    from ..services.account_registration_service import AccountRegistrationService
    from ..services.defect_rectification_service import RectificationError

    try:
        return await run_in_threadpool(getattr(AccountRegistrationService(), method), *args)
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except Exception as exc:
        logger.warning("注册服务失败 error_type=%s", type(exc).__name__)
        raise HTTPException(503, "注册审批服务暂不可用，请刷新核对，勿重复提交") from None


def _normalize_account(raw_value: str | None) -> str:
    return str(raw_value or "").strip()


def _find_user_by_account(account: str) -> dict | None:
    return find_user_by_account(account)


def _user_payload(user: dict) -> dict:
    normalized_email = str(user.get("email") or "").strip().lower()
    return {
        "id": user["id"],
        "email": user["email"],
        "username": user.get("username"),
        "display_name": user["display_name"],
        "institute_id": str(user.get("institute_id") or "").strip(),
        "is_active": bool(user.get("is_active", True)),
        "department": user["department"],
        "roles": effective_roles(user["roles"]),
        "avatar": user["avatar"],
        "phone": user["phone"],
        "bio": user["bio"],
        "created_at": user["created_at"],
        "last_login": user["last_login"],
        "is_demo_account": normalized_email in DEFAULT_DEMO_USER_EMAILS,
    }


def _login_payload(*, access_token: str, refresh_token: str) -> dict:
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def _auth_shell(request: Request, payload: dict, *, message: str | None = None) -> dict:
    body = success_response(data=payload, message=message, trace_id=get_trace_id(request))
    body.update(payload)
    return body


@router.options("/login")
async def login_options(request: Request):
    return success_response(data={}, message="OK", trace_id=get_trace_id(request))


@router.post("/login")
async def login(request: Request, login_data: LoginRequest):
    enforce_rate_limit(request, bucket="auth_login", max_requests=10, window_seconds=60)
    settings = get_settings()
    account = _normalize_account(login_data.account)
    user = _find_user_by_account(account)
    if not user or not verify_password(login_data.password, user["password_hash"]):
        # 防止爆破（失败也计入限流）
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    updated_user = touch_last_login(str(user.get("id") or ""))
    if updated_user is not None:
        user = updated_user

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # 旧账号沿用邮箱 subject；无邮箱注册账号使用已有持久 ID 解析链路。
    token_sub = str(user.get("email") or user["id"])
    access_token = create_access_token(
        data={"sub": token_sub, "uid": user.get("id"), "type": "access"},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": token_sub, "uid": user.get("id"), "type": "refresh"},
        expires_delta=refresh_token_expires,
    )

    # 审计日志（不记录明文凭据）
    logger.info("auth.login.success account=%s email=%s", account, user["email"])
    return _auth_shell(
        request,
        _login_payload(access_token=access_token, refresh_token=refresh_token),
        message="登录成功",
    )


@router.post("/register")
async def register(request: Request, user_data: RegistrationCreate):
    enforce_rate_limit(request, bucket="registration_submit", max_requests=10, window_seconds=60)
    result = await _registration_call("submit", user_data.model_dump())
    return _auth_shell(request, result, message="注册申请已保存，请等待管理员审批")


@router.get("/registration-departments")
async def registration_departments(request: Request):
    enforce_rate_limit(request, bucket="registration_departments", max_requests=60, window_seconds=60)
    result = await _registration_call("departments")
    return _auth_shell(request, result)


@router.post("/registration-status")
async def registration_status(request: Request, query: RegistrationStatusQuery):
    enforce_rate_limit(request, bucket="registration_status", max_requests=10, window_seconds=60)
    result = await _registration_call("status", query.account, query.password)
    return _auth_shell(request, result)


@router.get("/registration")
async def own_registration(request: Request, current_user: dict = Depends(get_current_user)):
    result = await _registration_call("own_status", str(current_user.get("id") or ""))
    return _auth_shell(request, result)


@router.get("/me")
async def get_current_user_info(    request: Request,current_user: dict = Depends(get_current_user)):
    return _auth_shell(request, _user_payload(current_user))


@router.put("/profile")
async def update_profile(    request: Request,profile_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    if (
        "doctor" in (current_user.get("roles") or [])
        and not set(current_user.get("roles") or []) & {"admin", "qc_manager", "qc_staff", "sync_admin", "super_admin"}
        and profile_data.display_name is not None
        and profile_data.display_name.strip() != str(current_user.get("display_name") or "").strip()
    ):
        raise HTTPException(403, "医生姓名用于病历授权，仅可由系统管理员核定变更")
    if profile_data.department is not None and profile_data.department != current_user.get("department"):
        raise HTTPException(403, "账号科室授权仅可由系统管理员变更")
    try:
        user = update_user_profile(
            user_id=str(current_user.get("id") or ""),
            display_name=profile_data.display_name,
            department=profile_data.department,
            phone=profile_data.phone,
            bio=profile_data.bio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return _auth_shell(request, _user_payload(user), message="资料已更新")


@router.put("/password")
async def update_password(
    request: Request,
    new_password: str = Form(...),
    current_password: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    user = current_user
    if not current_password or not current_password.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不能为空")
    if not new_password or not new_password.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="新密码不能为空")
    if len(new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="新密码长度不能超过 72 字节")
    stored_hash = str(user.get("password_hash") or "")
    if not stored_hash or not verify_password(current_password, stored_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
    try:
        updated_user = update_user_password(
            user_id=str(user.get("id") or ""),
            password_hash=get_password_hash(new_password),
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="密码格式无效") from None
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return success_response(data={}, message="密码修改成功", trace_id=get_trace_id(request))


@router.post("/logout")
async def logout(    request: Request,):
    # 放宽登出：无论是否携带 Authorization，都返回 200，避免前端因 token 过期/缺失导致 401/403
    return success_response(data={}, message="登出成功", trace_id=get_trace_id(request))


@router.post("/refresh")
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
):
    from jose import jwt, JWTError
    settings = get_settings()
    token_value = str(payload.refresh_token or "").strip()
    if not token_value:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="refresh_token 不能为空")
    try:
        decoded = jwt.decode(token_value, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        token_subject: str = decoded.get("sub")
        token_type: str = decoded.get("type")
        if token_subject is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

        user = resolve_auth_store_user_by_subject(token_subject)
        if user is None or user.get("is_active") is False:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": token_subject, "uid": user.get("id"), "type": "access"},
            expires_delta=access_token_expires,
        )
        logger.info("auth.refresh.success subject=%s email=%s", token_subject, user.get("email"))
        return _auth_shell(
            request,
            _login_payload(access_token=access_token, refresh_token=token_value),
            message="刷新成功",
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: EmailStr | None = Form(default=None),
):
    enforce_rate_limit(request, bucket="auth_forgot_password", max_requests=5, window_seconds=60)
    target_email = str(email or "").strip().lower()
    if not target_email:
        try:
            body = await request.json()
            if isinstance(body, dict):
                target_email = str(body.get("email") or "").strip().lower()
        except Exception:
            target_email = ""
    user = resolve_auth_store_user_by_subject(target_email)
    if user:
        # 仅在服务端签发令牌，永不在 HTTP 响应中回传明文 reset_token（防未认证接管与邮箱枚举）
        create_password_reset_token(user["email"])
        logger.info("auth.forgot_password.issued email=%s", user["email"])
    else:
        logger.info("auth.forgot_password.request email=%s", target_email)
    # 统一返回中立成功提示以避免账户枚举
    return success_response(data={}, message="如果邮箱存在，重置密码邮件已发送", trace_id=get_trace_id(request))


@router.post("/reset-password")
async def reset_password(
    request: Request,
    token: str | None = Form(default=None),
    new_password: str | None = Form(default=None),
):
    enforce_rate_limit(request, bucket="auth_reset_password", max_requests=10, window_seconds=60)
    token_value = token
    password_value = new_password
    if not token_value or not password_value:
        try:
            body = await request.json()
            if isinstance(body, dict):
                token_value = token_value or str(body.get("token") or "").strip()
                password_value = password_value or str(body.get("new_password") or "")
        except Exception:
            pass
    if not token_value or not password_value or not password_value.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="token 和 new_password 不能为空")
    if len(password_value.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="新密码长度不能超过 72 字节")

    email, jti = verify_password_reset_token(token_value)
    if not consume_password_reset_jti(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="重置令牌已使用或失效")

    user = resolve_auth_store_user_by_subject(email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的重置令牌")
    try:
        updated_user = update_user_password(
            user_id=str(user.get("id") or ""),
            password_hash=get_password_hash(password_value),
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="密码格式无效") from None
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的重置令牌")
    logger.info("auth.reset_password.success email=%s", email)
    return success_response(data={}, message="密码重置成功", trace_id=get_trace_id(request))
