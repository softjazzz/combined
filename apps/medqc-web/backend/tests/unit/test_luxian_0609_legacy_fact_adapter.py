from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from app.services.luxian_0609.fact_schema import TimeValue
from app.services.luxian_0609 import legacy_fact_adapter as adapter_module
from app.services.luxian_0609.legacy_fact_adapter import (
    LEGACY_FACT_ADAPTER_VERSION,
    LegacyFactV2Mapping,
    RecordTimeHandling,
    adapt_luxian_0609_legacy_fact_shadow,
)
from app.services.luxian_0609.source_manifest import (
    DocumentManifest,
    SourceManifestEntry,
)
from app.services.luxian_0609_fact_extraction import Luxian0609Fact


CREATED_AT = "2026-07-11T20:00:00+08:00"
SNAPSHOT_A = "a" * 64
SNAPSHOT_B = "b" * 64


def _entry(
    source_key: str = "surgery_record",
    *,
    status: str = "available",
) -> SourceManifestEntry:
    if status == "available":
        record_count: int | None = 1
        error_code = ""
        reason_code = ""
    elif status == "empty":
        record_count = 0
        error_code = ""
        reason_code = ""
    elif status == "unavailable":
        record_count = None
        error_code = ""
        reason_code = "NOT_EXPOSED"
    else:
        record_count = None
        error_code = "QUERY_FAILED"
        reason_code = ""
    return SourceManifestEntry.create(
        source_key=source_key,
        query_status=status,
        record_count=record_count,
        query_version="query-v1",
        snapshot_ref=(
            "sha256:" + hashlib.sha256(source_key.encode("utf-8")).hexdigest()
        ),
        error_code=error_code,
        reason_code=reason_code,
    )


def _manifest(
    *entries: SourceManifestEntry,
    visit_ref: str = "visit-ref-001",
    snapshot_hash: str = SNAPSHOT_A,
) -> DocumentManifest:
    return DocumentManifest.create(
        manifest_schema_version="1.0",
        visit_ref=visit_ref,
        source_snapshot_hash=snapshot_hash,
        entries=entries or (_entry(),),
        created_at=CREATED_AT,
    )


def _legacy(**overrides) -> Luxian0609Fact:
    values = {
        "fact_type": "surgery_presence",
        "family": "surgery_anesthesia",
        "source_document_type": "手术记录",
        "source_document_id": "document-ref-001",
        "record_time": "",
        "quote": "存在手术记录",
        "confidence": 0.9,
        "extractor": "structured",
        "trace": {"matched_by": "legacy"},
    }
    values.update(overrides)
    return Luxian0609Fact(**values)


def _mapping(**overrides) -> LegacyFactV2Mapping:
    values = {
        "source_key": "surgery_record",
        "normalized_value": {"present": True},
        "trigger_scope": "current_visit",
        "current_visit_relevance": "relevant",
        "assertion": "affirmed",
        "assertion_context": "current_narrative",
        "event_status": "performed",
        "extractor_version": "policy-v1",
        "record_time_handling": "absent",
        "mapped_record_time": None,
        "omit_reason_code": "",
    }
    values.update(overrides)
    return LegacyFactV2Mapping(**values)


def _adapt(
    *,
    legacy_fact: Luxian0609Fact | None = None,
    mapping: LegacyFactV2Mapping | None = None,
    manifest: DocumentManifest | None = None,
    visit_ref: str = "visit-ref-001",
    created_at: str = CREATED_AT,
    redaction_terms=(),
):
    return adapt_luxian_0609_legacy_fact_shadow(
        legacy_fact=legacy_fact if legacy_fact is not None else _legacy(),
        mapping=mapping if mapping is not None else _mapping(),
        manifest=manifest if manifest is not None else _manifest(),
        visit_ref=visit_ref,
        created_at=created_at,
        redaction_terms=redaction_terms,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "changes",
    [
        {"trigger_scope": "prior_history", "current_visit_relevance": "not_relevant"},
        {"trigger_scope": "family_history", "assertion_context": "family_history"},
        {"assertion": "negated", "assertion_context": "denial_history"},
        {"assertion": "uncertain"},
        {"event_status": "planned"},
        {"event_status": "ordered"},
        {"event_status": "cancelled"},
    ],
)
def test_explicit_semantic_mapping_is_preserved_and_changes_identity(changes: dict) -> None:
    baseline = _adapt()
    changed = _adapt(mapping=_mapping(**changes))
    assert changed.fact_id != baseline.fact_id
    for field, expected in changes.items():
        actual = changed.to_dict()[field]
        assert actual == expected


