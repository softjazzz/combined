from pydantic import BaseModel, EmailStr, ConfigDict, Field, model_validator
from typing import Optional, List
from ..core.settings import get_settings


settings = get_settings()


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
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

    # 新语义：统一登录标识（用户名/手机号）
    account: Optional[str] = None
    # 过渡兼容：保留 email 入参，内部映射到 account
    email: Optional[EmailStr] = None
    password: str
    role: Optional[str] = None

    @model_validator(mode="after")
    def normalize_account(self):
        account = str(self.account or "").strip()
        if not account and self.email:
            account = str(self.email).strip()
        if not account:
            raise ValueError("account 或 email 至少提供一个")
        self.account = account
        return self


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class QrBrowserSecretRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    browser_secret: str = Field(min_length=32, max_length=256)


class QrConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_code: str = Field(pattern=r"^\d{6}$")

