from pydantic import BaseModel
from typing import Optional


class MedicalRecordBase(BaseModel):
    patient_name: str
    patient_age: int
    patient_gender: str
    department: str
    admission_date: str
    record_type: str
    content: str


class MedicalRecordResponse(MedicalRecordBase):
    id: str
    status: str
    created_at: str
    updated_at: str
    created_by: str
    file_url: Optional[str] = None

