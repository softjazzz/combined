"""QC43 v2：手术覆盖回归及客户判断说明，仅使用合成材料。"""
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609_rule_catalog import load_luxian_0609_engine_judgment
from test_luxian_0609_native_surgery_gate_execution import (
    CREATED_AT,
    SnapshotSourceRows,
    _typed_003_session,
    build_luxian_0609_evidence_read_session,
)


def _anesthesia(day, *, minute=0, document_id=None):
    return {
        "document_id": document_id or f"a{day}-{minute}",
        "record_content": (
            "本次手术已完成。"
            f"手术开始时间：2026-01-{day:02d} 01:{minute:02d}:00+08:00 "
            f"手术结束时间：2026-01-{day:02d} 08:00:00+08:00"
        ),
    }


def _record(day, *, document_id=None, begin=True):
    return {
        "document_id": document_id or f"s{day}",
        "surgery_begin_time": datetime(2026, 1, day, 1) if begin else None,
        "surgery_end_time": datetime(2026, 1, day, 8),
        "record_time": datetime(2026, 1, day, 9),
    }


def _multi_session(records, anesthesia):
    def reader(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source,
            rows={"surgery_record": records, "anesthesia_record": anesthesia}.get(source, ()),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-02-01",), institute_id="I", patient_id="P",
        visit_id="V", source_schema=None, created_at=CREATED_AT,
        evaluation_as_of_date="2026-01-05", row_reader=reader,
    )


@pytest.mark.parametrize(
    "begin,anesthesia,expected",
    [
        pytest.param(datetime(2026, 1, 1, 1), (_anesthesia(1, minute=5),), "satisfied", id="A1"),
        pytest.param(None, (_anesthesia(1),), "satisfied", id="A2"),
        pytest.param(datetime(2026, 1, 1, 1), (_anesthesia(1), _anesthesia(2)), "association_failed", id="A3"),
        pytest.param(datetime(2026, 1, 1, 1), (_anesthesia(1), _anesthesia(1, document_id="a-copy")), "satisfied", id="A5"),
    ],
)
def test_single_record_coverage(begin, anesthesia, expected):
    session = _typed_003_session(
        surgery_document_id="s1", surgery_begin_time=begin,
        surgery_time=datetime(2026, 1, 1, 8), record_time=datetime(2026, 1, 1, 9),
        original_anesthesia_rows=anesthesia, evaluation_as_of_date="2026-01-05",
    )
    decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
    if expected == "satisfied":
        assert decision.qc_direction.value == "satisfied"
    else:
        assert decision.evidence_state.value == "data_gap"
        assert decision.reason_code == expected


@pytest.mark.parametrize(
    "records,anesthesia,expected",
    [
        pytest.param((_record(1), _record(2)), (_anesthesia(1), _anesthesia(2)), "satisfied", id="A4"),
        pytest.param((_record(1), _record(1, document_id="s-copy")), (_anesthesia(1), _anesthesia(2)), "association_failed", id="A6"),
        pytest.param((_record(1, document_id="same"), _record(2, document_id="same")), (_anesthesia(1), _anesthesia(2)), "association_failed", id="duplicate-identity-conflict"),
        pytest.param((_record(1, begin=False), _record(2, begin=False)), (_anesthesia(1), _anesthesia(2)), "association_failed", id="unknown-event-identity"),
        pytest.param((_record(1), _record(2)), (_anesthesia(1, minute=5), _anesthesia(2, minute=5)), "satisfied", id="distinct-records-not-exact-times"),
    ],
)
def test_distinct_record_coverage(records, anesthesia, expected):
    session = _multi_session(records, anesthesia)
    decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
    if expected == "satisfied":
        assert decision.qc_direction.value == "satisfied"
    else:
        assert decision.evidence_state.value == "data_gap"
        assert decision.reason_code == expected


def test_records_completed_before_second_operation_cannot_cover_it():
    records = (
        _record(1),
        {**_record(1, document_id="s-before-second-operation"),
         "surgery_begin_time": datetime(2026, 1, 1, 1, 5)},
    )
    session = _multi_session(records, (_anesthesia(1), _anesthesia(2)))
    decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
    assert decision.evidence_state.value == "data_gap"
    assert decision.reason_code == "association_failed"


def test_similarity_judgment_does_not_promise_model_review():
    steps = " ".join(load_luxian_0609_engine_judgment()["rules"]["LX0609-12-01-02"]["steps"])
    assert not any(phrase in steps for phrase in ("模型复核", "调用一次模型", "进入问题候选"))
    assert "70%" in steps and "及以上" in steps and "程序" in steps


def test_invasive_judgment_does_not_use_homepage_codes():
    steps = " ".join(load_luxian_0609_engine_judgment()["rules"]["LX0609-10-03-01"]["steps"])
    assert "首页手术操作编码" not in steps
    assert "原始医嘱" in steps and "文书" in steps
