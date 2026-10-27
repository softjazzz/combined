"""冻结时点后的文书不能提前满足入院、首程与主治查房时限。"""

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from tests.unit.test_luxian_0609_native_basic_timeliness import (
    _typed_basic_session,
    _reduce_typed_basic,
)
from test_luxian_0609_death_record_timeliness import saved_roundtrip


@pytest.mark.parametrize(
    "rule,source,body",
    [
        ("LX0609-01-01-01", "admission_record", {"chief_complaint": "反复头痛。"}),
        (
            "LX0609-01-02-01",
            "first_course_record",
            {"record_content": "患者突发头痛，入院进一步诊治，完善检查。"},
        ),
    ],
)
def test_post_discharge_completion_before_task_freeze_keeps_original_deadline(
    rule, source, body
):
    from app.services.luxian_0609.evaluation_horizon import (
        build_record_evaluation_horizon_snapshot,
    )
    from app.services.luxian_0609.evidence_snapshot_provider import (
        SnapshotSourceRows,
        build_luxian_0609_evidence_read_session,
    )

    frozen = build_record_evaluation_horizon_snapshot(
        [
            {
                "record_id": "V",
                "institute_id": "I",
                "patient_id": "P",
                "visit_id": "V",
                "scope": "final",
                "admission_datetime": "2026-01-01 08:00:00",
                "discharge_datetime": "2026-01-01 12:00:00",
            }
        ],
        task_frozen_date="2026-01-02",
    )[0]
    rows = {
        "inpat_registration": [
            {
                "admission_datetime": "2026-01-01 08:00:00",
                "discharge_datetime": "2026-01-01 12:00:00",
            }
        ],
        source: [
            {
                "document_id": "POST-DISCHARGE",
                "record_time": "2026-01-01 14:00:00",
                **body,
            }
        ],
    }

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-01-02T10:00:00+08:00",
        evaluation_as_of_date="2026-01-02",
        evaluation_horizon_policy="authoritative_discharge",
        evaluation_horizon_snapshot=frozen,
        row_reader=reader,
    )
    execution, reduced = _reduce_typed_basic(session, (rule,))
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0],
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["elapsed_hours"] == 6
    assert saved_roundtrip(final)["status"] == "compliant"


@pytest.mark.parametrize(
    "rule,source,record_time,body",
    [
        (
            "LX0609-01-01-01",
            "admission_record",
            "2026-01-02 07:00:00",
            {"chief_complaint": "反复头痛。"},
        ),
        (
            "LX0609-01-02-01",
            "first_course_record",
            "2026-01-02 02:00:00",
            {"record_content": "患者突发头痛，入院进一步诊治，完善检查。"},
        ),
        (
            "LX0609-02-01-01",
            "senior_course_record",
            "2026-01-03 18:00:00",
            {
                "document_title": "主治医师首次查房记录",
                "record_content": "主治医师查房。",
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "frozen,state",
    [("2026-01-01", "data_gap"), ("2026-01-04", "compliant"), (None, "data_gap")],
)
def test_document_becomes_usable_only_at_its_frozen_evaluation_date(
    rule, source, record_time, body, frozen, state
):
    rows = {
        "inpat_registration": [{"admission_datetime": "2026-01-01 20:00:00"}],
        source: [{"document_id": "TARGET", "record_time": record_time, **body}],
    }
    session = _typed_basic_session(
        rows, selected_rule_ids=(rule,), evaluation_as_of_date=frozen
    )
    execution, reduced = _reduce_typed_basic(session, (rule,))
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0],
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert final["status"] == state
    if state == "data_gap":
        assert final["reason_code"] == (
            "evaluation_window_not_mature" if frozen else "authoritative_time_missing"
        )
    loaded = saved_roundtrip(final)
    assert loaded["status"] == state
    assert loaded.get("customer_display_facts") == final.get("customer_display_facts")
    assert getattr(execution, "llm_call_count", 0) == 0
