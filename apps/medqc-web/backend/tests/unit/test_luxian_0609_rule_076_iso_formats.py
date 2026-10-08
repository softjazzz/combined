"""076 明确时刻的 ISO 格式保护。"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.services.luxian_0609.extended_document.rule_076 import _parse_time, evaluate_rule_076


@pytest.mark.parametrize("fields", [
    {"death_time": "2026-07-01T00:05:00Z"},
    {"death_time": "2026-07-01 08:05:00.123456"},
    {"death_time": "2026-07-01", "record_content": "死亡时间：2026-07-01T08:05:00。"},
])
def test_known_concrete_iso_death_formats_remain_complete(fields):
    outcome = evaluate_rule_076(
        death_state="present",
        death_rows=(("d" * 64, {"record_content": "经抢救无效死亡。", **fields}),),
    )
    assert outcome.status == "compliant"
    assert outcome.reason_code == "requirement_satisfied"
    assert outcome.criterion_results[0].actual_value is True


@pytest.mark.parametrize("value", [
    "2026-07-01t00:05:00Z", "2026-07-01 00:00:00Z",
    "2026-07-01T08:05:00.123456+08:00", "2026.07.01 08:05:00.123456",
    "2026/07/01 08:05:00.123456",
])
def test_iso_formats_in_either_structured_death_field(value):
    for field in ("death_time", "death_datetime"):
        outcome = evaluate_rule_076(
            death_state="present",
            death_rows=(("d" * 64, {field: value, "record_content": "经抢救无效死亡。"}),),
        )
        assert outcome.status == "compliant"
        assert outcome.criterion_results[0].actual_value is True


def test_iso_parser_retains_offset_and_fractional_second_precision():
    assert _parse_time("2026-07-01T00:05:00Z") == datetime(
        2026, 7, 1, 0, 5, tzinfo=timezone.utc,
    )
    assert _parse_time("2026.07.01T08:05:00.123456+08:00") == datetime(
        2026, 7, 1, 8, 5, microsecond=123456,
        tzinfo=timezone(timedelta(hours=8)),
    )


@pytest.mark.parametrize("value", [
    "2026-07-01t08:05:00", "2026-07-01T00:05:00Z",
    "2026-07-01T08:05:00.123456+08:00", "2026.07.01T08:05:00.123456",
    "2026/07/01 08:05:00.123456",
])
@pytest.mark.parametrize("template", ["死亡时间：{}。", "患者于{}宣告临床死亡。"])
def test_existing_death_labels_capture_a_complete_iso_time(value, template):
    outcome = evaluate_rule_076(
        death_state="present",
        death_rows=(("d" * 64, {"death_time": "2026-07-01", "record_content": template.format(value)}),),
    )
    assert outcome.status == "compliant"


@pytest.mark.parametrize("value", [
    "2026-07-01", "2026-07-01T08", "2026-02-30T08:05:00Z",
    "2026-07-01T24:00:00Z", "2026-07-01T08:60:00Z",
    "2026-07-01T08:05:99Z", "2026-07-01T08:05:00+25:00",
    "2026-07-01T08:05:00.123456oops", "2026-07-01T08:05:00+08:invalid",
    "2026-07-01T08:05:00.abc", "2026-07-01T08:05:00+8",
])
def test_invalid_time_tokens_are_not_shortened_to_valid_prefixes(value):
    for fields in ({"death_time": value, "record_content": "经抢救无效死亡。"},
                   {"death_time": "2026-07-01", "record_content": "死亡时间：" + value + "。"}):
        outcome = evaluate_rule_076(death_state="present", death_rows=(("d" * 64, fields),))
        assert outcome.status == "non_compliant"
        assert outcome.reason_code == "defect_proven"
        assert outcome.criterion_results[0].actual_value is False


@pytest.mark.parametrize("fields,registration,expected", [
    ({"death_time": "2026-07-01T00:05:00Z"}, [{"patient_status": "死亡"}], "compliant"),
    ({"death_time": "2026-07-01T08:05:00.123456+08:00"}, [{"patient_status": "死亡"}], "compliant"),
    ({"death_time": "2026-07-01", "record_content": "死亡时间：2026-07-01T08:05:00。"}, [{"patient_status": "死亡"}], "compliant"),
    ({"death_time": "2026-07-01", "record_content": "死亡时间：2026-07-01T00:05:00.123456Z。"}, [{"patient_status": "死亡"}], "compliant"),
    ({"death_time": "2026-07-01T00:05:00Z"}, [{"death_datetime": "2026-07-01 08:05:00+08:00"}], "compliant"),
    ({"death_time": "2026-07-01T00:05:00Z"}, [{"death_datetime": "2026-07-01 08:06:00+08:00"}], "data_gap"),
    ({"death_time": "2026-07-01", "record_content": "死亡时间仅填写日期。"}, [{"patient_status": "死亡"}], "non_compliant"),
    ({"death_time": "2026-07-01", "record_content": ""}, [{"patient_status": "死亡"}], "data_gap"),
    ({"record_content": "死亡时间：2026-07-01T08:05:99Z。"}, [{"patient_status": "死亡"}], "non_compliant"),
    ({"record_content": "死亡时间：2026-07-01T08:05:00+25:00。"}, [{"patient_status": "死亡"}], "non_compliant"),
])
def test_iso_death_formats_survive_formal_finalizer_and_new_sqlite_engine(
    tmp_path, fields, registration, expected,
):
    from tests.unit.test_luxian_0609_rule_076_time_precision import (
        _canonical_death_result, _sqlite_new_session_roundtrip,
    )

    canonical = asyncio.run(_canonical_death_result(
        {"document_id": "iso-death-076", "record_time": "2026-07-01 10:00:00",
         "record_content": "经抢救无效死亡。", **fields}, registration,
    ))
    assert canonical["status"] == expected
    if expected == "compliant":
        assert canonical["criterion_results"][0]["actual_value"] is True
    loaded = _sqlite_new_session_roundtrip(canonical, tmp_path / "076-iso.sqlite")
    assert loaded["status"] == expected
