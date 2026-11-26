"""Stage 3 P1-1 / P1-4 回归单测：检验整表未同步降级守卫与 06-01-02 报告驱动入院 24h 豁免。"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing import Any, Mapping, Sequence

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.exam_lab_fact_extraction import (
    MULTI_EVENT_SCHEMA_VERSION,
    build_exam_lab_text_projection,
    events_for_family,
)
from app.services.luxian_0609.native_exam_lab_execution import (
    execute_luxian_0609_native_exam_lab_rules,
)
from app.services.luxian_0609.routine_lab_presence import (
    BLOOD_ITEMS,
    ITEM_SOURCE,
    evaluate_routine_lab_presence,
)


BLOOD = "LX0609-06-03-05"
URINE = "LX0609-06-03-06"
START = datetime(2026, 7, 31, 9, 18, 39)


class _SequentialExamLabClient:
    def __init__(self, payloads: Sequence[Mapping[str, Any]]) -> None:
        self._payloads = list(payloads)
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        payload = self._payloads.pop(0)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                }
            ],
            "usage": {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
        }


def _routine_base_sources(*, stay_hours: float = 72.0) -> dict[str, Any]:
    return {
        "inpat_registration": (("reg-1", {"admission_datetime": None}),),
        "admission_record": (("adm-1", {"admission_datetime": START}),),
        "evaluation_context.horizon": (
            (
                "hor-1",
                {
                    "basis": "discharge_date",
                    "horizon_datetime": START + timedelta(hours=stay_hours),
                },
            ),
        ),
        "labtest_master": (),
        "labtest_item_report": (),
        ITEM_SOURCE: (),
    }


async def _run_exam_lab_pipeline(
    *,
    selected_rule_ids: Sequence[str],
    eval_rule_ids: Sequence[str],
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    llm_client: Any = None,
    truncated_sources: Sequence[str] = (),
    admission_datetime: str = "2026-07-31 09:18:39",
    discharge_datetime: str = "2026-09-02 09:18:39",
) -> tuple[Any, dict[str, dict[str, Any]]]:
    truncated_set = set(truncated_sources)

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows_by_source.get(key, ()),
            truncated=key in truncated_set,
            limit_rows=5000,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=tuple(selected_rule_ids),
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        created_at="2026-09-10T10:00:00+08:00",
        row_reader=reader,
        evaluation_horizon_snapshot={
            "institute_id": "INST",
            "patient_id": "PAT",
            "visit_id": "VIS",
            "record_scene": "final",
            "evaluation_basis": "discharge_datetime",
            "resolution_status": "resolved",
            "evaluation_horizon": discharge_datetime[:10],
            "admission_datetime": admission_datetime,
            "discharge_datetime": discharge_datetime,
            "discharge_time_precision": "datetime",
        },
    )
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=tuple(eval_rule_ids),
        decision_rule_ids=tuple(eval_rule_ids),
        wrapper_rules=[{"rule_id": rid, "custom_prompt": "stub"} for rid in eval_rule_ids],
        evidence_payload={},
        llm_client=llm_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=tuple(eval_rule_ids),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    facts_by_rule = dict(execution.customer_display_facts)
    finals = {
        item.rule_id: finalize_luxian_0609_reduced_customer_result(
            decision=item,
            raw_customer_display_facts=facts_by_rule.get(item.rule_id),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        for item in reduced
    }
    return execution, finals


# ---------------------------------------------------------------------------
# P1-1: LX0609-06-03-05 & LX0609-06-03-06 unsynced lab source guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule_id", [BLOOD, URINE])
@pytest.mark.parametrize(
    "order_source,order_row",
    [
        ("inpat_nondrug_order", {"order_name": "血常规", "order_type": "检验", "order_status": "执行"}),
        ("inpat_nondrug_order", {"order_name": "尿液分析", "order_type": "检验", "order_status": "新开"}),
        ("inpat_nondrug_order", {"order_name": "尿常规", "order_class": "检验", "order_status": "核实"}),
        ("inpat_nondrug_order", {"order_name": "血常规", "order_status": "执行"}),
        ("inpat_nondrug_order", {"order_name": "全血需氧培养", "order_type": "检验", "order_status": "执行"}),
        (
            "inpat_nondrug_order.exam_lab_order",
            {"order_name": "痰一般细菌培养", "order_status": "执行"},
        ),
    ],
)
def test_06_03_05_and_06_03_06_empty_lab_master_with_lab_orders_downgrades_to_data_gap(
    rule_id: str,
    order_source: str,
    order_row: Mapping[str, Any],
) -> None:
    sources = _routine_base_sources()
    sources[order_source] = (("ord-1", order_row),)

    outcome = evaluate_routine_lab_presence(rule_id=rule_id, sources=sources)
    assert outcome.status == "data_gap"
    assert outcome.reason == "source_empty"
    assert outcome.facts is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected_rules,order_rows",
    [
        (
            # Full multi-family session carrying inpat_nondrug_order (like 51-rule run)
            (BLOOD, URINE, "LX0609-10-02-02"),
            {
                "inpat_nondrug_order": [
                    {"order_id": "O1", "order_name": "血常规", "order_type": "检验", "order_status": "执行"},
                    {"order_id": "O2", "order_name": "尿液分析", "order_type": "检验", "order_status": "执行"},
                ],
            },
        ),
        (
            # Exam-lab-only session carrying inpat_nondrug_order.exam_lab_order
            (BLOOD, URINE, "LX0609-06-03-03"),
            {
                "inpat_nondrug_order.exam_lab_order": [
                    {"order_id": "O3", "order_name": "痰一般细菌培养", "order_status": "执行"},
                ],
            },
        ),
    ],
)
async def test_06_03_05_and_06_03_06_native_unsynced_lab_passes_binding_and_finalizer(
    selected_rules: Sequence[str],
    order_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-07-31 09:18:39"}],
        "labtest_master": [],
        "labtest_item_report": [],
        ITEM_SOURCE: [],
        **order_rows,
    }
    execution, finals = await _run_exam_lab_pipeline(
        selected_rule_ids=selected_rules,
        eval_rule_ids=(BLOOD, URINE),
        rows_by_source=rows_by_source,
    )
    assert execution.llm_call_count == 0
    for rid in (BLOOD, URINE):
        assert finals[rid]["status"] == "data_gap"
        assert finals[rid]["reason_code"] == "source_empty"
        assert finals[rid]["findings"]


def test_06_03_06_nonempty_labtest_master_missing_urine_remains_non_compliant() -> None:
    """CRITICAL INVARIANT (#02/#04/#15/#23): labtest_master 有行但真缺尿常规必须维持 non_compliant。"""

    when = START + timedelta(hours=12)
    sources = _routine_base_sources()
    sources["labtest_master"] = (
        ("m-1", {"test_id": "T-CBC", "report_datetime": when, "labtest_subject": "临检"}),
    )
    sources[ITEM_SOURCE] = tuple(
        (
            f"i-{code}",
            {
                "test_id": "T-CBC",
                "document_id": f"D-{code}",
                "item_code": code,
                "item_name": name,
                "result": "5.0",
                "report_time": when,
            },
        )
        for code, name in BLOOD_ITEMS.items()
    )
    sources["inpat_nondrug_order"] = (
        ("ord-1", {"order_name": "血常规", "order_type": "检验", "order_status": "执行"}),
        ("ord-2", {"order_name": "全血需氧培养", "order_type": "检验", "order_status": "执行"}),
    )

    blood_outcome = evaluate_routine_lab_presence(rule_id=BLOOD, sources=sources)
    urine_outcome = evaluate_routine_lab_presence(rule_id=URINE, sources=sources)
    assert blood_outcome.status == "compliant"
    assert urine_outcome.status == "non_compliant"
    assert urine_outcome.reason == "required_document_missing"


@pytest.mark.parametrize("rule_id", [BLOOD, URINE])
@pytest.mark.parametrize(
    "order_rows",
    [
        (),
        (("o1", {"order_name": "头颅CT平扫", "order_type": "检查", "order_status": "执行"}),),
        (("o2", {"order_name": "导尿", "order_type": "治疗", "order_status": "执行"}),),
        (("o3", {"order_name": "一次性使用导尿包", "order_type": "其他", "order_status": "执行"}),),
        (("o4", {"order_name": "血常规", "order_type": "检验", "order_status": "已撤销"}),),
        (("o5", {"order_name": "尿液分析", "order_type": "检验", "order_status": "取消"}),),
    ],
)
def test_06_03_05_and_06_03_06_empty_lab_master_without_active_lab_orders_stays_non_compliant(
    rule_id: str,
    order_rows: Sequence[tuple[str, Mapping[str, Any]]],
) -> None:
    sources = _routine_base_sources()
    sources["inpat_nondrug_order"] = tuple(order_rows)

    outcome = evaluate_routine_lab_presence(rule_id=rule_id, sources=sources)
    assert outcome.status == "non_compliant"
    assert outcome.reason == "required_document_missing"


def test_06_03_05_stay_within_48h_stays_not_applicable_even_with_unsynced_lab_orders() -> None:
    sources = _routine_base_sources(stay_hours=36.0)
    sources["inpat_nondrug_order"] = (
        ("ord-1", {"order_name": "血常规", "order_type": "检验", "order_status": "执行"}),
    )
    outcome = evaluate_routine_lab_presence(rule_id=BLOOD, sources=sources)
    assert outcome.status == "not_applicable"
    assert outcome.reason == "trigger_absent_complete"


def test_06_03_05_outpatient_transcription_stays_compliant_even_with_unsynced_lab_orders() -> None:
    sources = _routine_base_sources()
    sources["admission_record"] = (
        (
            "adm-1",
            {
                "document_id": "ADM-1",
                "admission_datetime": START,
                "record_time": START + timedelta(hours=1),
                "record_content": "2026-07-30门诊血常规：WBC 6.1，Hb 128。",
            },
        ),
    )
    sources["inpat_nondrug_order"] = (
        ("ord-1", {"order_name": "血常规", "order_type": "检验", "order_status": "执行"}),
    )
    outcome = evaluate_routine_lab_presence(rule_id=BLOOD, sources=sources)
    assert outcome.status == "compliant"
    assert outcome.facts["evidence_kind"] == "outpatient_transcription"


@pytest.mark.asyncio
async def test_06_03_05_truncated_optional_nondrug_order_does_not_fail_compliant_case() -> None:
    when = START + timedelta(hours=10)
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-07-31 09:18:39"}],
        "labtest_master": [
            {"test_id": "T1", "report_datetime": when, "labtest_subject": "临检"}
        ],
        "labtest_item_report": [],
        ITEM_SOURCE: [
            {
                "test_id": "T1",
                "document_id": f"D-{code}",
                "item_code": code,
                "item_name": name,
                "result": "5.0",
                "report_time": when,
            }
            for code, name in BLOOD_ITEMS.items()
        ],
        "inpat_nondrug_order": [
            {"order_id": "O1", "order_name": "常规护理", "order_type": "护理", "order_status": "执行"},
        ],
    }
    _, finals = await _run_exam_lab_pipeline(
        selected_rule_ids=(BLOOD, "LX0609-10-02-02"),
        eval_rule_ids=(BLOOD,),
        rows_by_source=rows_by_source,
        truncated_sources=("inpat_nondrug_order",),
    )
    assert finals[BLOOD]["status"] == "compliant"


