"""合成错误穿过模型包装器、失败清单和补跑计划，不发起真实请求。"""

import httpx
import pytest

from app.services.qc_execution_errors import safe_exception_failure, safe_failure_projection
from app.services.qc_llm_client import SichuanQCLLMClient
from app.services.llm_dispatch.client import GatewayDispatchError
from app.services.luxian_0609.llm_prompt_privacy import (
    _Luxian0609PrivacyRedactingLLMClient, classify_luxian_0609_llm_call_failure,
)
from app.services.qc_workspace.execution_failure import _build_luxian_execution_failure_record
from app.services.qc_workspace.failed_rule_retry import build_failed_rule_auto_retry_plan


@pytest.mark.parametrize("status,reason,retryable", [
    (400, "model_http_error", False), (401, "model_http_error", False),
    (403, "model_http_error", False), (404, "model_http_error", False),
    (422, "model_http_error", False), (408, "model_timeout", True),
    (429, "model_rate_limited", True), (503, "model_upstream_error", True),
    (None, "execution_failed", False),
])
@pytest.mark.asyncio
async def test_http_failure_keeps_safe_category_and_bounded_retry(monkeypatch, status, reason, retryable):
    import app.services.luxian_0609.llm_prompt_privacy as privacy
    import app.services.luxian_0609.execution_time_budget as budget
    async def no_sleep(_):
        pass
    monkeypatch.setattr(privacy.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(budget, "retry_fits", lambda **_: True)

    class Delegate:
        calls = 0
        timeout_seconds = 1
        async def generate(self, *_args, **_kwargs):
            self.calls += 1
            SichuanQCLLMClient._raise_for_upstream_error(None, {
                "__error__": True, "__status__": status,
                "body": {"message": "患者正文 SECRET https://u:credential@host/path?token=secret"},
            })
    delegate = Delegate()
    with pytest.raises(RuntimeError) as caught:
        await _Luxian0609PrivacyRedactingLLMClient(delegate).generate("合成测试")
    assert delegate.calls == (3 if retryable else 1)
    failure = safe_exception_failure(caught.value)
    assert failure["reason_code"] == reason
    assert failure["retryable"] is retryable
    assert classify_luxian_0609_llm_call_failure(caught.value) == reason
    record = _build_luxian_execution_failure_record(
        rule_job_id="synthetic", rule_id="LX0609-06-01-05", rule_code="LX0609-06-01-05",
        rule_name="合成规则", record_id="v", record_key="i:p:v", institute_id="i",
        patient_id="p", visit_id="v", raw_status="technical_error", eval_item=failure, metadata={},
    )
    assert record["reason_code"] == reason and record["retryable"] is retryable
    plan = build_failed_rule_auto_retry_plan(summary={"execution_status": "failed"}, failures=[record])
    assert plan["should_retry"] is retryable
    assert build_failed_rule_auto_retry_plan(summary={"execution_status": "failed"}, failures=[record],
                                            retry_scope={"attempt": 3})["should_retry"] is False
    for secret in ("患者正文", "SECRET", "credential", "https://", "token="):
        assert secret not in str(caught.value) + str(record)


@pytest.mark.parametrize("error,reason,retryable", [
    (httpx.ReadTimeout("SECRET"), "model_timeout", True),
    (GatewayDispatchError("gateway_provider_timeout", retryable=True), "model_timeout", True),
    (GatewayDispatchError("gateway_provider_rejected", retryable=False), "model_http_error", False),
    (GatewayDispatchError("gateway_provider_rejected", retryable=True, status_code=502), "model_http_error", False),
    (GatewayDispatchError("gateway_provider_rejected", retryable=True, status_code=503), "model_upstream_error", True),
    (GatewayDispatchError("gateway_invalid_auth", retryable=True), "model_configuration_error", False),
    (GatewayDispatchError("unknown_SECRET", retryable=True), "execution_program_error", False),
    (GatewayDispatchError("gateway_error", retryable=True, status_code=429), "model_rate_limited", True),
    (RuntimeError("upstream_http_error upstream_http_status=unknown SECRET"), "execution_program_error", False),
    (RuntimeError("SECRET"), "execution_program_error", False),
])
def test_gateway_and_unknown_errors_do_not_gain_retry_permission(error, reason, retryable):
    failure = safe_exception_failure(error)
    assert failure["reason_code"] == reason
    assert failure["retryable"] is retryable
    assert "SECRET" not in str(failure)


@pytest.mark.parametrize("status,retryable", [(400, False), (401, False), (403, False), (404, False),
                                              (408, True), (429, True), (503, True)])
def test_gateway_provider_http_contract_preserves_deterministic_and_transient_split(status, retryable):
    from app.llm_gateway.providers import ProviderHTTPError
    provider_error = ProviderHTTPError(status)
    worker_error = GatewayDispatchError(provider_error.code, retryable=provider_error.retryable,
                                       status_code=provider_error.status_code)
    assert worker_error.retryable is retryable
    assert safe_exception_failure(worker_error)["retryable"] is retryable


def test_terminal_flag_survives_legacy_executor_that_only_carries_reason_code():
    error = GatewayDispatchError("gateway_provider_timeout", retryable=False)
    reason = classify_luxian_0609_llm_call_failure(error)
    # 真实旧执行器仅传原因码，不传异常对象/属性，不能因此重新允许自动重试。
    result = safe_failure_projection({"reason_code": reason})
    assert result["reason_code"] == "model_retry_stopped"
    assert result["retryable"] is False


@pytest.mark.parametrize("reason", ["model_http_error", "model_configuration_error", "arbitrary_secret",
                                  "data_gap", "material_capture_failed", "candidate_scope_incomplete"])
def test_explicit_true_cannot_make_deterministic_unknown_or_material_failure_retryable(reason):
    failure = safe_failure_projection({"reason_code": reason, "retryable": True, "error": "SECRET"})
    assert failure["retryable"] is False
    assert "SECRET" not in str(failure)
    assert build_failed_rule_auto_retry_plan(summary={"execution_status": "failed"},
        failures=[{"error_phase": "result_status", "rule_id": "LX0609-06-01-05", **failure}])["should_retry"] is False


@pytest.mark.asyncio
async def test_direct_client_transport_exception_does_not_expose_request_or_raw_error(monkeypatch):
    import app.services.qc_llm_client as client_module

    async def fail(**_kwargs):
        raise httpx.ReadTimeout("患者正文 SECRET https://user:password@host/path")

    monkeypatch.setattr(client_module, "safe_post_json", fail)
    client = SichuanQCLLMClient(config={"api_endpoint": "https://synthetic.invalid/v1",
                                      "api_key": "synthetic", "model": "synthetic"})
    with pytest.raises(RuntimeError) as caught:
        await client.generate("合成输入")
    assert caught.value.reason_code == "model_timeout"
    assert caught.value.retryable is True
    assert caught.value.__suppress_context__ is True
    assert "SECRET" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.usefixtures("workspace_tables_without_database")
@pytest.mark.parametrize("rejection", [403, 503, "unexpected", "provider_configuration"])
async def test_automatic_retry_rejection_keeps_completed_source_untouched(monkeypatch, caplog, rejection):
    import copy
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.services import sichuan_workspace_batch_worker as worker
    from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
    from test_qc_sichuan_batch_throughput import (
        _WorkspaceStub, _ServiceStub, _configure_formal_customer_sample_batch_fixture,
        _freeze_formal_customer_batch_fixture_runtime,
    )

    completed = []
    retries = []
    mutations = []

    class Workspace(_WorkspaceStub):
        def mark_batch_job_running(self, **kwargs):
            assert super().mark_batch_job_running(**kwargs)
            return "synthetic-claim"

        def is_batch_job_canceled_or_missing(self, **_kwargs):
            return False

        def update_batch_job_progress(self, **kwargs):
            kwargs.pop("attempt_filters_json", None)
            super().update_batch_job_progress(**kwargs)
            return True

        def complete_batch_job(self, **kwargs):
            kwargs.pop("attempt_filters_json", None)
            super().complete_batch_job(**kwargs)
            completed.append(copy.deepcopy(self.job))
            return True

        def retry_batch_job(self, **kwargs):
            retries.append(kwargs)
            if rejection == "unexpected":
                raise RuntimeError("SECRET enqueue failed")
            if rejection == "provider_configuration":
                raise worker.ProviderConfigurationError("SECRET configuration failure")
            raise HTTPException(status_code=rejection, detail="SECRET source or permission rejection")

        def mark_failed_rule_auto_retry_enqueue_failed(self, **kwargs):
            mutations.append(("mark", kwargs))

        def fail_batch_job(self, **kwargs):
            mutations.append(("fail", kwargs))
            super().fail_batch_job(**kwargs)

    workspace = Workspace()
    rule_id = "LX0609-01-01-01"
    rule = get_luxian_0609_rule(rule_id)
    _configure_formal_customer_sample_batch_fixture(workspace, rule_ids=[rule_id], record_ids=["visit-001"])
    workspace.job["created_by"] = "synthetic-user"
    service = _ServiceStub()
    settings = _freeze_formal_customer_batch_fixture_runtime(workspace, service)

    async def evaluate(**_kwargs):
        return {"evaluation_results": [{"rule_id": rule_id, "rule_version": rule["rule_version"],
            "schema_version": "lx0609-customer-result-v2", "status": "technical_error",
            "reason_code": "model_timeout", "metadata": {"technical_error_internal": True}}],
            "token_usage": {}, "luxian_0609_usage_observation_complete": True}

    service.evaluate_running_final_bundle_input = evaluate
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "load_luxian_0609_rules", lambda: [rule])
    monkeypatch.setattr(worker, "get_product_activation_service", lambda: SimpleNamespace(enforce=lambda: None))
    async def provider():
        return service
    await worker.run_sichuan_workspace_batch_job(workspace.job["id"], workspace=workspace,
                                                qc_service_provider=provider)
    assert len(completed) == len(retries) == 1
    assert retries[0]["expected_attempt_filters_json"] == "synthetic-claim"
    assert completed[0]["status"] == "failed"
    assert completed[0]["summary"]["automatic_failed_rule_retry"]["should_retry"] is True
    assert workspace.job == completed[0]
    assert mutations == []
    assert "SECRET" not in caplog.text


