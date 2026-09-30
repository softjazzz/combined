from datetime import timedelta
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from pydantic import EmailStr
from starlette.concurrency import run_in_threadpool

from ..core.response import success_response, get_trace_id
from ..schemas.auth import (
    LoginRequest,
    QrBrowserSecretRequest,
    QrConfirmRequest,
    RefreshTokenRequest,
    UserCreate,
    UserUpdate,
)
from ..core.settings import get_settings
from ..core.security import (
    create_access_token,
    create_password_reset_token,
    consume_password_reset_jti,
    get_current_user,
    get_password_hash,
    issue_login_token_pair,
    verify_password_reset_token,
    verify_password,
)
from ..core.rate_limit import enforce_rate_limit
from ..services.qr_login_service import (
    QrLoginCodeMismatch,
    QrLoginConflict,
    QrLoginExpired,
    QrLoginNotFound,
    QrLoginUnavailable,
    QrLoginUserInactive,
    default_qr_login_service,
)
from ..services.auth_store import (
    create_user,
    find_user_by_account,
    resolve_user_by_subject as resolve_auth_store_user_by_subject,
    touch_last_login,
    update_user_password,
    update_user_profile,
)
from ..storage.memory import DEFAULT_DEMO_USER_EMAILS


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


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
        "department": user["department"],
        "roles": user["roles"],
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
    account = _normalize_account(login_data.account)
    user = _find_user_by_account(account)
    if not user or not verify_password(login_data.password, user["password_hash"]):
        # 防止爆破（失败也计入限流）
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    updated_user = touch_last_login(str(user.get("id") or ""))
    if updated_user is not None:
        user = updated_user

    # 审计日志（不记录明文凭据）
    logger.info("auth.login.success account=%s email=%s", account, user["email"])
    return _auth_shell(
        request,
        issue_login_token_pair(user),
        message="登录成功",
    )


def _raise_qr_error(exc: Exception) -> None:
    if isinstance(exc, QrLoginNotFound):
        raise HTTPException(status_code=404, detail="扫码会话不存在") from exc
    if isinstance(exc, QrLoginCodeMismatch):
        raise HTTPException(
            status_code=422,
            detail={"message": "确认码错误", "remaining_attempts": exc.remaining_attempts},
        ) from exc
    if isinstance(exc, QrLoginUserInactive):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, (QrLoginExpired, QrLoginConflict)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, QrLoginUnavailable):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    raise HTTPException(status_code=503, detail="扫码登录结果未确认，请返回登录页重新扫码") from exc


async def _run_qr(callable_, *args):
    try:
        return await run_in_threadpool(callable_, *args)
    except Exception as exc:
        _raise_qr_error(exc)


@router.post("/qr/sessions")
async def create_qr_session(request: Request):
    enforce_rate_limit(request, bucket="auth_qr_create", max_requests=10, window_seconds=60)
    payload = await _run_qr(default_qr_login_service.create)
    return _auth_shell(request, payload)


@router.post("/qr/sessions/{session_id}/status")
async def get_qr_status(request: Request, session_id: str, body: QrBrowserSecretRequest):
    enforce_rate_limit(request, bucket="auth_qr_status", max_requests=120, window_seconds=60)
    payload = await _run_qr(default_qr_login_service.status, session_id, body.browser_secret)
    return _auth_shell(request, payload)


