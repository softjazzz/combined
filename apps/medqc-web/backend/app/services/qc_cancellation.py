from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar


class QCJobCancelled(Exception):
    """Raised when a running QC job has been cancelled by user request."""


_CANCELLATION_CHECK: ContextVar[Callable[[], bool] | None] = ContextVar(
    "qc_cancellation_check",
    default=None,
)


def current_cancellation_check() -> Callable[[], bool] | None:
    """Return the active cancellation predicate in the current context, if any."""
    return _CANCELLATION_CHECK.get()


@contextmanager
def cancellation_scope(
    cancellation_check: Callable[[], bool] | None,
) -> Iterator[None]:
    """Bind a cancellation predicate for nested async/sync execution.

    Nested scopes compose with outer scopes so an inner call cannot silently
    clear or mask an outer cancellation signal.
    """
    if cancellation_check is None:
        yield
        return
    outer = _CANCELLATION_CHECK.get()
    if outer is None or outer is cancellation_check:
        effective = cancellation_check
    else:
        def effective() -> bool:
            return bool(outer()) or bool(cancellation_check())

    token = _CANCELLATION_CHECK.set(effective)
    try:
        yield
    finally:
        _CANCELLATION_CHECK.reset(token)


def is_cancelled(
    cancellation_check: Callable[[], bool] | None = None,
) -> bool:
    """Check both the explicit predicate (if given) and the active ContextVar."""
    if cancellation_check is not None and bool(cancellation_check()):
        return True
    active = _CANCELLATION_CHECK.get()
    if active is not None and active is not cancellation_check and bool(active()):
        return True
    return False


def raise_if_cancelled(
    cancellation_check: Callable[[], bool] | None = None,
) -> None:
    if is_cancelled(cancellation_check):
        raise QCJobCancelled("QC job cancelled")
