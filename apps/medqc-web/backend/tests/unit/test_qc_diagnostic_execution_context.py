"""冻结真实 prepare 参数，不录制客户端/密钥对象。"""

from types import SimpleNamespace

from app.services.qc_diagnostics.capture import capture_scope, capture_execution_context


def record(payload, settings):
    capture_execution_context(medical_text="synthetic", evidence_payload=payload,
        prepared_rules=[{"rule_id": "LX0609-03-01-01"}], settings=settings,
        source_schema="cdm", source_gate_decisions_present=False)


def test_capture_context_freezes_input_and_only_lx_settings():
    payload = {"context": [None, "", 1]}
    settings = SimpleNamespace(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True, JWT_SECRET="never-include",
                               LUXIAN_0609_API_KEY="never-include")
    with capture_scope() as capture:
        record(payload, settings)
        payload["context"].append("later")
        settings.LUXIAN_0609_UNIFIED_ENGINE_ENABLED = False
        context = capture.read_internal()["execution_context"]
        assert context["evidence_payload"] == {"context": [None, "", 1]}
        assert context["runtime_settings"] == {"LUXIAN_0609_UNIFIED_ENGINE_ENABLED": True}
        assert "never-include" not in repr(context)
        assert "execution_context_not_captured" not in capture.summary()["missing_reasons"]


def test_disabled_context_does_not_inspect_settings():
    record(object(), object())


def test_capture_preserves_actual_source_gate_decisions():
    from app.services.luxian_0609_trigger_gate import Luxian0609GateDecision
    gate = Luxian0609GateDecision(rule_id="LX0609-11-01-01", status="data_gap", reason="source_unavailable")
    with capture_scope() as capture:
        capture_execution_context(medical_text="", evidence_payload={}, prepared_rules=[],
            settings=SimpleNamespace(), source_schema="cdm", source_gate_decisions_present=True,
            source_gate_decisions={"LX0609-11-01-01": gate})
        assert capture.read_internal()["execution_context"]["source_gate_decisions"]["LX0609-11-01-01"] == gate.to_metadata()
        assert "source_gate_decisions_not_captured" not in capture.summary()["missing_reasons"]


def test_duplicate_context_and_overflow_are_explicit():
    with capture_scope() as capture:
        record({"x": 1}, SimpleNamespace())
        record({"x": 2}, SimpleNamespace())
        assert capture.read_internal()["execution_context"]["evidence_payload"] == {"x": 1}
        assert "duplicate_execution_context" in capture.summary()["missing_reasons"]
    with capture_scope(max_bytes=1) as capture:
        record({}, SimpleNamespace())
        assert capture.read_internal()["execution_context"] is None
        assert "capacity_exceeded" in capture.summary()["missing_reasons"]
