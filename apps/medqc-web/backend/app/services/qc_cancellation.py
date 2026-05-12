from __future__ import annotations

from collections.abc import Callable


class QCJobCancelled(Exception):
    """Raised when a running QC job has been cancelled by user request."""


def raise_if_cancelled(cancellation_check: Callable[[], bool] | None) -> None:
    if cancellation_check is not None and bool(cancellation_check()):
        raise QCJobCancelled("QC job cancelled")
