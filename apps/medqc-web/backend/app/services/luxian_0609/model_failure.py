"""模型调用边界的受控异常分类；不输出异常文字、响应、URL 或凭据。"""

from __future__ import annotations

import logging
from pathlib import Path
import re



def classify_model_failure(error: Exception, *, stage: str = "call") -> tuple[str, str, bool]:
    """返回诊断类别、失败原因码和是否属于瞬时上游错误。"""
    from ..qc_execution_errors import safe_exception_failure

    failure = safe_exception_failure(error, stage=stage)
    return failure["error_category"], failure["reason_code"], failure["retryable"]


def log_model_failure(logger: logging.Logger, *, rule: str, stage: str, error: Exception) -> None:
    kind, _, _ = classify_model_failure(error, stage=stage)
    trace = error.__traceback__
    while trace is not None and trace.tb_next is not None:
        trace = trace.tb_next
    origin = "unknown"
    line = 0
    if trace is not None:
        basename = Path(trace.tb_frame.f_code.co_filename).stem
        function = trace.tb_frame.f_code.co_name
        if all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,100}", item) for item in (basename, function)):
            origin = f"{basename}:{function}"
            line = trace.tb_lineno
    exception_type = type(error).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,80}", exception_type):
        exception_type = "Exception"
    logger.warning("LX0609_MODEL_FAILURE rule=%s stage=%s kind=%s exception_type=%s origin=%s line=%s",
                   rule, stage, kind, exception_type, origin, line)
