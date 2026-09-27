"""当次资料旁路：合成 session，禁止重新读取资料和导出原件。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.qc_diagnostics.capture import capture_scope, capture_execution_inputs, begin_attempt
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows, SourceEvidenceQueryError


def session_fixture():
    calls = []
    def reader(**kwargs):
        key = kwargs["source_key"]
        calls.append(key)
        if key == "admission_record":
            rows = [{"record_content": None}, {"record_content": ""}, {"record_content": ""}]
            return SnapshotSourceRows.create(source_key=key, rows=rows, truncated=True, limit_rows=3)
        if key == "inpat_registration":
            rows = [{"admission_datetime": "2026-07-01 08:00:00"}]
        elif key == "inpat_registration.discharge_horizon":
            rows = [{"discharge_datetime": "2026-07-03 08:00:00"}]
        else:
            raise SourceEvidenceQueryError("DO_NOT_CAPTURE_EXCEPTION")
        return SnapshotSourceRows.create(source_key=key, rows=rows, truncated=False, limit_rows=7)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-03-01-01", "LX0609-03-01-04"), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-05T00:00:00+08:00", evaluation_as_of_date="2026-07-05",
        additional_source_keys=("admission_record",), row_reader=reader,
    )
    return session, calls


def record(session):
    capture_execution_inputs(session, selected_rule_ids=("LX0609-03-01-01", "LX0609-03-01-04"),
                             evaluation_as_of_date="2026-07-05", evaluation_horizon_policy=None,
                             horizon_unavailable_reason=None)


def test_off_never_inspects_session():
    class Unsafe:
        def __getattribute__(self, name):
            pytest.fail("disabled capture inspected session")
    record(Unsafe())


def test_exact_materials_and_full_facts_not_safe_summary(monkeypatch):
    session, calls = session_fixture()
    before = list(calls)
    with capture_scope() as capture:
        record(session)
        inputs = capture.read_internal()["execution_inputs"]
        assert inputs["sources"]["admission_record"]["rows"] == (
            {"record_content": None}, {"record_content": ""}, {"record_content": ""})
        assert inputs["sources"]["admission_record"]["limit_rows"] == 3
        assert inputs["sources"]["admission_record"]["truncated"] is True
        assert inputs["snapshot"]["facts"] == [fact.to_dict() for fact in session.snapshot.facts]
        assert any("normalized_value" in fact for fact in inputs["snapshot"]["facts"])
        assert inputs["evaluation_as_of_date"] == "2026-07-05"
        assert "DO_NOT_CAPTURE_EXCEPTION" not in repr(inputs)
        assert calls == before
        inputs.clear()
        assert capture.read_internal()["execution_inputs"]
        assert "execution_inputs_not_captured" not in capture.summary()["missing_reasons"]
        assert "execution_sources_incomplete" in capture.summary()["missing_reasons"]
        assert "final_result_not_captured" in capture.summary()["missing_reasons"]
    assert capture.summary()["retained_bytes"] == 0


def test_duplicate_capture_keeps_first_and_rejects_case_change(monkeypatch):
    from app.services import llm_observability
    context = SimpleNamespace(root_job_id="job", record_key_hash="first", executor_key="consultation")
    monkeypatch.setattr(llm_observability, "current_llm_observation_context", lambda: context)
    session, _ = session_fixture()
    with capture_scope() as capture:
        record(session)
        size = capture.summary()["retained_bytes"]
        record(session)
        assert capture.summary()["retained_bytes"] == size
        assert "duplicate_execution_inputs" in capture.summary()["missing_reasons"]
        context.record_key_hash = "another"
        assert begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"x": 1}) is None
        assert "case_context_mismatch" in capture.summary()["missing_reasons"]


def test_quota_or_invalid_session_never_changes_clinical_session():
    session, _ = session_fixture()
    snapshot = session.snapshot
    with capture_scope(max_bytes=1) as capture:
        record(session)
        assert capture.read_internal()["execution_inputs"] is None
        assert "capacity_exceeded" in capture.summary()["missing_reasons"]
    with capture_scope() as capture:
        record(object())
        assert capture.read_internal()["execution_inputs"] is None
        assert "capture_failed" in capture.summary()["missing_reasons"]
    assert session.snapshot is snapshot


@pytest.mark.parametrize("mutation", ["content", "object", "source_key"])
def test_mutated_material_cannot_masquerade_as_original_snapshot(mutation):
    from dataclasses import replace
    from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
    class Unsafe:
        def __repr__(self):
            pytest.fail("custom serialization must not execute")
        __str__ = __repr__
    session, _ = session_fixture()
    sources = dict(session.materials.diagnostic_sources(snapshot=session.snapshot))
    source = sources["admission_record"]
    sources["admission_record"] = (
        replace(source, source_key="other") if mutation == "source_key"
        else replace(source, rows=({"record_content": Unsafe() if mutation == "object" else "changed"},) * 3)
    )
    forged = replace(session, materials=Luxian0609EvidenceMaterialStore(
        snapshot_hash=session.snapshot.snapshot_hash, _sources=sources))
    with capture_scope() as capture:
        record(forged)
        assert capture.read_internal()["execution_inputs"] is None
        assert "capture_failed" in capture.summary()["missing_reasons"]


def test_model_calls_and_materials_share_one_quota():
    session, _ = session_fixture()
    with capture_scope() as capture:
        record(session)
        size = capture.summary()["retained_bytes"]
    with capture_scope(max_bytes=size) as capture:
        record(session)
        assert begin_attempt(logical_call_id=str(uuid4()), attempt_no=1, payload={"x": 1}) is None
        assert capture.summary()["retained_bytes"] == size
        assert "capacity_exceeded" in capture.summary()["missing_reasons"]


def test_expired_materials_are_released(monkeypatch):
    session, _ = session_fixture()
    with capture_scope(ttl_seconds=1) as capture:
        record(session)
        monkeypatch.setattr("app.services.qc_diagnostics.capture.time.monotonic", lambda: float("inf"))
        assert capture.summary()["retained_bytes"] == 0
        assert "execution_inputs_not_captured" in capture.summary()["missing_reasons"]


@pytest.mark.asyncio
async def test_formal_preparation_reuses_session_and_capture_failure_is_fail_open(monkeypatch):
    """正式 prepare 接缝验证；引擎替身不用于宣称临床规则正确。"""
    from unittest.mock import AsyncMock, Mock
    from app.services.luxian_0609 import execution
    from app.services.luxian_0609.native_package import Luxian0609PackagePlan
    selected = ("LX0609-03-01-01", "LX0609-03-01-04")
    session, _ = session_fixture()
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected, native_sync_rule_ids=(), native_async_rule_ids=selected,
        compatibility_rule_ids=(), compatibility_execution_rule_ids=(), bypassed_execution_rule_ids=(),
        native_executor_batches=(("consultation_quality", selected),),
    )
    builder = Mock(return_value=session)
    monkeypatch.setattr(execution, "build_luxian_0609_package_plan_from_settings", lambda **_: package_plan)
    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", builder)
    engine = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(outcomes=())))
    monkeypatch.setattr(execution, "Luxian0609ExecutionEngine", lambda **_: engine)
    async def run():
        return await execution.prepare_luxian_0609_execution(
            rule_set_key=execution.LUXIAN_0609_RULE_SET_KEY, prepared_rules=[], visit_id="V", medical_text="",
            evidence_payload={}, llm_client=object(), institute_id="I", patient_id="P",
            settings=SimpleNamespace(LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
                                     LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
                                     LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
                                     LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
                                     LUXIAN_0609_FAMILY_MAX_CONCURRENCY=2),
            selected_customer_rule_ids=selected, evaluation_as_of_date="2026-07-05",
        )
    baseline_rules, baseline = await run()
    with capture_scope() as capture:
        enabled_rules, enabled = await run()
        assert capture.read_internal()["execution_inputs"]["snapshot"]["snapshot_hash"] == session.snapshot.snapshot_hash
    with capture_scope(max_bytes=1) as capture:
        failed_rules, failed = await run()
        assert "capacity_exceeded" in capture.summary()["missing_reasons"]
    assert builder.call_count == 3  # 每次质控一次已有读取，导出旁路没有第二次取材。
    assert engine.execute.await_count == 3
    assert all(call.kwargs["snapshot"] is session.snapshot for call in engine.execute.await_args_list)
    assert all(call.kwargs["max_concurrency"] == 2 for call in engine.execute.await_args_list)
    assert baseline_rules == enabled_rules == failed_rules
    assert baseline.native_results == enabled.native_results == failed.native_results