@pytest.mark.unit
def test_required_semantic_fields_have_no_silent_defaults() -> None:
    with pytest.raises(TypeError):
        LegacyFactV2Mapping(  # type: ignore[call-arg]
            source_key="surgery_record",
            normalized_value={"present": True},
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trigger_scope", "during_visit"),
        ("current_visit_relevance", "yes"),
        ("assertion", "positive"),
        ("assertion_context", "history"),
        ("event_status", "done"),
        ("record_time_handling", "infer"),
    ],
)
def test_invalid_mapping_enums_are_rejected_without_echo(field: str, value: str) -> None:
    with pytest.raises(ValueError) as exc_info:
        _adapt(mapping=_mapping(**{field: value}))
    assert value not in str(exc_info.value)


@pytest.mark.unit
def test_adapter_requires_real_legacy_fact_and_contract_objects() -> None:
    with pytest.raises(TypeError):
        adapt_luxian_0609_legacy_fact_shadow(
            legacy_fact={"fact_type": "surgery_presence"},  # type: ignore[arg-type]
            mapping=_mapping(),
            manifest=_manifest(),
            visit_ref="visit-ref-001",
            created_at=CREATED_AT,
            redaction_terms=(),
        )
    with pytest.raises(TypeError):
        _adapt(mapping={})  # type: ignore[arg-type]


@pytest.mark.unit
def test_manifest_visit_source_and_available_status_are_required() -> None:
    with pytest.raises(ValueError):
        _adapt(visit_ref="other-visit")
    with pytest.raises(ValueError):
        _adapt(mapping=_mapping(source_key="daily_course_record"))
    for status in ("empty", "unavailable", "error"):
        with pytest.raises(ValueError):
            _adapt(manifest=_manifest(_entry(status=status)))


@pytest.mark.unit
def test_adapter_never_guesses_source_or_semantics_from_legacy_text() -> None:
    legacy = _legacy(
        source_document_type="手术记录",
        quote="本次住院已经完成手术",
    )
    mapped = _adapt(
        legacy_fact=legacy,
        mapping=_mapping(
            source_key="admission_record",
            trigger_scope="prior_history",
            current_visit_relevance="not_relevant",
            assertion="negated",
            assertion_context="past_history",
            event_status="cancelled",
        ),
        manifest=_manifest(_entry("admission_record")),
    )
    assert mapped.source_key == "admission_record"
    assert mapped.trigger_scope.value == "prior_history"
    assert mapped.assertion.value == "negated"
    assert mapped.event_status.value == "cancelled"


@pytest.mark.unit
def test_record_time_absent_mapped_and_omitted_are_explicit() -> None:
    absent = _adapt()
    mapped_time = TimeValue.create(
        value="2026-01-02T03:04:05+08:00",
        source="caller-mapped-record-time",
        timezone="Asia/Shanghai",
        precision="second",
    )
    mapped = _adapt(
        legacy_fact=_legacy(record_time="legacy raw time"),
        mapping=_mapping(
            record_time_handling="mapped",
            mapped_record_time=mapped_time,
        ),
    )
    omitted = _adapt(
        legacy_fact=_legacy(record_time="untrusted raw time"),
        mapping=_mapping(
            record_time_handling="omitted_untrusted",
            omit_reason_code="UNTRUSTED_FORMAT",
        ),
    )
    assert absent.record_time is None
    assert mapped.record_time is mapped_time
    assert mapped.record_time.to_dict() == {
        "precision": "second",
        "source": "caller-mapped-record-time",
        "timezone": "Asia/Shanghai",
        "value": "2026-01-02T03:04:05+08:00",
    }
    assert omitted.record_time is None
    for fact in (absent, mapped, omitted):
        assert fact.submit_time is None
        assert fact.update_time is None
    omitted_json = omitted.canonical_json()
    assert "untrusted raw time" not in omitted_json
    assert "UNTRUSTED_FORMAT" not in omitted_json


