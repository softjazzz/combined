from __future__ import annotations

import pytest

from app.services.luxian_0609 import planner, runtime_shadow_input_provider as provider
from app.services.luxian_0609.source_manifest import QueryStatus

VISIT = "visit-provider-001"


def _plan(*rules):
    return planner.build_luxian_0609_shadow_plan(
        visit_ref=VISIT, selected_rule_ids=list(rules), scoped_customer_rule_ids=list(rules),
        record_rule_map={VISIT: list(rules)}, planner_schema_version="planner-v1",
        rule_plan_version="029-030-032-v1", created_at="2026-07-12T18:00:00+08:00",
    )


def test_provider_queries_exact_sorted_scope_and_emits_safe_rows(monkeypatch):
    seen = []
    def _reader(**kwargs):
        seen.append(kwargs["source_key"])
        return [{"surgery_begin_time": "2026-01-01 08:00"}] if kwargs["source_key"] == "surgery_record" else [{}]
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT)
    assert seen == sorted(seen)
    assert set(seen) == {item.source_key for item in result.source_query_observations}
    documents = result.evidence_payload["programmatic_timeline"]["documents"]
    assert all(set(row) == {"row_ref", "source_snapshot"} for rows in documents.values() for row in rows)
    signal_outcome = next(item for item in result.extraction_inputs if item.source_key == "surgery_record")
    assert signal_outcome.positive_signals and signal_outcome.positive_signals[0].event_status == "performed"


@pytest.mark.parametrize("mode,status,code", [
    ("unavailable", QueryStatus.UNAVAILABLE, "source_table_unavailable"),
    ("error", QueryStatus.ERROR, "source_query_failed"),
])
def test_provider_distinguishes_unavailable_and_error_without_echo(monkeypatch, mode, status, code):
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            if mode == "unavailable": raise provider._SourceUnavailable()
            raise RuntimeError("Bearer_secret")
        return []
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT)
    observation = next(item for item in result.source_query_observations if item.source_key == "surgery_record")
    assert observation.query_status is status
    assert (observation.reason_code or observation.error_code) == code
    assert "Bearer_secret" not in repr(result)


def test_provider_empty_and_non_time_rows_do_not_fabricate_facts(monkeypatch):
    def _reader(**kwargs):
        return [{"surgery_name": "ignored", "surgery_process": "ignored"}] if kwargs["source_key"] == "surgery_record" else []
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT)
    assert all(not item.positive_signals for item in result.extraction_inputs)
    assert all(item.state == "complete" for item in result.extraction_inputs)


def test_032_has_no_order_pair_and_safecheck_target_is_queried(monkeypatch):
    seen = []
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", lambda **kwargs: seen.append(kwargs["source_key"]) or [])
    result = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-032"), institute_id="i", patient_id="p", visit_id=VISIT)
    assert "surgery_safecheck_record" in seen
    assert all(item.fact_type != "current_visit_surgery_order_confirmed" for item in result.extraction_inputs)


def test_row_refs_are_order_independent_duplicate_safe_and_visit_scoped(monkeypatch):
    rows = [{"surgery_begin_time": "2026-01-02"}, {"surgery_begin_time": "2026-01-01"}, {"surgery_begin_time": "2026-01-01"}]
    def _reader(**kwargs): return list(reversed(rows)) if kwargs["source_key"] == "surgery_record" else [{}]
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    first = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT)
    def _reader_forward(**kwargs): return list(rows) if kwargs["source_key"] == "surgery_record" else [{}]
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader_forward)
    second = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT)
    assert first.evidence_payload == second.evidence_payload
    first_refs = [item.signal_ref for item in next(item for item in first.extraction_inputs if item.source_key == "surgery_record").positive_signals]
    assert len(first_refs) == len(set(first_refs)) == 3
    other_visit = "visit-provider-002"
    other_plan = planner.build_luxian_0609_shadow_plan(visit_ref=other_visit, selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={other_visit: ["LX0609-030"]}, planner_schema_version="planner-v1", rule_plan_version="029-030-032-v1", created_at="2026-07-12T18:00:00+08:00")
    other = provider.provide_luxian_0609_runtime_shadow_inputs(plan=other_plan, institute_id="i", patient_id="p", visit_id=other_visit)
    other_refs = [item.signal_ref for item in next(item for item in other.extraction_inputs if item.source_key == "surgery_record").positive_signals]
    assert set(first_refs).isdisjoint(other_refs)
    assert VISIT not in repr(first) and "visit-provider-002" not in repr(other)


def test_trusted_schema_resolver_handles_single_split_and_rejects_arbitrary(monkeypatch):
    monkeypatch.setattr(provider.bundle_assembly, "DB_SCHEMA_MODE", "single")
    assert provider.bundle_assembly._default_source_schema() == "public"
    monkeypatch.setattr(provider.bundle_assembly, "DB_SCHEMA_MODE", "split")
    assert provider.bundle_assembly._default_source_schema() == "cdm"
    monkeypatch.setattr(provider.bundle_assembly, "engine", None)
    with pytest.raises(provider._SourceUnavailable):
        provider.read_luxian_0609_runtime_source_rows(source_key="surgery_record", institute_id="i", patient_id="p", visit_id=VISIT, source_schema="other")
