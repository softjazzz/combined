from __future__ import annotations

import asyncio

import pytest

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.transfusion_course_presence import (
    TransfusionCoursePresenceResult,
)
from app.services.luxian_0609.transfusion_order_trigger import (
    TransfusionOrderTriggerResult,
)


class _ThreeWayBarrier:
    def __init__(self) -> None:
        self.arrivals = 0
        self._released = asyncio.Event()

    async def arrive(self) -> None:
        self.arrivals += 1
        if self.arrivals == 3:
            self._released.set()
        await asyncio.wait_for(self._released.wait(), timeout=0.5)


@pytest.mark.asyncio
async def test_independent_transfusion_gates_run_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """病程、医嘱和术中文书三个独立门控不能串成单病历关键路径。"""

    barrier = _ThreeWayBarrier()

    async def classify_course_records(*_args, **_kwargs):
        await barrier.arrive()
        return TransfusionCoursePresenceResult(
            state="absent",
            llm_call_count=1,
            prompt_tokens=10,
            completion_tokens=2,
            total_tokens=12,
            api_time=1.0,
        )

    async def classify_orders(*_args, **_kwargs):
        await barrier.arrive()
        return TransfusionOrderTriggerResult(
            state="absent",
            llm_call_count=1,
            prompt_tokens=10,
            completion_tokens=2,
            total_tokens=12,
            api_time=1.0,
        )

    async def assess_intraoperative(*_args, **_kwargs):
        await barrier.arrive()
        return transfusion._Intraoperative048Assessment(
            status="not_applicable",
            reason_code="intraoperative_transfusion_fact_absent",
            llm_call_count=1,
            prompt_tokens=10,
            completion_tokens=2,
            total_tokens=12,
            api_time=1.0,
        )

    monkeypatch.setattr(
        transfusion,
        "classify_transfusion_course_records",
        classify_course_records,
    )
    monkeypatch.setattr(
        transfusion,
        "classify_transfusion_orders",
        classify_orders,
    )
    monkeypatch.setattr(
        transfusion,
        "_intraoperative_048_assessment",
        assess_intraoperative,
    )

    documents = {
        "mr_bloodtrans": [],
        "bloodtrans_record": [
            {"document_id": "course-1", "content": "脱敏输血过程记录"}
        ],
        "inpat_nondrug_order": [
            {"order_id": "order-1", "order_name": "输注红细胞"}
        ],
        "inpat_drug_order": [],
        "surgery_record": [
            {"document_id": "surgery-1", "content": "脱敏手术记录"}
        ],
        "anesthesia_record": [],
        "postsurg_firstcourse_record": [],
        "__logical_source_states__": {
            "bloodtrans_record": "available",
            "surgery_record": "available",
            "anesthesia_record": "empty",
        },
    }

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=(
            "LX0609-07-01-01",
            "LX0609-07-01-02",
            "LX0609-07-04-01",
        ),
        wrapper_rules=(),
        evidence_payload={"programmatic_timeline": {"documents": documents}},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=object(),
    )

    assert barrier.arrivals == 3
    assert result.llm_call_count == 3
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 6
    assert result.total_tokens == 36
    assert result.api_time == 3.0
    assert [item["status"] for item in result.results] == [
        "data_gap",
        "not_applicable",
        "not_applicable",
    ]
