from copy import deepcopy

import pytest

from app.services.draft_test_validation_service import fixed_test_validation_state


def _draft():
    revision = "2026-09-28T12:00:01+00:00"
    selected = [
        {
            "item_id": f"item-{number}", "item_updated_at": "2026-09-28T11:00:00+00:00",
            "record_ref": {"institute_id": "H1", "patient_id": f"P{number}", "visit_id": "V1"},
        }
        for number in (1, 2)
    ]
    return {
        "id": "draft-1", "status": "draft", "updated_at": revision,
        "prompt_template": "明确的测试判据", "check_logic": {},
        "last_test_summary": {
            "schema_version": "fixed_test_records_v1", "validation_id": "validation-1",
            "draft_id": "draft-1", "validated_revision": "2026-09-28T12:00:00+00:00",
            "proof_revision": revision, "created_at": revision,
            "item_count": 2, "success_count": 2, "failed_count": 0,
            "issue_records": 0, "compliant_records": 2,
            "unknown_count": 0, "technical_error_count": 0,
            "selected_items": selected,
            "results": [
                {
                    **deepcopy(item), "status": "compliant", "issue_count": 0,
                    "finding": {"description": "未触发缺陷", "evidence": ""},
                    "condition_trace": [],
                }
                for item in selected
            ],
            "failures": [],
        },
    }


def test_complete_server_proof_accepts_distinct_patients_sharing_visit_number():
    assert fixed_test_validation_state(_draft()) == (True, None)


@pytest.mark.parametrize("corruption", ["non_object", "duplicate", "identity", "version", "draft"])
def test_publish_rejects_broken_or_mismatched_proof_even_with_success_count(corruption):
    draft = _draft()
    proof = draft["last_test_summary"]
    if corruption == "non_object":
        proof["results"][1] = None
    elif corruption == "duplicate":
        proof["results"][1] = deepcopy(proof["results"][0])
    elif corruption == "identity":
        proof["results"][1]["record_ref"]["institute_id"] = "OTHER-HOSPITAL"
    elif corruption == "version":
        proof["results"][1]["item_updated_at"] = "2026-09-28T10:00:00+00:00"
    else:
        proof["draft_id"] = "other-draft"
    assert fixed_test_validation_state(draft)[0] is False


def test_definition_change_invalidates_completed_proof():
    draft = _draft()
    draft["updated_at"] = "2026-09-28T12:00:02+00:00"
    assert fixed_test_validation_state(draft) == (False, "draft_changed")


@pytest.mark.parametrize("count", ["broken", "2", True, None, {}, 2.0])
def test_corrupt_success_count_is_rejected_without_exception(count):
    draft = _draft()
    draft["last_test_summary"]["success_count"] = count
    assert fixed_test_validation_state(draft)[0] is False


def test_published_draft_cannot_be_published_again():
    draft = _draft()
    draft["status"] = "published"
    draft["published_rule_id"] = "rule-1"
    assert fixed_test_validation_state(draft)[0] is False


@pytest.mark.parametrize("field", [
    "failed_count", "issue_records", "compliant_records", "unknown_count", "technical_error_count",
])
@pytest.mark.parametrize("value", [None, True, -1, 99])
def test_summary_counts_must_match_individual_results(field, value):
    draft = _draft()
    draft["last_test_summary"][field] = value
    assert fixed_test_validation_state(draft)[0] is False
