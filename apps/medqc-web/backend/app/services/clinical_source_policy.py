"""部署级普通临床来源策略；不连接数据库、不改变历史或材料来源。"""

import os

FIXED = "fixed_donghua_cdm"
COMPAT = "legacy_compat"


def fixed_cdm():
    mode = os.getenv("MEDQC_CLINICAL_SOURCE_MODE", FIXED).strip()
    if mode not in {FIXED, COMPAT}:
        raise ValueError("clinical_source_mode_invalid")
    return mode == FIXED


def require_legacy_sync():
    if fixed_cdm():
        raise ValueError("legacy_sync_disabled_in_fixed_cdm")


def legacy_sync_operation(function):
    from functools import wraps

    @wraps(function)
    def guarded(*args, **kwargs):
        require_legacy_sync()
        return function(*args, **kwargs)

    return guarded
