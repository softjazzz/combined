from __future__ import annotations

from dataclasses import replace

import pytest

from app.services.luxian_0609.customer_evidence_enrichment import (
    project_selected_grouped_document_refs,
    project_selected_document_evidence,
)
from app.services.luxian_0609.source_registry import (
    resolve_luxian_0609_customer_document_type,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    build_material_document_refs,
)
from test_luxian_0609_basic_timeliness_evidence_freeze import (
    _coordinates,
    _execute_and_aggregate,
    _multi_document_session,
)
from test_luxian_0609_document_ref_binding import (
    _bind,
    _decision,
    _snapshot_and_materials,
    _source_rows,
)


def _result_by_rule(results, rule_id: str):
    return next(result for result in results if result["rule_id"] == rule_id)


def _daily_document_binding(rows):
    source_rows = _source_rows("daily_course_record", rows)
    snapshot, materials = _snapshot_and_materials(
        {"daily_course_record": source_rows}
    )
    document_ref = build_material_document_refs("daily_course_record", source_rows.rows)[
        0
    ]
    reduced = _bind(
        snapshot,
        _decision(snapshot, document_ref, rule_id="LX0609-005"),
        materials,
    )
    return snapshot, materials, document_ref, reduced


def test_001_projects_selected_admission_document_coordinate():
    _execution, _reduced, results = _execute_and_aggregate(
        _multi_document_session(("LX0609-001",)), ("LX0609-001",)
    )
    result = _result_by_rule(results, "LX0609-001")

    assert result["status"] == "compliant"
    assert _coordinates(result) == [
        ("admission_record", "ADM-SELECTED", "chief_complaint", "2026-06-01 11:00:00")
    ]


def test_002_projects_selected_first_course_document_coordinate():
    _execution, _reduced, results = _execute_and_aggregate(
        _multi_document_session(("LX0609-002",)), ("LX0609-002",)
    )
    result = _result_by_rule(results, "LX0609-002")

    assert result["status"] == "compliant"
    assert _coordinates(result) == [
        ("first_course_record", "FC-SELECTED", "record_content", "2026-06-01 10:00:00")
    ]


def test_005_projects_selected_daily_course_document_coordinate():
    _execution, _reduced, results = _execute_and_aggregate(
        _multi_document_session(("LX0609-005",)), ("LX0609-005",)
    )
    result = _result_by_rule(results, "LX0609-005")

    assert result["status"] == "compliant"
    assert _coordinates(result) == [
        (
            "daily_course_record",
            "ROUND-ATTENDING-SELECTED",
            "document_title",
            "2026-06-02 08:00:00",
        )
    ]


def test_projector_preserves_cdm_document_id_with_delimiter():
    snapshot, materials, _document_ref, reduced = _daily_document_binding(
        ({"document_id": "CDM||DAILY-1", "document_title": "查房记录"},)
    )

    assert project_selected_document_evidence(
        decision=reduced,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    ) == [{"source_type": "daily_course_record", "source_document_id": "CDM||DAILY-1"}]


@pytest.mark.parametrize(
    "rows",
    (
        ({"document_title": "无业务 ID 的查房记录"},),
        (
            {"document_id": "DUPLICATED", "document_title": "查房记录 A"},
            {"document_id": "DUPLICATED", "document_title": "查房记录 B"},
        ),
    ),
)
def test_projector_returns_empty_when_selected_document_cannot_be_uniquely_located(rows):
    snapshot, materials, _document_ref, reduced = _daily_document_binding(rows)

    assert project_selected_document_evidence(
        decision=reduced,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    ) == []


def test_projector_deduplicates_all_selected_rows_with_same_business_id():
    rows = _source_rows(
        "daily_course_record",
        (
            {"document_id": "DAILY-1", "document_title": "查房记录 A"},
            {"document_id": "DAILY-1", "document_title": "查房记录 B"},
        ),
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})
    refs = build_material_document_refs("daily_course_record", rows.rows)
    decision = replace(_decision(snapshot, refs[0], rule_id="LX0609-005"), fact_refs=refs)
    reduced = _bind(snapshot, decision, materials)

    assert project_selected_document_evidence(
        decision=reduced, evidence_snapshot=snapshot, evidence_materials=materials
    ) == [{"source_type": "daily_course_record", "source_document_id": "DAILY-1"}]


def test_projector_rejects_partial_selection_of_same_business_id():
    snapshot, materials, _document_ref, reduced = _daily_document_binding(
        (
            {"document_id": "DAILY-1", "document_title": "查房记录 A"},
            {"document_id": "DAILY-1", "document_title": "查房记录 B"},
        )
    )

    assert project_selected_document_evidence(
        decision=reduced, evidence_snapshot=snapshot, evidence_materials=materials
    ) == []


