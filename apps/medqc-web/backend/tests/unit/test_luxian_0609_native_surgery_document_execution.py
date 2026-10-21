from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest
from luxian_0609_anesthesia_test_facts import ExplicitAnesthesiaFactClient

from app.services.luxian_0609 import native_surgery_document_execution as surgery_doc
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "一般缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _fact(
    fact_type: str,
    *,
    source_key: str,
    state: str = "performed",
    anesthesia_method: str = "全身麻醉",
) -> dict:
    return {
        "fact_type": fact_type,
        "source_key": source_key,
        "state": state,
        "current_visit_bound": True,
        "normalized_value": {"anesthesia_method": anesthesia_method},
    }


def _payload(*, facts: list[dict] | None = None, **overrides: list[dict]) -> dict:
    documents = {
        "anesthesia_record": [
            {"content": ("麻醉记录：麻醉诱导完成，气管插管顺利，术中持续监测并维持麻醉，" "术毕苏醒拔管。")}
        ],
        "consent_form": [{"content": "麻醉知情同意书：已告知风险，患者和麻醉医师签名，签署时间精确到分钟。"}],
        "preane_surveil_record": [{"content": "麻醉术前访视记录：完成病史、检查、ASA评估、麻醉计划及医师签名。"}],
        "postane_surveil_record": [{"content": "麻醉术后访视记录：神志清楚，恢复情况稳定，麻醉医师已签名。"}],
        "presurg_discussion": [{"content": "术前讨论记录：术者参加并讨论手术指征、方案、风险及应对措施。"}],
        "surgery_record": [{"content": "手术记录：本次手术已完成，记录手术经过及术者。"}],
        "rescue_record": [],
    }
    documents.update(overrides)
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": documents},
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 8, "total_tokens": 88},
            "_api_time": 0.1,
        }


def _typed_029_session(
    *,
    summary_rows: tuple[dict, ...] = (),
    surgery_mode: str = "exact",
    mr_surgery_mode: str = "empty",
    order_mode: str = "empty",
    summary_mode: str = "available",
    selected_rule_ids: tuple[str, ...] = ("LX0609-04-01-01",),
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        truncated = False
        if source_key == "surgery_record":
            if surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            if surgery_mode == "exact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            elif surgery_mode == "cross_matched_single":
                rows = (
                    {
                        "document_id": "surgery-document-a",
                        "surgery_begin_time": "2026-01-01 08:00:00+08",
                        "surgery_end_time": "2026-01-01 10:00:00+08",
                        "surgery_code": "17.1300X001",
                        "surgery_name": "腹腔镜下经腹膜前腹股沟疝补片修补术(TAPP)",
                    },
                )
            elif surgery_mode == "duplicate_document":
                rows = (
                    {
                        "document_id": "surgery-document-a",
                        "surgery_begin_time": "2026-01-01 08:00:00+08",
                    },
                    {
                        "document_id": "surgery-document-a",
                        "surgery_begin_time": "2026-01-01 08:00:00+08",
                    },
                )
            elif surgery_mode == "c01_time_shell":
                rows = (
                    {
                        "document_id": "surgery-time-shell",
                        "surgery_begin_time": "2026-01-01 08:00:00+08",
                        "record_time": "2026-01-02 11:00:00",
                        "surgery_code": "51.2300",
                        "surgery_name": "腹腔镜胆囊切除术",
                    },
                    {
                        "document_id": "surgery-substantive",
                        "surgery_begin_time": "2026-01-02 08:00:00+08",
                        "surgery_code": "51.2300",
                        "surgery_name": "腹腔镜胆囊切除术",
                        "surgery_process": "手术经过完整。",
                    },
                )
            elif surgery_mode == "typed_datetime":
                rows = (
                    {
                        "surgery_begin_time": datetime(
                            2026,
                            1,
                            1,
                            8,
                            0,
                            tzinfo=timezone(timedelta(hours=8)),
                        )
                    },
                )
            elif surgery_mode == "multi":
                rows = (
                    {"surgery_begin_time": "2026-01-01 08:00:00+08"},
                    {"surgery_begin_time": "2026-01-01 10:00:00+08"},
                )
            elif surgery_mode == "multi_same_time":
                rows = (
                    {"surgery_begin_time": "2026-01-01 08:00:00+08"},
                    {"surgery_begin_time": "2026-01-01 08:00:00+08"},
                )
            elif surgery_mode == "multi_named":
                rows = (
                    {
                        "document_id": "surgery-document-a",
                        "surgery_begin_time": "2026-01-01 08:00:00+08",
                        "surgery_end_time": "2026-01-01 10:00:00+08",
                        "surgery_name": "开颅右侧颅内血肿清除术+去骨瓣减压术+颅内压监测探头置入术",
                    },
                    {
                        "document_id": "surgery-document-b",
                        "surgery_begin_time": "2026-01-02 08:00:00+08",
                        "surgery_end_time": "2026-01-02 09:00:00+08",
                        "surgery_name": "右眼球破裂修补术",
                    },
                )
            elif surgery_mode == "nonexact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00"},)
            else:
                rows = ()
        elif source_key == "mr_surgery":
            if mr_surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if mr_surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            if mr_surgery_mode == "truncated":
                rows = (
                    {
                        "surgery_id": "mr-surgery-truncated",
                        "surgery_begin_datetime": datetime(2026, 1, 1, 10, 0),
                        "surgical_level": "二级",
                    },
                )
                truncated = True
            else:
                rows = (
                    (
                        {
                            "surgery_begin_datetime": datetime(2026, 1, 1, 8, 0),
                            "surgery_name": "连续性肾脏替代治疗",
                        },
                    )
                    if mr_surgery_mode == "nontraditional"
                    else ()
                )
            if mr_surgery_mode == "multi_traditional":
                rows = (
                    {
                        "surgery_id": "mr-surgery-a",
                        "surgery_begin_datetime": datetime(2026, 1, 1, 8, 0),
                        "surgical_level": "二级",
                    },
                    {
                        "surgery_id": "mr-surgery-b",
                        "surgery_begin_datetime": datetime(2026, 1, 1, 10, 0),
                        "surgical_level": "二级",
                    },
                )
            if mr_surgery_mode == "single_traditional_shared":
                rows = (
                    {
                        "surgery_id": "mr-surgery-a",
                        "surgery_begin_datetime": datetime(2026, 1, 1, 8, 0),
                        "surgery_end_datetime": datetime(2026, 1, 1, 10, 0),
                        "surgery_code": "17.1300x001",
                        "surgery_name": "腹腔镜下经腹膜前腹股沟疝补片修补术(TAPP)",
                        "surgical_level": "二级",
                    },
                )
            if mr_surgery_mode == "matched_plus_extra":
                rows = (
                    {
                        "surgery_id": "mr-surgery-a",
                        "surgery_begin_datetime": datetime(2026, 1, 1, 8, 0),
                        "surgery_end_datetime": datetime(2026, 1, 1, 10, 0),
                        "surgery_code": "17.1300x001",
                        "surgery_name": "腹腔镜下经腹膜前腹股沟疝补片修补术(TAPP)",
                        "surgical_level": "二级",
                    },
                    {
                        "surgery_id": "mr-surgery-b",
                        "surgery_begin_datetime": datetime(2026, 1, 1, 11, 0),
                        "surgery_end_datetime": datetime(2026, 1, 1, 12, 0),
                        "surgery_code": "17.1300x002",
                        "surgery_name": "另一台手术",
                        "surgical_level": "二级",
                    },
                )
            if mr_surgery_mode == "c01_anchor":
                rows = (
                    {
                        "surgery_id": "mr-surgery-c01",
                        "surgery_begin_datetime": datetime(2026, 1, 2, 0, 0),
                        "surgery_code": "51.2300",
                        "surgery_name": "腹腔镜胆囊切除术",
                        "surgical_level": "二级",
                    },
                )
        elif source_key == "presurg_summary":
            if summary_mode == "error":
                raise SourceEvidenceQueryError()
            if summary_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = summary_rows if summary_mode == "available" else ()
        elif source_key == "inpat_nondrug_order":
            if order_mode == "error":
                raise SourceEvidenceQueryError()
            if order_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = (
                (
                    {
                        "order_id": "surgery-order-029",
                        "order_type": "手术",
                        "order_status": "新开",
                        "order_name": "腹腔镜下经腹膜前腹股沟疝补片修补术(TAPP)",
                    },
                )
                if order_mode == "surgery"
                else (
                    (
                        {
                            "order_id": "2551076||445",
                            "order_type": "手术",
                            "order_status": "新开",
                            "order_name": "腹腔镜下经腹膜前腹股沟疝补片修补术(TAPP)",
                        },
                    )
                    if order_mode == "surgery_pipe_id"
                else (
                    (
                        {
                            "order_id": "non-surgery-order-029",
                            "order_type": "检查",
                            "order_status": "新开",
                            "order_name": "中心静脉置管术",
                        },
                    )
                    if order_mode == "non_surgery"
                    else (
                        (
                            {
                            "order_id": "unknown-order-029",
                            "order_type": "待核实",
                            "order_status": "新开",
                            "order_name": "待定治疗项目",
                            },
                        )
                        if order_mode == "unknown"
                        else ()
                    )
                    )
                )
            )
        elif source_key == "surgery_application":
            rows = ()
        else:
            rows = ()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=truncated,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-21T06:00:00+08:00",
        row_reader=reader,
    )


