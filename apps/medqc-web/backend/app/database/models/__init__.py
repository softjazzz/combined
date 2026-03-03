"""CDM 数据库模型包"""
from .cdm import (
    PatientInformation,
    InpatRegistration,
    MedicalRecordFrontpage,
    MrSurgery,
    MrCost,
    Diagnosis,
    AdmissionRecord,
    DischargeRecord,
    QCResult,
)

__all__ = [
    "PatientInformation",
    "InpatRegistration",
    "MedicalRecordFrontpage",
    "MrSurgery",
    "MrCost",
    "Diagnosis",
    "AdmissionRecord",
    "DischargeRecord",
    "QCResult",
]
