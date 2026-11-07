"""配置收口：覆盖后台保存后实际重载链；仅由严格离线入口运行。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.core.settings import Settings
from app.services import llm_config_loader as loader, qc_llm_client
from app.services import sichuan_qc_service as service_module
from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
from app.services.llm_task_roles import TASK_ROLES_KEY


@pytest.mark.asyncio
async def test_service_reload_preserves_roles_at_actual_formal_http_exit(monkeypatch):
    """页面保存会调用此重载；不能在重建二审客户端时丢掉已保存的三个用途。"""
    settings = Settings(
        _env_file=None, JWT_SECRET="synthetic-only", LLM_VISIBLE_PROVIDERS=["alibaba"],
        LLM_DEFAULT_PROVIDER="alibaba", LLM_DISPATCH_MODE="direct",
        DASHSCOPE_BASE_URL="https://synthetic.invalid/v1", DASHSCOPE_API_KEY="synthetic-only",
        LLM_ADJUDICATOR_MODEL="legacy-default", LLM_ROLE_MODELS=None,
    )
    for module in (loader, qc_llm_client, service_module):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    roles = {
        "fact_extraction": {"provider_code": "alibaba", "model_code": "synthetic-facts"},
        "judgment_analysis": {"provider_code": "alibaba", "model_code": "synthetic-analysis"},
        "specialty_verification": {"provider_code": "alibaba", "model_code": "synthetic-check"},
    }
    runtime = loader.build_provider_runtime_config("alibaba", "synthetic-default", {
        TASK_ROLES_KEY: roles, loader.QC_USE_SELECTED_MODEL_KEY: True,
        "enable_thinking": False, "max_tokens": 4096,
    })

    async def saved_config(*_args, **_kwargs):
        return deepcopy(runtime)

    monkeypatch.setattr(loader.LLMConfigLoader, "load_config", saved_config)
    monkeypatch.setattr(service_module, "configure_shared_http_max_concurrency", lambda *_: None)
    sent = []

    async def fixed_response(*_args, **kwargs):
        sent.append(deepcopy(kwargs["payload"]))
        return {"choices": [{"finish_reason": "stop", "message": {"content": "合成应答"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}}

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed_response)
    service = service_module.SichuanQCService.__new__(service_module.SichuanQCService)
    recorder = LLMObservabilityRecorder(store=NullLLMCallEventStore())
    service.client = qc_llm_client.SichuanQCLLMClient(runtime, observability_recorder=recorder)
    service.adjudicator_client = qc_llm_client.SichuanQCLLMClient(
        loader.build_adjudicator_runtime_config(runtime), observability_recorder=recorder,
    )
    service.prompt_builder = SimpleNamespace()

    assert await service.reload_config()
    assert service.client.task_role_selections == roles
    for role in roles:
        await service.adjudicator_client.for_task_role(role).generate("合成原文", max_completion_tokens=64)
    assert [item["model"] for item in sent] == [spec["model_code"] for spec in roles.values()]
    assert all(item["enable_thinking"] is False for item in sent)
    assert all(item["max_tokens"] == 64 for item in sent)
    assert all(TASK_ROLES_KEY not in item for item in sent)
    assert service.adjudicator_client.model == "synthetic-default"
    assert service.adjudicator_client.task_role_selections == roles
    assert service.adjudicator_client.task_role_identity == service.client.task_role_identity