@pytest.mark.unit
@pytest.mark.parametrize(
    ("legacy_time", "handling", "mapped_time", "reason"),
    [
        ("has time", "absent", None, ""),
        ("", "absent", "time", ""),
        ("", "absent", None, "UNEXPECTED"),
        ("", "mapped", None, ""),
        ("has time", "mapped", None, ""),
        ("has time", "mapped", "time", "UNEXPECTED"),
        ("", "omitted_untrusted", None, "UNTRUSTED_FORMAT"),
        ("has time", "omitted_untrusted", "time", "UNTRUSTED_FORMAT"),
        ("has time", "omitted_untrusted", None, ""),
    ],
)
def test_record_time_handling_rejects_all_contradictory_combinations(
    legacy_time: str,
    handling: str,
    mapped_time,
    reason: str,
) -> None:
    explicit_time = TimeValue.create(
        value="2026-01-02T03:04:05+08:00",
        source="caller-mapped-record-time",
        timezone="Asia/Shanghai",
        precision="second",
    )
    with pytest.raises((TypeError, ValueError)):
        _adapt(
            legacy_fact=_legacy(record_time=legacy_time),
            mapping=_mapping(
                record_time_handling=handling,
                mapped_record_time=explicit_time if mapped_time else None,
                omit_reason_code=reason,
            ),
        )


@pytest.mark.unit
def test_omit_reason_is_controlled_and_error_does_not_echo_raw_time() -> None:
    raw_time = "raw-private-time-marker"
    with pytest.raises(ValueError) as exc_info:
        _adapt(
            legacy_fact=_legacy(record_time=raw_time),
            mapping=_mapping(
                record_time_handling="omitted_untrusted",
                omit_reason_code="free text reason",
            ),
        )
    assert raw_time not in str(exc_info.value)
    assert "free text reason" not in str(exc_info.value)

    for invalid_reason in (
        "138" + "0000" + "0000",
        "Author" + "ization",
        "lowercase_reason",
        "API_KEY",
        "AUTHORIZATION",
        "X138" + "0000" + "0000",
    ):
        with pytest.raises(ValueError):
            _adapt(
                legacy_fact=_legacy(record_time=raw_time),
                mapping=_mapping(
                    record_time_handling="omitted_untrusted",
                    omit_reason_code=invalid_reason,
                ),
            )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("legacy_overrides", "mapping_overrides"),
    [
        ({"source_document_type": "person-name手术记录"}, {}),
        ({"source_document_id": "person-name-ref"}, {}),
        ({"extractor": "person-name-extractor"}, {}),
        ({}, {"normalized_value": {"note": "person-name本次住院"}}),
    ],
)
def test_explicit_redaction_terms_fail_closed_outside_quote(
    legacy_overrides: dict,
    mapping_overrides: dict,
) -> None:
    with pytest.raises(ValueError) as exc_info:
        _adapt(
            legacy_fact=_legacy(**legacy_overrides),
            mapping=_mapping(**mapping_overrides),
            redaction_terms=("person-name",),
        )
    assert "person-name" not in str(exc_info.value)


@pytest.mark.unit
def test_explicit_redaction_term_rejects_mapped_time_metadata() -> None:
    mapped_time = TimeValue.create(
        value="2026-01-02T03:04:05+08:00",
        source="person-name-time-source",
        timezone="Asia/Shanghai",
        precision="second",
    )
    with pytest.raises(ValueError):
        _adapt(
            legacy_fact=_legacy(record_time="legacy time"),
            mapping=_mapping(
                record_time_handling="mapped",
                mapped_record_time=mapped_time,
            ),
            redaction_terms=("person-name",),
        )