@pytest.mark.parametrize("code", [
    "task_settings_missing", "task_settings_changed", "task_runtime_missing",
    "task_runtime_changed", "task_scope_invalid",
])
def test_task_contract_failure_preserves_only_typed_controlled_code(code):
    from app.services.task_execution_contract import TaskExecutionContractError

    failure = safe_exception_failure(TaskExecutionContractError(code, "SECRET"))
    assert failure["reason_code"] == code
    assert failure["error_category"] == "execution_contract"
    assert failure["retryable"] is False
    assert "SECRET" not in str(failure)
    assert safe_exception_failure(ValueError(code))["reason_code"] == "execution_program_error"
    assert safe_exception_failure(TaskExecutionContractError("SECRET", "SECRET"))["reason_code"] == "execution_program_error"


@pytest.mark.parametrize("error_type", ["PatientPrivacyViolation", "PrivacyIdentityContextError"])
def test_shared_model_boundary_preserves_privacy_guard_category(error_type):
    from app.services.luxian_0609 import llm_prompt_privacy
    from app.services.luxian_0609.model_failure import classify_model_failure

    error = getattr(llm_prompt_privacy, error_type)("SECRET")
    assert classify_model_failure(error) == ("privacy_guard", "privacy_guard_blocked", False)
    assert "SECRET" not in str(safe_exception_failure(error))


def test_executor_timeout_retry_budget_remains_bounded():
    from app.services.qc_workspace.failed_rule_retry import build_failed_rule_auto_retry_plan
    failure = {"reason_code": "executor_timeout", "error_phase": "result_status", "rule_id": "LX0609-01-01-01"}
    summary = {"execution_status": "partial_failed"}
    first = build_failed_rule_auto_retry_plan(summary=summary, failures=[failure])
    last = build_failed_rule_auto_retry_plan(summary=summary, failures=[failure], retry_scope={"attempt": 3})
    assert first["should_retry"] is True and first["next_attempt"] == 1
    assert last["should_retry"] is False and last["status"] == "exhausted"
