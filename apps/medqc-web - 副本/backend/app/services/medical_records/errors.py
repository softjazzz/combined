"""medical_records 域错误。"""


class MedicalRecordsError(Exception):
    """medical_records 域基础错误。"""


class MedicalRecordsValidationError(MedicalRecordsError):
    """参数校验失败。"""


class MedicalRecordsNotFoundError(MedicalRecordsError):
    """资源不存在。"""


class MedicalRecordsStorageError(MedicalRecordsError):
    """存储或查询失败。"""

