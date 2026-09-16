import pytest

from app.services.luxian_0916.input_context import (
    add_luxian_0916_evidence_sources,
    build_luxian_0916_context,
    merge_luxian_0916_semantic_facts,
)


def test_adds_consent_form_from_bundle_inventory_without_changing_common_sources() -> None:
    evidence = {
        "programmatic_timeline": {
            "documents": {"surgery_inform_consent": [{"document_id": "S-1", "content": "手术同意书"}]}
        }
    }
    bundle = {
        "structured_context": {
            "document_inventory": [
                {
                    "source_table": "consent_form",
                    "document_id": "A-1",
                    "document_title": "麻醉知情同意书",
                    "content": "拟行全身麻醉。",
                }
            ]
        }
    }

    projected = add_luxian_0916_evidence_sources(bundle=bundle, evidence_payload=evidence)

    documents = projected["programmatic_timeline"]["documents"]
    assert documents["surgery_inform_consent"][0]["document_id"] == "S-1"
    assert documents["consent_form"] == (
        {
            "document_id": "A-1",
            "title": "麻醉知情同意书",
            "content": "拟行全身麻醉。",
        },
    )
    assert projected["programmatic_timeline"]["locatable_document_coordinates"] == (
        ("consent_form", "A-1"),
    )


def test_projects_locatable_coordinates_from_top_level_bundle_inventory() -> None:
    projected = add_luxian_0916_evidence_sources(
        bundle={
            "source_documents": [
                {"source_table": "DAILY_COURSE_RECORD", "id": "D-1"},
                {"document_type": "EXAM_MASTER", "document_id": "E-1"},
                {"type": "labtest_master", "id": "L-1"},
                {"doc_type": "inpat_drug_order", "id": "O-1"},
                {"source_table": "labtest_item_report", "document_id": ""},
            ]
        },
        evidence_payload={"programmatic_timeline": {"documents": {}}},
    )

    assert projected["programmatic_timeline"]["locatable_document_coordinates"] == (
        ("daily_course_record", "D-1"),
        ("exam_master", "E-1"),
        ("inpat_drug_order", "O-1"),
        ("labtest_master", "L-1"),
    )


def test_context_builder_projects_documents_and_deterministic_events_without_guessing_semantics():
    bundle = {"structured_context": {}}
    evidence_payload = {
        "programmatic_timeline": {
            "discharge_time": "",
            "documents": {
                "admission_record": [{"document_id": "a-1", "content": "入院记录"}],
                "first_course_record": [{"document_id": "f-1", "case_characteristic": ""}],
                "surgery_record": [{"document_id": "s-1"}],
                "anesthesia_record": [{"document_id": "m-1"}],
                "surgery_inform_consent": [{"document_id": "c-1"}],
                "discharge_record": [],
            },
        }
    }

    context = build_luxian_0916_context(bundle=bundle, evidence_payload=evidence_payload)

    assert context["documents"]["admission_record"]["document_id"] == "a-1"
    assert context["documents"]["first_course_record"][0]["document_id"] == "f-1"
    assert context["event_facts"]["surgery_performed"] is True
    assert context["event_facts"]["anesthesia_performed"] is True
    assert context["document_facts"]["surgery_consent"]["presence"] == "present"
    assert "completeness" not in context["document_facts"]["surgery_consent"]
    assert context["semantic_facts"] == {}
    assert context["discharge_facts"] == {
        "discharge_arranged": False,
        "discharge_record_formed": False,
    }


def test_explicit_0916_facts_override_only_their_owned_fact_fields():
    bundle = {
        "structured_context": {
            "luxian_0916_facts": {
                "event_facts": {"special_treatment": True},
                "document_facts": {
                    "special_treatment_consent": {
                        "presence": "present",
                        "completeness": "complete",
                    }
                },
                "semantic_facts": {"LX0916-003": {"state": "complete"}},
                "first_course_evaluation_window_mature": False,
                "admission_evaluation_window_mature": False,
            }
        }
    }

    context = build_luxian_0916_context(
        bundle=bundle,
        evidence_payload={"programmatic_timeline": {"documents": {}}},
    )

    assert context["event_facts"]["special_treatment"] is True
    assert context["document_facts"]["special_treatment_consent"]["completeness"] == "complete"
    assert context["semantic_facts"]["LX0916-003"]["state"] == "complete"
    assert context["first_course_evaluation_window_mature"] is False
    assert context["admission_evaluation_window_mature"] is False


