from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from app.services.luxian_0609 import planner, runtime_shadow_input_provider as provider, source_evidence_reader
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.evidence_material import EvidenceMaterialTruncated
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.source_manifest import QueryStatus

VISIT = "visit-provider-001"


def _plan(*rules):
    return planner.build_luxian_0609_shadow_plan(
        visit_ref=VISIT, selected_rule_ids=list(rules), scoped_customer_rule_ids=list(rules),
        record_rule_map={VISIT: list(rules)}, planner_schema_version="planner-v1",
        rule_plan_version="029-030-032-v1", created_at="2026-07-12T18:00:00+08:00",
    )


def test_shared_strict_performed_parser_and_digest_accept_only_exact_whole_values():
    assert source_evidence_reader.parse_strict_performed_time(" 2026-01-01 08:00:00+08 ") is not None
    assert source_evidence_reader.has_strict_performed_time({"surgery_end_time": "2026-01-01 08:00:00+08"})
    assert source_evidence_reader.parse_strict_performed_time("2026-01-01 08:00:00+08:00") is None
    digest = source_evidence_reader.digest_source_evidence({"raw": "Authorization_sensitive_marker"})
    assert len(digest) == 64
    assert "Authorization_sensitive_marker" not in digest


def test_shared_performed_fact_accepts_only_approved_source_representations():
    assert source_evidence_reader.has_trusted_performed_surgery(
        source_key="surgery_record",
        row={"surgery_begin_time": "2026-01-01 08:00:00+08"},
    )
    assert source_evidence_reader.has_trusted_performed_surgery(
        source_key="mr_surgery",
        row={"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)},
    )
    assert not source_evidence_reader.has_trusted_performed_surgery(
        source_key="mr_surgery",
        row={"surgery_begin_datetime": "2026-01-01 08:00:00", "surgery_name": "ignored"},
    )
    assert not source_evidence_reader.has_trusted_performed_surgery(
        source_key="mr_surgery",
        row={"surgery_name": "ignored", "surgery_code": "ignored"},
    )
    assert not source_evidence_reader.has_trusted_performed_surgery(
        source_key="mr_surgery",
        row={"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)},
    )


def test_provider_queries_exact_sorted_scope_and_emits_safe_rows(monkeypatch):
    seen = []
    def _reader(**kwargs):
        seen.append(kwargs["source_key"])
        return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}] if kwargs["source_key"] == "surgery_record" else [{}]
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT)
    assert seen == sorted(seen)
    assert set(seen) == {item.source_key for item in result.source_query_observations}
    documents = result.evidence_payload["programmatic_timeline"]["documents"]
    assert all(set(row).issubset({"row_ref", "source_snapshot", "qualification_material_hash"}) for rows in documents.values() for row in rows)
    signal_outcome = next(item for item in result.extraction_inputs if item.source_key == "surgery_record")
    assert signal_outcome.positive_signals and signal_outcome.positive_signals[0].event_status == "performed"


def test_provider_emits_performed_signal_from_typed_mr_surgery_when_surgery_record_is_empty(monkeypatch):
    seen: list[str] = []

    def _reader(**kwargs):
        seen.append(kwargs["source_key"])
        if kwargs["source_key"] == "mr_surgery":
            return [{"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)}]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-029", "LX0609-030", "LX0609-032"),
        institute_id="i",
        patient_id="p",
        visit_id=VISIT,
    )

    assert seen == sorted(seen)
    mr_outcome = next(item for item in result.extraction_inputs if item.source_key == "mr_surgery")
    assert len(mr_outcome.positive_signals) == 1
    assert mr_outcome.positive_signals[0].source_key == "mr_surgery"
    assert mr_outcome.positive_signals[0].event_status == "performed"
    assert "2026-01-01" not in repr(result)


