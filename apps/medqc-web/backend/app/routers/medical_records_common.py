"""medical_records 路由公共工具。"""

import logging

from fastapi import HTTPException

from ..services.medical_records.errors import (
    MedicalRecordsNotFoundError,
    MedicalRecordsStorageError,
    MedicalRecordsValidationError,
)

logger = logging.getLogger(__name__)


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
        logger.warning("Clinical source read error in medical_records", exc_info=exc)
        raise HTTPException(503, "clinical_source_read_unavailable") from None
    if isinstance(exc, MedicalRecordsStorageError):
        logger.error("Medical records storage error", exc_info=exc)
        raise HTTPException(status_code=500, detail="病案数据读取失败，请稍后重试") from None
    logger.exception("Unexpected error in medical_records endpoint", exc_info=exc)
    raise HTTPException(status_code=500, detail="病案服务内部错误，请稍后重试") from None