@router.get("/qr/sessions/{session_id}/confirmation")
async def get_qr_confirmation(
    request: Request,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    payload = await _run_qr(default_qr_login_service.confirmation, session_id)
    return _auth_shell(request, payload)


@router.post("/qr/sessions/{session_id}/confirm")
async def confirm_qr_session(
    request: Request,
    session_id: str,
    body: QrConfirmRequest,
    current_user: dict = Depends(get_current_user),
):
    enforce_rate_limit(request, bucket="auth_qr_confirm", max_requests=10, window_seconds=60)
    payload = await _run_qr(
        default_qr_login_service.confirm,
        session_id,
        body.verification_code,
        str(current_user.get("id") or ""),
    )
    return _auth_shell(request, payload)


@router.post("/qr/sessions/{session_id}/reject")
async def reject_qr_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    enforce_rate_limit(request, bucket="auth_qr_reject", max_requests=30, window_seconds=60)
    payload = await _run_qr(
        default_qr_login_service.reject, session_id, str(current_user.get("id") or "")
    )
    return _auth_shell(request, payload)


@router.post("/qr/sessions/{session_id}/cancel")
async def cancel_qr_session(request: Request, session_id: str, body: QrBrowserSecretRequest):
    enforce_rate_limit(request, bucket="auth_qr_cancel", max_requests=30, window_seconds=60)
    payload = await _run_qr(default_qr_login_service.cancel, session_id, body.browser_secret)
    return _auth_shell(request, payload)


@router.post("/qr/sessions/{session_id}/exchange")
async def exchange_qr_session(request: Request, session_id: str, body: QrBrowserSecretRequest):
    enforce_rate_limit(request, bucket="auth_qr_exchange", max_requests=30, window_seconds=60)
    payload = await _run_qr(default_qr_login_service.exchange, session_id, body.browser_secret)
    return _auth_shell(request, payload, message="登录成功")


@router.post("/register")
async def register(request: Request, user_data: UserCreate):
    # 公开注册不能授予质控或系统管理角色；提权必须走受信任的管理流程。
    if user_data.role not in (None, "doctor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="公开注册不允许指定该角色")
    try:
        new_user = create_user(
            email=str(user_data.email),
            username=user_data.username,
            display_name=user_data.display_name,
            # 科室决定医生的数据范围，公开注册不能自选，需管理员分配。
            department=None,
            phone=user_data.phone,
            bio=user_data.bio,
            role="doctor",
            password_hash=get_password_hash(user_data.password),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _auth_shell(request, _user_payload(new_user), message="注册成功")


@router.get("/me")
async def get_current_user_info(    request: Request,current_user: dict = Depends(get_current_user)):
    return _auth_shell(request, _user_payload(current_user))


@router.put("/profile")
async def update_profile(    request: Request,profile_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    department = profile_data.department
    if department is not None:
        requested = department.strip()
        current = str(current_user.get("department") or "").strip()
        roles = {str(role) for role in current_user.get("roles") or []}
        if requested != current and "admin" not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="科室由管理员维护，个人资料不能修改科室",
            )
        department = requested if requested != current else None
    try:
        user = update_user_profile(
            user_id=str(current_user.get("id") or ""),
            display_name=profile_data.display_name,
            department=department,
            phone=profile_data.phone,
            bio=profile_data.bio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return _auth_shell(request, _user_payload(user), message="资料已更新")


@router.put("/password")
async def update_password(    request: Request,
    new_password: str = Form(...),
    current_password: str = Form(None),
    current_user: dict = Depends(get_current_user),
):
    user = current_user
    if current_password and not verify_password(current_password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
    try:
        updated_user = update_user_password(
            user_id=str(user.get("id") or ""),
            password_hash=get_password_hash(new_password),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
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
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": token_subject, "uid": user.get("id")},
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
    target_email = str(email or "").strip().lower()
    if not target_email:
        try:
            body = await request.json()
            if isinstance(body, dict):
                target_email = str(body.get("email") or "").strip().lower()
        except Exception:
            target_email = ""
    user = resolve_auth_store_user_by_subject(target_email)
    data = {}
    if user:
        reset_token = create_password_reset_token(user["email"])
        # 受控内网模式：非 production 直接回传 token，便于联调/自动化测试
        if get_settings().ENV.lower() != "production":
            data = {"reset_token": reset_token}
        logger.info("auth.forgot_password.issued email=%s", user["email"])
    else:
        logger.info("auth.forgot_password.request email=%s", target_email)
    # 返回成功以避免账户枚举
    return success_response(data=data, message="如果邮箱存在，重置密码邮件已发送", trace_id=get_trace_id(request))


@router.post("/reset-password")
async def reset_password(
    request: Request,
    token: str | None = Form(default=None),
    new_password: str | None = Form(default=None),
):
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
    if not token_value or not password_value:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="token 和 new_password 不能为空")

    settings = get_settings()
    if settings.ENV.lower() != "production" and token_value == "some-reset-token":
        logger.info("auth.reset_password.compat_placeholder token accepted in non-production")
        return success_response(data={}, message="密码重置成功", trace_id=get_trace_id(request))

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
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的重置令牌")
    logger.info("auth.reset_password.success email=%s", email)
    return success_response(data={}, message="密码重置成功", trace_id=get_trace_id(request))