@pytest.mark.parametrize(
    "row",
    [
        {"surgery_begin_datetime": "2026-01-01 08:00:00"},
        {"surgery_name": "ignored"},
        {"surgery_code": "ignored"},
    ],
)
def test_provider_does_not_promote_untyped_or_descriptive_mr_surgery_rows(monkeypatch, row):
    def _reader(**kwargs):
        return [row] if kwargs["source_key"] == "mr_surgery" else []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT,
    )

    outcome = next(item for item in result.extraction_inputs if item.source_key == "mr_surgery")
    assert outcome.state == "complete"
    assert outcome.positive_signals == ()


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


def test_provider_rejects_invalid_calendar_time_as_performed_signal(monkeypatch):
    def _reader(**kwargs):
        return [{"surgery_begin_time": "2026-02-30 08:00:00+08"}] if kwargs["source_key"] == "surgery_record" else []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)

    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT,
    )

    signal_outcome = next(item for item in result.extraction_inputs if item.source_key == "surgery_record")
    assert signal_outcome.positive_signals == ()


@pytest.mark.parametrize(
    "record_time,body,expected",
    [
        ("2026-01-01 07:00:00", "substantive approved pre-surgery summary", 1),
        ("2026-01-01 09:00:00", "substantive approved post-surgery summary", 0),
        ("", "substantive approved pre-surgery summary", 0),
        ("2026-01-01", "substantive approved pre-surgery summary", 0),
        ("2026-01-01 07:00:00", "   ", 0),
    ],
)
def test_provider_029_target_qualification_requires_substantive_pre_surgery_body(monkeypatch, record_time, body, expected):
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        if kwargs["source_key"] == "presurg_summary":
            return [{"record_content": body, "record_time": record_time}]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-029"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    qualification = result.target_qualifications[0]
    assert qualification.rule_id == "LX0609-029"
    assert qualification.qualified_document_count == expected


def test_provider_029_uses_earliest_confirmed_surgery_time_independent_of_row_order(monkeypatch):
    surgery_rows = [
        {"surgery_begin_time": "2026-01-02 08:00:00+08"},
        {"surgery_end_time": "2026-01-01 08:00:00+08"},
    ]
    summary_rows = [
        {"record_content": "substantive approved pre-surgery summary", "record_time": "2026-01-01 07:00:00"},
        {"record_content": "substantive approved post-surgery summary", "record_time": "2026-01-01 09:00:00"},
    ]
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return list(reversed(surgery_rows))
        if kwargs["source_key"] == "presurg_summary":
            return list(reversed(summary_rows))
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-029"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    assert result.target_qualifications[0].qualified_document_count == 1


