"""P1-7 / P1-8 / P1-9 回归单测：病理报告时间与空手术记录守卫、06-01-02 具体证据渲染、双瓶血培养提示词。"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.customer_renderer import (
    customer_finding_from_controlled_facts,
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
    build_exam_lab_fact_prompt,
    build_exam_lab_text_projection,
)
from app.services.luxian_0609.exam_lab_result_mapping import (
    safe_exam_lab_customer_display_facts,
)
from app.services.luxian_0609.native_exam_lab_execution import (
    execute_luxian_0609_native_exam_lab_rules,
)
from app.services.luxian_0609.native_tumor_pathology_execution import (
    SourceMaterial,
    _has_documented_pathology_sampling,
    _pathology_display_report_time,
    execute_luxian_0609_native_tumor_pathology_rules,
)
from luxian_0609_pathology_test_facts import (
    PathologyFactsClient,
    default_pathology_facts,
)


async def _run_pathology_rule(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    rule_id: str,
    client: Any = None,
) -> dict[str, Any]:
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows.get(key, ()),
            truncated=False,
            limit_rows=500,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        created_at="2026-09-20T10:00:00+08:00",
        row_reader=reader,
        evaluation_horizon_snapshot={
            "institute_id": "INST",
            "patient_id": "PAT",
            "visit_id": "VIS",
            "record_scene": "final",
            "evaluation_basis": "discharge_datetime",
            "resolution_status": "resolved",
            "evaluation_horizon": "2026-09-14",
            "admission_datetime": "2026-08-19 08:00:00",
            "discharge_datetime": "2026-09-14 10:00:00",
            "discharge_time_precision": "datetime",
        },
    )
    llm_client = client if client is not None else PathologyFactsClient()
    result = await execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule_id,),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        llm_client=llm_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=(rule_id,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(result.customer_display_facts).get(rule_id),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )


def _scripted_pathology_client(*states: str) -> PathologyFactsClient:
    def script(sampling: bool, events: list[dict[str, Any]], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        defaults = default_pathology_facts(sampling, events, documents)
        answers: list[dict[str, Any]] = []
        for event, state, default in zip(events, states, defaults):
            if state == "documented":
                if default["state"] == "documented":
                    answers.append(default)
                else:
                    doc = documents[0]
                    answers.append(
                        {
                            "event": event["event"],
                            "state": "documented",
                            "document": doc["document"],
                            "quote": doc["body"][:20],
                        }
                    )
            else:
                answers.append(
                    {
                        "event": event["event"],
                        "state": state,
                        "document": None,
                        "quote": None,
                    }
                )
        return answers

    return PathologyFactsClient(script)


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
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }


async def _run_exam_lab_rules(
    *,
    rule_ids: Sequence[str],
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    llm_client: Any,
    admission_datetime: str = "2026-08-19 08:00:00",
    discharge_datetime: str = "2026-09-14 10:00:00",
) -> dict[str, dict[str, Any]]:
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows_by_source.get(key, ()),
            truncated=False,
            limit_rows=500,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=tuple(rule_ids),
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        created_at="2026-09-20T10:00:00+08:00",
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
    result = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=tuple(rule_ids),
        wrapper_rules=[{"rule_id": rid, "custom_prompt": "stub"} for rid in rule_ids],
        evidence_payload={},
        llm_client=llm_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=tuple(rule_ids),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=tuple(rule_ids),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    facts_by_rule = dict(result.customer_display_facts)
    return {
        item.rule_id: finalize_luxian_0609_reduced_customer_result(
            decision=item,
            raw_customer_display_facts=facts_by_rule.get(item.rule_id),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        for item in reduced
    }


# ---------------------------------------------------------------------------
# P1-7: LX0609-06-02-03 literal "None" & LX0609-06-02-02 empty surgery_record
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("report_time", [None, "", "None", "   "])
def test_06_02_03_renderer_never_prints_literal_none_when_report_time_missing(
    report_time: Any,
) -> None:
    facts: dict[str, Any] = {
        "verification_kind": "pathology_result_documentation_check",
        "requirement_met": False,
        "checked_target_sources": [
            {"source": "surgery_record", "state": "empty"},
            {"source": "daily_course_record", "state": "present"},
            {"source": "senior_course_record", "state": "present"},
        ],
    }
    if report_time is not None:
        facts["report_time"] = report_time
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-06-02-03",
        facts=facts,
    )
    assert "None" not in finding
    assert finding == "已核对手术记录、日常病程记录和上级医师查房记录，未找到病理结果记录。"


def test_06_02_03_display_report_time_normalizes_iso_and_falls_back() -> None:
    assert (
        _pathology_display_report_time({"report_datetime": "2026-09-02T11:39:42+08:00"})
        == "2026-09-02 11:39:42"
    )
    assert (
        _pathology_display_report_time({"exam_datetime": "2026-09-02 09:15:00"})
        == "2026-09-02 09:15:00"
    )
    assert (
        _pathology_display_report_time({"apply_datetime": "2026-09-01 16:00:00"})
        == "2026-09-01 16:00:00"
    )
    assert (
        _pathology_display_report_time(
            {"pathology_exam_id": "P1"},
            master_rows=({"pathology_exam_id": "P1", "request_datetime": "2026-09-01 10:30:00"},),
        )
        == "2026-09-01 10:30:00"
    )


@pytest.mark.asyncio
async def test_06_02_03_multi_report_backfills_unmet_report_time_without_none() -> None:
    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "肺占位"},
            {"document_id": "m2", "pathology_exam_id": "P2", "specimen_name": "冲洗液"},
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "右肺上叶",
                "diagnosis": "(右肺上叶)：肺叶切除标本，浸润性非粘液腺癌。",
                "report_datetime": "2026-09-02 11:39:42",
            },
            {
                "document_id": "r2",
                "pathology_exam_id": "P2",
                "specimen_name": "胸腔积液",
                "diagnosis": "送检冲洗液液基薄层制片，未见恶性肿瘤细胞。",
                "report_datetime": "2026-08-22 16:19:29",
            },
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-08-23 09:00:00",
                "record_content": "冲洗液脱落细胞病理结果：未见恶性肿瘤细胞。",
            },
            {
                "document_id": "c2",
                "record_time": "2026-09-03 09:00:00",
                "record_content": "患者术后恢复平稳，继续观察。",
            },
        ],
        "senior_course_record": [],
    }
    final = await _run_pathology_rule(
        rows,
        "LX0609-06-02-03",
        _scripted_pathology_client("not_documented", "documented"),
    )
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["report_time"] == "2026-09-02 11:39:42"
    assert "None" not in final["findings"]
    assert "2026-09-02 11:39:42" in final["findings"]


@pytest.mark.asyncio
async def test_06_02_03_multi_unmet_reports_omit_timestamp_cleanly_without_none() -> None:
    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "肺占位"},
            {"document_id": "m2", "pathology_exam_id": "P2", "specimen_name": "冲洗液"},
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "右肺上叶",
                "diagnosis": "(右肺上叶)：肺叶切除标本，浸润性非粘液腺癌。",
                "report_datetime": "2026-09-02 11:39:42",
            },
            {
                "document_id": "r2",
                "pathology_exam_id": "P2",
                "specimen_name": "胸腔积液",
                "diagnosis": "送检冲洗液液基薄层制片，未见恶性肿瘤细胞。",
                "report_datetime": "2026-08-22 16:19:29",
            },
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-09-03 09:00:00",
                "record_content": "患者一般情况可。",
            },
        ],
        "senior_course_record": [],
    }
    final = await _run_pathology_rule(
        rows,
        "LX0609-06-02-03",
        _scripted_pathology_client("not_documented", "not_documented"),
    )
    assert final["status"] == "non_compliant"
    assert "report_time" not in final["customer_display_facts"]
    assert "None" not in final["findings"]
    assert "未找到病理结果记录" in final["findings"]


@pytest.mark.asyncio
async def test_06_02_02_surgical_resection_pathology_with_empty_surgery_record_is_data_gap() -> None:
    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "肺占位"},
            {"document_id": "m2", "pathology_exam_id": "P2", "specimen_name": "冲洗液"},
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "右肺上叶",
                "diagnosis": "(右肺上叶)：肺叶切除标本，浸润性非粘液腺癌。",
                "report_datetime": "2026-09-02 11:39:42",
            },
            {
                "document_id": "r2",
                "pathology_exam_id": "P2",
                "specimen_name": "胸腔积液",
                "diagnosis": "送检冲洗液液基薄层制片，未见恶性肿瘤细胞。",
                "report_datetime": "2026-08-22 16:19:29",
            },
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-08-21 15:09:00",
                "document_title": "（有创）操作记录",
                "record_content": "支气管镜检查留取肺泡灌洗液送检脱落细胞学检查。",
            },
            {
                "document_id": "c2",
                "record_time": "2026-09-04 16:17:00",
                "document_title": "记录",
                "record_content": "复查支气管镜留取灌洗液送脱落细胞检查。",
            },
        ],
    }
    final = await _run_pathology_rule(
        rows,
        "LX0609-06-02-02",
        _scripted_pathology_client("not_documented", "documented"),
    )
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_empty"
    assert "手术记录" in final["findings"]


@pytest.mark.asyncio
async def test_06_02_02_lavage_sampling_in_daily_course_procedure_note_is_compliant() -> None:
    course_rows = (
        {
            "document_id": "c1",
            "record_time": "2026-08-21 15:09:00",
            "document_title": "（有创）操作记录",
            "record_content": "行电子支气管镜检查，留取灌洗液送检脱落细胞。",
        },
    )
    assert _has_documented_pathology_sampling(SourceMaterial("present", course_rows)) is True

    rows = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "冲洗液"},
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "胸腔积液",
                "diagnosis": "送检冲洗液液基薄层制片，未见恶性肿瘤细胞。",
                "report_datetime": "2026-08-22 16:19:29",
            },
        ],
        "surgery_record": [],
        "daily_course_record": list(course_rows),
    }
    client = _scripted_pathology_client("documented")
    final = await _run_pathology_rule(rows, "LX0609-06-02-02", client)
    assert final["status"] == "compliant"
    assert "（有创）操作记录" in client.prompts[0]


@pytest.mark.asyncio
async def test_06_02_02_present_surgery_record_omitting_sampling_stays_non_compliant() -> None:
    rows = {
        "pathology_exam_master": [
            {
                "document_id": "m1",
                "pathology_exam_id": "P1",
                "specimen_name": "右肺上叶",
                "surgery_name": "胸腔镜右肺上叶切除术",
            },
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "右肺上叶",
                "diagnosis": "(右肺上叶)：肺叶切除标本，浸润性非粘液腺癌。",
                "report_datetime": "2026-09-02 11:39:42",
            },
        ],
        "surgery_record": [
            {
                "document_id": "s1",
                "record_time": "2026-08-30 12:00:00",
                "surgery_process": "行胸腔镜下右肺上叶切除术，止血彻底，关胸顺利。",
            },
        ],
        "daily_course_record": [],
    }
    final = await _run_pathology_rule(
        rows,
        "LX0609-06-02-02",
        _scripted_pathology_client("not_documented"),
    )
    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"


# ---------------------------------------------------------------------------
# P1-8: LX0609-06-01-02 CT/MRI pre-exam reason concrete findings rendering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_06_01_02_multi_event_non_compliant_renders_exam_names_and_times() -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-19 08:00:00"}],
        "inpat_nondrug_order.exam_lab_order": [
            {
                "order_id": "ORD-1",
                "order_name": "胸部螺旋CT增强扫描",
                "prescribed_datetime": "2026-08-19 11:13:40",
            },
            {
                "order_id": "ORD-2",
                "order_name": "胸部螺旋CT平扫",
                "prescribed_datetime": "2026-08-28 08:20:00",
            },
            {
                "order_id": "ORD-3",
                "order_name": "颅脑螺旋CT平扫",
                "prescribed_datetime": "2026-09-01 09:00:00",
            },
        ],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "order_id": "ORD-1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT增强扫描",
                "report_time": "2026-08-19 11:54:36",
                "description": "右肺上叶占位。",
            },
            {
                "document_id": "EX-2",
                "exam_id": "E2",
                "order_id": "ORD-2",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-28 10:36:01",
                "description": "术后肺复张良好。",
            },
            {
                "document_id": "EX-3",
                "exam_id": "E3",
                "order_id": "ORD-3",
                "exam_type": "CT",
                "exam_name": "颅脑螺旋CT平扫",
                "report_time": "2026-09-01 10:17:51",
                "description": "颅脑未见急性出血。",
            },
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-27 16:00:00",
                "record_content": "拟复查胸部CT了解术前肺部病灶及肺复张情况。",
            },
            {
                "document_id": "C-2",
                "record_time": "2026-08-31 10:00:00",
                "record_content": "患者今日一般情况可，继续原抗感染及对症支持治疗。",
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
                    {
                        "rule_id": "LX0609-06-01-02",
                        "event_position": 3,
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
                        "quote_type": "reason_stated",
                        "quote": "拟复查胸部CT了解术前肺部病灶及肺复张情况",
                    },
                    {
                        "event_position": 3,
                        "course_doc_ref": "D06-02",
                        "quote_type": "none",
                        "quote": "",
                    },
                ],
            },
        ]
    )
    finals = await _run_exam_lab_rules(
        rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
        llm_client=client,
    )
    final = finals["LX0609-06-01-02"]
    assert final["status"] == "non_compliant"
    assert final["findings"] != "发现质控问题"
    assert "共核对3次CT/MRI检查（其中1次未见检查前原因）" in final["findings"]
    assert "胸部螺旋CT增强扫描（开立时间 2026-08-19 11:13:40）：入院24小时内开立，本项豁免" in final["findings"]
    assert "胸部螺旋CT平扫（开立时间 2026-08-28 08:20:00）：检查前病程已记录检查原因（相关病程 2026-08-27 16:00:00）" in final["findings"]
    assert "颅脑螺旋CT平扫（开立时间 2026-09-01 09:00:00）" in final["findings"]
    assert "未找到检查原因" in final["findings"]


@pytest.mark.asyncio
async def test_06_01_02_multi_event_compliant_renders_exam_names_and_times() -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-19 08:00:00"}],
        "inpat_nondrug_order.exam_lab_order": [
            {
                "order_id": "ORD-1",
                "order_name": "胸部螺旋CT平扫",
                "prescribed_datetime": "2026-08-22 08:30:00",
            },
            {
                "order_id": "ORD-2",
                "order_name": "上腹部螺旋CT增强扫描",
                "prescribed_datetime": "2026-08-26 09:15:00",
            },
        ],
        "exam_master": [
            {
                "document_id": "EX-1",
                "exam_id": "E1",
                "order_id": "ORD-1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-22 11:00:00",
                "description": "肺部炎症吸收。",
            },
            {
                "document_id": "EX-2",
                "exam_id": "E2",
                "order_id": "ORD-2",
                "exam_type": "CT",
                "exam_name": "上腹部螺旋CT增强扫描",
                "report_time": "2026-08-26 11:30:00",
                "description": "肝胆胰脾未见异常。",
            },
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-21 15:00:00",
                "record_content": "复查胸部CT了解肺部感染吸收情况。",
            },
            {
                "document_id": "C-2",
                "record_time": "2026-08-25 14:00:00",
                "record_content": "患者腹痛，完善上腹部增强CT明确有无腹部病灶。",
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
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1],
                    },
                    {
                        "rule_id": "LX0609-06-01-02",
                        "event_position": 2,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [2],
                    },
                ],
            },
            {
                "schema_version": "lx0609-exam-reason-check-v1",
                "docs": [
                    {
                        "event_position": 1,
                        "course_doc_ref": "D06-01",
                        "quote_type": "reason_stated",
                        "quote": "复查胸部CT了解肺部感染吸收情况",
                    },
                    {
                        "event_position": 2,
                        "course_doc_ref": "D06-02",
                        "quote_type": "reason_stated",
                        "quote": "完善上腹部增强CT明确有无腹部病灶",
                    },
                ],
            },
        ]
    )
    finals = await _run_exam_lab_rules(
        rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
        llm_client=client,
    )
    final = finals["LX0609-06-01-02"]
    assert final["status"] == "compliant"
    assert "共核对2次CT/MRI检查" in final["findings"]
    assert "胸部螺旋CT平扫（开立时间 2026-08-22 08:30:00）" in final["findings"]
    assert "上腹部螺旋CT增强扫描（开立时间 2026-08-26 09:15:00）" in final["findings"]
    assert "2026-08-21 15:00:00" in final["findings"]
    assert "2026-08-25 14:00:00" in final["findings"]


def test_06_01_02_display_facts_validation_contract() -> None:
    valid = {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "reason_before_order",
        "event_phase": "order",
        "checked_sources": ["exam_lab_order", "course_record"],
        "reviewed_record_scope": "检查前48小时内病程记录",
        "exam_name": "胸部螺旋CT平扫",
        "order_time": "2026-09-01 09:00:00",
        "window_start_time": "2026-08-30 09:00:00",
        "window_end_time": "2026-09-01 10:17:51",
        "response_record_count": 1,
        "requirement_met": False,
    }
    safe = safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-02", raw=valid)
    assert safe is not None
    assert safe["exam_name"] == "胸部螺旋CT平扫"
    finding = customer_finding_from_controlled_facts(rule_id="LX0609-06-01-02", facts=safe)
    assert "胸部螺旋CT平扫（开立时间 2026-09-01 09:00:00）" in finding
    assert "1 份病程" in finding
    assert "未找到检查原因" in finding

    assert (
        safe_exam_lab_customer_display_facts(
            rule_id="LX0609-06-01-02",
            raw={**valid, "exam_name": "含换行\n非法"},
        )
        is None
    )
    assert (
        safe_exam_lab_customer_display_facts(
            rule_id="LX0609-06-01-02",
            raw={**valid, "order_time": "2026/09/01"},
        )
        is None
    )
    assert (
        safe_exam_lab_customer_display_facts(
            rule_id="LX0609-06-01-02",
            raw={**valid, "exempt_reason": "unknown_reason"},
        )
        is None
    )


# ---------------------------------------------------------------------------
# P1-9: Dual-bottle blood culture prompt guidance & end-to-end compliance
# ---------------------------------------------------------------------------


def _dual_bottle_blood_culture_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "labtest_master": [
            {
                "document_id": "LAB-AEROBIC",
                "test_id": "BC-1",
                "specimen": "全血",
                "labtest_subject": "需氧血培养及鉴定",
                "report_datetime": "2026-04-14 09:43:06",
                "result": "检出白色念珠菌（培养阳性）",
            },
            {
                "document_id": "LAB-ANAEROBIC",
                "test_id": "BC-2",
                "specimen": "全血",
                "labtest_subject": "厌氧血培养及鉴定",
                "report_datetime": "2026-04-14 09:43:50",
                "result": "检出白色念珠菌（培养阳性）",
            },
        ],
        "daily_course_record": [
            {
                "document_id": "COURSE-CRISIS",
                "record_time": "2026-04-14 09:52:00",
                "document_title": "危急值处理记录",
                "record_content": "血培养双瓶报阳：白色念珠菌，已加用氟康唑抗真菌治疗。",
            },
        ],
    }


def test_exam_lab_prompt_includes_dual_bottle_blood_culture_guidance() -> None:
    projection = build_exam_lab_text_projection(
        rows_by_source=_dual_bottle_blood_culture_rows(),
    )
    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-06-03-03", "LX0609-06-03-04"),
        projection=projection,
    )
    assert "双瓶/多瓶血培养" in prompt
    assert "血培养双瓶报阳" in prompt
    assert "双瓶/需氧及厌氧均报阳" in prompt
    assert "多瓶血培养同病原体报阳" in prompt
    assert "需氧与厌氧两份血培养报告" in prompt


@pytest.mark.asyncio
async def test_dual_bottle_blood_culture_single_note_satisfies_both_events() -> None:
    rows = _dual_bottle_blood_culture_rows()
    client = _SequentialExamLabClient(
        [
            {
                "schema_version": MULTI_EVENT_SCHEMA_VERSION,
                "facts": [
                    {
                        "rule_id": "LX0609-06-03-03",
                        "event_position": 1,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1],
                    },
                    {
                        "rule_id": "LX0609-06-03-03",
                        "event_position": 2,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1],
                    },
                    {
                        "rule_id": "LX0609-06-03-04",
                        "event_position": 1,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "positive",
                        "course_doc_positions": [1],
                    },
                    {
                        "rule_id": "LX0609-06-03-04",
                        "event_position": 2,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "positive",
                        "course_doc_positions": [1],
                    },
                ],
            }
        ]
    )
    finals = await _run_exam_lab_rules(
        rule_ids=("LX0609-06-03-03", "LX0609-06-03-04"),
        rows_by_source=rows,
        llm_client=client,
        admission_datetime="2026-04-01 08:00:00",
        discharge_datetime="2026-04-30 10:00:00",
    )
    assert finals["LX0609-06-03-03"]["status"] == "compliant"
    assert finals["LX0609-06-03-04"]["status"] == "compliant"
    assert "2026-04-14 09:43:06" in finals["LX0609-06-03-03"]["findings"]
    assert "2026-04-14 09:43:50" in finals["LX0609-06-03-03"]["findings"]
    assert "2026-04-14 09:52:00" in finals["LX0609-06-03-04"]["findings"]