@pytest.mark.asyncio
async def test_typed_029_ungraded_mr_operation_is_not_applicable_without_llm():
    session = _typed_029_session(
        surgery_mode="empty",
        mr_surgery_mode="nontraditional",
        selected_rule_ids=("LX0609-04-01-01", "LX0609-04-01-02"),
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state == "not_applicable"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_nonempty_summary_is_compliant_without_llm():
    secret = "RAW_029_SUMMARY_Bearer_secret_13800138000"
    session = _typed_029_session(
        summary_rows=(
            {
                "document_title": "不参与029判定",
                "record_time": "not-used-by-029",
                "record_content": secret,
            },
        )
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )

    assert result.results == ()
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert reduced[0].final_state == "compliant"
    assert dict(result.customer_display_facts)["LX0609-04-01-01"] == {
        "verification_kind": "surgery_document_present",
        "target_document": "presurg_summary",
        "surgery_trigger_kind": "performed_surgery",
        "performed_surgery_confirmed": True,
    }
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_typed_029_accepts_database_timestamptz_with_nonempty_summary():
    session = _typed_029_session(
        surgery_mode="typed_datetime",
        summary_rows=({"record_content": "术前小结正文完整"},),
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_typed_029_multiple_surgery_rows_with_one_summary_requires_association():
    session = _typed_029_session(
        surgery_mode="multi",
        summary_rows=({"record_content": "术前小结正文完整"},),
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "association_failed"
    assert result.customer_display_facts == ()
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_matches_named_summary_and_reports_unmatched_surgery():
    session = _typed_029_session(
        surgery_mode="multi_named",
        summary_rows=(
            {
                "record_content": (
                    "手术名称：开颅右侧颅内血肿清除术+去骨瓣减压术+颅内压监测探头置入术。"
                    "手术时间：今日急诊。手术医师签名：韩平"
                )
            },
        ),
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "non_compliant"
    assert reduced[0].reason_code == "required_document_missing"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_same_time_multiple_surgeries_with_one_summary_requires_association():
    session = _typed_029_session(
        surgery_mode="multi_same_time",
        summary_rows=({"record_content": "术前小结正文完整"},),
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "association_failed"
    assert result.customer_display_facts == ()
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_cross_source_extra_surgery_requires_stable_event_coverage():
    session = _typed_029_session(
        summary_rows=({"record_content": "术前小结正文完整"},),
        mr_surgery_mode="multi_traditional",
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "association_failed"
    assert result.customer_display_facts == ()
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_cross_source_matched_code_name_and_times_is_one_event():
    session = _typed_029_session(
        surgery_mode="cross_matched_single",
        summary_rows=({"record_content": "术前小结正文完整"},),
        mr_surgery_mode="single_traditional_shared",
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_cross_source_one_to_two_events_requires_association():
    session = _typed_029_session(
        surgery_mode="cross_matched_single",
        summary_rows=({"record_content": "术前小结正文完整"},),
        mr_surgery_mode="matched_plus_extra",
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "association_failed"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_duplicate_surgery_document_is_one_event():
    session = _typed_029_session(
        surgery_mode="duplicate_document",
        summary_rows=({"record_content": "术前小结正文完整"},),
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_c01_time_shell_remains_one_event():
    session = _typed_029_session(
        surgery_mode="c01_time_shell",
        mr_surgery_mode="c01_anchor",
        summary_rows=({"record_content": "术前小结正文完整"},),
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_multiple_surgeries_and_empty_summary_is_non_compliant():
    session = _typed_029_session(surgery_mode="multi", summary_rows=())

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "non_compliant"
    assert reduced[0].reason_code == "required_document_missing"
    assert dict(result.customer_display_facts)["LX0609-04-01-01"] == {
        "failure_kind": "surgery_document_missing",
        "target_document": "presurg_summary",
        "surgery_trigger_kind": "performed_surgery",
        "performed_surgery_confirmed": True,
    }
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mr_surgery_mode", "expected_reason"),
    (
        ("unavailable", "source_unavailable"),
        ("error", "source_unavailable"),
        ("truncated", "source_truncated"),
    ),
)
async def test_typed_029_unavailable_second_surgery_source_blocks_single_event_conclusion(
    mr_surgery_mode: str,
    expected_reason: str,
):
    session = _typed_029_session(
        summary_rows=({"record_content": "本次手术术前评估及准备情况已记录。"},),
        mr_surgery_mode=mr_surgery_mode,
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state == "data_gap"
    assert result.decisions[0].reason_code == expected_reason
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_029_blank_or_placeholder_summary_is_non_compliant_without_llm():
    session = _typed_029_session(
        summary_rows=(
            {
                "document_title": "不参与029判定",
                "record_time": "not-used-by-029",
                "record_content": "   ",
            },
            {
                "document_title": "不参与029判定",
                "record_time": "not-used-by-029",
                "record_content": "  []  ",
            },
        )
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert reduced[0].final_state == "non_compliant"
    assert result.decisions[0].reason_code == "defect_proven"
    assert result.customer_display_facts == (
        (
            "LX0609-04-01-01",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "presurg_summary",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
        ),
    )
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
        ("surgery_mode", "summary_mode", "expected_state"),
        (
            ("empty", "available", "not_applicable"),
            ("nonexact", "available", "data_gap"),
            ("unavailable", "available", "data_gap"),
            ("error", "available", "technical_error"),
            ("exact", "available", "non_compliant"),
            ("exact", "unavailable", "data_gap"),
            ("exact", "error", "technical_error"),
        ),
)
async def test_typed_029_source_states_are_fail_closed_without_llm(
    surgery_mode: str,
    summary_mode: str,
    expected_state: str,
):
    session = _typed_029_session(
        surgery_mode=surgery_mode,
        summary_mode=summary_mode,
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state == expected_state
    if surgery_mode == "exact" and summary_mode == "available":
        assert result.decisions[0].reason_code == "required_document_missing"
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


def _strong_facts(*, anesthesia_method: str = "全身麻醉") -> list[dict]:
    return [
        _fact(
            "current_visit_anesthesia_performed",
            source_key="anesthesia_record",
            anesthesia_method=anesthesia_method,
        ),
        _fact("current_visit_surgery_confirmed", source_key="surgery_record"),
    ]


def _typed_session(
    *,
    surgery_mode: str = "exact",
    mr_surgery_mode: str = "empty",
    discussion_mode: str = "available",
    rescue_mode: str = "empty",
    selected_rule_ids: tuple[str, ...] = surgery_doc.SURGERY_DOCUMENT_RULE_IDS,
    daily_text: str | None = None,
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "daily_course_record" and daily_text is not None:
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=({"record_time": "2026-01-01 07:00:00", "record_content": daily_text},),
                truncated=False,
                limit_rows=50,
            )
        if source_key == "surgery_record":
            if surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            if surgery_mode == "exact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            elif surgery_mode == "multi":
                rows = (
                    {
                        "surgery_begin_time": "2026-01-01 08:00:00+08",
                        "record_content": "本次手术不属于紧急抢救手术。",
                    },
                    {
                        "surgery_begin_time": "2026-01-02 08:00:00+08",
                        "record_content": "本次手术不属于紧急抢救手术。",
                    },
                )
            else:
                rows = ()
        elif source_key == "mr_surgery":
            if mr_surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if mr_surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = (
                ({"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0, 0)},)
                if mr_surgery_mode == "exact"
                else ()
            )
        elif source_key == "presurg_discussion":
            if discussion_mode == "error":
                raise SourceEvidenceQueryError()
            rows = (
                ({"record_content": "术前讨论已记录手术指征、风险及处理预案。"},)
                if discussion_mode == "available"
                else ()
            )
        elif source_key == "rescue_record":
            if rescue_mode == "error":
                raise SourceEvidenceQueryError()
            rows = ()
        else:
            rows = ()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-17T06:00:00+08:00",
        row_reader=reader,
        additional_source_keys=("surgery_record",),
    )


def _typed_037_session(
    *,
    preanesthesia_content: str,
    anesthesia_method: str | None = "全身麻醉",
    anesthesia_record_content: str = "",
    mr_surgery_mode: str = "empty",
    visit_mode: str | None = None,
    pre_visit_mode: str = "available",
    post_visit_mode: str = "available",
):
    if visit_mode is not None:
        pre_visit_mode = visit_mode
        post_visit_mode = visit_mode

    rows_by_source = {
        "anesthesia_record": (
            (
                {
                    "anesthesia_method": anesthesia_method,
                    "record_content": anesthesia_record_content,
                },
            )
            if anesthesia_method is not None
            else ({"record_content": anesthesia_record_content},)
        ),
    }

    if mr_surgery_mode == "with_end":
        # 术后访视（07-31 08:00）在手术结束后48小时内。
        rows_by_source["mr_surgery"] = ({
            "surgery_id": "S-037", "anesthesia_method": anesthesia_method or "全身麻醉",
            "surgery_begin_datetime": "2026-07-30 09:00:00", "surgery_end_datetime": "2026-07-30 11:00:00",
        },)

    visit_rows = {
        "preane_surveil_record": {
            "record_time": "2026-07-30 08:00:00",
            "record_content": preanesthesia_content,
            "anesthetist_sign": "麻醉医师陈某",
        },
        "postane_surveil_record": {
            "record_time": "2026-07-31 08:00:00",
            "record_content": "神志清醒，呼吸平稳，循环稳定，无麻醉并发症。",
            "anesthetist_sign": "麻醉医师陈某",
        },
    }
    visit_modes = {
        "preane_surveil_record": pre_visit_mode,
        "postane_surveil_record": post_visit_mode,
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "mr_surgery" and mr_surgery_mode == "error":
            raise SourceEvidenceQueryError()
        if source_key == "mr_surgery" and mr_surgery_mode == "unavailable":
            raise SourceEvidenceUnavailable()
        if source_key in visit_modes:
            mode = visit_modes[source_key]
            if mode == "error":
                raise SourceEvidenceQueryError()
            if mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = () if mode == "empty" else (visit_rows[source_key],)
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows,
                truncated=mode == "truncated",
                limit_rows=50,
            )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-04-02",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-17T06:00:00+08:00",
        row_reader=reader,
    )


@pytest.mark.parametrize(
    ("record_content", "expected_status", "expected_reason"),
    (
        (
            "麻醉记录：麻醉方式：静吸复合全麻 ASA 分级：II级",
            "non_compliant",
            "anesthesia_visit_missing",
        ),
        (
            "麻醉记录：麻醉方式：局部麻醉 ASA 分级：I级",
            "not_applicable",
            "local_anesthesia_exception",
        ),
        (
            "麻醉方式：静吸复合全麻；术中变更，麻醉方式：局部麻醉。",
            "data_gap",
            "anesthesia_method_unavailable",
        ),
    ),
)
def test_typed_037_reads_only_unambiguous_labeled_anesthesia_method(
    record_content: str,
    expected_status: str,
    expected_reason: str,
):
    session = _typed_037_session(
        preanesthesia_content="",
        anesthesia_method=None,
        anesthesia_record_content=record_content,
        visit_mode="empty",
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-04-02",
        snapshot=session.snapshot,
        materials=session.materials,
    )

    assert outcome.status == expected_status
    assert outcome.reason_code == expected_reason


@pytest.mark.asyncio
async def test_typed_037_public_executor_rejects_local_negated_assessments():
    session = _typed_037_session(
        preanesthesia_content=(
            "未见ASA分级；无气道评估（未作气道评估）；已核对禁食禁饮；"
            "否认麻醉史；未见麻醉风险告知。"
        ),
        mr_surgery_mode="with_end",
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-04-02",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=ExplicitAnesthesiaFactClient("native_negated_assessments"),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-04-02",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-04-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "non_compliant"
    assert dict(result.customer_display_facts)["LX0609-04-04-02"] == {
        "failure_kind": "anesthesia_visit_incomplete",
        "performed_anesthesia_confirmed": True,
        "missing_fields_by_visit": {
            "preanesthesia_visit": [
                "anesthesia_indication",
                "precautions",
            ]
        },
    }
    assert result.llm_call_count == 1
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (10, 5, 15)


@pytest.mark.asyncio
async def test_typed_037_public_executor_fails_closed_when_method_is_unknown():
    session = _typed_037_session(
        preanesthesia_content=(
            "ASA II级，气道评估正常，禁食禁饮已核对，否认麻醉史，"
            "已完成麻醉风险告知。"
        ),
        anesthesia_method=None,
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-04-02",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-04-02",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-04-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "data_gap"
    assert result.decisions[0].reason_code == "applicability_source_gap"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_037_public_executor_treats_mr_surgery_query_error_as_technical():
    session = _typed_037_session(
        preanesthesia_content=(
            "ASA II级，气道评估正常，禁食禁饮已核对，否认麻醉史，"
            "已完成麻醉风险告知。"
        ),
        mr_surgery_mode="error",
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-04-02",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-04-02",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-04-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "technical_error"
    assert result.decisions[0].reason_code == "source_query_error"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.parametrize(
    ("rule_id", "observation_states", "expected_facts"),
    [
        (
            "LX0609-11-02-01",
            {"consent_form": "empty"},
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
            },
        ),
        (
            "LX0609-04-04-01",
            {
                "preane_surveil_record": "empty",
                "postane_surveil_record": "empty",
            },
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": [
                    "preane_surveil_record",
                    "postane_surveil_record",
                ],
            },
        ),
    ],
)
def test_typed_anesthesia_missing_documents_emit_controlled_customer_facts(
    monkeypatch,
    rule_id: str,
    observation_states: dict[str, str],
    expected_facts: dict[str, object],
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("unknown", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: observation_states.get(source_key, "available"),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id=rule_id,
        snapshot=object(),
    )

    assert outcome.status == "non_compliant"
    assert outcome.customer_display_facts == expected_facts


@pytest.mark.parametrize(
    ("rule_id", "empty_sources", "reason_code"),
    [("LX0609-11-02-02", {"consent_form"}, "anesthesia_consent_absent")],
)
def test_typed_detail_rules_are_not_applicable_when_parent_document_is_absent(
    monkeypatch,
    rule_id: str,
    empty_sources: set[str],
    reason_code: str,
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "empty" if source_key in empty_sources else "available"
        ),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id=rule_id,
        snapshot=object(),
    )

    assert outcome.status == "not_applicable"
    assert outcome.reason_code == reason_code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pre_visit_mode", "post_visit_mode"),
    (
        ("empty", "empty"),
        ("empty", "available"),
        ("available", "empty"),
    ),
)
async def test_typed_037_missing_visit_is_non_compliant(
    pre_visit_mode: str,
    post_visit_mode: str,
):
    session = _typed_037_session(
        preanesthesia_content="ASA II级，已完成气道评估，已核对禁食禁饮，麻醉史无，已完成麻醉风险告知。",
        pre_visit_mode=pre_visit_mode,
        post_visit_mode=post_visit_mode,
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-04-02",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-04-02",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-04-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "non_compliant"
    assert result.decisions[0].reason_code == "required_document_missing"
    assert dict(result.customer_display_facts)["LX0609-04-04-02"] == {
        "failure_kind": "anesthesia_visit_missing",
        "performed_anesthesia_confirmed": True,
        "missing_visit_sources": [
            source_key
            for source_key, mode in (
                ("preane_surveil_record", pre_visit_mode),
                ("postane_surveil_record", post_visit_mode),
            )
            if mode == "empty"
        ],
    }
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("visit_source_mode", "expected_state", "expected_reason"),
    (
        ("unavailable", "data_gap", "source_unavailable"),
        ("truncated", "data_gap", "source_unavailable"),
        ("error", "technical_error", "source_query_error"),
    ),
)
async def test_typed_037_visit_source_failure_is_not_a_clinical_defect(
    visit_source_mode: str,
    expected_state: str,
    expected_reason: str,
):
    session = _typed_037_session(
        preanesthesia_content="ASA II级，已完成气道评估，已核对禁食禁饮，麻醉史无，已完成麻醉风险告知。",
        pre_visit_mode=visit_source_mode,
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-04-02",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-04-02",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-04-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == expected_state
    assert result.decisions[0].reason_code == expected_reason
    assert result.llm_call_count == 0


def test_typed_037_incomplete_visits_report_exact_missing_fields(monkeypatch):
    rows_by_source = {
        "preane_surveil_record": (
            {
                "record_time": "2026-07-30 08:00:00",
                "record_content": "ASA III级。",
                "anesthetist_sign": "",
            },
        ),
        "postane_surveil_record": (
            {
                "record_time": "2026-07-31 08:00:00",
                "record_content": "神志清醒。",
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
    }
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_visit_rows",
        lambda _materials, source_key: rows_by_source[source_key],
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "available",
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-04-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials({}),
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "anesthesia_visit_incomplete"
    assert outcome.customer_display_facts == {
        "failure_kind": "anesthesia_visit_incomplete",
        "performed_anesthesia_confirmed": True,
        "missing_fields_by_visit": {
            "preanesthesia_visit": [
                "airway_assessment",
                "fasting_status",
                "anesthesia_history",
                "risk_discussion",
                "anesthetist_signature",
            ],
            "postanesthesia_visit": [
                "respiratory_status",
                "circulatory_status",
                "complication_assessment",
            ],
        },
    }


def test_037_complete_visits_are_compliant(monkeypatch):
    rows_by_source = {
        "preane_surveil_record": (
            {
                "record_time": "2026-07-30 08:00:00",
                "record_content": (
                    "ASA III级，完成气道评估，已核对禁食禁饮；"
                    "既往麻醉史无，已完成麻醉风险告知。"
                ),
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
        "postane_surveil_record": (
            {
                "record_time": "2026-07-31 08:00:00",
                "record_content": "神志清醒，呼吸平稳，循环稳定，无麻醉并发症。",
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
    }
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_visit_rows",
        lambda _materials, source_key: rows_by_source[source_key],
    )
    state, missing = surgery_doc._anesthesia_visit_completeness(
        _RowsOnlyMaterials({})
    )

    assert state == "complete"
    assert missing == {}


def test_037_merges_split_visit_rows_instead_of_reporting_association_gap(monkeypatch):
    rows_by_source = {
        "preane_surveil_record": (
            {"document_id": "visit-1", "record_time": "2026-07-30 08:00:00", "record_content": "ASA III级，完成气道评估；麻醉史无。"},
            {"document_id": "visit-1", "record_time": "2026-07-30 08:01:00", "record_content": "已核对禁食禁饮，已完成麻醉风险告知。", "anesthetist_sign": "陈某"},
        ),
        "postane_surveil_record": (
            {"document_id": "visit-1", "record_time": "2026-07-31 08:00:00", "record_content": "神志清醒，呼吸平稳，循环稳定，无麻醉并发症。", "anesthetist_sign": "陈某"},
        ),
    }
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_visit_rows",
        lambda _materials, source_key: rows_by_source[source_key],
    )

    state, missing = surgery_doc._anesthesia_visit_completeness(_RowsOnlyMaterials({}))

    assert state == "complete"
    assert missing == {}


def test_037_explicitly_negated_preanesthesia_items_are_incomplete(monkeypatch):
    rows_by_source = {
        "preane_surveil_record": (
            {
                "record_time": "2026-07-30 08:00:00",
                "record_content": (
                    "ASA III级，气道评估未完成，已核对禁食禁饮；"
                    "既往麻醉史无，麻醉风险尚未告知。"
                ),
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
        "postane_surveil_record": (
            {
                "record_time": "2026-07-31 08:00:00",
                "record_content": "神志清醒，呼吸平稳，循环稳定，无麻醉并发症。",
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
    }
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_visit_rows",
        lambda _materials, source_key: rows_by_source[source_key],
    )

    state, missing = surgery_doc._anesthesia_visit_completeness(_RowsOnlyMaterials({}))

    assert state == "incomplete"
    assert missing == {
        "preanesthesia_visit": ["airway_assessment", "risk_discussion"]
    }


def test_037_structured_asa_level_overrides_a_negated_text_fragment(monkeypatch):
    rows_by_source = {
        "preane_surveil_record": (
            {
                "record_time": "2026-07-30 08:00:00",
                "ASA_level": "III",
                "record_content": (
                    "ASA评估未完成；完成气道评估，已核对禁食禁饮；"
                    "既往麻醉史无，已完成麻醉风险告知。"
                ),
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
        "postane_surveil_record": (
            {
                "record_time": "2026-07-31 08:00:00",
                "record_content": "神志清醒，呼吸平稳，循环稳定，无麻醉并发症。",
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
    }
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_visit_rows",
        lambda _materials, source_key: rows_by_source[source_key],
    )

    state, missing = surgery_doc._anesthesia_visit_completeness(_RowsOnlyMaterials({}))

    assert state == "complete"
    assert missing == {}


def test_037_rejects_structured_placeholders_for_asa_and_signature(monkeypatch):
    rows_by_source = {
        "preane_surveil_record": (
            {
                "record_time": "2026-07-30 08:00:00",
                "ASA_level": "-",
                "record_content": (
                    "完成气道评估，已核对禁食禁饮；"
                    "既往麻醉史无，已完成麻醉风险告知。"
                ),
                "anesthetist_sign": "未签名",
            },
        ),
        "postane_surveil_record": (
            {
                "record_time": "2026-07-31 08:00:00",
                "record_content": "神志清醒，呼吸平稳，循环稳定，无麻醉并发症。",
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
    }
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_visit_rows",
        lambda _materials, source_key: rows_by_source[source_key],
    )

    state, missing = surgery_doc._anesthesia_visit_completeness(_RowsOnlyMaterials({}))

    assert state == "incomplete"
    assert missing == {
        "preanesthesia_visit": ["asa_level", "anesthetist_signature"]
    }


def test_037_rejects_front_negation_of_unperformed_preanesthesia_assessment(
    monkeypatch,
):
    rows_by_source = {
        "preane_surveil_record": (
            {
                "record_time": "2026-07-30 08:00:00",
                "record_content": (
                    "未进行ASA分级；未行气道评估；已核对禁食禁饮；"
                    "未询问麻醉史；未进行麻醉风险告知。"
                ),
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
        "postane_surveil_record": (
            {
                "record_time": "2026-07-31 08:00:00",
                "record_content": "神志清醒，呼吸平稳，循环稳定，无麻醉并发症。",
                "anesthetist_sign": "麻醉医师陈某",
            },
        ),
    }
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_visit_rows",
        lambda _materials, source_key: rows_by_source[source_key],
    )

    state, missing = surgery_doc._anesthesia_visit_completeness(_RowsOnlyMaterials({}))

    assert state == "incomplete"
    assert missing == {
        "preanesthesia_visit": [
            "asa_level",
            "airway_assessment",
            "anesthesia_history",
            "risk_discussion",
        ]
    }


def test_typed_038_uses_independent_nonlocal_anesthesia_trigger_for_missing_record(
    monkeypatch,
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "mr_surgery"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "empty" if source_key == "anesthesia_record" else "available"
        ),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-04-03",
        snapshot=object(),
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "anesthesia_record_missing"


def test_typed_039_missing_discussion_emits_controlled_customer_facts(monkeypatch):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda _rule_id: frozenset(
            {
                "surgery_record",
                "mr_surgery",
                "rescue_record",
                "presurg_discussion",
            }
        ),
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "")
            if source_key == "surgery_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "empty"
        if source_key == "presurg_discussion"
        else "available",
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
    )

    assert outcome.status == "non_compliant"
    assert outcome.customer_display_facts == {
        "failure_kind": "preop_discussion_missing",
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
        "checked_sources": ["presurg_discussion"],
    }


class _RowsOnlyMaterials:
    def __init__(
        self,
        rows_by_source: dict[str, tuple[dict, ...]],
        *,
        unavailable_sources: frozenset[str] = frozenset(),
    ):
        self._rows_by_source = rows_by_source
        self._unavailable_sources = unavailable_sources

    def rows(self, source_key: str) -> tuple[dict, ...]:
        if source_key in self._unavailable_sources:
            raise surgery_doc.EvidenceMaterialUnavailable()
        return self._rows_by_source.get(source_key, ())


def test_typed_anesthesia_trigger_uses_qualified_surgery_material(monkeypatch):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda *_args, **_kwargs: ("absent", ""),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "available" if source_key == "anesthesia_record" else "empty"
        ),
    )
    materials = _RowsOnlyMaterials(
        {
            "mr_surgery": (
                {
                    "surgical_level": "3",
                    "anesthesia_method": "静吸复合全麻",
                },
            ),
            "anesthesia_record": (
                {
                    "document_title": "麻醉记录",
                    "submit_datetime": datetime(2026, 7, 7, 18, 33, 26),
                },
            ),
        }
    )

    assert surgery_doc._typed_anesthesia_trigger(object(), materials) == (
        "present",
        "静吸复合全麻",
        "mr_surgery",
    )


def test_typed_anesthesia_trigger_handles_unavailable_anesthesia_record_material(
    monkeypatch,
):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda *_args, **_kwargs: ("absent", ""),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "available" if source_key == "anesthesia_record" else "empty"
        ),
    )
    materials = _RowsOnlyMaterials(
        {},
        unavailable_sources=frozenset({"anesthesia_record"}),
    )

    assert surgery_doc._typed_anesthesia_trigger(object(), materials) == (
        "present",
        "",
        "anesthesia_record",
    )


def test_typed_anesthesia_trigger_ignores_ungraded_non_surgical_operations(
    monkeypatch,
):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda *_args, **_kwargs: ("absent", ""),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda *_args, **_kwargs: "empty",
    )
    materials = _RowsOnlyMaterials(
        {
            "mr_surgery": (
                {
                    "surgery_name": "中心静脉置管术",
                    "surgical_level": None,
                    "anesthesia_method": "局部浸润麻醉",
                },
            ),
        }
    )

    assert surgery_doc._typed_anesthesia_trigger(object(), materials) == (
        "absent",
        "",
        "",
    )


def _patch_typed_039_present_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda _rule_id: frozenset(
            {
                "surgery_record",
                "mr_surgery",
                "rescue_record",
                "presurg_discussion",
            }
        ),
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "") if source_key == "surgery_record" else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "available",
    )


def _patch_typed_039_unknown_emergency(monkeypatch) -> None:
    _patch_typed_039_present_sources(monkeypatch)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "")
            if source_key == "surgery_record"
            else ("unknown", "")
            if source_key == "rescue_record"
            else ("absent", "")
        ),
    )


def test_typed_039_unknown_emergency_with_confirmed_participation_is_compliant(
    monkeypatch,
):
    _patch_typed_039_unknown_emergency(monkeypatch)
    materials = _RowsOnlyMaterials(
        {
            "surgery_record": (
                {"document_id": "surgery-unknown", "surgeon": "韩平"},
            ),
            "presurg_discussion": (
                {
                    "document_id": "discussion-unknown",
                    "discuss_staff": "韩平、刘娟",
                },
            ),
        }
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=materials,
    )

    assert outcome.status == "compliant"
    assert outcome.reason_code == "surgeon_participation_confirmed"
    assert outcome.customer_display_facts is None


def test_typed_039_unknown_emergency_with_missing_discussion_is_data_gap(monkeypatch):
    _patch_typed_039_unknown_emergency(monkeypatch)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "empty" if source_key == "presurg_discussion" else "available"
        ),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials(
            {"surgery_record": ({"surgeon": "韩平"},)}
        ),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "surgeon_participation_unresolved"
    assert outcome.customer_display_facts is None


def test_typed_039_unknown_emergency_with_unmatched_surgeon_is_data_gap(monkeypatch):
    _patch_typed_039_unknown_emergency(monkeypatch)
    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials(
            {
                "surgery_record": ({"surgeon": "韩平"},),
                "presurg_discussion": ({"discuss_staff": "刘娟"},),
            }
        ),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "surgeon_participation_unresolved"
    assert outcome.customer_display_facts is None


def test_typed_039_prefers_formal_surgeon_over_auxiliary_mr_rows(monkeypatch):
    _patch_typed_039_unknown_emergency(monkeypatch)
    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials(
            {
                "surgery_record": ({"surgeon": "梁应开"},),
                "mr_surgery": (
                    {"surgeon": "梁应开", "surgical_level": "四级"},
                    {"surgeon": "胃镜操作人员", "surgical_level": "一级"},
                    {"surgeon": "辅助操作人员", "surgical_level": None},
                ),
                "presurg_discussion": (
                    {"discuss_staff": "梁应开副主任医师"},
                ),
            }
        ),
    )

    assert outcome.status == "compliant"
    assert outcome.reason_code == "surgeon_participation_confirmed"


def test_typed_039_fallback_mr_uses_highest_level_only(monkeypatch):
    _patch_typed_039_unknown_emergency(monkeypatch)
    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials(
            {
                "surgery_record": (),
                "mr_surgery": (
                    {"surgeon": "梁应开", "surgical_level": "四级"},
                    {"surgeon": "胃镜操作人员", "surgical_level": "一级"},
                    {"surgeon": "辅助操作人员", "surgical_level": None},
                ),
                "presurg_discussion": (
                    {"discuss_staff": "梁应开副主任医师"},
                ),
            }
        ),
    )

    assert outcome.status == "compliant"
    assert outcome.reason_code == "surgeon_participation_confirmed"


def test_typed_039_fallback_mr_requires_all_surgeons_at_highest_level(monkeypatch):
    _patch_typed_039_unknown_emergency(monkeypatch)
    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials(
            {
                "surgery_record": (),
                "mr_surgery": (
                    {"surgeon": "梁应开", "surgical_level": "四级"},
                    {"surgeon": "张北南", "surgical_level": "四级"},
                    {"surgeon": "胃镜操作人员", "surgical_level": "一级"},
                ),
                "presurg_discussion": (
                    {"discuss_staff": "梁应开副主任医师"},
                ),
            }
        ),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "surgeon_participation_unresolved"


def test_typed_039_is_compliant_when_surgeon_is_in_discussion_staff(monkeypatch):
    _patch_typed_039_present_sources(monkeypatch)
    materials = _RowsOnlyMaterials(
        {
            "surgery_record": (
                {"document_id": "surgery-1", "surgeon": "韩平"},
            ),
            "presurg_discussion": (
                {
                    "document_id": "discussion-1",
                    "host_name": "刘娟",
                    "discuss_staff": "韩平、刘娟、曾亚丽",
                },
            ),
        }
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=materials,
    )

    assert outcome.status == "compliant"
    assert outcome.reason_code == "surgeon_participation_confirmed"
    assert outcome.customer_display_facts == {
        "surgeons": ["韩平"],
        "discussion_participants": ["刘娟", "曾亚丽", "韩平"],
        "matched_surgeons": ["韩平"],
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
        "discussion_state": "present",
        "surgeon_participation_state": "confirmed",
        "verification_kind": "preop_discussion_surgeon_participation_confirmed",
    }


def test_typed_039_is_non_compliant_when_known_surgeon_is_not_in_discussion(monkeypatch):
    _patch_typed_039_present_sources(monkeypatch)
    materials = _RowsOnlyMaterials(
        {
            "surgery_record": (
                {"document_id": "surgery-1", "surgeon": "韩平"},
            ),
            "presurg_discussion": (
                {
                    "document_id": "discussion-1",
                    "host_name": "刘娟",
                    "discuss_staff": "刘娟、曾亚丽",
                },
            ),
        }
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=materials,
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "surgeon_not_in_preop_discussion"
    assert outcome.customer_display_facts == {
        "failure_kind": "surgeon_not_in_preop_discussion",
        "surgeons": ["韩平"],
        "discussion_participants": ["刘娟", "曾亚丽"],
        "matched_surgeons": [],
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
        "discussion_state": "present",
        "surgeon_participation_state": "absent",
        "source_document_id": "surgery-1",
        "source_document_type": "surgery_record",
    }


def test_typed_039_requires_all_surgeons_in_preop_discussion(monkeypatch):
    _patch_typed_039_present_sources(monkeypatch)
    materials = _RowsOnlyMaterials(
        {
            "surgery_record": (
                {"document_id": "surgery-1", "surgeon": "韩平"},
                {"document_id": "surgery-2", "surgeon": "曾亚丽"},
            ),
            "presurg_discussion": (
                {"document_id": "discussion-1", "discuss_staff": "韩平"},
            ),
        }
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02", snapshot=object(), materials=materials
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "surgeon_not_in_preop_discussion"
    assert outcome.customer_display_facts["matched_surgeons"] == ["韩平"]


@pytest.mark.parametrize(
    ("surgery_rows", "discussion_rows", "expected_status", "expected_reason"),
    (
        (
            ({"surgeon": "韩平"},),
            ({"record_content": "未见麻醉科风险评估。"},),
            "data_gap",
            "surgeon_participation_unresolved",
        ),
        (
            ({},),
            ({"record_content": "缺少麻醉科医师签名。", "host_name": "李杰"},),
            "data_gap",
            "surgeon_participation_unresolved",
        ),
        (
            ({"surgeon": "韩平"},),
            ({
                "record_content": "缺少主持人及记录医师签名。",
                "host_name": "李杰",
                "submitter": "徐应福",
                "discuss_staff": "韩平、李杰、徐应福",
            },),
            "compliant",
            "surgeon_participation_confirmed",
        ),
        (
            ({"surgeon": "韩平"},),
            ({"record_time": "2025-07-06 09:52:44"},),
            "data_gap",
            "surgeon_participation_unresolved",
        ),
        (
            ({"surgeon": "韩平"},),
            ({"discuss_staff": "韩平、李杰", "record_time": "2025-10-15 09:00:00"},),
            "compliant",
            "surgeon_participation_confirmed",
        ),
        (
            ({},),
            ({"discuss_staff": "唐远君", "record_time": "2025-10-15 09:00:00"},),
            "data_gap",
            "surgeon_participation_unresolved",
        ),
    ),
)
def test_typed_039_uses_only_preop_discussion_and_surgeon_participation_facts(
    monkeypatch,
    surgery_rows,
    discussion_rows,
    expected_status,
    expected_reason,
):
    """麻醉、签名措辞或讨论存在性不得被下游重新解释成039缺陷。"""

    _patch_typed_039_present_sources(monkeypatch)
    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials(
            {
                "surgery_record": surgery_rows,
                "presurg_discussion": discussion_rows,
            }
        ),
    )

    assert outcome.status == expected_status
    assert outcome.reason_code == expected_reason


def test_035_structured_consent_completeness_lists_exact_missing_fields():
    state, missing = surgery_doc._anesthesia_consent_completeness(
        (
            {
                "patient_sign": "患者甲",
                "physician_sign": "",
                "patient_sign_datetime": "2026-07-30 10:20:00",
                "physician_sign_datetime": "2026-07-30",
            },
        )
    )

    assert state == "incomplete"
    assert missing == ["physician_signature", "physician_signature_time"]


def test_typed_035_incomplete_consent_is_non_compliant_with_exact_missing_fields(
    monkeypatch,
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "available",
    )
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_consent_rows",
        lambda _materials: (
            {
                "consent_type": "麻醉知情同意书",
                "patient_sign": "患者甲",
                "physician_sign": "",
                "patient_sign_datetime": "2026-07-30 10:20:00",
                "physician_sign_datetime": "2026-07-30",
            },
        ),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-11-02-02",
        snapshot=object(),
        materials=_RowsOnlyMaterials({}),
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "anesthesia_consent_incomplete"
    assert outcome.customer_display_facts == {
        "failure_kind": "anesthesia_consent_incomplete",
        "performed_anesthesia_confirmed": True,
        "missing_fields": ["physician_signature", "physician_signature_time"],
    }


def test_035_multiple_anesthesia_consents_fail_closed_on_association():
    state, missing = surgery_doc._anesthesia_consent_completeness(({}, {}))

    assert state == "association_failed"
    assert missing == []


def test_typed_missing_document_facts_keep_only_unique_trigger_document_id(monkeypatch):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda _rule_id: frozenset(
            {
                "anesthesia_record",
                "consent_form",
                "preane_surveil_record",
                "postane_surveil_record",
                "surgery_record",
                "mr_surgery",
                "rescue_record",
                "presurg_discussion",
            }
        ),
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else (("present", "") if source_key == "surgery_record" else ("absent", ""))
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "empty"
        if source_key
        in {
            "consent_form",
            "preane_surveil_record",
            "postane_surveil_record",
            "presurg_discussion",
        }
        else "available",
    )
    materials = _RowsOnlyMaterials(
        {
            "anesthesia_record": ({"document_id": "anesthesia-private-id"},),
            "surgery_record": ({"document_id": "surgery-private-id"},),
            "mr_surgery": ({"document_id": "mr-surgery-private-id"},),
        }
    )

    for rule_id, expected_document_id, expected_document_type in (
        ("LX0609-11-02-01", "anesthesia-private-id", "anesthesia_record"),
        ("LX0609-04-04-01", "anesthesia-private-id", "anesthesia_record"),
        ("LX0609-04-01-02", "surgery-private-id", "surgery_record"),
    ):
        outcome = surgery_doc._typed_terminal_outcome(
            rule_id=rule_id,
            snapshot=object(),
            materials=materials,
        )
        assert outcome.status == "non_compliant"
        assert outcome.customer_display_facts is not None
        assert outcome.customer_display_facts["source_document_id"] == expected_document_id
        assert outcome.customer_display_facts["source_document_type"] == expected_document_type


def test_trigger_document_id_fails_closed_when_row_is_missing_or_ambiguous():
    facts = {"failure_kind": "anesthesia_visit_missing"}

    assert surgery_doc._with_trigger_document_id(
        facts,
        materials=_RowsOnlyMaterials({"anesthesia_record": ()}),
        source_keys=("anesthesia_record",),
    ) == facts
    assert surgery_doc._with_trigger_document_id(
        facts,
        materials=_RowsOnlyMaterials(
            {
                "anesthesia_record": (
                    {"document_id": "anesthesia-a"},
                    {"document_id": "anesthesia-b"},
                )
            }
        ),
        source_keys=("anesthesia_record",),
    ) == facts
    assert surgery_doc._with_trigger_document_id(
        facts,
        materials=_RowsOnlyMaterials(
            {"anesthesia_record": ({"record_content": "PRIVATE_BODY"},)}
        ),
        source_keys=("anesthesia_record",),
    ) == facts


@pytest.mark.asyncio
async def test_strong_facts_run_each_selected_rule_once_in_customer_order():
    unrelated_marker = "UNRELATED_DAILY_COURSE_MUST_NOT_ENTER_PROMPT"
    legacy_document_rule_ids = tuple(
        rule_id
        for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        if rule_id not in {"LX0609-04-01-01", "LX0609-04-01-04", "LX0609-04-01-05"}
    )
    client = _Client([{"is_compliant": index % 2 == 0} for index in range(6)])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=tuple(reversed(legacy_document_rule_ids)),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in legacy_document_rule_ids
        ],
        evidence_payload=_payload(
            facts=_strong_facts(),
            daily_course_record=[{"content": unrelated_marker}],
        ),
        llm_client=client,
    )

    assert result.planned_rule_ids == legacy_document_rule_ids
    assert [item["rule_id"] for item in result.results] == list(
        legacy_document_rule_ids
    )
    assert [item["status"] for item in result.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
    ]
    assert result.llm_call_count == 6
    assert result.total_tokens == 528
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)
    assert all(unrelated_marker not in prompt for prompt in client.prompts)
    assert all("mapped_rule_ids" not in repr(item) for item in result.results)


@pytest.mark.asyncio
async def test_planned_anesthesia_template_and_method_only_are_not_performed_facts():
    marker = "SAFE_FALSE_EVIDENCE_MARKER"
    client = _Client([])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-11-02-01", "LX0609-11-02-02", "LX0609-04-04-01", "LX0609-04-04-02", "LX0609-04-04-03"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload=_payload(
            facts=[],
            anesthesia_record=[
                {"content": f"拟请麻醉科会诊。{marker}"},
                {"content": "麻醉方式：全身麻醉"},
                {"content": "麻醉记录（空模板）"},
            ],
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert marker not in repr(result)


@pytest.mark.asyncio
async def test_fully_silent_anesthesia_and_surgery_facts_are_data_gap_not_na():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-11-02-01", "LX0609-04-01-02"),
        wrapper_rules=[_wrapper("LX0609-11-02-01"), _wrapper("LX0609-04-01-02")],
        evidence_payload=_payload(
            facts=[],
            anesthesia_record=[],
            surgery_record=[],
            presurg_discussion=[],
        ),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_missing_consent_is_owned_by_034_and_035_is_not_applicable():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-11-02-01", "LX0609-11-02-02"),
        wrapper_rules=[_wrapper("LX0609-11-02-01"), _wrapper("LX0609-11-02-02")],
        evidence_payload=_payload(facts=_strong_facts(), consent_form=[]),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "not_applicable",
    ]
    assert result.results[0]["metadata"]["reason_code"] == (
        "anesthesia_consent_source_unproven"
    )
    assert result.results[1]["metadata"]["reason_code"] == "anesthesia_consent_absent"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_unrelated_generic_consent_does_not_qualify_as_anesthesia_consent():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-11-02-01",),
        wrapper_rules=[_wrapper("LX0609-11-02-01")],
        evidence_payload=_payload(
            facts=_strong_facts(),
            consent_form=[{"content": "手术知情同意书：已完成手术风险告知和患者签名。"}],
        ),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == (
        "anesthesia_consent_source_unproven"
    )


@pytest.mark.asyncio
async def test_consent_rules_do_not_require_anesthesia_method_when_performed_fact_exists():
    performed_without_method = {
        "fact_type": "current_visit_anesthesia_performed",
        "source_key": "anesthesia_record",
        "state": "performed",
        "current_visit_bound": True,
    }
    client = _Client([{"is_compliant": True}, {"is_compliant": True}])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-11-02-01", "LX0609-11-02-02"),
        wrapper_rules=[_wrapper("LX0609-11-02-01"), _wrapper("LX0609-11-02-02")],
        evidence_payload=_payload(facts=[performed_without_method]),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_local_anesthesia_is_not_applicable_to_visit_and_record_sheet_rules():
    client = _Client([])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-04-01", "LX0609-04-04-02", "LX0609-04-04-03"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload=_payload(facts=_strong_facts(anesthesia_method="局部麻醉")),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 3
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.parametrize(
    ("rule_id", "anesthesia_method", "expected_status", "expected_reason"),
    [
        ("LX0609-04-04-01", "局部麻醉", "not_applicable", "local_anesthesia_exception"),
        ("LX0609-04-04-02", "局部麻醉", "not_applicable", "local_anesthesia_exception"),
        ("LX0609-04-04-03", "局部麻醉", "not_applicable", "local_anesthesia_exception"),
        ("LX0609-04-04-03", "全身麻醉", "compliant", "anesthesia_record_present"),
        ("LX0609-04-04-01", "", "data_gap", "anesthesia_method_unavailable"),
        ("LX0609-04-04-02", "", "data_gap", "anesthesia_method_unavailable"),
        ("LX0609-04-04-03", "", "data_gap", "anesthesia_method_unavailable"),
    ],
)
def test_typed_anesthesia_method_state_matrix_fails_closed(
    monkeypatch,
    rule_id: str,
    anesthesia_method: str,
    expected_status: str,
    expected_reason: str,
):
    """局麻、非局麻和未知方式必须走互斥、受控的状态分支。"""

    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", anesthesia_method)
            if source_key == "anesthesia_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, _source_key: "available",
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id=rule_id,
        snapshot=object(),
    )

    assert (outcome.status, outcome.reason_code) == (expected_status, expected_reason)


@pytest.mark.parametrize("rule_id", ("LX0609-04-04-01", "LX0609-04-04-02", "LX0609-04-04-03"))
def test_typed_anesthesia_mr_surgery_query_error_is_technical_error(
    monkeypatch,
    rule_id: str,
):
    """麻醉触发所需的手术源查询失败不能伪装为不适用或临床缺陷。"""

    def source_gate(*, source_key: str, **_kwargs):
        if source_key == "mr_surgery":
            return surgery_doc._SurgeryDocumentOutcome(
                rule_id,
                "technical_error",
                "source_query_error",
                "program",
            )
        return None

    monkeypatch.setattr(surgery_doc, "_typed_source_gate", source_gate)

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id=rule_id,
        snapshot=object(),
    )

    assert (outcome.status, outcome.reason_code) == (
        "technical_error",
        "source_query_error",
    )


@pytest.mark.parametrize("rule_id", ("LX0609-11-02-01", "LX0609-11-02-02"))
def test_typed_anesthesia_consent_rules_do_not_require_mr_surgery_readiness(
    monkeypatch,
    rule_id: str,
):
    """知情同意书规则不因非依赖的手术主表故障改写既有口径。"""

    gated_sources: list[str] = []

    def source_gate(*, source_key: str, **_kwargs):
        gated_sources.append(source_key)
        if source_key == "mr_surgery":
            return surgery_doc._SurgeryDocumentOutcome(
                rule_id,
                "technical_error",
                "source_query_error",
                "program",
            )
        return None

    monkeypatch.setattr(surgery_doc, "_typed_source_gate", source_gate)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, _source_key: "available",
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id=rule_id,
        snapshot=object(),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "required_field_missing"
    assert "mr_surgery" not in gated_sources


def test_local_anesthesia_exception_reduces_to_eligibility_not_met():
    """局麻是资格排除，不能在 Canonical 结果中表述成“未实施麻醉”。"""

    session = _typed_session(selected_rule_ids=("LX0609-04-04-01",))
    decision = surgery_doc._typed_decision_from_outcome(
        outcome=surgery_doc._SurgeryDocumentOutcome(
            "LX0609-04-04-01",
            "not_applicable",
            "local_anesthesia_exception",
            "program",
        ),
        snapshot=session.snapshot,
    )

    assert decision.reason_code == "eligibility_not_met"


@pytest.mark.parametrize(
    ("rule_id", "outcome_reason", "expected_reason"),
    (
        ("LX0609-04-01-01", "preop_summary_blank", "defect_proven"),
        ("LX0609-04-01-01", "preop_summary_missing", "required_document_missing"),
        ("LX0609-11-02-01", "anesthesia_consent_missing", "required_document_missing"),
        ("LX0609-11-02-02", "anesthesia_consent_incomplete", "requirement_violated"),
        ("LX0609-04-04-01", "anesthesia_visit_missing", "required_document_missing"),
        ("LX0609-04-04-02", "anesthesia_visit_incomplete", "requirement_violated"),
        ("LX0609-04-04-03", "anesthesia_record_missing", "required_document_missing"),
        ("LX0609-04-01-02", "preop_discussion_missing", "required_document_missing"),
        (
            "LX0609-04-01-02",
            "surgeon_not_in_preop_discussion",
            "requirement_violated",
        ),
    ),
)
def test_typed_non_compliance_preserves_missing_vs_requirement_violation_reason(
    rule_id: str,
    outcome_reason: str,
    expected_reason: str,
):
    """缺文书与已读文书不符合要求必须保留不同的 Canonical 原因码。"""

    session = _typed_session(selected_rule_ids=(rule_id,))

    decision = surgery_doc._typed_decision_from_outcome(
        outcome=surgery_doc._SurgeryDocumentOutcome(
            rule_id,
            "non_compliant",
            outcome_reason,
            "program",
        ),
        snapshot=session.snapshot,
    )

    assert decision.reason_code == expected_reason


def test_typed_039_emergency_exception_is_eligibility_and_references_rescue_source():
    """急救例外不是未实施手术，且例外来源必须进入 Binding 引用集合。"""

    session = _typed_session(selected_rule_ids=("LX0609-04-01-02",))
    rescue_ref = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in session.snapshot.observations
        if observation.source_key == "rescue_record"
    )

    decision = surgery_doc._typed_decision_from_outcome(
        outcome=surgery_doc._SurgeryDocumentOutcome(
            "LX0609-04-01-02",
            "not_applicable",
            "emergency_rescue_exception",
            "program",
        ),
        snapshot=session.snapshot,
    )

    assert decision.reason_code == "eligibility_not_met"
    assert rescue_ref in decision.fact_refs


@pytest.mark.asyncio
async def test_typed_039_rescue_source_query_error_is_technical_error():
    """039 已依赖抢救例外源时，其查询失败必须保持技术错误。"""

    session = _typed_session(
        rescue_mode="error",
        selected_rule_ids=("LX0609-04-01-02",),
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )

    assert result.decisions[0].evidence_state.value == "technical_error"
    assert result.decisions[0].reason_code == "source_query_error"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_missing_visits_are_defects_for_037_even_when_036_is_selected():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-04-01", "LX0609-04-04-02"),
        wrapper_rules=[_wrapper("LX0609-04-04-01"), _wrapper("LX0609-04-04-02")],
        evidence_payload=_payload(
            facts=_strong_facts(),
            preane_surveil_record=[],
            postane_surveil_record=[],
        ),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "non_compliant",
    ]
    assert result.results[1]["metadata"]["reason_code"] == "anesthesia_visit_missing"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_emergency_rescue_surgery_is_039_exception_without_model():
    facts = _strong_facts() + [
        _fact(
            "current_visit_emergency_rescue_surgery",
            source_key="rescue_record",
            state="present",
        )
    ]
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=_payload(facts=facts, presurg_discussion=[]),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "not_applicable"
    assert result.results[0]["metadata"]["reason_code"] == "emergency_rescue_exception"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_performed_surgery_without_attested_preop_source_is_data_gap():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=_payload(facts=_strong_facts(), presurg_discussion=[]),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "preop_discussion_source_unproven"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_llm_failure_and_invalid_json_are_sanitized_data_gap():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), "not-json"])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-11-02-01", "LX0609-04-01-02"),
        wrapper_rules=[_wrapper("LX0609-11-02-01"), _wrapper("LX0609-04-01-02")],
        evidence_payload=_payload(facts=_strong_facts()),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "surgery_document_llm_failure",
        "surgery_document_llm_invalid_output",
    ]
    assert result.llm_call_count == 2
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_typed_surgery_document_rules_are_ordered_fail_closed_and_never_read_legacy_payload():
    session = _typed_session()
    secret = "RAW_BODY_Bearer_secret_13800138000"
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=tuple(reversed(surgery_doc.SURGERY_DOCUMENT_RULE_IDS)),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload={"medical_text": secret},
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=surgery_doc.SURGERY_DOCUMENT_RULE_IDS,
    )

    assert result.planned_rule_ids == surgery_doc.SURGERY_DOCUMENT_RULE_IDS
    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(
        surgery_doc.SURGERY_DOCUMENT_RULE_IDS
    )
    # 029在当前快照中触发且术前小结为空，034-038来源契约不可用；
    # 039有手术强事实但术者参与关联仍未获批准。
    assert [
        bind_and_reduce_luxian_0609_rule_decisions(
            expected_rule_ids=(decision.rule_id,),
            snapshot=session.snapshot,
            decisions=(decision,),
            evidence_materials=session.materials,
        )[0].final_state
        for decision in result.decisions
    ] == [
        "non_compliant",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        "data_gap",
        "not_applicable",
        "not_applicable",
    ]
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_typed_078_source_query_error_is_delivered_as_data_gap():
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "presurg_summary":
            raise SourceEvidenceQueryError()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-04",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-09-20T00:00:00+08:00",
        row_reader=reader,
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-04",),
        wrapper_rules=[_wrapper("LX0609-04-01-04")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-04",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        expected_rule_ids=("LX0609-04-01-04",),
        snapshot=session.snapshot,
        decisions=result.decisions,
        evidence_materials=session.materials,
    )

    assert (reduced[0].final_state, reduced[0].reason_code) == (
        "data_gap",
        "source_readiness_unproven",
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_empty_surgery_is_not_applicable_after_binding_contract(
    monkeypatch,
):
    original = surgery_doc._typed_binding_source_keys
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda rule_id: original(rule_id) | {"surgery_record"},
    )
    session = _typed_session(surgery_mode="empty", discussion_mode="empty")
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )

    assert result.results == ()
    assert result.decisions[0].applicability.value == "not_applicable"
    assert result.decisions[0].reason_code == "performed_event_absent"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_ungraded_mr_operation_is_not_a_traditional_surgery_trigger():
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            ({"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0, 0)},)
            if source_key == "mr_surgery"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-02",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-17T06:00:00+08:00",
        row_reader=reader,
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )

    assert result.results == ()
    assert result.decisions[0].applicability.value == "not_applicable"
    assert result.decisions[0].evidence_state.value == "sufficient"
    assert result.decisions[0].reason_code == "performed_event_absent"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_039_empty_discussion_without_emergency_mention_is_defect(
    monkeypatch,
):
    """院方口径（2026-10-10）：文书未写急诊即视为非急诊，无术前讨论判不合规。"""
    original = surgery_doc._typed_binding_source_keys
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda rule_id: original(rule_id) | {"surgery_record"},
    )
    session = _typed_session(surgery_mode="exact", discussion_mode="empty")
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )

    assert result.decisions[0].applicability.value == "applicable"
    assert result.decisions[0].qc_direction.value == "defect"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_multiple_surgeries_with_complete_empty_discussion_is_non_compliant(
    monkeypatch,
):
    original = surgery_doc._typed_binding_source_keys
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda rule_id: original(rule_id) | {"surgery_record"},
    )
    session = _typed_session(surgery_mode="multi", discussion_mode="empty")

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )

    assert result.decisions[0].evidence_state.value == "sufficient"
    assert result.decisions[0].qc_direction.value == "defect"
    assert result.decisions[0].reason_code == "required_document_missing"
    assert dict(result.customer_display_facts)["LX0609-04-01-02"]["failure_kind"] == (
        "preop_discussion_missing"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_source_query_error_is_technical_error_without_echo(monkeypatch):
    original = surgery_doc._typed_binding_source_keys
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda rule_id: original(rule_id) | {"surgery_record"},
    )
    session = _typed_session(surgery_mode="error", discussion_mode="available")
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )

    assert result.decisions[0].evidence_state.value == "technical_error"
    assert result.decisions[0].reason_code == "source_query_error"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_dual_source_failure_semantics_and_positive_precedence():
    unavailable = _typed_session(
        surgery_mode="unavailable",
        mr_surgery_mode="empty",
        discussion_mode="available",
        selected_rule_ids=("LX0609-04-01-02",),
    )
    unavailable_result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=unavailable.snapshot,
        evidence_materials=unavailable.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )
    assert unavailable_result.decisions[0].evidence_state.value == "data_gap"
    assert unavailable_result.decisions[0].reason_code == "source_unavailable"

    positive = _typed_session(
        surgery_mode="error",
        mr_surgery_mode="exact",
        discussion_mode="available",
        selected_rule_ids=("LX0609-04-01-02",),
    )
    positive_result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=positive.snapshot,
        evidence_materials=positive.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )
    # mr_surgery 的可信肯定事实优先；后续仍因急救例外事实未解析而 DG，
    # 不能被另一手术来源的查询失败覆盖成技术错误。
    assert positive_result.decisions[0].evidence_state.value == "data_gap"
    assert positive_result.decisions[0].reason_code == "applicability_source_gap"
    assert positive_result.llm_call_count == positive_result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_scope_and_snapshot_material_binding_fail_closed():
    session = _typed_session(selected_rule_ids=("LX0609-04-01-02",))
    with pytest.raises(ValueError, match="unsupported typed surgery document rule scope"):
        await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
            rule_ids=("LX0609-04-01-02",),
            wrapper_rules=[_wrapper("LX0609-04-01-02")],
            evidence_payload=None,
            llm_client=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            decision_rule_ids=("LX0609-11-02-01",),
        )

    other_session = _typed_session(
        selected_rule_ids=("LX0609-04-01-02",), discussion_mode="empty"
    )
    with pytest.raises(ValueError, match="require one evidence session"):
        await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
            rule_ids=("LX0609-04-01-02",),
            wrapper_rules=[_wrapper("LX0609-04-01-02")],
            evidence_payload=None,
            llm_client=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=other_session.materials,
            decision_rule_ids=("LX0609-04-01-02",),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("summary_rows", "expected_state", "expected_reason", "expected_finding"),
    (
        (
            ({"document_id": "summary-029", "record_content": "术前小结正文完整。"},),
            "compliant",
            "requirement_satisfied",
            "已发现手术医嘱，术前小结已完整记录。",
        ),
        (
            (),
            "non_compliant",
            "required_document_missing",
            "已发现手术医嘱，但未找到对应术前小结。",
        ),
        (
            ({"document_id": "summary-029", "record_content": "   "},),
            "non_compliant",
            "defect_proven",
            "已发现手术医嘱，但对应术前小结正文为空。",
        ),
    ),
)
async def test_typed_029_surgery_order_only_triggers_and_binds_selected_evidence(
    summary_rows: tuple[dict, ...],
    expected_state: str,
    expected_reason: str,
    expected_finding: str,
) -> None:
    """029 的医嘱触发必须走既有 any-of 合同，不等待已实施手术。"""

    session = _typed_029_session(
        surgery_mode="empty",
        mr_surgery_mode="empty",
        order_mode="surgery",
        summary_rows=summary_rows,
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == result.total_tokens == 0
    order_ref = session.materials.document_rows(
        "inpat_nondrug_order", snapshot=session.snapshot
    )[0][0]
    order_fact = next(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_surgery_order_confirmed"
    )
    assert order_fact.source_document_id == ""
    assert order_fact.fact_id in result.decisions[0].fact_refs
    assert order_ref in result.decisions[0].fact_refs
    if summary_rows:
        summary_ref = session.materials.document_rows(
            "presurg_summary", snapshot=session.snapshot
        )[0][0]
        assert summary_ref in result.decisions[0].fact_refs
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper("LX0609-04-01-01")],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]
    coordinates = {
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    }
    assert ("inpat_nondrug_order", "surgery-order-029") in coordinates
    assert all(len(document_id) != 64 for _, document_id in coordinates)
    assert canonical["findings"] == expected_finding
    assert "实施手术" not in canonical["findings"]