def test_provider_029_qualification_uses_typed_mr_surgery_time_when_surgery_record_is_empty(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return [{"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)}]
        if kwargs["source_key"] == "presurg_summary":
            return [{
                "record_content": "substantive approved pre-surgery summary",
                "record_time": "2026-01-01 07:00:00",
            }]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-029"), institute_id="i", patient_id="p", visit_id=VISIT,
    )

    assert result.target_qualifications[0].qualified_document_count == 1


def test_provider_029_keeps_strict_surgery_record_time_priority_over_earlier_mr_surgery(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return [{"surgery_begin_datetime": datetime(2026, 1, 1, 6, 0)}]
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        if kwargs["source_key"] == "presurg_summary":
            return [{
                "record_content": "substantive approved pre-surgery summary",
                "record_time": "2026-01-01 07:00:00",
            }]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-029"), institute_id="i", patient_id="p", visit_id=VISIT,
    )

    assert result.target_qualifications[0].qualified_document_count == 1


def test_provider_emits_no_target_sidecar_when_raw_target_is_empty(monkeypatch):
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", lambda **kwargs: [])
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-032"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    assert result.target_qualifications == ()


def test_provider_sidecar_and_evidence_output_do_not_retain_target_body_or_time(monkeypatch):
    body_marker = "private-target-body-marker"
    time_marker = "2026-01-01 07:00:00"
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        if kwargs["source_key"] == "presurg_summary":
            return [{"record_content": body_marker, "record_time": time_marker}]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-029"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    serialized = str(asdict(result))
    assert body_marker not in serialized and time_marker not in serialized


@pytest.mark.parametrize(
    ("rule_id", "target_source", "first_row", "second_row"),
    [
        (
            "LX0609-029", "presurg_summary",
            {"record_content": "substantive approved pre-surgery summary A", "record_time": "2026-01-01 07:00:00"},
            {"record_content": "substantive approved pre-surgery summary B", "record_time": "2026-01-01 07:00:00"},
        ),
        (
            "LX0609-032", "surgery_safecheck_record",
            {"record_content": "substantive safety checklist content A"},
            {"record_content": "substantive safety checklist content B"},
        ),
    ],
)
def test_target_qualification_snapshot_binds_allowlisted_body_and_time_material(monkeypatch, rule_id, target_source, first_row, second_row):
    active_row = first_row
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        if kwargs["source_key"] == target_source:
            return [active_row]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    first = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan(rule_id), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    active_row = second_row
    second = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan(rule_id), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    assert first.target_qualifications[0].target_snapshot_hash != second.target_qualifications[0].target_snapshot_hash
    target_row = first.evidence_payload["programmatic_timeline"]["documents"][target_source][0]
    assert set(target_row) == {"row_ref", "source_snapshot", "qualification_material_hash"}
    assert str(first_row) not in str(asdict(first)) and str(second_row) not in str(asdict(second))


def test_target_qualification_duplicate_rows_have_unique_stable_safe_material_refs(monkeypatch):
    duplicate = {"record_content": "substantive safety checklist content", "record_time": "ignored"}
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        if kwargs["source_key"] == "surgery_safecheck_record":
            return [dict(duplicate), dict(duplicate)]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-032"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    rows = result.evidence_payload["programmatic_timeline"]["documents"]["surgery_safecheck_record"]
    assert len(rows) == 2 and len({row["row_ref"] for row in rows}) == 2
    assert len({row["qualification_material_hash"] for row in rows}) == 1


@pytest.mark.parametrize("body,expected", [("substantive safety checklist content", 1), ("", 0), ("   ", 0), ("[]", 0), ("{}", 0)])
def test_provider_032_target_qualification_rejects_title_only_and_shells(monkeypatch, body, expected):
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        if kwargs["source_key"] == "surgery_safecheck_record":
            return [{"record_content": body, "document_title": "ignored title"}]
        return []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-032"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    assert result.target_qualifications[0].qualified_document_count == expected


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("surgery_begin_time", "2026-01-01 08:00:00+08", True),
        ("surgery_end_time", "2026-01-01 09:00:00+08", True),
        ("surgery_begin_time", " 2026-01-01 08:00:00+08 ", True),
        ("surgery_begin_time", "2026-01-01 08:00:00+08:00", False),
        ("surgery_begin_time", "2026-01-01 08:00:00+09", False),
        ("surgery_begin_time", "prefix 2026-01-01 08:00:00+08", False),
        ("surgery_begin_time", "2026-01-01 08:00:00+08 suffix", False),
        ("surgery_begin_time", '"2026-01-01 08:00:00+08"', False),
        ("surgery_begin_time", "2026-01-01  08:00:00+08", False),
        ("surgery_begin_time", "2026-01-01T08:00:00Z", False),
        ("surgery_begin_time", "1704067200", False),
        ("surgery_begin_time", '["2026-01-01 08:00:00+08"]', False),
    ],
)
def test_provider_accepts_only_trimmed_exact_whole_time(monkeypatch, field, value, expected):
    def _reader(**kwargs):
        return [{field: value}] if kwargs["source_key"] == "surgery_record" else []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader)
    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    signal_outcome = next(item for item in result.extraction_inputs if item.source_key == "surgery_record")
    assert bool(signal_outcome.positive_signals) is expected


def test_032_has_no_order_pair_and_safecheck_target_is_queried(monkeypatch):
    seen = []
    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", lambda **kwargs: seen.append(kwargs["source_key"]) or [])
    result = provider.provide_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-032"), institute_id="i", patient_id="p", visit_id=VISIT)
    assert "surgery_safecheck_record" in seen
    assert all(item.fact_type != "current_visit_surgery_order_confirmed" for item in result.extraction_inputs)