# ---------------------------------------------------------------------------
# P1-4: LX0609-06-01-02 report/exam-driven admission 24h exemption
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_06_01_02_report_time_within_24h_without_order_time_is_exempt_without_llm() -> None:
    """复现 #01：入院 07-31 09:18（reg NULL 回退 admission_record），急诊 CT 仅报告时间 10:03（+45min）。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-07-31 09:18:39"}],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-07-31 10:03:21",
                "description": "双肺渗出。",
            }
        ],
        "daily_course_record": [],
    }
    projection = build_exam_lab_text_projection(rows_by_source=rows_by_source)
    event = events_for_family(projection, "exam")[0]
    assert event.order_time is None
    assert event.exam_time is None
    assert event.within_admission_window is True

    client = _SequentialExamLabClient([])
    execution, finals = await _run_exam_lab_pipeline(
        selected_rule_ids=("LX0609-06-01-02",),
        eval_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
        llm_client=client,
    )
    assert execution.llm_call_count == 0
    assert client.prompts == []
    final = finals["LX0609-06-01-02"]
    assert final["status"] == "not_applicable"
    assert final["reason_code"] == "eligibility_not_met"
    assert "入院 24 小时内" in final["findings"]


def test_06_01_02_exam_time_within_24h_without_order_time_is_exempt() -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-07-31 09:18:39"}],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "头颅螺旋CT平扫",
                "exam_time": "2026-07-31 11:00:00",
                "report_time": "2026-08-01 11:00:00",
                "description": "颅脑未见急性出血。",
            }
        ],
    }
    event = events_for_family(
        build_exam_lab_text_projection(rows_by_source=rows_by_source),
        "exam",
    )[0]
    assert event.order_time is None
    assert event.within_admission_window is True


@pytest.mark.asyncio
async def test_06_01_02_case01_multi_event_emergency_ct_exempt_and_later_ct_compliant() -> None:
    """复现 #01 整例：第 1 次入院 45m 急诊 CT（无 order_time）豁免，后续 CT 已记录原因，整例翻为 compliant。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-07-31 09:18:39"}],
        "inpat_nondrug_order.exam_lab_order": [
            {
                "order_id": "ORD-2",
                "order_name": "胸部螺旋CT平扫",
                "prescribed_datetime": "2026-08-03 09:11:20",
            },
        ],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "急诊头胸CT平扫",
                "report_time": "2026-07-31 10:03:21",
                "description": "双肺渗出。",
            },
            {
                "document_id": "EX-2",
                "exam_id": "E2",
                "order_id": "ORD-2",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-03 11:07:14",
                "description": "双肺渗出较前吸收。",
            },
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-02 10:00:00",
                "record_content": "拟复查胸部CT了解双肺渗出吸收情况。",
            },
        ],
    }
    client = _SequentialExamLabClient(
        [
            {
                "schema_version": MULTI_EVENT_SCHEMA_VERSION,
                "facts": [
                    {
                        "rule_id": "LX0609-06-01-02",
                        "event_position": 1,
                        "applicability": "applicable",
                        "semantic_state": "absent",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [],
                    },
                    {
                        "rule_id": "LX0609-06-01-02",
                        "event_position": 2,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1],
                    },
                ],
            },
            {
                "schema_version": "lx0609-exam-reason-check-v1",
                "docs": [
                    {
                        "event_position": 2,
                        "course_doc_ref": "D06-01",
                        "quote_type": "reason_stated",
                        "quote": "拟复查胸部CT了解双肺渗出吸收情况",
                    },
                ],
            },
        ]
    )
    _, finals = await _run_exam_lab_pipeline(
        selected_rule_ids=("LX0609-06-01-02",),
        eval_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
        llm_client=client,
    )
    final = finals["LX0609-06-01-02"]
    assert final["status"] == "compliant"
    ev1, ev2 = final["customer_display_facts"]["event_results"]
    assert ev1["event_status"] == "not_applicable"
    assert ev1["exempt_reason"] == "admission_window"
    assert ev2["event_status"] == "compliant"
    assert "入院24小时内开立，本项豁免" in final["findings"]


