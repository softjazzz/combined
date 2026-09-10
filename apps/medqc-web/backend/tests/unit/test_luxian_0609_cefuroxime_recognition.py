from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.luxian_0609 import native_extended_document_execution as module
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from test_luxian_0609_native_extended_document_execution import _evaluate


def test_cefuroxime_exact_name_is_recognized_from_generic_name() -> None:
    assert module._antimicrobial_names_in(
        {"generic_name": "(4+7)注射用头孢呋辛钠(0.75g)"}
    ) == ("头孢呋辛",)


@pytest.mark.asyncio
async def test_055_cefuroxime_with_typed_start_triggers_mature_window() -> None:
    local_timezone = ZoneInfo("Asia/Shanghai")
    result, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": ({
                "generic_name": "(4+7)注射用头孢呋辛钠(0.75g)",
                "brand_name": "(4+7)注射用头孢呋辛钠(0.75g)",
                "drug_type": "第二代头孢菌素",
                "planned_start_datetime": datetime(
                    2025, 8, 13, 15, 32, 46, tzinfo=local_timezone
                ),
            },),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": datetime(
                    2025, 8, 17, 9, 24, 27, tzinfo=local_timezone
                ),
                "horizon_date": "2025-08-17",
                "basis": "authoritative_discharge",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"
    facts = dict(result.customer_display_facts)["LX0609-055"]
    assert facts["antimicrobials"] == ["头孢呋辛"]
    assert facts["unmatched_antimicrobials"] == ["头孢呋辛"]
    assert facts["event_windows"][0]["start_time"] == "2025-08-13 15:32:46"


@pytest.mark.asyncio
async def test_054_cefuroxime_action_binds_order_and_course_evidence() -> None:
    result, reduced = await _evaluate(
        "LX0609-054",
        {
            "inpat_drug_order": ({
                "order_id": "cefuroxime-order",
                "generic_name": "注射用头孢呋辛钠",
            },),
            "daily_course_record": (),
            "senior_course_record": ({
                "linked_order_id": "cefuroxime-order",
                "record_time": "2025-08-14 09:00:00",
                "record_content": "停用头孢呋辛。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"
    facts = dict(result.customer_display_facts)["LX0609-054"]
    assert facts["antimicrobials"] == ["头孢呋辛"]
    assert facts["unmatched_antimicrobials"] == ["头孢呋辛"]
    assert facts["action_count"] == 1
    assert len(result.decisions[0].fact_refs) == 2