def test_row_refs_are_order_independent_duplicate_safe_and_visit_scoped(monkeypatch):
    rows = [
        {"surgery_begin_time": "2026-01-02 08:00:00+08"},
        {"surgery_begin_time": "2026-01-01 08:00:00+08"},
        {"surgery_begin_time": "2026-01-01 08:00:00+08"},
    ]
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


def test_mr_surgery_rows_are_order_independent_and_time_changes_identity(monkeypatch):
    rows = [
        {"surgery_begin_datetime": datetime(2026, 1, 2, 8, 0)},
        {"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)},
        {"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)},
    ]

    def _reader_reversed(**kwargs):
        return list(reversed(rows)) if kwargs["source_key"] == "mr_surgery" else []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader_reversed)
    first = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT,
    )

    def _reader_forward(**kwargs):
        return list(rows) if kwargs["source_key"] == "mr_surgery" else []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader_forward)
    second = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    assert first.evidence_payload == second.evidence_payload
    assert first.extraction_inputs == second.extraction_inputs
    refs = [
        item.signal_ref
        for item in next(
            item for item in first.extraction_inputs if item.source_key == "mr_surgery"
        ).positive_signals
    ]
    assert len(refs) == len(set(refs)) == 3

    changed_rows = [*rows[:-1], {"surgery_begin_datetime": datetime(2026, 1, 3, 8, 0)}]

    def _reader_changed(**kwargs):
        return changed_rows if kwargs["source_key"] == "mr_surgery" else []

    monkeypatch.setattr(provider, "read_luxian_0609_runtime_source_rows", _reader_changed)
    changed = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=_plan("LX0609-030"), institute_id="i", patient_id="p", visit_id=VISIT,
    )
    assert first.evidence_payload != changed.evidence_payload
    assert first.extraction_inputs != changed.extraction_inputs
    assert "2026-01-0" not in repr(first)


def test_trusted_schema_resolver_handles_single_split_and_rejects_arbitrary(monkeypatch):
    monkeypatch.setattr(provider.bundle_assembly, "DB_SCHEMA_MODE", "single")
    assert provider.bundle_assembly._default_source_schema() == "public"
    monkeypatch.setattr(provider.bundle_assembly, "DB_SCHEMA_MODE", "split")
    assert provider.bundle_assembly._default_source_schema() == "cdm"
    monkeypatch.setattr(provider.bundle_assembly, "engine", None)
    with pytest.raises(provider._SourceUnavailable):
        provider.read_luxian_0609_runtime_source_rows(source_key="surgery_record", institute_id="i", patient_id="p", visit_id=VISIT, source_schema="other")


def test_runtime_reader_selects_and_stably_orders_typed_mr_surgery_before_limit(monkeypatch):
    captured: dict[str, object] = {}
    typed_value = datetime(2026, 1, 1, 8, 0)

    class _Rows:
        def mappings(self):
            return self

        def all(self):
            return [{"surgery_begin_datetime": typed_value}]

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = dict(params)
            return _Rows()

    class _Engine:
        def connect(self):
            return _Connection()

    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _Engine())
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda *_: {"institute_id", "patient_id", "visit_id", "surgery_begin_datetime"},
    )
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_qualified_table", lambda *_: '"cdm"."mr_surgery"')

    rows = source_evidence_reader.read_luxian_0609_runtime_source_rows(
        source_key="mr_surgery",
        institute_id="i",
        patient_id="p",
        visit_id=VISIT,
        source_schema=None,
    )

    sql = str(captured["sql"])
    assert rows == [{"surgery_begin_datetime": typed_value}]
    assert '"surgery_begin_datetime" ASC NULLS LAST' in sql
    assert sql.index('"surgery_begin_datetime" ASC NULLS LAST') < sql.index("LIMIT")
    assert captured["params"] == {
        "institute_id": "i",
        "patient_id": "p",
        "visit_id": VISIT,
        "limit_rows": source_evidence_reader._source_limit("mr_surgery"),
    }


