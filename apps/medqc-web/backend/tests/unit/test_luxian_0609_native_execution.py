from __future__ import annotations

from types import SimpleNamespace

from app.services.luxian_0609 import native_execution


def test_native_core_uses_provider_once_and_returns_exact_customer_order(monkeypatch):
    calls: list[str] = []
    plan = SimpleNamespace(planned_rules=[SimpleNamespace(rule_id=rule_id) for rule_id in native_execution.NATIVE_RULE_IDS])
    provided = SimpleNamespace(
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        source_query_observations=(),
        extraction_inputs=(),
        target_qualifications=(),
    )
    assembly = SimpleNamespace(source_query_observations=(), fact_pairs=(), deterministic_coverage_outcomes=())
    execution = SimpleNamespace(
        results=tuple(
            SimpleNamespace(
                rule_id=rule_id,
                final_state=SimpleNamespace(value=state),
                finding_kind=SimpleNamespace(value=kind),
            )
            for rule_id, state, kind in (
                ("LX0609-029", "non_compliant", "required_document_missing"),
                ("LX0609-030", "compliant", "requirement_satisfied"),
                ("LX0609-032", "non_compliant", "required_document_missing"),
            )
        ),
        fingerprint=lambda: "a" * 64,
    )
    monkeypatch.setattr(native_execution.planner, "build_luxian_0609_shadow_plan", lambda **kwargs: plan)
    monkeypatch.setattr(native_execution.runtime_shadow_input_provider, "provide_luxian_0609_runtime_shadow_inputs", lambda **kwargs: calls.append("provider") or provided)
    monkeypatch.setattr(native_execution.runtime_shadow_assembler, "assemble_luxian_0609_runtime_shadow_inputs", lambda **kwargs: assembly)
    monkeypatch.setattr(native_execution.shadow_execution, "build_luxian_0609_shadow_execution", lambda **kwargs: execution)

    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-unit-001",
        institute_id="inst-native-unit-001",
        patient_id="patient-native-unit-001",
        source_schema=None,
    )

    assert calls == ["provider"]
    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert [item["status"] for item in result.results] == ["non_compliant", "compliant", "non_compliant"]
    assert all(item["metadata"]["executor_type"] == "program" for item in result.results)
    assert all(item["metadata"]["total_tokens"] == 0 for item in result.results)


def test_native_wrapper_selection_accepts_customer_or_mapped_prepared_rule_id():
    wrapper = {"rule_id": "LX0609-029", "mapped_rule_ids": ["CL-181", "SC-081"]}
    assert native_execution.native_rule_ids_from_wrappers(wrapper_rules=[wrapper], prepared_rule_ids={"LX0609-029"}) == ("LX0609-029",)
    assert native_execution.native_rule_ids_from_wrappers(wrapper_rules=[wrapper], prepared_rule_ids={"CL-181"}) == ("LX0609-029",)


def test_native_core_missing_coordinates_returns_complete_safe_technical_results():
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="",
        institute_id="",
        patient_id="",
        source_schema=None,
    )

    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert result.terminal_reason_code == "native_coordinates_unavailable"


def test_native_core_infrastructure_failure_is_complete_and_does_not_echo(monkeypatch):
    secret = "Bearer_secret 13800138000 raw_text"
    monkeypatch.setattr(
        native_execution.planner,
        "build_luxian_0609_shadow_plan",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-unit-002",
        institute_id="inst-native-unit-002",
        patient_id="patient-native-unit-002",
        source_schema=None,
    )

    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert result.terminal_reason_code == "native_execution_failure"
    assert secret not in repr(result)
