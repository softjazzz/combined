import pytest

from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.course_quality.rule_007 import evaluate_rule_007_typed, rule_007_customer_display_facts
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result


def test_existing_rounds_with_missing_registration_explain_actual_gap():
    def reader(**kwargs):
        source = kwargs["source_key"]
        rows = ([{"document_id": "round-1", "document_title": "查房记录", "record_time": "2026-01-02 08:00:00", "record_content": "查房内容"}]
                if source == "senior_course_record" else [])
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-03T09:00:00+08:00", row_reader=reader,
    )
    decision = evaluate_rule_007_typed(snapshot=session.snapshot, materials=session.materials)
    facts = rule_007_customer_display_facts(materials=session.materials, decision=decision)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,), expected_rule_ids=("LX0609-007",), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    result = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=facts,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert result["status"] == "data_gap"
    assert result["customer_display_facts"]["gap_source"] == "inpat_registration"
    assert result["data_gap_details"]["missing_sources"] == ["本次住院登记"]
    assert result["data_gap_details"]["missing_fields"] == ["入院时间"]
    assert result["data_gap_details"]["customer_message"] == result["findings"]
    assert "缺少病情稳定期间查房记录时间" not in result["findings"]
    assert "未读取到本次住院登记" in result["findings"]

def _run_admission_fallback_case(registration_rows, admission_rows):
    from app.services.luxian_0609.source_evidence_reader import CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY

    rows_by_source = {
        "inpat_registration": registration_rows,
        "admission_record": admission_rows,
        "senior_course_record": [{"document_id": "round-1", "document_title": "查房记录", "record_time": "2025-08-15 17:30:00", "record_content": "查房内容"}],
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [{"discharge_datetime": "2025-08-16 08:00:00"}],
    }
    def reader(**kwargs):
        # 真实读取边界必须保持同一机构、患者、就诊；不能用病案号替换就诊号。
        assert (kwargs["institute_id"], kwargs["patient_id"], kwargs["visit_id"]) == ("I", "P", "V")
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=source, rows=rows_by_source.get(source, []), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2025-08-16T09:00:00+08:00", row_reader=reader,
    )
    decision = evaluate_rule_007_typed(snapshot=session.snapshot, materials=session.materials)
    facts = rule_007_customer_display_facts(materials=session.materials, decision=decision)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,), expected_rule_ids=("LX0609-007",), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=facts,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


@pytest.mark.parametrize("anchor_field", ["admission_datetime", "admission_time"])
@pytest.mark.parametrize("registration_rows", [[], [{"admission_datetime": None}]])
def test_007_admission_document_anchor_is_not_record_or_submit_time(anchor_field, registration_rows):
    result = _run_admission_fallback_case(
        registration_rows,
        [{"document_id": "admission-1", anchor_field: "2025-08-12 17:24:13", "record_time": "2025-08-12 17:42:11", "submit_time": "2025-08-20 20:15:36"}],
    )
    # 首次查房比真实入院晚72小时5分47秒；误用记录时间会错误放行。
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["interval_start_time"] == "2025-08-12 17:24:13"
    assert result["customer_display_facts"]["interval_start_source"] == "admission_record"
    assert any(
        item["source_type"] == "admission_record"
        and item["source_document_id"] == "admission-1"
        for item in result["customer_evidence"]
    )


def test_007_registration_anchor_takes_priority_over_admission_document():
    result = _run_admission_fallback_case(
        [{"admission_datetime": "2025-08-13 08:00:00"}],
        [{"document_id": "admission-1", "admission_time": "2025-08-12 17:24:13"}],
    )
    assert result["status"] == "compliant"