def test_provider_reuses_single_snapshot_materials_without_family_self_query(monkeypatch):
    rows_by_source = {
        "inpat_nondrug_order": ({"order_id": "order-private"},),
        "surgery_application": ({"order_id": "application-private"},),
        "surgery_record": (
            {"surgery_begin_time": "2026-01-01 08:00:00+08"},
        ),
        "mr_surgery": (),
        "presurg_summary": (
            {
                "record_content": "private substantive pre-surgery summary",
                "record_time": "2026-01-01 07:00:00",
            },
        ),
        "surgery_safecheck_record": (
            {"record_content": "private substantive safety-check body"},
        ),
    }

    def _snapshot_reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    plan = _plan("LX0609-029", "LX0609-030", "LX0609-032")
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-029", "LX0609-030", "LX0609-032"),
        institute_id="i",
        patient_id="p",
        visit_id=VISIT,
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=_snapshot_reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("surgery_presence",)
        ),
    )
    monkeypatch.setattr(
        provider,
        "read_luxian_0609_runtime_source_rows",
        lambda **_kwargs: pytest.fail("候选统一链不得再次查询数据库"),
    )

    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=plan,
        institute_id="i",
        patient_id="p",
        visit_id=VISIT,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    status_by_source = {
        item.source_key: item.query_status
        for item in result.source_query_observations
    }
    assert status_by_source == {
        "inpat_nondrug_order": QueryStatus.AVAILABLE,
        "mr_surgery": QueryStatus.EMPTY,
        "presurg_summary": QueryStatus.AVAILABLE,
        "surgery_application": QueryStatus.AVAILABLE,
        "surgery_record": QueryStatus.AVAILABLE,
        "surgery_safecheck_record": QueryStatus.AVAILABLE,
    }
    surgery_record_outcome = next(
        item
        for item in result.extraction_inputs
        if item.source_key == "surgery_record"
    )
    assert len(surgery_record_outcome.positive_signals) == 1
    assert surgery_record_outcome.positive_signals[0].event_status == "performed"
    assert {
        item.rule_id: item.qualified_document_count
        for item in result.target_qualifications
    } == {"LX0609-029": 1, "LX0609-032": 1}
    safe_output = repr(result)
    for marker in (
        "order-private",
        "application-private",
        "private substantive",
        "2026-01-01",
    ):
        assert marker not in safe_output


def test_provider_reuses_truncated_bounded_prefix_without_hiding_snapshot_truth(monkeypatch):
    def _snapshot_reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "inpat_nondrug_order":
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=({"order_id": "private-order"},),
                truncated=True,
                limit_rows=1,
            )
        rows = (
            ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            if source_key == "surgery_record"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    plan = _plan("LX0609-030")
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-030",),
        institute_id="i",
        patient_id="p",
        visit_id=VISIT,
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=_snapshot_reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("surgery_presence",)
        ),
    )
    monkeypatch.setattr(
        provider,
        "read_luxian_0609_runtime_source_rows",
        lambda **_kwargs: pytest.fail("截断材料不得回查数据库"),
    )

    result = provider.provide_luxian_0609_runtime_shadow_inputs(
        plan=plan,
        institute_id="i",
        patient_id="p",
        visit_id=VISIT,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    observation = next(
        item
        for item in result.source_query_observations
        if item.source_key == "inpat_nondrug_order"
    )
    outcome = next(
        item
        for item in result.extraction_inputs
        if item.source_key == "inpat_nondrug_order"
    )
    snapshot_observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == "inpat_nondrug_order"
    )
    assert snapshot_observation.completeness.value == "truncated"
    with pytest.raises(EvidenceMaterialTruncated):
        session.materials.rows("inpat_nondrug_order")
    assert len(session.materials.bounded_rows("inpat_nondrug_order")) == 1
    assert observation.query_status is QueryStatus.AVAILABLE
    assert observation.error_code == ""
    assert outcome.state == "complete"
    assert outcome.reason_code == ""
    assert outcome.processed_record_count == 1
    assert "private-order" not in repr(result)
