from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import pytest

from app.services.luxian_0609 import fact_schema as fact_schema_module
from app.services.luxian_0609.fact_schema import (
    Assertion,
    AssertionContext,
    CurrentVisitRelevance,
    EventStatus,
    FACT_SCHEMA_VERSION,
    MAX_QUOTE_LENGTH,
    FactV2,
    RuleProjection,
    TimePrecision,
    TimeValue,
    TriggerScope,
)


SNAPSHOT_A = "a" * 64
SNAPSHOT_B = "b" * 64
UPSTREAM_A = "1" * 64
UPSTREAM_B = "2" * 64


def _time(value: str = "2026-07-11T08:30:00+08:00") -> TimeValue:
    return TimeValue.create(
        value=value,
        source="surgery_record.record_time",
        timezone="Asia/Shanghai",
        precision="second",
    )


def _projection(**overrides) -> RuleProjection:
    values = {
        "projection_type": "surgery_presence",
        "projection_version": "projection-v1",
        "derived_from_fact_ids": [UPSTREAM_B, UPSTREAM_A, UPSTREAM_A],
        "projection_reason": "SOURCE_ALIGNED",
        "normalized_value": {"present": True},
    }
    values.update(overrides)
    return RuleProjection.create(**values)


def _fact(**overrides) -> FactV2:
    values = {
        "visit_ref": "visit-ref-001",
        "family": "surgery_anesthesia",
        "fact_type": "surgery_event",
        "normalized_value": {"procedure_code": "OP-001", "performed": True},
        "trigger_scope": "current_visit",
        "current_visit_relevance": "relevant",
        "assertion": "affirmed",
        "assertion_context": "current_narrative",
        "event_status": "performed",
        "source_key": "surgery_record",
        "source_document_id": "doc-ref-001",
        "source_document_type": "手术记录",
        "record_time": _time(),
        "submit_time": None,
        "update_time": None,
        "quote": "患者已完成相关手术。",
        "redaction_terms": [],
        "confidence": 0.95,
        "extractor": "deterministic",
        "extractor_version": "extractor-v1",
        "fact_schema_version": FACT_SCHEMA_VERSION,
        "source_snapshot_hash": SNAPSHOT_A,
        "created_at": "2026-07-11T20:00:00+08:00",
        "extensions": {},
        "known_upstream_fact_ids": set(),
    }
    values.update(overrides)
    return FactV2.create(**values)


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    [
        (TriggerScope, ["current_visit", "prior_history", "family_history", "external_context", "unknown"]),
        (CurrentVisitRelevance, ["relevant", "not_relevant", "unknown"]),
        (Assertion, ["affirmed", "negated", "uncertain"]),
        (AssertionContext, ["current_narrative", "denial_history", "past_history", "family_history", "other"]),
        (EventStatus, ["planned", "ordered", "performed", "cancelled", "unknown"]),
    ],
)
def test_enums_have_exact_values(enum_type, expected: list[str]) -> None:
    assert [item.value for item in enum_type] == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trigger_scope", "during_visit"),
        ("current_visit_relevance", "yes"),
        ("assertion", "positive"),
        ("assertion_context", "history"),
        ("event_status", "done"),
    ],
)
def test_invalid_enum_strings_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValueError) as exc_info:
        _fact(**{field: value})
    assert value not in str(exc_info.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"trigger_scope": "prior_history"},
        {"trigger_scope": "family_history"},
        {"assertion": "negated", "assertion_context": "denial_history"},
        {"event_status": "planned"},
        {"event_status": "ordered"},
        {"event_status": "cancelled"},
    ],
)
def test_scope_assertion_and_event_semantics_remain_distinct_in_identity(changes: dict) -> None:
    original = _fact()
    changed = _fact(**changes)
    assert changed.fact_id != original.fact_id
    for key, value in changes.items():
        serialized_value = changed.to_dict()[key]
        assert serialized_value == value