def test_007_conflicting_registration_must_not_fall_back_to_document():
    result = _run_admission_fallback_case(
        [{"admission_datetime": "2025-08-12 17:24:13"}, {"admission_datetime": "2025-08-13 08:00:00"}],
        [{"document_id": "admission-1", "admission_time": "2025-08-13 08:00:00"}],
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_conflict"


def test_007_conflicting_admission_documents_fail_closed():
    result = _run_admission_fallback_case(
        [],
        [{"document_id": "admission-1", "admission_time": "2025-08-12 17:24:13"}, {"document_id": "admission-2", "admission_time": "2025-08-13 08:00:00"}],
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_conflict"


def test_007_record_and_submit_times_do_not_fill_missing_admission_anchor():
    result = _run_admission_fallback_case(
        [],
        [{"document_id": "admission-1", "record_time": "2025-08-12 17:42:11", "submit_time": "2025-08-20 20:15:36"}],
    )
    assert result["status"] == "data_gap"


def _run_round_time_gap_case(*, discharge_time, registration_has_id=True, round_has_id=True):
    from app.services.luxian_0609.source_evidence_reader import CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY

    rows_by_source = {
        "inpat_registration": [{"document_id": "registration-1", "admission_datetime": "2026-01-01 08:00:00"}],
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [{"discharge_datetime": discharge_time}],
        "senior_course_record": [
            {"document_id": "round-1", "document_title": "上级医师查房记录", "record_time": "2026-01-02 08:00:00", "record_content": "查房内容"},
            {"document_id": "round-2", "document_title": "上级医师查房记录", "record_time": "2026-01-03 08:00:00", "record_content": "查房内容"},
            {"document_id": "round-missing-time", "document_title": "出院前上级医师查房记录", "record_content": "查房内容"},
        ],
    }

    if not registration_has_id:
        rows_by_source["inpat_registration"][0].pop("document_id")
    if not round_has_id:
        rows_by_source["senior_course_record"][-1].pop("document_id")

    def reader(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=source, rows=rows_by_source.get(source, []), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-09-09T09:00:00+08:00", row_reader=reader,
    )
    decision = evaluate_rule_007_typed(snapshot=session.snapshot, materials=session.materials)
    if discharge_time == "2026-01-04 08:00:00":
        missing_refs = {
            ref for ref, row in session.materials.document_rows("senior_course_record", snapshot=session.snapshot)
            if row.get("document_id") == "round-missing-time"
        }
        assert missing_refs and missing_refs.isdisjoint(decision.fact_refs)
    facts = rule_007_customer_display_facts(materials=session.materials, decision=decision)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,), expected_rule_ids=("LX0609-007",), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=facts,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


def test_007_missing_round_time_explains_count_and_projects_missing_document():
    result = _run_round_time_gap_case(discharge_time="2026-01-09 08:00:00")
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"
    assert result["customer_display_facts"] == {
        "failure_kind": "course_interval_source_gap", "gap_source": "senior_course_record",
        "gap_kind": "time_missing", "record_count": 3, "missing_time_count": 1,
    }
    assert result["data_gap_details"]["missing_fields"] == ["上级医师查房记录的权威时间（1份）"]
    assert "已读取3份上级医师查房记录，其中1份缺少有效的查房记录时间" in result["findings"]
    assert any(item["source_document_id"] == "round-missing-time" for item in result["customer_evidence"])


def test_007_missing_time_extra_round_does_not_change_complete_coverage():
    result = _run_round_time_gap_case(discharge_time="2026-01-04 08:00:00")
    assert result["status"] == "compliant"
    assert all(item["source_document_id"] != "round-missing-time" for item in result.get("customer_evidence", []))


@pytest.mark.parametrize("counts", [{"record_count": True, "missing_time_count": 1}, {"record_count": 3, "missing_time_count": 4}, {"record_count": 3}, {"record_count": 3, "missing_time_count": 0}])
def test_007_gap_display_rejects_invalid_counts(counts):
    from app.services.luxian_0609.course_quality_result_mapping import course_007_gap_display

    assert course_007_gap_display({
        "failure_kind": "course_interval_source_gap", "gap_source": "senior_course_record",
        "gap_kind": "time_missing", **counts,
    }) is None


def test_007_registration_without_document_id_preserves_round_locations():
    result = _run_round_time_gap_case(discharge_time="2026-01-09 08:00:00", registration_has_id=False)
    assert result["status"] == "data_gap"
    assert {item["source_document_id"] for item in result["customer_evidence"]} == {"round-1", "round-2", "round-missing-time"}


def test_007_missing_round_identity_still_fails_closed():
    result = _run_round_time_gap_case(discharge_time="2026-01-09 08:00:00", registration_has_id=False, round_has_id=False)
    assert result["status"] == "data_gap"
    assert result.get("customer_evidence", []) == []