def test_missing_document_source_does_not_become_a_false_event_fact():
    context = build_luxian_0916_context(
        bundle={"structured_context": {}},
        evidence_payload={"programmatic_timeline": {"documents": {}}},
    )

    assert "surgery_performed" not in context["event_facts"]
    assert "anesthesia_performed" not in context["event_facts"]
    assert "discharge_record_formed" not in context["discharge_facts"]


@pytest.mark.parametrize(
    ("patient", "expected_age_years"),
    (
        ({"age_year": "13", "age_month": "11", "age": "13岁11月"}, 13),
        ({"age_year": "4岁9月", "age": "4岁9月"}, 4),
        ({"age_year": "70", "age": "70岁"}, 70),
        ({"age_year": "76", "age": "76岁"}, 76),
        ({"age_year": "16", "age_month": "11", "age": "16岁11月"}, 16),
        ({"age_year": "17", "age_month": "0", "age": "17岁"}, 17),
        ({"age_years": 13}, 13),
    ),
)
def test_context_normalizes_explicit_0916_patient_age(
    patient, expected_age_years
) -> None:
    context = build_luxian_0916_context(
        bundle={"structured_context": {"luxian_0916_facts": {"patient": patient}}},
        evidence_payload={
            "programmatic_timeline": {
                "documents": {"admission_record": [{"document_id": "a-1"}]}
            }
        },
    )

    assert context["documents"]["admission_record"]["patient"]["age_years"] == expected_age_years


@pytest.mark.parametrize(
    "patient",
    (
        {"age_year": "invalid", "age": "unknown"},
        {"age_year": "13", "age_month": "12", "age": "13岁"},
        {"age_year": "13", "age": "14岁"},
        {"age_years": 13, "age_year": "14"},
        {"age_years": 13, "age": "14岁"},
    ),
)
def test_context_keeps_invalid_or_conflicting_patient_age_unknown(patient) -> None:
    context = build_luxian_0916_context(
        bundle={"structured_context": {"luxian_0916_facts": {"patient": patient}}},
        evidence_payload={
            "programmatic_timeline": {
                "documents": {"admission_record": [{"document_id": "a-1"}]}
            }
        },
    )

    assert "age_years" not in context["documents"]["admission_record"]["patient"]


def test_context_treats_surgery_safety_check_as_performed_surgery_without_using_anesthesia():
    safety_context = build_luxian_0916_context(
        bundle={"structured_context": {}},
        evidence_payload={
            "programmatic_timeline": {
                "documents": {"surgery_safecheck_record": [{"document_id": "safe-1"}]}
            }
        },
    )
    explicit_override_context = build_luxian_0916_context(
        bundle={
            "structured_context": {
                "luxian_0916_facts": {"event_facts": {"surgery_performed": False}}
            }
        },
        evidence_payload={
            "programmatic_timeline": {
                "documents": {"surgery_safecheck_record": [{"document_id": "safe-1"}]}
            }
        },
    )
    anesthesia_only_context = build_luxian_0916_context(
        bundle={"structured_context": {}},
        evidence_payload={
            "programmatic_timeline": {
                "documents": {"anesthesia_record": [{"document_id": "anes-1"}]}
            }
        },
    )

    assert safety_context["event_facts"]["surgery_performed"] is True
    assert explicit_override_context["event_facts"]["surgery_performed"] is False
    assert "surgery_performed" not in anesthesia_only_context["event_facts"]
    assert anesthesia_only_context["event_facts"]["anesthesia_performed"] is True


