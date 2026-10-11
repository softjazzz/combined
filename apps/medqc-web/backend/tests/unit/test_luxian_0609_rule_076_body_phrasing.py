"""076 死亡时间：正文“于〈日期时刻〉……死亡”的常见写法应视为已填写。"""

from datetime import datetime

import pytest

from app.services.luxian_0609.extended_document.rule_076 import (
    death_time_from_body,
    evaluate_rule_076,
)
from app.services.luxian_0609.native_extended_document_execution import _death_context


@pytest.mark.parametrize(
    "body",
    (
        "患者于2026-06-09 10:00因感染性休克死亡。",
        "于2026-06-09 10:00心跳呼吸停止，经抢救无效宣告临床死亡。",
        "死亡时刻：2026-06-09 10:00",
        "死亡日期：2026年06月09日 10时00分",
    ),
)
def test_body_phrasings_carry_concrete_death_time(body) -> None:
    assert death_time_from_body({"record_content": body}) == datetime(2026, 6, 9, 10, 0)
    outcome = evaluate_rule_076(
        death_state="present", death_rows=(("d" * 64, {"record_content": body}),),
    )
    assert outcome.status == "compliant"


@pytest.mark.parametrize(
    "body",
    (
        "患者于2026-06-01 08:00入院，住院期间病情恶化死亡。",
        "患者于2026-06-09因感染性休克死亡。",
        "患者于2026-06-09 10:00出现呼吸困难。经抢救无效死亡。",
    ),
)
def test_admission_time_date_only_or_cross_sentence_is_not_death_time(body) -> None:
    assert death_time_from_body({"record_content": body}) is None


def test_death_context_falls_back_to_death_record_body() -> None:
    state, death_time = _death_context(
        registration_rows=(),
        death_rows=({"record_content": "患者于2026-06-09 10:00因感染性休克死亡。"},),
        discharge_rows=(),
    )

    assert (state, death_time) == ("present", datetime(2026, 6, 9, 10, 0))


def test_conflicting_body_death_times_are_conflict() -> None:
    state, _death_time = _death_context(
        registration_rows=(),
        death_rows=(
            {"record_content": "于2026-06-09 10:00死亡。"},
            {"record_content": "于2026-06-09 11:00死亡。"},
        ),
        discharge_rows=(),
    )

    assert state == "conflict"