def test_projector_projects_multiple_fully_selected_business_ids_from_one_source():
    rows = _source_rows(
        "daily_course_record",
        (
            {"document_id": "DAILY-1", "document_title": "查房记录 A"},
            {"document_id": "DAILY-2", "document_title": "查房记录 B"},
        ),
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})
    refs = build_material_document_refs("daily_course_record", rows.rows)
    decision = replace(_decision(snapshot, refs[0], rule_id="LX0609-005"), fact_refs=refs)
    reduced = _bind(snapshot, decision, materials)

    projected = project_selected_document_evidence(
        decision=reduced, evidence_snapshot=snapshot, evidence_materials=materials
    )

    expected_document_ids = {
        reference: str(row["document_id"])
        for reference, row in materials.document_rows(
            "daily_course_record", snapshot=snapshot
        )
    }
    assert projected == [
        {
            "source_type": "daily_course_record",
            "source_document_id": expected_document_ids[reference],
        }
        for reference in refs
    ]


def test_projector_returns_empty_for_cross_snapshot_or_tampered_materials():
    rows = ({"document_id": "DAILY-1", "document_title": "查房记录"},)
    snapshot, materials, document_ref, reduced = _daily_document_binding(rows)
    other_snapshot, _other_materials = _snapshot_and_materials(
        {"daily_course_record": _source_rows("daily_course_record", rows)},
        patient_id="OTHER",
    )
    tampered = Luxian0609EvidenceMaterialStore(
        snapshot_hash=snapshot.snapshot_hash,
        _sources={
            "daily_course_record": _source_rows(
                "daily_course_record", ({"document_id": "FORGED"},)
            )
        },
    )
    tampered_reduced = _bind(
        snapshot,
        _decision(snapshot, document_ref, rule_id="LX0609-005"),
        tampered,
    )

    assert project_selected_document_evidence(
        decision=reduced,
        evidence_snapshot=other_snapshot,
        evidence_materials=materials,
    ) == []
    assert project_selected_document_evidence(
        decision=tampered_reduced,
        evidence_snapshot=snapshot,
        evidence_materials=tampered,
    ) == []


def test_projector_does_not_deliver_partial_coordinates_for_multiple_selected_refs():
    rows = _source_rows(
        "daily_course_record",
        ({"document_title": "缺业务ID"}, {"document_id": "SAFE-ID"}),
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})
    refs = build_material_document_refs("daily_course_record", rows.rows)
    decision = replace(_decision(snapshot, refs[0], rule_id="LX0609-005"), fact_refs=refs)
    reduced = _bind(snapshot, decision, materials)

    assert project_selected_document_evidence(
        decision=reduced, evidence_snapshot=snapshot, evidence_materials=materials
    ) == []


@pytest.mark.parametrize(
    ("source_key", "expected"),
    (
        ("inpat_nondrug_order.rescue_order", "inpat_nondrug_order"),
        ("admission_record", "admission_record"),
        ("mr_surgery", "mr_surgery"),
        ("inpat_registration", "inpat_registration"),
        ("labtest_item_report", "labtest_item_report"),
        ("admission_record.evil", None),
        ("inpat_nondrug_order.unregistered_internal_alias", None),
        ("unknown_source.child", None),
        ("evaluation_context.horizon", None),
    ),
)
def test_customer_source_type_only_exposes_registered_document_type(source_key, expected):
    assert resolve_luxian_0609_customer_document_type(source_key) == expected


def test_grouped_reference_projector_converts_internal_document_ids_to_safe_refs() -> None:
    projected = project_selected_grouped_document_refs(
        raw_refs=[
            {
                "source_type": "consultation_record",
                "source_document_id": "CONSULT-PRIVATE-1",
            }
        ],
        public=False,
        allowed_source_types=frozenset({"consultation_record"}),
    )

    assert projected is not None
    assert projected[0]["source_type"] == "consultation_record"
    assert projected[0]["source_ref"].startswith("src_")
    assert "CONSULT-PRIVATE-1" not in str(projected)


def test_grouped_reference_projector_preserves_valid_public_refs_and_rejects_duplicates() -> None:
    public_ref = "src_0123456789abcdef01234567"
    assert project_selected_grouped_document_refs(
        raw_refs=[{"source_type": "consultation_record", "source_ref": public_ref}],
        public=True,
        allowed_source_types=frozenset({"consultation_record"}),
    ) == [{"source_type": "consultation_record", "source_ref": public_ref}]
    assert project_selected_grouped_document_refs(
        raw_refs=[
            {"source_type": "consultation_record", "source_ref": public_ref},
            {"source_type": "consultation_record", "source_ref": public_ref},
        ],
        public=True,
        allowed_source_types=frozenset({"consultation_record"}),
    ) is None
