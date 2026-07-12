from __future__ import annotations

import hashlib
from types import SimpleNamespace

from app.core.settings import Settings
from app.services.luxian_0609 import planner, runtime_shadow_hook, runtime_shadow_input_provider
from app.services.luxian_0609.runtime_shadow_assembler import RuntimePairExtractionInput, RuntimeStructuredFactSignal
from app.services.luxian_0609.source_manifest_builder import SourceQueryObservation

VISIT = "visit-hook-001"
CREATED = "2026-07-12T18:00:00+08:00"


class Explosive:
    def __iter__(self): raise AssertionError("must not read downstream")
    def __len__(self): raise AssertionError("must not read downstream")


def _plan():
    return planner.build_luxian_0609_shadow_plan(visit_ref=VISIT, selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={VISIT: ["LX0609-030"]}, planner_schema_version="planner-v1", rule_plan_version="029-030-032-v1", created_at=CREATED)


def _inputs():
    plan = _plan()
    sources = sorted({source for rule in plan.planned_rules for source in rule.required_source_keys})
    observations = tuple(SourceQueryObservation.create(source_key=source, query_status="available", query_version="query-v1") for source in sources)
    ref = hashlib.sha256(b"hook-signal").hexdigest()
    signal = RuntimeStructuredFactSignal(ref, "current_visit_surgery_confirmed", "surgery_record", "performed", hashlib.sha256(b"hook-record").hexdigest(), "runtime_structured", "extractor-v1", "mapping-v1")
    pairs = sorted({(req.fact_type, source) for rule in plan.planned_rules for req in rule.trigger_requirements for source in req.allowed_source_keys})
    extraction = tuple(RuntimePairExtractionInput(fact, source, "complete", "extractor-v1", "mapping-v1", 1, (signal,) if (fact, source) == (signal.fact_type, signal.source_key) else ()) for fact, source in pairs)
    payload = {"programmatic_timeline": {"documents": {source: [{"content": "ignored"}] for source in sources}}}
    return observations, extraction, payload


def _call(**kwargs):
    return runtime_shadow_hook.run_luxian_0609_runtime_shadow(visit_ref=VISIT, selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={VISIT: ["LX0609-030"]}, **kwargs)


def test_disabled_does_not_read_downstream_inputs():
    result = _call(evidence_payload=Explosive(), source_query_observations=Explosive(), extraction_inputs=Explosive(), settings=SimpleNamespace(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False))
    assert result["disposition"] == "disabled" and result["llm_total_tokens"] == 0


def test_real_settings_runtime_shadow_flag_defaults_false_and_parses_environment(monkeypatch):
    monkeypatch.delenv("LUXIAN_0609_RUNTIME_SHADOW_ENABLED", raising=False)
    assert Settings(JWT_SECRET="test-secret").LUXIAN_0609_RUNTIME_SHADOW_ENABLED is False
    monkeypatch.setenv("LUXIAN_0609_RUNTIME_SHADOW_ENABLED", "true")
    assert Settings(JWT_SECRET="test-secret").LUXIAN_0609_RUNTIME_SHADOW_ENABLED is True


def test_enabled_zero_scope_is_planner_only():
    result = runtime_shadow_hook.run_luxian_0609_runtime_shadow(visit_ref=VISIT, selected_rule_ids=[], scoped_customer_rule_ids=[], record_rule_map={}, evidence_payload=Explosive(), source_query_observations=Explosive(), extraction_inputs=Explosive(), settings=SimpleNamespace(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True))
    assert result["disposition"] == "skipped_no_effective_rules" and result["planned_rule_ids"] == []


def test_enabled_nonzero_without_explicit_inputs_is_safe_unavailable():
    result = _call(settings=SimpleNamespace(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True))
    assert result["disposition"] == "inputs_unavailable" and result["reason_code"] == "explicit_runtime_inputs_unavailable"


def test_full_real_030_path_is_completed_with_zero_llm():
    observations, extraction, payload = _inputs()
    result = _call(evidence_payload=payload, source_query_observations=observations, extraction_inputs=extraction, redaction_terms=(), settings=SimpleNamespace(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True))
    assert result["disposition"] == "completed"
    assert result["final_state_counts"]["compliant_count"] == 1
    assert result["expected_llm_call_count"] == result["llm_total_tokens"] == 0


def test_nonzero_coordinates_use_provider_and_complete(monkeypatch):
    seen = []
    def _reader(**kwargs):
        seen.append(kwargs["source_key"])
        return [{"surgery_begin_time": "2026-01-01 08:00"}] if kwargs["source_key"] == "surgery_record" else [{}]
    monkeypatch.setattr(runtime_shadow_input_provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = _call(institute_id="i", patient_id="p", settings=SimpleNamespace(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True))
    assert result["disposition"] == "completed"
    assert result["final_state_counts"]["compliant_count"] == 1
    assert seen == sorted(seen)


def test_exception_is_isolated_without_echo(monkeypatch):
    monkeypatch.setattr(runtime_shadow_hook.runtime_shadow_assembler, "assemble_luxian_0609_runtime_shadow_inputs", lambda **_: (_ for _ in ()).throw(RuntimeError("Bearer_secret")))
    result = _call(source_query_observations=(), extraction_inputs=(), settings=SimpleNamespace(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True))
    assert result["disposition"] == "shadow_error" and "Bearer_secret" not in str(result)
