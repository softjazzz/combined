from __future__ import annotations

import pytest

from app.services.luxian_0609 import build_luxian_0609_input_profile
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.execution import (
    Luxian0609ExecutionContext,
    attach_luxian_0609_execution_metadata,
)
from app.services.luxian_0609.source_manifest_builder import (
    SourceQueryObservation,
    build_luxian_0609_source_manifest_shadow,
)


def _evidence_payload() -> dict:
    return {
        "primary_document_text": "入院记录全文",
        "timeline_facts": [],
        "programmatic_timeline": {
            "documents": {
                "admission_record": [
                    {"content": "入院记录正文", "record_time": "2026-01-01 09:00:00"},
                ],
                "daily_course_record": [
                    {"content": "病程记录正文", "record_time": "2026-01-03 09:00:00"},
                ],
                "surgery_record": [
                    {"content": "手术记录正文", "record_time": "2026-01-04 11:00:00"},
                ],
            }
        },
    }


def _shadow_manifest(visit_ref: str = "2207717"):
    return build_luxian_0609_source_manifest_shadow(
        visit_ref=visit_ref,
        evidence_payload=_evidence_payload(),
        observations=(
            SourceQueryObservation.create(
                source_key="surgery_record",
                query_status="available",
                query_version="query-v1",
            ),
            SourceQueryObservation.create(
                source_key="bloodtrans_record",
                query_status="empty",
                query_version="query-v1",
            ),
        ),
        manifest_schema_version="1.0",
        created_at="2026-07-11T20:00:00+08:00",
    )


@pytest.mark.unit
def test_luxian_0609_input_profile_should_describe_available_family_contexts():
    profile = build_luxian_0609_input_profile(
        visit_id="2207717",
        medical_text="完整病历文本",
        evidence_payload=_evidence_payload(),
    )

    assert profile["mode"] == "full_text_compat"
    assert profile["visit_id"] == "2207717"
    assert profile["document_count"] == 3
    assert profile["source_table_counts"] == {
        "admission_record": 1,
        "daily_course_record": 1,
        "surgery_record": 1,
    }
    assert "course_quality" in profile["available_family_contexts"]
    assert "surgery_anesthesia" in profile["available_family_contexts"]
    assert profile["family_profiles"]["transfusion"]["ready_for_trimmed_context"] is False
    assert "source_manifest_shadow" not in profile


@pytest.mark.unit
def test_luxian_0609_input_profile_should_tolerate_missing_payload():
    profile = build_luxian_0609_input_profile(
        visit_id="",
        medical_text="",
        evidence_payload=None,
    )

    assert profile["evidence_payload_available"] is False
    assert profile["document_count"] == 0
    assert profile["available_family_contexts"] == []
    assert "source_manifest_shadow" not in profile


@pytest.mark.unit
@pytest.mark.parametrize(
    ("visit_id", "medical_text", "evidence_payload"),
    [
        ("2207717", "完整病历文本", _evidence_payload()),
        ("", "", None),
    ],
)
def test_default_none_preserves_complete_legacy_profile_structure(
    visit_id: str,
    medical_text: str,
    evidence_payload: dict | None,
) -> None:
    legacy_call = build_luxian_0609_input_profile(
        visit_id=visit_id,
        medical_text=medical_text,
        evidence_payload=evidence_payload,
    )
    explicit_none = build_luxian_0609_input_profile(
        visit_id=visit_id,
        medical_text=medical_text,
        evidence_payload=evidence_payload,
        source_manifest_shadow=None,
    )
    assert explicit_none == legacy_call
    assert set(explicit_none) == {
        "mode",
        "basis",
        "visit_id",
        "evidence_payload_available",
        "payload_keys",
        "primary_text_char_count",
        "medical_text_char_count",
        "document_count",
        "source_table_count",
        "source_table_counts",
        "source_table_text_lengths",
        "available_family_contexts",
        "family_profiles",
    }


@pytest.mark.unit
def test_explicit_manifest_attaches_only_safe_shadow_metadata() -> None:
    manifest = _shadow_manifest()
    baseline = build_luxian_0609_input_profile(
        visit_id="2207717",
        medical_text="完整病历文本",
        evidence_payload=_evidence_payload(),
    )
    with_shadow = build_luxian_0609_input_profile(
        visit_id="2207717",
        medical_text="完整病历文本",
        evidence_payload=_evidence_payload(),
        source_manifest_shadow=manifest,
    )
    shadow = with_shadow.pop("source_manifest_shadow")

    assert with_shadow == baseline
    assert shadow == {
        "mode": "shadow_only",
        "manifest_schema_version": manifest.manifest_schema_version,
        "visit_ref": manifest.visit_ref,
        "fingerprint": manifest.fingerprint(),
        "source_snapshot_hash": manifest.source_snapshot_hash,
        "entries": [entry.to_dict() for entry in manifest.entries],
    }
    assert "ready_for_trimmed_context" not in shadow
    assert "document_id" not in str(shadow)
    assert "content" not in str(shadow)


@pytest.mark.unit
def test_explicit_shadow_does_not_change_profile_semantics() -> None:
    baseline = build_luxian_0609_input_profile(
        visit_id="2207717",
        medical_text="完整病历文本",
        evidence_payload=_evidence_payload(),
    )
    with_shadow = build_luxian_0609_input_profile(
        visit_id="2207717",
        medical_text="完整病历文本",
        evidence_payload=_evidence_payload(),
        source_manifest_shadow=_shadow_manifest(),
    )
    assert with_shadow["mode"] == "full_text_compat"
    for field in (
        "source_table_counts",
        "source_table_text_lengths",
        "family_profiles",
        "available_family_contexts",
        "document_count",
    ):
        assert with_shadow[field] == baseline[field]


@pytest.mark.unit
def test_shadow_manifest_visit_ref_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_luxian_0609_input_profile(
            visit_id="2207717",
            medical_text="完整病历文本",
            evidence_payload=_evidence_payload(),
            source_manifest_shadow=_shadow_manifest("different-visit"),
        )


@pytest.mark.unit
def test_luxian_0609_execution_metadata_should_attach_input_profile():
    orchestrated: dict[str, object] = {}

    attach_luxian_0609_execution_metadata(
        orchestrated=orchestrated,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        context=Luxian0609ExecutionContext(
            input_profile={"mode": "full_text_compat", "document_count": 2},
            prepared_rule_count=9,
            executable_rule_count=6,
        ),
    )

    assert orchestrated["luxian_0609_input_profile"] == {
        "mode": "full_text_compat",
        "document_count": 2,
    }
    assert orchestrated["luxian_0609_execution_rule_count"] == 9
    assert orchestrated["luxian_0609_executed_rule_count"] == 6
