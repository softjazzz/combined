"""
智慧医保质控系统 - 独立后端服务
基于 FastAPI 的医保规则管理和质控分析 API 服务
端口: 8002 (独立于 medqc 后端的 8001 端口)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid

from fastapi import FastAPI, HTTPException, Depends, status, Form, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
import uvicorn

# Supabase 集成
from supabase import create_client, Client

# 认证工具
from auth_utils import (
    get_current_user, authenticate_user, create_access_token,
    verify_password, get_password_hash, DEMO_USERS, pwd_context,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 配置和环境变量 ====================

# Supabase 配置
SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("VITE_SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# ==================== Supabase 客户端初始化 ====================

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        # 优先使用 Service Role Key，回退到 Anon Key
        api_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
        supabase = create_client(SUPABASE_URL, api_key)
        logger.info(f"Supabase 客户端初始化成功: {SUPABASE_URL}")
    except Exception as e:
        logger.warning(f"Supabase 客户端初始化失败，将使用 Mock 数据: {e}")
        supabase = None
else:
    logger.warning("Supabase 配置缺失，将使用 Mock 数据")

# ==================== FastAPI 应用初始化 ====================

app = FastAPI(
    title="智慧医保质控系统 API",
    description="医保规则管理和质控分析的独立后端服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
ALLOWED_ORIGINS = [
    "http://localhost:3008",
    "http://localhost:3009", 
    "http://localhost:3010",
    "http://127.0.0.1:3008",
    "http://127.0.0.1:3009",
    "http://127.0.0.1:3010",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 数据模型 ====================

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: Optional[Dict[str, Any]] = None

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    department: Optional[str] = None
    roles: List[str] = []

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    department: Optional[str] = None
    role: Optional[str] = "user"

# ==================== Mock 用户数据 ====================
# 用户数据已移至 auth_utils.py

# ==================== 工具函数 ====================
# 认证相关函数已移至 auth_utils.py

# ==================== 基础路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "智慧医保质控系统 API",
        "version": "1.0.0",
        "service": "yibao-backend",
        "port": 8002,
        "docs": "/docs",
        "health": "/api/health",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    supabase_status = "connected" if supabase else "not_configured"
    
    return {
        "status": "healthy",
        "service": "yibao-backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "supabase_status": supabase_status,
        "features": {
            "authentication": True,
            "rule_management": True,
            "sandbox_testing": True,
            "statistics": True
        },
        "message": "智慧医保质控系统后端服务运行正常"
    }

# ==================== 认证 API ====================

@app.options("/api/auth/login")
async def login_options():
    """处理登录接口的CORS预检请求"""
    return {"message": "OK"}

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """用户登录"""
    user = authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 更新最后登录时间
    user["last_login"] = datetime.utcnow().isoformat() + "Z"

    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )

    # 创建刷新令牌（有效期更长）
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": user["email"], "type": "refresh"}, expires_delta=refresh_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "department": user["department"],
            "roles": user["roles"]
        }
    )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        display_name=current_user["display_name"],
        department=current_user["department"],
        roles=current_user["roles"]
    )

@app.post("/api/auth/logout")
async def logout():
    """用户登出"""
    return {"message": "登出成功"}

@app.post("/api/auth/refresh", response_model=LoginResponse)
async def refresh_token(refresh_token: str = Form(...)):
    """刷新token"""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")

        if email is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌"
            )

        user = DEMO_USERS.get(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        # 创建新的访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": email}, expires_delta=access_token_expires
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # 刷新令牌保持不变
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

# ==================== 注册路由 ====================

# 导入并注册规则管理路由
def register_rules_router():
    try:
        from rules_api import router as rules_router
        app.include_router(rules_router)
        logger.info("规则管理路由注册成功")
    except ImportError as e:
        logger.warning(f"无法导入规则管理路由: {e}")

# 延迟注册路由
register_rules_router()

if __name__ == "__main__":
    # 启动服务器 - 使用端口 8002
    port = int(os.getenv("YIBAO_API_PORT", "8002"))
    print(f"🚀 启动智慧医保质控系统后端服务...")
    print(f"📡 服务地址: http://0.0.0.0:{port}")
    print(f"📚 API文档: http://localhost:{port}/docs")
    print(f"🔍 健康检查: http://localhost:{port}/api/health")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