def test_time_values_are_independent_and_preserve_all_semantics() -> None:
    record_time = _time("2026-07-11T08:30:00+08:00")
    submit_time = TimeValue.create(
        value="2026-07-11T08:35:00+08:00",
        source="surgery_record.submit_time",
        timezone="Asia/Shanghai",
        precision=TimePrecision.MINUTE,
    )
    fact = _fact(record_time=record_time, submit_time=submit_time, update_time=None)
    payload = fact.to_dict()

    assert payload["record_time"]["value"] == "2026-07-11T08:30:00+08:00"
    assert payload["record_time"]["precision"] == "second"
    assert payload["submit_time"]["value"] == "2026-07-11T08:35:00+08:00"
    assert payload["submit_time"]["precision"] == "minute"
    assert payload["update_time"] is None


def test_direct_time_and_projection_construction_cannot_bypass_validation() -> None:
    with pytest.raises(ValueError):
        TimeValue(
            value="not-a-time",
            source="surgery_record.record_time",
            timezone="Asia/Shanghai",
            precision=TimePrecision.SECOND,
        )
    with pytest.raises(ValueError):
        RuleProjection(
            projection_type="surgery_presence",
            projection_version="projection-v1",
            derived_from_fact_ids=(UPSTREAM_A,),
            projection_reason="SOURCE_ALIGNED",
            normalized_value={"status": "non_compliant"},
        )


def test_fact_id_is_stable_and_excludes_created_at_quote_and_confidence() -> None:
    first = _fact(
        created_at="2026-07-11T20:00:00+08:00",
        quote="person-name 已完成手术",
        redaction_terms=["person-name"],
        confidence=0.8,
    )
    second = _fact(
        created_at="2026-07-12T20:00:00+08:00",
        quote="another-name 完全不同的短引用",
        redaction_terms=["another-name"],
        confidence=0.99,
    )
    assert first.fact_id == second.fact_id
    assert first.identity_json() == second.identity_json()
    assert first.to_dict()["created_at"] != second.to_dict()["created_at"]


@pytest.mark.parametrize(
    "changes",
    [
        {"fact_schema_version": "2.1"},
        {"extractor_version": "extractor-v2"},
        {"source_snapshot_hash": SNAPSHOT_B},
        {"normalized_value": {"procedure_code": "OP-002", "performed": True}},
        {"source_document_id": "doc-ref-002"},
        {"record_time": _time("2026-07-11T09:30:00+08:00")},
    ],
)
def test_semantic_version_snapshot_value_source_or_time_changes_fact_id(changes: dict) -> None:
    assert _fact(**changes).fact_id != _fact().fact_id


@pytest.mark.parametrize("confidence", [0, 1, 0.5])
def test_confidence_accepts_closed_unit_interval(confidence: float) -> None:
    assert _fact(confidence=confidence).confidence == confidence


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf"), -float("inf"), "0.5", True])
def test_confidence_rejects_non_numeric_non_finite_or_out_of_range_values(confidence) -> None:
    with pytest.raises((TypeError, ValueError)):
        _fact(confidence=confidence)


def test_quote_is_redacted_before_truncation_and_terms_are_not_serialized() -> None:
    name = "person-name"
    id_card = "510000" + "000000" + "000000"
    phone = "138" + "0000" + "0000"
    credential = "Author" + "ization: " + "Bear" + "er hidden-token"
    api_key = "API " + "key=another-token"
    prefix = "x" * (MAX_QUOTE_LENGTH - 4)
    fact = _fact(
        quote=f"{prefix}{name} {id_card} {phone} {credential} {api_key}",
        redaction_terms=[name],
    )
    serialized = fact.canonical_json()

    assert len(fact.quote) <= MAX_QUOTE_LENGTH
    assert name not in fact.quote
    assert "pers" not in fact.quote
    assert id_card not in serialized
    assert phone not in serialized
    assert "hidden-token" not in serialized
    assert "another-token" not in serialized
    assert "redaction_terms" not in serialized


