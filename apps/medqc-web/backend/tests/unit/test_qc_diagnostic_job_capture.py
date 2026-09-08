"""授权单病例跨执行/提交生命周期，不接触真实数据库或模型。"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.qc_diagnostics.capture import begin_attempt, finish_attempt, capture_committed_results
from app.services.qc_diagnostics.job_capture import DiagnosticJobCapture, diagnostic_job_lifecycle
from test_qc_diagnostic_execution_inputs import session_fixture, record
from test_qc_diagnostic_saved_result import receipt


@pytest.fixture
def observed(monkeypatch):
    from app.services import llm_observability
    monkeypatch.setattr(llm_observability, "current_llm_observation_context", lambda:
        SimpleNamespace(root_job_id="root", record_key_hash="case", executor_key="test"))


@pytest.mark.asyncio
async def test_selected_case_survives_until_commit_without_capturing_other_cases(observed):
    delivered = []
    capture = DiagnosticJobCapture(job_id="child", record_identity=("I", "P", "V"),
                                   consume=lambda data, summary: delivered.append((data, summary)))
    session, _ = session_fixture()
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        async def evaluate(identity, body):
            with diagnostic_capture.record_scope(identity):
                if identity == ("I", "P", "V"):
                    record(session)
                handle = begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"body": body})
                await asyncio.sleep(0)
                finish_attempt(handle, result={"answer": body})
        await asyncio.gather(evaluate(("I", "P", "V"), "selected"), evaluate(("I", "Q", "W"), "other"))
        assert diagnostic_capture.summary()["retained_bytes"] > 0
        with diagnostic_capture.result_scope():
            capture_committed_results((receipt(),))
    await worker("child", diagnostic_capture=capture)
    assert len(delivered) == 1
    assert len(delivered[0][0]["calls"]) == 1
    assert delivered[0][0]["calls"][0]["request"] == {"body": "selected"}
    assert delivered[0][0]["saved_result"]
    assert capture.summary()["retained_bytes"] == 0
    capture.finish(deliver=True)
    assert len(delivered) == 1


@pytest.mark.asyncio
async def test_cancellation_releases_without_delivery(observed):
    delivered = []
    capture = DiagnosticJobCapture(job_id="child", record_identity=("I", "P", "V"), consume=lambda *args: delivered.append(args))
    session, _ = session_fixture()
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        with diagnostic_capture.record_scope(("I", "P", "V")):
            record(session)
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await worker("child", diagnostic_capture=capture)
    assert not delivered
    assert capture.summary()["retained_bytes"] == 0


@pytest.mark.asyncio
async def test_expiry_clears_while_worker_still_running(observed):
    capture = DiagnosticJobCapture(job_id="child", record_identity=("I", "P", "V"), consume=lambda *args: pytest.fail("expired"), ttl_seconds=1)
    session, _ = session_fixture()
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        with diagnostic_capture.record_scope(("I", "P", "V")):
            record(session)
        await asyncio.sleep(1.05)
        assert diagnostic_capture.summary()["retained_bytes"] == 0
    await worker("child", diagnostic_capture=capture)


@pytest.mark.asyncio
async def test_wrong_job_disables_capture_not_execution():
    capture = DiagnosticJobCapture(job_id="child", record_identity=("I", "P", "V"), consume=lambda *args: pytest.fail("wrong job"))
    called = []
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        called.append(job_id)
        assert diagnostic_capture is None
    await worker("other", diagnostic_capture=capture)
    assert called == ["other"]
    assert capture.summary()["retained_bytes"] == 0


@pytest.mark.asyncio
async def test_repeated_selected_record_never_exports_first_inputs_with_later_result(observed):
    delivered = []
    capture = DiagnosticJobCapture(job_id="child", record_identity=("I", "P", "V"), consume=lambda *args: delivered.append(args))
    session, _ = session_fixture()
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        for _ in range(2):
            with diagnostic_capture.record_scope(("I", "P", "V")):
                record(session)
        with diagnostic_capture.result_scope():
            capture_committed_results((receipt(),))
    await worker("child", diagnostic_capture=capture)
    assert not delivered
    assert "duplicate_record_execution" in capture.summary()["missing_reasons"]


@pytest.mark.asyncio
async def test_local_consumer_error_does_not_fail_clinical_job(observed):
    def broken(*args):
        raise RuntimeError("private synthetic detail")
    capture = DiagnosticJobCapture(job_id="child", record_identity=("I", "P", "V"), consume=broken)
    session, _ = session_fixture()
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        with diagnostic_capture.record_scope(("I", "P", "V")):
            record(session)
        with diagnostic_capture.result_scope():
            capture_committed_results((receipt(),))
    await worker("child", diagnostic_capture=capture)
    assert "diagnostic_delivery_failed" in capture.summary()["missing_reasons"]
    assert "private" not in repr(capture.summary())
    assert capture.summary()["retained_bytes"] == 0


@pytest.mark.asyncio
async def test_disabled_job_does_not_inherit_another_capture_context():
    from app.services.qc_diagnostics.capture import capture_scope
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        assert begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"x": 1}) is None
    with capture_scope() as ambient:
        await worker("child")
        assert ambient.summary()["attempt_count"] == 0


@pytest.mark.asyncio
async def test_duplicate_worker_does_not_close_original_capture(observed):
    entered, release = asyncio.Event(), asyncio.Event()
    delivered = []
    capture = DiagnosticJobCapture(job_id="child", record_identity=("I", "P", "V"), consume=lambda *args: delivered.append(args))
    session, _ = session_fixture()
    runs = 0
    @diagnostic_job_lifecycle
    async def worker(job_id, *, diagnostic_capture=None):
        nonlocal runs
        runs += 1
        if runs > 1:
            return  # 模拟已有任务的重复派发被原 mark-running 门禁拒绝。
        with diagnostic_capture.record_scope(("I", "P", "V")):
            record(session)
        entered.set()
        await release.wait()
        with diagnostic_capture.result_scope():
            capture_committed_results((receipt(),))
    first = asyncio.create_task(worker("child", diagnostic_capture=capture))
    await entered.wait()
    await worker("child", diagnostic_capture=capture)
    release.set()
    await first
    assert len(delivered) == 1
