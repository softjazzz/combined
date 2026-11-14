"""09563/09832端点精度、多事件关联和Canonical保存读取。"""

from datetime import date, datetime, timedelta

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from test_luxian_0609_death_record_timeliness import saved_roundtrip
from test_luxian_0609_surgery_record_event_coverage_regression import anesthesia

RESCUE = "LX0609-09-01-01"
SURGERY = "LX0609-04-02-01"
START = datetime(2026, 1, 1, 8)


async def pipeline(rule, rows, *, unavailable=(), truncated=()):
    def reader(**kwargs):
        key = kwargs["source_key"]
        if key in unavailable:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows.get(key, ()),
            truncated=key in truncated,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-01-10T12:00:00+08:00",
        evaluation_as_of_date="2026-01-10",
        row_reader=reader,
    )
    if rule == RESCUE:
        from app.services.luxian_0609.native_basic_timeliness import (
            execute_luxian_0609_native_basic_timeliness,
        )

        execution = execute_luxian_0609_native_basic_timeliness(
            rule_ids=(rule,),
            decision_rule_ids=(rule,),
            evidence_payload=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
    else:
        from app.services.luxian_0609.native_surgery_gate_execution import (
            execute_luxian_0609_native_surgery_gate_rules,
        )

        execution = await execute_luxian_0609_native_surgery_gate_rules(
            rule_ids=(rule,),
            decision_rule_ids=(rule,),
            wrapper_rules=[{"rule_id": rule}],
            evidence_payload=None,
            institute_id="I",
            patient_id="P",
            visit_id="V",
            source_schema=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            llm_client=None,
        )
    assert getattr(execution, "llm_call_count", 0) == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    result = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    loaded = saved_roundtrip(result)
    assert loaded["status"] == result["status"]
    assert loaded.get("customer_display_facts") == result.get("customer_display_facts")
    return result


def surgery_row(
    *,
    end=START + timedelta(hours=2),
    completion=START + timedelta(hours=3),
    identifier="S",
):
    return {
        "document_id": identifier,
        "surgery_name": "左侧手术",
        "surgeon": "甲",
        "surgery_begin_time": START,
        "surgery_end_time": end,
        "record_time": completion,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("rule,hours", [(RESCUE, 6), (SURGERY, 24)])
@pytest.mark.parametrize(
    "extra,state", [(-1, "compliant"), (0, "compliant"), (1, "non_compliant")]
)
async def test_exact_second_boundary_survives_saving(rule, hours, extra, state):
    end = START + timedelta(hours=2)
    completion = end + timedelta(hours=hours, seconds=extra)
    rows = (
        {
            "rescue_record": (
                {
                    "document_id": "R",
                    "record_content": "抢救结束时间：2026-01-01 10:00:00",
                    "record_time": completion,
                },
            )
        }
        if rule == RESCUE
        else {"surgery_record": (surgery_row(end=end, completion=completion),)}
    )
    assert (await pipeline(rule, rows))["status"] == state


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_rescue_events_keep_their_own_end_and_completion(reverse):
    rows = (
        {
            "document_id": "R1",
            "record_content": "抢救结束时间：2026-01-01 08:00:00",
            "record_time": "2026-01-01 14:00:00",
        },
        {
            "document_id": "R2",
            "record_content": "抢救结束时间：2026-01-03 08:00:00",
            "record_time": "2026-01-03 14:00:01",
        },
    )
    result = await pipeline(
        RESCUE, {"rescue_record": tuple(reversed(rows)) if reverse else rows}
    )
    assert result["status"] == "non_compliant"
    facts = result["customer_display_facts"]
    assert facts["anchor_time"] == "2026-01-03 08:00:00"
    assert {
        (r["rescue_end_time"], r["document_completion_time"], r["event_state"])
        for r in facts["rescue_events"]
    } == {
        ("2026-01-01 08:00:00", "2026-01-01 14:00:00", "within"),
        ("2026-01-03 08:00:00", "2026-01-03 14:00:01", "late"),
    }


@pytest.mark.asyncio
async def test_rescue_explicit_utc_end_and_completion_are_normalized_together():
    result = await pipeline(
        RESCUE,
        {
            "rescue_record": (
                {
                    "document_id": "UTC",
                    "record_content": "抢救结束时间：2026-01-01 09:00:00Z",
                    "record_time": "2026-01-01T15:00:00Z",
                },
            )
        },
    )
    assert result["status"] == "compliant"
    assert result["customer_display_facts"]["elapsed_hours"] == 6


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "抢救结束时间：2026-01-01 08:00:00not-a-clock",
        "抢救结束时间：2026-01-01 10:00:00；抢救结束时间：2026-01-01 09:00:00。",
    ],
)
async def test_rescue_malformed_or_nonunique_end_is_not_a_usable_anchor(text):
    result = await pipeline(
        RESCUE,
        {
            "rescue_record": (
                {
                    "document_id": "AMBIGUOUS",
                    "record_content": text,
                    "record_time": "2026-01-01 14:00:00",
                },
            )
        },
    )
    assert result["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_two_surgeries_are_checked_independently(reverse):
    rows = (
        surgery_row(identifier="S1", completion=START + timedelta(hours=26)),
        {
            **surgery_row(identifier="S2"),
            "surgery_begin_time": START + timedelta(days=2),
            "surgery_end_time": START + timedelta(days=2, hours=2),
            "record_time": START + timedelta(days=3, hours=2, seconds=1),
        },
    )
    result = await pipeline(
        SURGERY, {"surgery_record": tuple(reversed(rows)) if reverse else rows}
    )
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["elapsed_seconds"] == 86401


@pytest.mark.asyncio
@pytest.mark.parametrize("first", [START, date(2026, 1, 1), "2026-01-01"])
async def test_surgery_end_alias_cannot_hide_conflict_or_invalid_precision(first):
    row = surgery_row(end=first, completion=START + timedelta(days=1, hours=1))
    row["surgery_end_datetime"] = START + timedelta(days=1)
    result = await pipeline(SURGERY, {"surgery_record": (row,)})
    assert result["status"] == "data_gap"
    if isinstance(first, datetime):
        assert result["reason_code"] == "authoritative_time_conflict"
        assert result["customer_display_facts"]["conflicting_end_fields"] is True
        assert "字段存在冲突" in result["findings"]
        assert "早于" not in result["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unavailable", "truncated"])
