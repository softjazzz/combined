"""medical_records 路由公共工具。"""

from fastapi import HTTPException

from ..services.medical_records.errors import (
    MedicalRecordsConflictError,
    MedicalRecordsNotFoundError,
    MedicalRecordsSourceUnavailableError,
    MedicalRecordsStorageError,
    MedicalRecordsValidationError,
)


def raise_medical_records_http_error(exc: Exception) -> None:
    """域错误 → HTTP 状态码。

    Validation/NotFound/Conflict/SourceUnavailable 只回固定文案；存储与未预期异常一律
    回固定文案，不回显数据库异常、SQL、连接细节或患者标识。
    """

    if isinstance(exc, MedicalRecordsValidationError):
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, MedicalRecordsNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, MedicalRecordsConflictError):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, MedicalRecordsSourceUnavailableError):
        raise HTTPException(status_code=503, detail="病案数据取数来源不可用，请稍后重试")
    if isinstance(exc, MedicalRecordsStorageError):
        raise HTTPException(status_code=500, detail="病案数据存储读取失败，请稍后重试")
    raise HTTPException(status_code=500, detail="病案数据服务内部错误")

