"""
认证相关的数据模型
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """登录请求"""
    email: EmailStr
    password: str
    role: Optional[str] = None


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    """用户信息响应"""
    id: str
    email: str
    display_name: Optional[str] = None
    department: Optional[str] = None
    hospital_id: Optional[str] = None
    roles: list[str] = []
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None


class RegisterRequest(BaseModel):
    """注册请求"""
    email: EmailStr
    password: str
    display_name: str
    role: str = "coder"
    department: Optional[str] = None
    hospital_id: Optional[str] = None
