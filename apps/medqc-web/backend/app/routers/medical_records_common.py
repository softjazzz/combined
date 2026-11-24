"""medical_records 路由公共工具。"""

from fastapi import HTTPException

from ..services.medical_records.errors import (
    MedicalRecordsNotFoundError,
    MedicalRecordsStorageError,
    MedicalRecordsValidationError,
)


def raise_medical_records_http_error(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    from ..services.data_pipeline_settings import PipelineError
    if isinstance(exc, PipelineError):
        raise HTTPException(exc.status, exc.code) from None
    if isinstance(exc, (MedicalRecordsValidationError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if isinstance(exc, MedicalRecordsNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from None
    from ..database.clinical_connection import configured
    if configured():
        raise HTTPException(503, "clinical_source_read_unavailable") from None
    if isinstance(exc, MedicalRecordsStorageError):
        raise HTTPException(status_code=500, detail=str(exc)) from None
    raise HTTPException(status_code=500, detail=str(exc)) from None

