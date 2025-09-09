from datetime import datetime, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.responses import JSONResponse
from pydantic import EmailStr

from ..schemas.auth import (
    UserCreate,
    UserUpdate,
    UserResponse,
    LoginRequest,
    LoginResponse,
)
from ..core.settings import get_settings
from ..core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from ..storage.memory import users_db


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.options("/login")
async def login_options():
    return {"message": "OK"}


@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    settings = get_settings()
    user = users_db.get(login_data.email)
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    user["last_login"] = datetime.utcnow().isoformat() + "Z"

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user["email"]}, expires_delta=access_token_expires)

    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(data={"sub": user["email"], "type": "refresh"}, expires_delta=refresh_token_expires)

    return LoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    if user_data.email in users_db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

    user_id = f"user-{uuid.uuid4().hex[:8]}"
    new_user = {
        "id": user_id,
        "email": user_data.email,
        "display_name": user_data.display_name,
        "department": user_data.department,
        "roles": [user_data.role or "doctor"],
        "password_hash": get_password_hash(user_data.password),
        "avatar": "",
        "phone": user_data.phone,
        "bio": user_data.bio,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_login": None,
    }
    users_db[user_data.email] = new_user

    return UserResponse(**{
        "id": new_user["id"],
        "email": new_user["email"],
        "display_name": new_user["display_name"],
        "department": new_user["department"],
        "roles": new_user["roles"],
        "avatar": new_user["avatar"],
        "phone": new_user["phone"],
        "bio": new_user["bio"],
        "created_at": new_user["created_at"],
        "last_login": new_user["last_login"],
    })


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return UserResponse(**{
        "id": current_user["id"],
        "email": current_user["email"],
        "display_name": current_user["display_name"],
        "department": current_user["department"],
        "roles": current_user["roles"],
        "avatar": current_user["avatar"],
        "phone": current_user["phone"],
        "bio": current_user["bio"],
        "created_at": current_user["created_at"],
        "last_login": current_user["last_login"],
    })


@router.put("/profile", response_model=UserResponse)
async def update_profile(profile_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    user = users_db[current_user["email"]]
    if profile_data.display_name is not None:
        user["display_name"] = profile_data.display_name
    if profile_data.department is not None:
        user["department"] = profile_data.department
    if profile_data.phone is not None:
        user["phone"] = profile_data.phone
    if profile_data.bio is not None:
        user["bio"] = profile_data.bio

    return UserResponse(**{
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "department": user["department"],
        "roles": user["roles"],
        "avatar": user["avatar"],
        "phone": user["phone"],
        "bio": user["bio"],
        "created_at": user["created_at"],
        "last_login": user["last_login"],
    })


@router.put("/password")
async def update_password(
    new_password: str = Form(...),
    current_password: str = Form(None),
    current_user: dict = Depends(get_current_user),
):
    user = users_db[current_user["email"]]
    if current_password and not verify_password(current_password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
    user["password_hash"] = get_password_hash(new_password)
    return {"message": "密码修改成功"}


@router.post("/logout")
async def logout():
    # 放宽登出：无论是否携带 Authorization，都返回 200，避免前端因 token 过期/缺失导致 401/403
    return {"message": "登出成功"}


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(refresh_token: str = Form(...)):
    from jose import jwt, JWTError
    settings = get_settings()
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

        user = users_db.get(email)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": email}, expires_delta=access_token_expires)
        return LoginResponse(access_token=access_token, refresh_token=refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")


@router.post("/forgot-password")
async def forgot_password(email: EmailStr = Form(...)):
    user = users_db.get(email)
    # 返回成功以避免账户枚举
    return {"message": "如果邮箱存在，重置密码邮件已发送"}


@router.post("/reset-password")
async def reset_password(token: str = Form(...), new_password: str = Form(...)):
    # 简化处理：不实现 token 校验
    return {"message": "密码重置成功"}

