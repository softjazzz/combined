"""Strata模型准入的匿名病例上下文；不持锁或修改医学材料。"""

from functools import wraps
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json

from .llm_observability import (
    current_llm_observation_context,
    llm_record_identity_context,
    opaque_observation_id,
)


@dataclass
class _PackageScope:
    package_id: str
    active: bool = True


_PACKAGE_SCOPE: ContextVar[_PackageScope | None] = ContextVar(
    "strata_rule_package", default=None
)


@contextmanager
def strata_rule_package_scope(package_id):
    """只携带既有包标识，不修改包内容；退出后失效复制给子任务的上下文。"""
    scope = _PackageScope(str(package_id or "").strip())
    token = _PACKAGE_SCOPE.set(scope)
    try:
        yield
    finally:
        scope.active = False
        _PACKAGE_SCOPE.reset(token)


def current_strata_package_key():
    context = current_llm_observation_context()
    if context.record_key_hash is None:
        return None
    scope = _PACKAGE_SCOPE.get()
    if scope is not None:
        if not scope.active or not scope.package_id:
            return None
        package = scope.package_id
    else:
        package = context.executor_key
        if not package or package in {"unclassified", "unknown", "legacy_orchestrated"}:
            return None
    # 复用现有脱敏owner；不发送原始包号、任务号或患者信息。
    material = json.dumps(
        [
            context.root_job_id,
            context.rule_set_key,
            context.rule_set_version,
            context.executor_key,
            package,
        ],
        ensure_ascii=True,
    )
    return opaque_observation_id("strata_rule_package_v1", material)


def strata_case_execution_scope(method):
    """统一服务入口可独立调用，不能只依赖批处理Worker提供病例身份。"""

    @wraps(method)
    async def scoped(service, *args, **kwargs):
        clients = (
            getattr(service, "client", None),
            getattr(service, "adjudicator_client", None),
        )
        if not any(
            getattr(client, "provider_code", None) == "strata" for client in clients
        ):
            return await method(service, *args, **kwargs)
        identity = tuple(
            str(kwargs.get(key) or "").strip()
            for key in ("source_institute_id", "source_patient_id", "source_visit_id")
        )
        with llm_record_identity_context(identity):
            return await method(service, *args, **kwargs)

    return scoped
