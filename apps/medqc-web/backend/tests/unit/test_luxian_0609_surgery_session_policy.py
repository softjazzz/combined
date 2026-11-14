"""主控代定口径（2026-10-18，待客户复核）：合成台次与逐台文书覆盖。"""

from datetime import datetime

import pytest

from app.services.luxian_0609 import native_surgery_document_execution as documents
from app.services.luxian_0609 import native_surgery_gate_execution as gates
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.surgery_event_association import (
    _has_strict_cross_source_bijection,
    _is_single_composite_event,
    build_performed_surgery_events,
    count_associated_performed_surgery_events,
    group_surgery_rows_by_start,
)
from app.services.luxian_0609.surgery_procedure_catalog import classify_surgery_procedure
from app.services.luxian_0609.surgery_procedure_catalog import load_surgery_procedure_catalog


class Materials:
    def __init__(self, **sources):
        self.sources = sources

    def rows(self, source):
        return self.sources.get(source, ())


def master(index, *, day=1, hour=8, method="全身麻醉"):
    return {
        "surgery_id": f"surgery-{index}", "surgery_name": f"合成术式{index}",
        "surgical_level": "二级", "surgeon": f"合成术者{index}",
        "surgery_begin_datetime": datetime(2026, 1, day, hour),
        "anesthesia_method": method,
    }


def record(index, *, day=1, hour=8, method="全身麻醉"):
    return {
        "document_id": f"record-{index}", "surgery_id": f"surgery-{index}",
        "surgery_name": f"合成术式{index}", "anesthesia_method": method,
        "surgeon": f"合成术者{index}",
        "surgery_begin_time": f"2026-01-{day:02} {hour:02}:00:00+08:00",
        "surgery_process": "合成手术过程记录。",
    }


def summary(index, *, day=1):
    return {"document_id": f"summary-{index}", "record_time": f"2026-01-{day:02} 07:00:00",
            "record_content": "术前小结：合成术前准备已经完成。"}


def anesthesia(index, *, day=1, hour=8):
    return {"document_id": f"anesthesia-{index}", "anesthesia_method": "全身麻醉",
            "record_content": f"手术开始时间：2026-01-{day:02} {hour:02}:00:00+08:00\n合成麻醉记录。"}


async def run(rule, **sources):
    def reader(**kwargs):
        source = kwargs["source_key"]
        rows = sources.get(source, ())
        if source == "evaluation_context.horizon":
            rows = ({"horizon_date": "2026-01-10"},)
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-10T12:00:00+08:00", row_reader=reader,
    )
    if rule == "LX0609-04-02-01":
        result = await gates.execute_luxian_0609_native_surgery_gate_rules(
            rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=[], evidence_payload=None,
            visit_id="V", institute_id="I", patient_id="P", source_schema=None, llm_client=None,
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        )
    else:
        result = await documents.execute_luxian_0609_native_surgery_document_rules(
            rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=[], evidence_payload=None,
            llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    return final["status"], final["reason_code"]


def test_formal_components_merge_and_union_surgeons():
    events, reason = build_performed_surgery_events(Materials(surgery_record=[record(1), record(2)]))
    assert reason == "" and len(events) == 1
    assert set(events[0].row["surgeon"].split("、")) == {"合成术者1", "合成术者2"}
    assert len(events[0].component_rows) == 2


@pytest.mark.parametrize("hours, expected", [([8, 8], 1), ([8, 14], 2)])
def test_master_count_uses_exact_start(hours, expected):
    # 首页只在历史纯关联 helper 中保留边界，不参与当前质控触发。
    groups = group_surgery_rows_by_start(
        "mr_surgery", [master(i, hour=hour) for i, hour in enumerate(hours)]
    )
    assert groups is not None and len(groups) == expected


def test_same_day_different_component_starts_do_not_collapse_across_sources():
    assert not _is_single_composite_event(
        [record(1)], [master(1), master(2, hour=14)]
    )
    assert count_associated_performed_surgery_events(Materials(
        surgery_record=[record(1), record(2, hour=14)],
    )) == (2, "")


def test_master_missing_start_does_not_merge_using_end():
    rows = [master(1), master(2)]
    rows[1]["surgery_begin_datetime"] = None
    rows[1]["surgery_end_datetime"] = datetime(2026, 1, 1, 10)
    assert group_surgery_rows_by_start("mr_surgery", rows) is None


def test_untimed_qualified_master_component_stays_gap():
    rows = [master(1), master(2)]
    rows[1]["surgery_begin_datetime"] = None
    assert group_surgery_rows_by_start("mr_surgery", rows) is None


def test_formal_components_without_start_stay_gap():
    row = record(1)
    row["surgery_begin_time"] = None
    row["surgery_end_time"] = "2026-01-01 10:00:00+08:00"
    assert build_performed_surgery_events(Materials(surgery_record=[row])) == (None, "association_failed")


def test_formal_same_day_different_starts_remain_separate():
    events, reason = build_performed_surgery_events(Materials(surgery_record=[record(1), record(2, hour=14)]))
    assert reason == "" and len(events) == 2


def test_cross_source_component_order_does_not_change_session_identity():
    records = [record(1), record(2), record(3, hour=14), record(4, hour=14)]
    masters = [master(2), master(1), master(4, hour=14), master(3, hour=14)]
    assert _has_strict_cross_source_bijection(records, masters)
    assert count_associated_performed_surgery_events(Materials(
        surgery_record=records,
    )) == (2, "")


@pytest.mark.asyncio
async def test_029_one_summary_covers_same_start_components():
    assert await run("LX0609-04-01-01", surgery_record=[record(1), record(2)],
                     presurg_summary=[summary(1)]) == ("compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_029_each_separate_session_needs_its_summary():
    rows = [record(1), record(2, day=3)]
    assert await run("LX0609-04-01-01", surgery_record=rows, presurg_summary=[summary(1)]) == (
        "non_compliant", "required_document_missing")
    assert await run("LX0609-04-01-01", surgery_record=rows,
                     presurg_summary=[summary(1), summary(2, day=3)]) == ("compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_029_source_date_conflict_stays_gap():
    # 两个临床实施时间字段冲突时，不用单台小结回退掩盖时间歧义。
    row = record(1)
    row["surgery_begin_datetime"] = "2026-01-03 08:00:00+08:00"
    assert await run("LX0609-04-01-01", surgery_record=[row],
                     presurg_summary=[summary(1)]) == ("data_gap", "association_failed")
    assert not _is_single_composite_event(
        [record(1)], [master(1, day=3), master(2, day=3)]
    )


@pytest.mark.asyncio
async def test_038_multiple_records_match_sessions_by_labeled_time():
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2), record(3, day=3)],
                     anesthesia_record=[anesthesia(1), anesthesia(2, day=3)]) == (
        "compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_038_extra_record_for_other_date_does_not_block_covered_session():
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2)],
                     anesthesia_record=[anesthesia(1), anesthesia(2, day=3)]) == (
        "compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_038_one_record_does_not_cover_two_different_starts():
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2, hour=14)],
                     anesthesia_record=[anesthesia(1)]) == ("non_compliant", "required_document_missing")