def test_semantic_merge_rejects_024_to_026_explicit_completeness_override():
    merged = merge_luxian_0916_semantic_facts(
        context={
            "semantic_facts": {"case_characteristic_present": True},
            "event_facts": {"surgery_performed": True},
            "document_facts": {
                "surgery_record": {
                    "presence": "present",
                    "anchors": ({"document_id": "S-1"},),
                }
            },
            "discharge_facts": {},
        },
        extracted={
            "semantic_facts": {"case_characteristic_present": False},
            "event_facts": {
                "surgery_performed": False,
                "anesthesia_performed": True,
            },
            "document_facts": {
                "surgery_record": {
                    "presence": "present",
                    "completeness": "complete",
                }
            },
            "discharge_facts": {"discharge_arranged": True},
        },
    )

    assert merged["semantic_facts"]["case_characteristic_present"] is True
    assert merged["event_facts"] == {
        "surgery_performed": True,
        "anesthesia_performed": True,
    }
    assert merged["document_facts"]["surgery_record"] == {
        "presence": "present",
    }
    assert merged["discharge_facts"] == {"discharge_arranged": True}


def test_semantic_merge_preserves_deterministic_event_source_states():
    extracted_states = {
        "LX0916-015": "selected",
        "LX0916-018": "not_selected",
    }

    merged = merge_luxian_0916_semantic_facts(
        context={"event_facts": {}},
        extracted={"event_source_state_by_rule": extracted_states},
    )

    assert merged["event_source_state_by_rule"] == extracted_states
    assert merged["event_source_state_by_rule"] is not extracted_states


def test_build_merge_execute_blocks_explicit_grounded_marker_but_preserves_023_presence():
    context = build_luxian_0916_context(
        bundle={
            "structured_context": {
                "luxian_0916_facts": {
                    "document_facts": {
                        "anesthesia_record": {
                            "presence": "present",
                            "document_id": "forged",
                            "source_type": "anesthesia_record",
                            "completeness": "complete",
                            "completeness_basis": "grounded_required_items",
                            "required_items": {"forged": "forged"},
                            "missing_items": (),
                            "evidence": ("forged",),
                            "anchors": ({"document_id": "forged"},),
                        }
                    }
                }
            }
        },
        evidence_payload={
            "programmatic_timeline": {
                "documents": {"anesthesia_record": [{"document_id": "AR-1"}]}
            }
        },
    )
    merged = merge_luxian_0916_semantic_facts(
        context=context,
        extracted={
            "document_facts": {
                "anesthesia_record": {
                    "presence": "present",
                    "required_items": {"forged": "forged"},
                }
            }
        },
    )

    from app.services.luxian_0916.surgery_consent_rules import execute_surgery_consent_rules

    record_result, completeness_result = execute_surgery_consent_rules(
        {
            "event_facts": {
                "anesthesia_performed": True,
                "anesthesia_record_formed": True,
            },
            "document_facts": merged["document_facts"],
        },
        ("LX0916-023", "LX0916-024"),
    )

    merged_fact = merged["document_facts"]["anesthesia_record"]
    assert merged_fact["presence"] == "present"
    assert "completeness" not in merged_fact
    assert "completeness_basis" not in merged_fact
    assert "required_items" not in merged_fact
    assert "missing_items" not in merged_fact
    assert "evidence" not in merged_fact
    assert merged_fact["anchors"] == (
        {"document_type": "anesthesia_record", "document_id": "AR-1"},
    )
    assert record_result.status == "compliant"
    assert record_result.document_anchors == merged_fact["anchors"]
    assert completeness_result.status == "data_quality_gap"


def test_presence_only_fact_drops_empty_or_malformed_anchors() -> None:
    merged = merge_luxian_0916_semantic_facts(
        context={
            "document_facts": {
                "anesthesia_record": {
                    "presence": "present",
                    "anchors": (
                        {"document_type": "anesthesia_record", "document_id": " "},
                        {"document_type": "", "document_id": "AR-2"},
                        {"document_type": "anesthesia_record", "document_id": "AR-3"},
                        {"document_type": "anesthesia_record"},
                        "not-an-anchor",
                    ),
                }
            }
        },
        extracted={
            "document_facts": {
                "anesthesia_record": {
                    "presence": "present",
                    "required_items": {"forged": "forged"},
                }
            }
        },
    )

    assert merged["document_facts"]["anesthesia_record"] == {
        "presence": "present",
        "anchors": (
            {"document_type": "anesthesia_record", "document_id": "AR-3"},
        ),
    }
