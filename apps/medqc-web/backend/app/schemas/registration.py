"""注册申请与审批合同，申请方不接受启用标志或可信角色。"""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


class RegistrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    username: str = Field(
        min_length=3, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]+$"
    )
    email: EmailStr | None = Field(default=None, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    institute_id: str | None = Field(default=None, min_length=1, max_length=128)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    department_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    phone: str | None = Field(None, pattern=r"^1[3-9]\d{9}$")
    password: Annotated[
        str, StringConstraints(strip_whitespace=False, min_length=12, max_length=72)
    ] = Field(repr=False)
    role: Literal["doctor"] = "doctor"

    @model_validator(mode="after")
    def department_selection(self):
        if self.department_key:
            if self.institute_id is not None or self.department is not None:
                raise ValueError("科室选项不能同时指定机构或科室文本")
        elif not (self.institute_id and self.department):
            raise ValueError("请选择申请科室")
        return self

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("口令UTF-8长度不得超过72字节")
        return value


class RegistrationStatusQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=72, repr=False)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        return RegistrationCreate.password_bytes(value)


class RegistrationReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(strict=True, ge=1)
    decision: Literal["approve", "reject"]
    comment: str = Field(min_length=1, max_length=1000)
    institute_id: str | None = Field(None, min_length=1, max_length=128)
    department: str | None = Field(None, min_length=1, max_length=100)
    roles: list[Literal["admin", "qc_manager", "qc_staff", "doctor"]] | None = Field(
        None, min_length=1, max_length=4
    )

    @model_validator(mode="after")
    def require_binding(self):
        if self.decision == "approve" and not (
            self.institute_id and self.department and self.roles
        ):
            raise ValueError("开通必须核定机构、科室及角色")
        if self.decision == "reject" and any(
            (self.institute_id, self.department, self.roles)
        ):
            raise ValueError("驳回不得同时授予业务权限")
        return self