@pytest.mark.asyncio
async def test_038_unbound_records_stay_gap():
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2)], anesthesia_record=[
        {"document_id": "a", "record_content": "合成麻醉记录。"},
        {"document_id": "b", "record_content": "另一份合成麻醉记录。"},
    ]) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_038_date_precision_session_uses_unique_same_day_record():
    assert await run("LX0609-04-04-03", surgery_record=[record(1, hour=0), record(2, hour=0)],
                     anesthesia_record=[anesthesia(1), anesthesia(2, day=3)]) == (
        "compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_038_unknown_method_for_another_session_is_not_covered_globally():
    assert await run("LX0609-04-04-03", surgery_record=[record(1, method="-"), record(2, day=3)],
                     anesthesia_record=[anesthesia(1, day=3)]) == ("data_gap", "applicability_source_gap")


@pytest.mark.asyncio
async def test_038_local_session_does_not_require_anesthesia_record():
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2, day=3, method="局部浸润麻醉")],
                     anesthesia_record=[anesthesia(1)]) == ("compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_038_single_record_with_explicit_other_date_does_not_cover_components():
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2)],
                     anesthesia_record=[anesthesia(1, day=3)]) == ("non_compliant", "required_document_missing")


@pytest.mark.asyncio
async def test_038_business_key_and_time_conflict_stays_gap():
    row = anesthesia(1, day=3)
    row["surgery_id"] = "surgery-1"
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2)],
                     anesthesia_record=[row]) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_038_conflicting_labeled_times_do_not_use_single_session_fallback():
    row = anesthesia(1)
    row["record_content"] += "\n手术开始时间：2026-01-03 08:00:00+08:00"
    assert await run("LX0609-04-04-03", surgery_record=[record(1), record(2)],
                     anesthesia_record=[row]) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_003_merged_components_still_need_authoritative_end():
    assert await run("LX0609-04-02-01", surgery_record=[record(1), record(2)]) == (
        "data_gap", "authoritative_time_missing")


def test_catalog_intervention_components_trigger_as_surgery():
    # 用户口径（2026-10-21）：介入治疗按手术触发；复合名称仍只按已识别项分类，不猜测未识别项。
    intervention = next(row for row in load_surgery_procedure_catalog() if row.code == "00.6600X004")
    item = classify_surgery_procedure(name=f"合成未收录操作+{intervention.name}")
    assert item is not None and item.category == "介入治疗" and item.is_surgery