def test_quote_explicit_identifier_and_credential_patterns_are_redacted() -> None:
    name = "person-name"
    id_card = "510000" + "000000" + "000000"
    phone = "138" + "0000" + "0000"
    credential = "Author" + "ization: " + "Bear" + "er hidden-token"
    basic_credential = "Author" + "ization: " + "Basic hidden-basic-token"
    api_key = "API " + "key=another-token"
    fact = _fact(
        quote=(
            f"{name} 正常医学文本 {id_card} {phone} {credential}; "
            f"{basic_credential}; {api_key}"
        ),
        redaction_terms=[name],
    )
    assert fact.quote == (
        "[REDACTED] 正常医学文本 [REDACTED_ID] [REDACTED_PHONE] "
        "[REDACTED_CREDENTIAL]; [REDACTED_CREDENTIAL]; "
        "API key=[REDACTED_CREDENTIAL]"
    )


@pytest.mark.parametrize(
    "value",
    [
        b"binary",
        object(),
        {"bad": float("nan")},
        {"bad": float("inf")},
        {1: "non-string-key"},
        ("tuple",),
    ],
)
def test_normalized_value_rejects_non_json_or_non_finite_values(value) -> None:
    with pytest.raises((TypeError, ValueError)):
        _fact(normalized_value=value)


def test_normalized_value_canonicalization_is_stable_across_dict_order() -> None:
    left = _fact(normalized_value={"b": [2, 1], "a": {"x": True}})
    right = _fact(normalized_value={"a": {"x": True}, "b": [2, 1]})
    assert left.fact_id == right.fact_id
    assert left.canonical_json() == right.canonical_json()


def test_fact_normalized_value_is_deeply_immutable_and_defensively_copied() -> None:
    source = {"a": [1, {"b": [2]}]}
    fact = _fact(normalized_value=source)
    expected_identity = fact.identity_json()

    source["a"].append(3)
    source["a"][1]["b"].append(4)
    assert fact.identity_json() == expected_identity

    with pytest.raises(TypeError):
        fact.normalized_value["a"] = ()
    with pytest.raises(AttributeError):
        fact.normalized_value["a"].append(5)
    with pytest.raises(TypeError):
        fact.normalized_value["a"][1]["b"] = ()

    exported = fact.to_dict()
    exported["normalized_value"]["a"].append(6)
    exported["normalized_value"]["a"][1]["b"].append(7)
    assert fact.identity_json() == expected_identity
    assert fact.fact_id == hashlib.sha256(expected_identity.encode("utf-8")).hexdigest()


def test_projection_normalized_value_is_deeply_immutable_and_defensively_copied() -> None:
    source = {"metric": [1, {"nested": [2]}]}
    projection = _projection(normalized_value=source)
    expected_json = projection.canonical_json()

    source["metric"].append(3)
    source["metric"][1]["nested"].append(4)
    assert projection.canonical_json() == expected_json

    with pytest.raises(TypeError):
        projection.normalized_value["metric"] = ()
    with pytest.raises(AttributeError):
        projection.normalized_value["metric"].append(5)
    with pytest.raises(TypeError):
        projection.normalized_value["metric"][1]["nested"] = ()

    exported = projection.to_dict()
    exported["normalized_value"]["metric"].append(6)
    exported["normalized_value"]["metric"][1]["nested"].append(7)
    assert projection.canonical_json() == expected_json


def test_normalized_clinical_text_is_not_subject_to_broad_name_regex() -> None:
    fact = _fact(normalized_value={"diagnosis": "李氏综合征", "finding": "张力正常"})
    assert fact.to_dict()["normalized_value"]["diagnosis"] == "李氏综合征"


@pytest.mark.parametrize(
    "normalized_value",
    [
        {"result": "non_compliant"},
        {"result": "AI says non_compliant now"},
        {"result": "AI_SUGGESTED_NON_COMPLIANT"},
        {"result": "ai-suggested-compliant"},
        {"result": "AI SUGGESTED COMPLIANT"},
        {"recommended_status": 1},
        {"nested": [{"quality-status": 1}]},
    ],
)
def test_fact_normalized_value_cannot_hide_final_status(normalized_value) -> None:
    with pytest.raises(ValueError):
        _fact(normalized_value=normalized_value)