@pytest.mark.parametrize("source", ["surgery_record", "mr_surgery"])
async def test_source_completeness_only_uses_clinical_surgery_records(mode, source):
    result = await pipeline(
        SURGERY,
        {
            "surgery_record": (surgery_row(),),
            "mr_surgery": (
                {
                    "surgery_name": "左侧手术",
                    "surgery_begin_datetime": START,
                    "surgery_end_datetime": START + timedelta(hours=2),
                },
            ),
        },
        unavailable=(source,) if mode == "unavailable" else (),
        truncated=(source,) if mode == "truncated" else (),
    )
    if source == "surgery_record":
        assert result["status"] == "data_gap"
        assert result["reason_code"] == "source_" + mode
    else:
        assert result["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("end", [None, date(2026, 1, 1), "2026-01-01"])
async def test_missing_surgery_record_cannot_use_start_or_date_as_precise_end(end):
    row = anesthesia()
    # 唯一麻醉文书仍必须显式提供完整结束时刻，开始时间及日期不能代替。
    row["record_content"] = (
        "本次手术已实施。手术开始时间：2026-01-01 08:00:00+08:00；"
        f"手术结束时间：{end or ''}。"
    )
    result = await pipeline(SURGERY, {"anesthesia_record": (row,)})
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("rule,hours", [(RESCUE, 6), (SURGERY, 24)])
async def test_accepted_subsecond_precision_survives_public_facts_and_saving(
    rule, hours
):
    end = START.replace(microsecond=100000)
    completion = end + timedelta(hours=hours, microseconds=100000)
    rows = (
        {
            "rescue_record": (
                {
                    "document_id": "PRECISE",
                    "record_content": "抢救结束时间：" + end.isoformat(sep=" "),
                    "record_time": completion,
                },
                {
                    "document_id": "OTHER",
                    "record_content": "抢救结束时间：2026-01-02 08:00:00",
                    "record_time": "2026-01-02 09:00:00",
                },
            )
        }
        if rule == RESCUE
        else {"surgery_record": (surgery_row(end=end, completion=completion),)}
    )
    result = await pipeline(rule, rows)
    assert result["status"] == "non_compliant"
    facts = result["customer_display_facts"]
    anchor = facts["anchor_time"] if rule == RESCUE else facts["surgery_end_time"]
    observed = facts["observed_time"] if rule == RESCUE else facts["record_time"]
    assert (
        datetime.fromisoformat(observed) - datetime.fromisoformat(anchor)
    ).total_seconds() == pytest.approx(hours * 3600 + 0.1, rel=0, abs=1e-9)


@pytest.mark.asyncio
@pytest.mark.parametrize("second_end", [None, START + timedelta(days=1, hours=2)])
@pytest.mark.parametrize("independent", [False, True])
async def test_incomplete_group_does_not_hide_independent_late_record(second_end, independent):
    from app.services.luxian_0609.native_surgery_gate_execution import _timeliness_group_end

    # 保留历史同开始时刻组件的全组结束锚点校验，不能取第一行补齐缺值或冲突。
    ends = ({"surgery_end_datetime": START + timedelta(hours=2)},
            {"surgery_end_datetime": second_end})
    anchor, issue = _timeliness_group_end(ends)
    assert anchor is None
    assert issue == ("authoritative_time_missing" if second_end is None else "authoritative_time_conflict")
    rows = (surgery_row(identifier="S1"), surgery_row(identifier="S2", end=second_end))
    if independent:
        rows += ({
            **surgery_row(identifier="LATE"),
            "surgery_begin_time": START - timedelta(days=10),
            "surgery_end_time": START - timedelta(days=10) + timedelta(hours=2),
            "record_time": START - timedelta(days=9) + timedelta(hours=3),
        },)
    result = await pipeline(SURGERY, {"surgery_record": rows})
    assert result["status"] == ("non_compliant" if independent else "data_gap")
    if independent:
        assert result["customer_display_facts"]["surgery_end_time"].startswith("2025-12-22")
