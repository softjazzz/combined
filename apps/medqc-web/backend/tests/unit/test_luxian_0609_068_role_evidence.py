"""068 语义意见的角色证据必须由来源或绑定引文确定。"""

from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    SCHEMA_VERSION,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import _evaluate


class _Client:
    def __init__(self, *items: dict[str, object]):
        self.items = items
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {
            "choices": [{
                "message": {"content": json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "items": self.items,
                })},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "total_tokens": 100,
            },
            "_api_time": 0.1,
        }


def _item(
    local_doc_id: str,
    *,
    opinion: str,
    quote: str,
) -> dict[str, object]:
    return {
        "local_doc_id": local_doc_id,
        "opinion": opinion,
        "quote": quote,
    }


def _base_rows() -> dict[str, tuple[dict[str, object], ...]]:
    return {
        "inpat_registration": ({
            "patient_status": "出院",
            "discharge_datetime": "2026-07-03 12:00:00",
        },),
        "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
    }


@pytest.mark.asyncio
async def test_daily_approval_without_role_evidence_does_not_block_senior_condition_gap() -> None:
    daily_text = "病情好转，予以办理出院。"
    senior_text = "主任医师指示：今日继续治疗，明日如无特殊情况可办理出院。"
    client = _Client(
        _item(
            "doc_01",
            opinion="approved",
            quote=daily_text,
        ),
        _item(
            "doc_02",
            opinion="conditional",
            quote=senior_text,
        ),
    )
    result, reduced = await _evaluate(
        "LX0609-068",
        {
            **_base_rows(),
            "daily_course_record": ({
                "document_id": "daily-without-role",
                "record_time": "2026-07-03 08:00:00",
                "record_content": daily_text,
            },),
            "senior_course_record": ({
                "document_id": "senior-conditional",
                "record_time": "2026-07-03 09:00:00",
                "record_content": senior_text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"
    assert dict(result.customer_display_facts)["LX0609-068"]["approval_present"] is False
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_daily_approval_with_senior_role_inside_opinion_quote_is_compliant() -> None:
    text = "主任医师指示：患者病情稳定，批准办理出院。"
    client = _Client(_item(
        "doc_01",
        opinion="approved",
        quote=text,
    ))
    result, reduced = await _evaluate(
        "LX0609-068",
        {
            **_base_rows(),
            "daily_course_record": ({
                "document_id": "daily-senior-approval",
                "record_time": "2026-07-03 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-068"]
    assert facts["approval_path"] == "senior_approval"
    assert facts["checked_source"] == "daily_course_record"
    assert result.llm_call_count == 1
    assert len(client.calls) == 1
