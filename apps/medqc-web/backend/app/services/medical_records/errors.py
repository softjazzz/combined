"""medical_records 域错误。"""


class MedicalRecordsError(Exception):
    """medical_records 域基础错误。"""


class MedicalRecordsValidationError(MedicalRecordsError):
    """参数校验失败。"""


class MedicalRecordsNotFoundError(MedicalRecordsError):
    """资源不存在。"""


class MedicalRecordsConflictError(MedicalRecordsError):
    """定位不唯一，无法确定唯一用例。"""


class MedicalRecordsSourceUnavailableError(MedicalRecordsError):
    """取数来源不可用（表结构不符或读取失败）。"""


class MedicalRecordsStorageError(MedicalRecordsError):
    """存储或查询失败。"""

