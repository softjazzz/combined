"""业务助手试点的服务端明确授权；个人资料和页面筛选不拥有授权权力。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .business_schemas import BusinessContext
from .business_store import owner_id


class CaseGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institute_id: str = Field(min_length=1, max_length=128)
    patient_id: str = Field(min_length=1, max_length=128)
    visit_id: str = Field(min_length=1, max_length=128)

    @field_validator("institute_id", "patient_id", "visit_id")
    @classmethod
    def exact_identifier(cls, value: str) -> str:
        if not value.strip() or value != value.strip() or value == "*":
            raise ValueError("授权身份必须是明确标识")
        return value


class DepartmentGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institute_id: str = Field(min_length=1, max_length=128)
    department: str = Field(min_length=1, max_length=128)

    @field_validator("institute_id", "department")
    @classmethod
    def exact_scope(cls, value: str) -> str:
        return CaseGrant.exact_identifier(value)


class AccountGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doctor_cases: list[CaseGrant] = Field(default_factory=list)
    manager_scopes: list[DepartmentGrant] = Field(default_factory=list)


class AccessFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    accounts: dict[str, AccountGrant]


class BusinessAccess:
    def __init__(self, payload: dict):
        self.config = AccessFile.model_validate(payload)

    def grant(self, user: dict) -> AccountGrant:
        grant = self.config.accounts.get(owner_id(user))
        if grant is None:
            raise HTTPException(403, "当前账号尚未配置业务助手访问范围")
        return grant

    @staticmethod
    def require_role(user: dict, view: str) -> None:
        allowed = {"doctor", "admin", "super_admin"} if view == "doctor" else {"qc_manager", "admin", "super_admin"}
        if not set(user.get("roles") or []).intersection(allowed):
            raise HTTPException(403, "当前角色不能使用此业务读取入口")

    def require_case(self, user: dict, identity: dict) -> None:
        self.require_role(user, "doctor")
        if not any(case.model_dump() == identity for case in self.grant(user).doctor_cases):
            raise HTTPException(403, "当前病例不在账号明确授权范围内")

    def require_department(self, user: dict, institute_id: str | None, department: str | None) -> None:
        self.require_role(user, "manager")
        if not any(scope.institute_id == institute_id and scope.department == department for scope in self.grant(user).manager_scopes):
            raise HTTPException(403, "当前机构和科室不在账号明确授权范围内")

    def require_context(self, user: dict, context: BusinessContext) -> None:
        if context.view == "doctor":
            self.require_case(user, {key: getattr(context, key) for key in ("institute_id", "patient_id", "visit_id")})
            return
        self.require_department(user, context.institute_id, context.department)
        try:
            start = datetime.fromisoformat((context.completed_from or "").replace("Z", "+00:00"))
            end = datetime.fromisoformat((context.completed_to or "").replace("Z", "+00:00"))
            if not context.care_phase or start.tzinfo is None or end.tzinfo is None or start > end:
                raise ValueError("invalid_range")
        except ValueError as exc:
            raise HTTPException(422, "管理问数需要完整病例范围和带时区的质控完成日期") from exc

    def visible_scope(self, user: dict) -> dict:
        grant = self.grant(user)
        roles = set(user.get("roles") or [])
        return {
            "doctor_case_count": len(grant.doctor_cases) if roles.intersection({"doctor", "admin", "super_admin"}) else 0,
            "manager_scopes": [scope.model_dump() for scope in grant.manager_scopes] if roles.intersection({"qc_manager", "admin", "super_admin"}) else [],
        }


def get_business_access() -> BusinessAccess:
    # 不缓存授权文件：撤销后下一次恢复、查询和引用读取立即重新校验。
    configured = os.getenv("MEDQC_AGENT_ACCESS_FILE", "")
    try:
        if not configured:
            raise ValueError("missing_access_file")
        path = Path(configured)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[3] / path
        return BusinessAccess(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        raise HTTPException(503, "业务助手授权范围尚未配置或配置无效") from exc
