"""默认关闭的内存旁路；只使用合成请求，无数据库、网络和文件写入。"""

import asyncio
from uuid import uuid4

import pytest

from app.services.qc_diagnostics.capture import capture_scope, begin_attempt, finish_attempt


def test_default_off_does_not_inspect_payload():
    class Unsafe:
        def __repr__(self):
            pytest.fail("must not inspect")
    assert begin_attempt(logical_call_id="invalid", attempt_no=1, payload=Unsafe()) is None
    finish_attempt(None, result=Unsafe())


def test_request_and_response_frozen_before_business_mutation():
    request = {"messages": [{"role": "user", "content": "synthetic"}], "model": "test"}
    response = {"choices": [{"message": {"content": "<think>synthetic</think>answer"}}]}
    with capture_scope() as capture:
        handle = begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload=request)
        request["messages"][0]["content"] = "changed"
        finish_attempt(handle, result=response)
        response["choices"][0]["message"]["content"] = "answer"
        calls = capture.read_internal()["calls"]
        assert calls[0]["request"]["messages"][0]["content"] == "synthetic"
        assert calls[0]["response"]["choices"][0]["message"]["content"].startswith("<think>")
        calls[0]["request"].clear()
        assert capture.read_internal()["calls"][0]["request"]
    assert capture.summary()["closed"]
    assert capture.summary()["retained_bytes"] == 0


@pytest.mark.asyncio
async def test_concurrent_cases_retries_do_not_share_fifo():
    logical_id = str(uuid4())
    async def one(label):
        with capture_scope() as capture:
            first = begin_attempt(logical_call_id=logical_id, attempt_no=1, payload={"label": label})
            await asyncio.sleep(0)
            finish_attempt(first, error_kind="timeout")
            second = begin_attempt(logical_call_id=logical_id, attempt_no=2, payload={"label": label})
            await asyncio.sleep(0)
            finish_attempt(second, result={"answer": label})
            return capture.read_internal()
    first, second = await asyncio.gather(one("one"), one("two"))
    assert first["calls"][1]["response"]["answer"] == "one"
    assert second["calls"][1]["response"]["answer"] == "two"
    assert first["calls"][0]["error_kind"] == "timeout"


def test_duplicate_unfinished_and_late_result_are_partial():
    logical_id = str(uuid4())
    with capture_scope() as capture:
        handle = begin_attempt(logical_call_id=logical_id, attempt_no=1, payload={"x": 1})
        assert begin_attempt(logical_call_id=logical_id, attempt_no=1, payload={"x": 2}) is None
        assert capture.summary()["capture_completeness"] == "partial"
        assert capture.read_internal()["calls"][0]["request"] == {"x": 1}
    finish_attempt(handle, result={"secret": "late"})
    assert capture.summary()["retained_bytes"] == 0


def test_quota_and_credentials_fail_only_capture():
    with capture_scope(max_bytes=100) as capture:
        assert begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"data": "x" * 200}) is None
        assert "capacity_exceeded" in capture.summary()["missing_reasons"]
    with capture_scope() as capture:
        assert begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"Authorization": "secret"}) is None
        assert capture.summary()["capture_completeness"] == "partial"
        assert "secret" not in repr(capture)


def test_expiry_releases_content(monkeypatch):
    with capture_scope(ttl_seconds=1) as capture:
        handle = begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"data": "synthetic"})
        monkeypatch.setattr("app.services.qc_diagnostics.capture.time.monotonic", lambda: float("inf"))
        finish_attempt(handle, result={"answer": "late"})
        assert capture.summary()["retained_bytes"] == 0
        assert "expired" in capture.summary()["missing_reasons"]


def test_one_scope_rejects_different_case_observation_context(monkeypatch):
    from types import SimpleNamespace
    from app.services import llm_observability
    context = SimpleNamespace(root_job_id="job", record_key_hash="record-one", executor_key="consultation")
    monkeypatch.setattr(llm_observability, "current_llm_observation_context", lambda: context)
    with capture_scope() as capture:
        begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"synthetic": 1})
        assert capture.read_internal()["calls"][0]["executor_key"] == "consultation"
        context.record_key_hash = "record-two"
        assert begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"synthetic": 2}) is None
        assert "case_context_mismatch" in capture.summary()["missing_reasons"]


def test_nested_readonly_mapping_cannot_hide_credentials():
    from types import MappingProxyType
    with capture_scope() as capture:
        assert begin_attempt(logical_call_id=str(uuid4()), attempt_no=1,
                             payload={"nested": MappingProxyType({"api_key": "secret"})}) is None
        assert capture.read_internal()["calls"] == []


@pytest.mark.asyncio
async def test_real_client_seam_preserves_result_headers_and_call_count(monkeypatch):
    from unittest.mock import AsyncMock
    from app.services import qc_llm_client
    recorder = type("Recorder", (), {})()
    recorder.start_attempt = AsyncMock(return_value=(None, 0))
    recorder.finish_attempt = AsyncMock()
    client = qc_llm_client.SichuanQCLLMClient(config={"api_endpoint": "http://unused", "api_key": "not-recorded", "model": "test"}, observability_recorder=recorder)
    response = {"choices": [{"message": {"content": "synthetic-answer"}}]}
    network = AsyncMock(return_value=response)
    monkeypatch.setattr(qc_llm_client, "safe_post_json", network)
    with capture_scope() as capture:
        returned, _ = await client._perform_observed_attempt(logical_call_id=str(uuid4()), attempt_no=1,
                                                            headers={"Authorization": "not-recorded"}, payload={"model": "test"})
        assert returned is response
        assert network.await_count == 1
        assert "not-recorded" not in str(capture.read_internal())
        assert capture.read_internal()["calls"][0]["response"] == response


@pytest.mark.asyncio
async def test_client_capture_failure_and_cancellation_do_not_change_clinical_control(monkeypatch):
    from unittest.mock import AsyncMock
    from app.services import qc_llm_client
    recorder = type("Recorder", (), {})()
    recorder.start_attempt = AsyncMock(return_value=(None, 0))
    recorder.finish_attempt = AsyncMock()
    client = qc_llm_client.SichuanQCLLMClient(config={"api_endpoint": "http://unused", "api_key": "dummy", "model": "test"}, observability_recorder=recorder)
    network = AsyncMock(return_value={"choices": []})
    monkeypatch.setattr(qc_llm_client, "safe_post_json", network)
    with capture_scope(max_bytes=1) as capture:
        returned, _ = await client._perform_observed_attempt(logical_call_id=str(uuid4()), attempt_no=1, headers={}, payload={"x": "y"})
        assert returned == {"choices": []}
        assert "capacity_exceeded" in capture.summary()["missing_reasons"]
    network.side_effect = asyncio.CancelledError()
    with capture_scope() as capture:
        with pytest.raises(asyncio.CancelledError):
            await client._perform_observed_attempt(logical_call_id=str(uuid4()), attempt_no=1, headers={}, payload={"x": "y"})
        assert capture.read_internal()["calls"][0]["finished"]
