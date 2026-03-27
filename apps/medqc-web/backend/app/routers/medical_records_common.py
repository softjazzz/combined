"""medical_records 路由公共工具。"""

from fastapi import HTTPException

from ..services.medical_records.errors import (
    MedicalRecordsNotFoundError,
    MedicalRecordsStorageError,
    MedicalRecordsValidationError,
)


def raise_medical_records_http_error(exc: Exception) -> None:
    if isinstance(exc, MedicalRecordsValidationError):
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, MedicalRecordsNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, MedicalRecordsStorageError):
        raise HTTPException(status_code=500, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))