@pytest.mark.unit
def test_trace_is_never_read_serialized_or_used_in_errors() -> None:
    patient_name = "person-" + "alpha"
    credential = "Author" + "ization: Basic hidden-token"

    class Explosive:
        def __repr__(self):
            raise AssertionError("trace repr must not be called")

        def __str__(self):
            raise AssertionError("trace str must not be called")

    trace = {
        "patient_name": patient_name,
        "prompt": "complete prompt",
        "status": "non_compliant",
        "credential": credential,
        "object": Explosive(),
    }
    fact = _adapt(legacy_fact=_legacy(trace=trace))
    serialized = fact.canonical_json()
    for forbidden in (
        patient_name,
        "complete prompt",
        "non_compliant",
        "hidden-token",
        "trace",
    ):
        assert forbidden not in serialized

    with pytest.raises(ValueError):
        _adapt(
            legacy_fact=_legacy(trace=trace),
            manifest=_manifest(visit_ref="different-visit"),
        )


@pytest.mark.unit
def test_quote_is_redacted_before_truncation_and_terms_are_not_output() -> None:
    name = "person-name"
    id_card = "510000" + "000000" + "000000"
    phone = "138" + "0000" + "0000"
    credential = "Author" + "ization: Basic hidden-token"
    quote = ("x" * 238) + name + " " + id_card + " " + phone + " " + credential
    fact = _adapt(
        legacy_fact=_legacy(quote=quote),
        redaction_terms=(name,),
    )
    serialized = fact.canonical_json()
    for forbidden in (name, "person", id_card, phone, "hidden-token", "redaction_terms"):
        assert forbidden not in serialized


@pytest.mark.unit
@pytest.mark.parametrize("redaction_terms", ["person-name", b"person-name", bytearray(b"person-name")])
def test_redaction_terms_reject_bare_text_and_binary_values(redaction_terms) -> None:
    with pytest.raises(TypeError):
        _adapt(redaction_terms=redaction_terms)


@pytest.mark.unit
def test_redaction_terms_reject_non_iterable() -> None:
    with pytest.raises(TypeError):
        _adapt(redaction_terms=42)


@pytest.mark.unit
def test_redaction_term_limit_allows_exact_max_and_counts_duplicates() -> None:
    limit = adapter_module.MAX_REDACTION_TERMS
    fact = _adapt(redaction_terms=["unused-term"] * limit)
    assert fact.fact_type == "surgery_presence"

    with pytest.raises(ValueError):
        _adapt(redaction_terms=["unused-term"] * (limit + 1))


@pytest.mark.unit
def test_redaction_term_finite_generator_stops_at_max_plus_one() -> None:
    limit = adapter_module.MAX_REDACTION_TERMS
    consumed = 0

    def terms():
        nonlocal consumed
        for index in range(5000):
            consumed += 1
            yield f"unused-{index}"

    with pytest.raises(ValueError):
        _adapt(redaction_terms=terms())
    assert consumed == limit + 1


@pytest.mark.unit
def test_redaction_term_infinite_generator_stops_at_max_plus_one() -> None:
    limit = adapter_module.MAX_REDACTION_TERMS
    consumed = 0

    def terms():
        nonlocal consumed
        while True:
            consumed += 1
            yield "unused-term"

    with pytest.raises(ValueError):
        _adapt(redaction_terms=terms())
    assert consumed == limit + 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "invalid_term",
    [object(), "x" * 129, "safe\nprivate-marker", "safe\rprivate-marker"],
)
def test_redaction_term_item_validation_is_fixed_and_does_not_echo(invalid_term) -> None:
    with pytest.raises((TypeError, ValueError)) as exc_info:
        _adapt(redaction_terms=(invalid_term,))
    assert "private-marker" not in str(exc_info.value)
    assert ("x" * 32) not in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.parametrize("container", [tuple, list, iter])
def test_small_redaction_term_collections_keep_quote_and_non_quote_boundaries(container) -> None:
    terms = container(["person-name"])
    quote_fact = _adapt(
        legacy_fact=_legacy(quote="person-name手术记录"),
        redaction_terms=terms,
    )
    assert "person-name" not in quote_fact.canonical_json()

    with pytest.raises(ValueError):
        _adapt(
            legacy_fact=_legacy(source_document_type="person-name手术记录"),
            redaction_terms=container(["person-name"]),
        )


