"""
认证工具模块
避免循环导入问题
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext

# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET", "yibao-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Demo 用户数据
DEMO_USERS = {
    "admin@yibao.com": {
        "id": "admin-001",
        "email": "admin@yibao.com",
        "display_name": "系统管理员",
        "department": "医保办",
        "roles": ["admin", "user"],
        "password_hash": pwd_context.hash("admin123")
    },
    "doctor@yibao.com": {
        "id": "doctor-001",
        "email": "doctor@yibao.com",
        "display_name": "医生用户",
        "department": "内科",
        "roles": ["doctor", "user"],
        "password_hash": pwd_context.hash("doctor123")
    },
    "auditor@yibao.com": {
        "id": "auditor-001",
        "email": "auditor@yibao.com",
        "display_name": "质控审核员",
        "department": "质控科",
        "roles": ["auditor", "user"],
        "password_hash": pwd_context.hash("auditor123")
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """验证令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    token = credentials.credentials
    payload = verify_token(token)
    email = payload.get("sub")
    
    # 从 Demo 用户中查找
    user = DEMO_USERS.get(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "department": user["department"],
        "roles": user["roles"]
    }

def authenticate_user(email: str, password: str):
    """认证用户"""
    user = DEMO_USERS.get(email)
    if not user:
        return False
    if not verify_password(password, user["password_hash"]):
        return False
    return user
