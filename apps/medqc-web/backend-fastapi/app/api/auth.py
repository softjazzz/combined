"""
认证相关的API端点
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from loguru import logger

from app.schemas.auth import LoginRequest, LoginResponse, UserResponse
from app.services.auth_service import AuthService


router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserResponse:
    """
    从请求头获取当前用户
    依赖项，用于保护需要认证的端点
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    try:
        # 提取 Bearer token
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="无效的认证方案")

        # 解码 token
        payload = AuthService.decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="无效的令牌")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="令牌中缺少用户ID")

        # 获取用户信息
        user = await AuthService.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")

        return user

    except ValueError:
        raise HTTPException(status_code=401, detail="无效的认证令牌格式")
    except Exception as e:
        logger.error(f"认证失败: {e}")
        raise HTTPException(status_code=401, detail="认证失败")


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    用户登录

    - **email**: 用户邮箱
    - **password**: 用户密码
    - **role**: 用户角色（可选）
    """
    logger.info(f"登录请求: {credentials.email}")

    # 认证用户
    user = await AuthService.authenticate_user(credentials)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    # 创建访问令牌
    access_token = AuthService.create_access_token(data={"sub": user.id, "email": user.email})

    # 构建响应
    response = LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "department": user.department,
            "hospital_id": user.hospital_id,
            "roles": user.roles,
            "is_active": user.is_active,
            "role": user.roles[0] if user.roles else "user"  # 为了兼容前端
        }
    )

    logger.info(f"用户登录成功: {user.email}")
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """
    获取当前登录用户信息

    需要在请求头中提供有效的 JWT token
    """
    return current_user


@router.post("/logout")
async def logout(current_user: UserResponse = Depends(get_current_user)):
    """
    用户登出

    实际上只是前端清除 token，后端无需处理
    """
    logger.info(f"用户登出: {current_user.email}")
    return {"message": "登出成功"}


@router.post("/register")
async def register():
    """
    用户注册

    暂未实现，返回 501 状态码
    """
    raise HTTPException(status_code=501, detail="注册功能暂未实现")


@router.post("/refresh")
async def refresh_token():
    """
    刷新访问令牌

    暂未实现，返回 501 状态码
    """
    raise HTTPException(status_code=501, detail="刷新令牌功能暂未实现")
