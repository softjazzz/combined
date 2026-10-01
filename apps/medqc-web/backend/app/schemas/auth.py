from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator, model_validator
from typing import Optional, List
from ..core.settings import get_settings


settings = get_settings()


class UserBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    username: Optional[str] = None
    display_name: str
    # 科室是数据范围授权依据，只由管理员维护；注册时提交的值不会保存。
    department: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


PASSWORD_MIN_LENGTH = 8


class UserCreate(UserBase):
    password: str
    role: Optional[str] = "doctor"

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        # 公开注册密码下限：至少 8 位，且同时包含字母和数字。
        if (
            len(value) < PASSWORD_MIN_LENGTH
            or not any(ch.isascii() and ch.isalpha() for ch in value)
            or not any(ch.isdigit() for ch in value)
        ):
            raise ValueError(f"密码至少 {PASSWORD_MIN_LENGTH} 位，且需同时包含字母和数字")
        return value


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