@pytest.mark.unit
@pytest.mark.parametrize("confidence", [True, "0.9", float("nan"), float("inf"), -0.1, 1.1])
def test_confidence_is_validated_by_fact_v2_without_clamping(confidence) -> None:
    with pytest.raises((TypeError, ValueError)):
        _adapt(legacy_fact=_legacy(confidence=confidence))


@pytest.mark.unit
def test_normalized_value_uses_fact_v2_immutability_and_privacy_boundary() -> None:
    original = {"nested": [1, {"flag": True}]}
    fact = _adapt(mapping=_mapping(normalized_value=original))
    identity = fact.identity_json()
    original["nested"].append(2)
    original["nested"][1]["flag"] = False
    assert fact.identity_json() == identity
    with pytest.raises(TypeError):
        fact.normalized_value["nested"] = ()
    exported = fact.to_dict()
    exported["normalized_value"]["nested"].append(3)
    assert fact.identity_json() == identity

    for invalid in (
        {"result": "non_compliant"},
        {"decision_hint": "ai_suggested"},
        {"patient_name": "person-name"},
        {"phone": "138" + "0000" + "0000"},
        {"prompt": "hidden"},
    ):
        with pytest.raises(ValueError):
            _adapt(mapping=_mapping(normalized_value=invalid))


@pytest.mark.unit
def test_identity_changes_only_for_existing_fact_v2_identity_dimensions() -> None:
    mapped_time = TimeValue.create(
        value="2026-01-02T03:04:05+08:00",
        source="caller-mapped-record-time",
        timezone="Asia/Shanghai",
        precision="second",
    )
    baseline = _adapt()
    changes = [
        _adapt(mapping=_mapping(extractor_version="policy-v2")),
        _adapt(manifest=_manifest(snapshot_hash=SNAPSHOT_B)),
        _adapt(
            mapping=_mapping(source_key="daily_course_record"),
            manifest=_manifest(_entry(), _entry("daily_course_record")),
        ),
        _adapt(mapping=_mapping(assertion="uncertain")),
        _adapt(mapping=_mapping(normalized_value={"present": False})),
        _adapt(
            legacy_fact=_legacy(record_time="legacy time"),
            mapping=_mapping(
                record_time_handling="mapped",
                mapped_record_time=mapped_time,
            ),
        ),
    ]
    assert all(changed.fact_id != baseline.fact_id for changed in changes)

    non_identity_changes = [
        _adapt(legacy_fact=_legacy(quote="different quote")),
        _adapt(legacy_fact=_legacy(confidence=0.5)),
        _adapt(created_at="2026-07-12T20:00:00+08:00"),
    ]
    assert all(changed.fact_id == baseline.fact_id for changed in non_identity_changes)


@pytest.mark.unit
def test_adapter_version_provenance_is_explicit_and_stable() -> None:
    left = _adapt()
    right = _adapt()
    assert left.fact_id == right.fact_id
    assert left.extractor == "structured"
    assert left.extractor_version == f"{LEGACY_FACT_ADAPTER_VERSION}.policy-v1"


@pytest.mark.unit
def test_adapter_version_change_invalidates_fact_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _adapt()
    monkeypatch.setattr(
        adapter_module,
        "LEGACY_FACT_ADAPTER_VERSION",
        "legacy-shadow-adapter-v2",
    )
    changed = _adapt()
    assert changed.fact_id != baseline.fact_id
    assert changed.extractor_version == "legacy-shadow-adapter-v2.policy-v1"


@pytest.mark.unit
def test_module_declares_single_fact_only_and_has_no_runtime_side_effect_dependencies() -> None:
    module_path = (
        Path(__file__).parents[2]
        / "app"
        / "services"
        / "luxian_0609"
        / "legacy_fact_adapter.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert "does not implement batch" in source
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    )
    assert imported.isdisjoint(
        {"os", "sqlalchemy", "httpx", "requests", "openai", "socket"}
    )
    call_names = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert call_names.isdisjoint({"generate", "execute", "connect", "request"})