@pytest.mark.asyncio
async def test_06_01_02_within_24h_event_exempt_even_if_main_llm_emits_unknown() -> None:
    """复现 #25 Event 1：入院 24h 内事件即便主抽取返回 applicability=unknown，仍须豁免而非 data_gap。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-08-19 08:55:40"}],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT增强扫描",
                "report_time": "2026-08-19 11:54:36",
                "description": "右肺占位。",
            },
            {
                "document_id": "EX-2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "颅脑螺旋CT平扫",
                "report_time": "2026-08-28 10:36:01",
                "description": "未见明显异常。",
            },
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-27 09:00:00",
                "record_content": "患者今日一般情况可，继续原治疗。",
            },
        ],
    }
    client = _SequentialExamLabClient(
        [
            {
                "schema_version": MULTI_EVENT_SCHEMA_VERSION,
                "facts": [
                    {
                        "rule_id": "LX0609-06-01-02",
                        "event_position": 1,
                        "applicability": "unknown",
                        "semantic_state": "unknown",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [],
                    },
                    {
                        "rule_id": "LX0609-06-01-02",
                        "event_position": 2,
                        "applicability": "applicable",
                        "semantic_state": "absent",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [],
                    },
                ],
            },
            {
                "schema_version": "lx0609-exam-reason-check-v1",
                "docs": [
                    {
                        "event_position": 2,
                        "course_doc_ref": "D06-01",
                        "quote_type": "none",
                        "quote": "",
                    },
                ],
            },
        ]
    )
    _, finals = await _run_exam_lab_pipeline(
        selected_rule_ids=("LX0609-06-01-02",),
        eval_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
        llm_client=client,
        admission_datetime="2026-08-19 08:55:40",
        discharge_datetime="2026-09-14 10:00:00",
    )
    final = finals["LX0609-06-01-02"]
    assert final["status"] == "non_compliant"
    ev1, ev2 = final["customer_display_facts"]["event_results"]
    assert ev1["event_status"] == "not_applicable"
    assert ev1["exempt_reason"] == "admission_window"
    assert ev2["event_status"] == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "report_time",
    [
        "2026-08-01 09:50:00",  # +24.52h (just over 24h, like #27)
        "2026-08-03 10:24:09",  # +73.09h (post-24h, like #09)
    ],
)
async def test_06_01_02_post_24h_report_only_ct_without_reason_stays_non_compliant(
    report_time: str,
) -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-07-31 09:18:39"}],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": report_time,
                "description": "双肺感染。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-01 08:00:00",
                "record_content": "患者今日体温平稳，继续目前治疗。",
            }
        ],
    }
    projection = build_exam_lab_text_projection(rows_by_source=rows_by_source)
    assert events_for_family(projection, "exam")[0].within_admission_window is False

    client = _SequentialExamLabClient(
        [
            {
                "schema_version": "lx0609-exam-lab-text-facts-v3",
                "facts": [
                    {
                        "rule_id": "LX0609-06-01-02",
                        "applicability": "applicable",
                        "semantic_state": "absent",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [],
                    }
                ],
            },
            {
                "schema_version": "lx0609-exam-reason-check-v1",
                "docs": [
                    {
                        "event_position": 1,
                        "course_doc_ref": "D06-01",
                        "quote_type": "none",
                        "quote": "",
                    }
                ],
            },
        ]
    )
    _, finals = await _run_exam_lab_pipeline(
        selected_rule_ids=("LX0609-06-01-02",),
        eval_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
        llm_client=client,
    )
    assert finals["LX0609-06-01-02"]["status"] == "non_compliant"


def test_06_01_02_pre_admission_report_time_is_not_exempted() -> None:
    """回退到 report_time/exam_time 时须满足 0 <= (anchor - admission_datetime) <= 24h。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": None}],
        "admission_record": [{"admission_datetime": "2026-07-31 09:18:39"}],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部CT平扫",
                "report_time": "2026-07-31 08:00:00",
                "description": "院前检查。",
            }
        ],
    }
    event = events_for_family(
        build_exam_lab_text_projection(rows_by_source=rows_by_source),
        "exam",
    )[0]
    assert event.within_admission_window is False


@pytest.mark.asyncio
async def test_06_01_02_missing_inpat_registration_falls_back_to_admission_record() -> None:
    """复现 #23：inpat_registration 为 0 行时，仍从 admission_record.admission_datetime 触发 24h 豁免。"""

    rows_by_source = {
        "inpat_registration": [],
        "admission_record": [{"admission_datetime": "2026-09-10 11:58:26"}],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "下腹部CT平扫",
                "report_time": "2026-09-10 14:18:57",
                "description": "阑尾增粗。",
            }
        ],
        "daily_course_record": [],
    }
    client = _SequentialExamLabClient([])
    execution, finals = await _run_exam_lab_pipeline(
        selected_rule_ids=("LX0609-06-01-02",),
        eval_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
        llm_client=client,
        admission_datetime="2026-09-10 11:58:26",
        discharge_datetime="2026-09-17 09:30:00",
    )
    assert execution.llm_call_count == 0
    assert finals["LX0609-06-01-02"]["status"] == "not_applicable"
    assert finals["LX0609-06-01-02"]["reason_code"] == "eligibility_not_met"
