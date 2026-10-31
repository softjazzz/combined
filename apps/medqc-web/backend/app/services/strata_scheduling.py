"""Strata模型准入的匿名病例上下文；不持锁或修改医学材料。"""

from functools import wraps

from .llm_observability import llm_record_identity_context


def strata_case_execution_scope(method):
    """统一服务入口可独立调用，不能只依赖批处理Worker提供病例身份。"""
    @wraps(method)
    async def scoped(service, *args, **kwargs):
        clients = (getattr(service, "client", None), getattr(service, "adjudicator_client", None))
        if not any(getattr(client, "provider_code", None) == "strata" for client in clients):
            return await method(service, *args, **kwargs)
        identity = tuple(str(kwargs.get(key) or "").strip() for key in
                         ("source_institute_id", "source_patient_id", "source_visit_id"))
        with llm_record_identity_context(identity):
            return await method(service, *args, **kwargs)
    return scoped
