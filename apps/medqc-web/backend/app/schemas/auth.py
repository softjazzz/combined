from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from ..core.settings import get_settings


settings = get_settings()


class UserBase(BaseModel):
    email: EmailStr
    display_name: str
    department: str
    phone: Optional[str] = None
    bio: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role: Optional[str] = "doctor"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


class UserResponse(UserBase):
    id: str
    roles: List[str]
    avatar: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')  # 忽略额外字段
    
    email: EmailStr
    password: str
    role: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

