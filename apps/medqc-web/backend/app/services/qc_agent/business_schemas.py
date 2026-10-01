"""业务助手的页面上下文与只读工具合同。"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BusinessContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    view: Literal["doctor", "manager"]
    institute_id: str | None = Field(default=None, max_length=128)
    patient_id: str | None = Field(default=None, max_length=128)
    visit_id: str | None = Field(default=None, max_length=128)
    patient_name: str | None = Field(default=None, max_length=128)
    document_id: str | None = Field(default=None, max_length=256)
    department: str | None = Field(default=None, max_length=128)
    care_phase: Literal["inpatient", "discharged"] | None = None
    completed_from: str | None = Field(default=None, max_length=64)
    completed_to: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def require_doctor_identity(self):
        if self.view == "doctor" and not all((self.institute_id, self.patient_id, self.visit_id)):
            raise ValueError("医生助手需要当前病例的机构、患者和住院标识")
        return self


class BusinessSessionCreate(BaseModel):
    context: BusinessContext


class BusinessChat(BaseModel):
    run_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    reference_id: str | None = Field(default=None, min_length=1, max_length=200)


class BusinessStop(BaseModel):
    run_id: UUID
