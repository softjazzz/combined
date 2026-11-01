"""热重载后通用执行器必须使用本服务当前客户端。"""

import pytest
from types import SimpleNamespace

from app.core.settings import Settings
from app.services import llm_config_loader, qc_llm_client
from app.services.sichuan_qc_service import SichuanQCService
from app.services.llm_observability import current_llm_observation_context, llm_observation_context
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.strata_scheduling import strata_case_execution_scope


@pytest.mark.asyncio
async def test_generic_engine_switches_to_new_client_and_isolated_runtime_keeps_old(monkeypatch):
    settings = Settings(_env_file=None, JWT_SECRET="synthetic", LLM_VISIBLE_PROVIDERS=["alibaba", "strata"],
        STRATA_API_ENDPOINT="http://strata.test/v1", STRATA_MODEL="local", LLM_ROLE_MODELS=None)
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_llm_client, "get_settings", lambda: settings)
    seen = []

    async def fixed(self, prompt, **kwargs):
        seen.append((self.provider_code, self.model, prompt))
        return {"choices": [{"message": {"content": "fixed"}}], "usage": {}}

    monkeypatch.setattr(qc_llm_client.SichuanQCLLMClient, "generate", fixed)
    service = SichuanQCService(llm_config_loader.build_provider_runtime_config("alibaba"))
    isolated = service.isolated_luxian_0609_runtime()
    old = service.client

    async def load(*args, **kwargs):
        return llm_config_loader.build_provider_runtime_config("strata")

    monkeypatch.setattr(llm_config_loader.LLMConfigLoader, "load_config", load)
    assert await service.reload_config()
    await service.rule_engine._llm_generate("原Prompt逐字保留")
    await isolated.rule_engine._llm_generate("原Prompt逐字保留")
    assert seen == [("strata", "local", "原Prompt逐字保留"), ("alibaba", old.model, "原Prompt逐字保留")]
    assert isolated.client is not service.client
    assert old.provider_code == "alibaba"


@pytest.mark.asyncio
async def test_service_case_scope_fills_identity_preserves_job_and_restores_after_call():
    class Service:
        client = SimpleNamespace(provider_code="strata")

        @strata_case_execution_scope
        async def evaluate(self, **kwargs):
            return current_llm_observation_context()

    identity = {"source_institute_id": "synthetic", "source_patient_id": "a", "source_visit_id": "v"}
    with llm_observation_context(business_scene="synthetic", root_job_id="job", executor_key="executor"):
        value = await Service().evaluate(**identity)
        assert value.root_job_id == "job" and value.executor_key == "executor"
        assert value.record_key_hash and len(value.record_key_hash) == 64
        assert current_llm_observation_context().record_key_hash is None
    with llm_observation_context(business_scene="synthetic", record_identity=("synthetic", "a", "v")):
        expected = current_llm_observation_context()
        assert await Service().evaluate(**identity) == expected
        with pytest.raises(ProviderConfigurationError):
            await Service().evaluate(**{**identity, "source_patient_id": "different"})
        assert current_llm_observation_context() == expected


@pytest.mark.asyncio
async def test_scope_does_not_invent_case_identity_from_partial_coordinates_or_touch_cloud():
    class Service:
        client = SimpleNamespace(provider_code="strata")

        @strata_case_execution_scope
        async def evaluate(self, **kwargs):
            return current_llm_observation_context().record_key_hash

    assert await Service().evaluate(source_visit_id="v") is None
    Service.client = SimpleNamespace(provider_code="alibaba")
    assert await Service().evaluate(source_institute_id="synthetic", source_patient_id="a", source_visit_id="v") is None
