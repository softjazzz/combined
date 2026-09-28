"""单次验收调用的资料作用域；普通质控无覆盖，不传播人工答案。"""
from contextlib import contextmanager
from contextvars import ContextVar

_CURRENT = ContextVar("test_case_validation_material", default=None)


@contextmanager
def validation_material_scope(reference, job):
    token = _CURRENT.set((reference, job) if reference is not None else None)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def build_validation_execution_session(builder, **parameters):
    current = _CURRENT.get()
    if current is None:
        return builder(**parameters)
    from .test_case_validation import TestCaseValidationService
    reference, job = current
    return TestCaseValidationService().execution_session(
        reference=reference, job=job, builder=builder, parameters=parameters)


def validation_material_active():
    return _CURRENT.get() is not None