@pytest.mark.asyncio
async def test_typed_029_performed_surgery_trigger_keeps_implemented_surgery_copy() -> None:
    """严格已实施手术触发仍保留其真实展示事实和客户文案。"""

    session = _typed_029_session(
        surgery_mode="exact",
        mr_surgery_mode="empty",
        order_mode="empty",
        summary_rows=(),
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[_wrapper("LX0609-04-01-01")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper("LX0609-04-01-01")],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]

    facts = canonical["customer_display_facts"]
    assert facts["surgery_trigger_kind"] == "performed_surgery"
    assert facts["performed_surgery_confirmed"] is True
    assert "surgery_order_confirmed" not in facts
    assert canonical["findings"] == "已确认本次实施手术，但未找到对应的术前小结。"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("order_mode", "expected_state", "expected_reason"),
    (
        ("non_surgery", "not_applicable", "performed_event_absent"),
        ("unknown", "data_gap", "applicability_source_gap"),
        ("error", "technical_error", "source_query_error"),
    ),
)
async def test_typed_029_surgery_order_trigger_failure_semantics(
    order_mode: str,
    expected_state: str,
    expected_reason: str,
) -> None:
    session = _typed_029_session(
        surgery_mode="empty",
        mr_surgery_mode="empty",
        order_mode=order_mode,
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_order_evidence_restores_real_pipe_delimited_id() -> None:
    """材料摘要只能作内部 ref，客户证据必须恢复源医嘱坐标。"""

    session = _typed_029_session(
        surgery_mode="empty",
        mr_surgery_mode="empty",
        order_mode="surgery_pipe_id",
        summary_rows=(
            {"document_id": "summary-029-pipe", "record_content": "术前小结正文完整。"},
        ),
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[_wrapper("LX0609-04-01-01")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper("LX0609-04-01-01")],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]

    coordinates = {
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    }
    assert ("inpat_nondrug_order", "2551076||445") in coordinates
    assert all(len(document_id) != 64 for _, document_id in coordinates)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_surgery_order_positive_wins_over_other_trigger_source_error() -> None:
    session = _typed_029_session(
        surgery_mode="error",
        mr_surgery_mode="empty",
        order_mode="surgery",
        summary_rows=({"document_id": "summary-029", "record_content": "术前小结正文完整。"},),
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_029_surgery_order_does_not_mask_target_source_error() -> None:
    session = _typed_029_session(
        surgery_mode="empty",
        mr_surgery_mode="empty",
        order_mode="surgery",
        summary_mode="error",
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "technical_error"
    assert reduced[0].reason_code == "source_query_error"
    assert result.llm_call_count == result.total_tokens == 0


class _NamedSurgeryMaterials:
    def __init__(self, record_names=(), mr_names=()):
        self._rows = {
            "surgery_record": tuple({"surgery_name": name} for name in record_names),
            "mr_surgery": tuple({"surgery_name": name} for name in mr_names),
        }

    def rows(self, source_key):
        return self._rows[source_key]


@pytest.mark.parametrize(("mr_names", "exempt"), [
    (("纤维支气管镜检查", "支气管镜下肺活检"), True),
    (("内镜下胃息肉切除术",), True),
    (("腹腔镜下胆囊切除术",), False),
    (("内镜下胃息肉切除术", "腹股沟疝修补术"), False),
    ((), False),
])
def test_029_endoscopic_only_procedures_need_no_preop_summary(mr_names, exempt):
    """院方口径（2026-10-10）：自然腔道内镜操作不需要术前小结，镜下手术仍核对。"""
    assert surgery_doc._only_endoscopic_procedures(_NamedSurgeryMaterials(mr_names=mr_names)) is exempt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("daily_text", "expected_reason"),
    [
        # 用户口径（2026-10-20，1019 C15）：病程写明急诊介入，属于039急诊抢救例外。
        ("于11:00送患者到导管室急诊行冠脉造影＋必要时支架置入。", "emergency_rescue_exception"),
        ("患者既往于外院急诊行PCI术，现病情平稳。", "preop_discussion_missing"),
        ("患者由急诊科收入，完善检查后择期手术。", "preop_discussion_missing"),
    ],
)
async def test_typed_039_course_emergency_intervention_is_rescue_exception(
    daily_text, expected_reason
):
    session = _typed_session(
        discussion_mode="empty",
        selected_rule_ids=("LX0609-04-01-02",),
        daily_text=daily_text,
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-02",),
        wrapper_rules=[_wrapper("LX0609-04-01-02")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-02",),
    )

    outcome_reason = dict(result.customer_display_facts).get("LX0609-04-01-02", {}).get(
        "failure_kind", result.decisions[0].reason_code
    )
    expected = "eligibility_not_met" if expected_reason == "emergency_rescue_exception" else expected_reason
    assert outcome_reason == expected
    assert result.llm_call_count == 0