def test_projection_is_versioned_traceable_deduplicated_and_changes_fact_identity() -> None:
    projection = _projection()
    fact = _fact(
        extensions={"lx0609.surgery_presence": projection},
        known_upstream_fact_ids={UPSTREAM_A, UPSTREAM_B},
    )
    changed = _fact(
        extensions={
            "lx0609.surgery_presence": _projection(projection_version="projection-v2")
        },
        known_upstream_fact_ids={UPSTREAM_A, UPSTREAM_B},
    )

    serialized = fact.to_dict()["extensions"]["lx0609.surgery_presence"]
    assert serialized["derived_from_fact_ids"] == [UPSTREAM_A, UPSTREAM_B]
    assert fact.fact_id != changed.fact_id
    assert fact.fingerprint() == fact.fact_id
    assert projection.canonical_json() == json.dumps(
        projection.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def test_projection_requires_known_existing_upstream_fact_ids() -> None:
    with pytest.raises(ValueError, match="known upstream"):
        _fact(
            extensions={"lx0609.surgery_presence": _projection()},
            known_upstream_fact_ids={UPSTREAM_A},
        )


def test_projection_reason_rejects_direct_identifier_or_free_text() -> None:
    with pytest.raises(ValueError):
        _projection(projection_reason="patient name person-name")
    with pytest.raises(ValueError):
        _projection(projection_reason="138" + "0000" + "0000")


@pytest.mark.parametrize(
    "normalized_value",
    [
        {"status": "non_compliant"},
        {"compliant": True},
        {"ai_suggested_non_compliant": 0},
        {"result": "AI says non_compliant now"},
        {"result": "AI_SUGGESTED_NON_COMPLIANT"},
        {"result": "ai-suggested-compliant"},
        {"result": "AI SUGGESTED COMPLIANT"},
        {"recommended_status": 1},
        {"aiSuggestedStatus": 1},
        {"quality-status": 1},
        {"nested": [{"result": "AI says non-compliant now"}]},
        {"nested": [{"result": "ai_suggested_non_compliant"}]},
        {"prompt": "hidden"},
        {"raw_response": "hidden"},
        {"full_text": "hidden"},
        {"error_stack": "Traceback"},
        {"patient_name": "person-name"},
        {"id_card": "hidden"},
        {"phone": "hidden"},
        {"quote": "hidden"},
        {"nested": "suppressed"},
        {"nested": "evaluation_unknown"},
    ],
)
def test_projection_recursively_rejects_status_payload_prompt_response_text_or_phi(
    normalized_value,
) -> None:
    with pytest.raises(ValueError):
        _projection(normalized_value=normalized_value)


def test_projection_rejects_current_fact_self_reference_even_if_claimed_known(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection(derived_from_fact_ids=[UPSTREAM_A])

    class FixedDigest:
        @staticmethod
        def hexdigest() -> str:
            return UPSTREAM_A

    monkeypatch.setattr(fact_schema_module.hashlib, "sha256", lambda _payload: FixedDigest())
    with pytest.raises(ValueError, match="currently being constructed"):
        _fact(
            extensions={"lx0609.surgery_presence": projection},
            known_upstream_fact_ids={UPSTREAM_A},
        )


def test_fact_payload_contains_no_customer_status_or_redaction_terms() -> None:
    fact = _fact(
        quote="person-name 正常医学文本",
        redaction_terms=["person-name"],
    )
    payload = fact.to_dict()
    serialized = fact.canonical_json()
    forbidden = {
        "applicability",
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_gap",
        "technical_error",
        "ai_suggested_compliant",
        "ai_suggested_non_compliant",
    }
    assert not forbidden.intersection(payload)
    assert "person-name" not in serialized
    assert "redaction_terms" not in serialized


def test_fact_schema_modules_import_only_python_stdlib() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "services" / "luxian_0609"
    for filename in ("source_manifest.py", "fact_schema.py"):
        tree = ast.parse((root / filename).read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert not imported.intersection({"app", "sqlalchemy", "httpx", "requests", "openai"})
