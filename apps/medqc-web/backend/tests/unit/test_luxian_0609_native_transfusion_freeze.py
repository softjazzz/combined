from __future__ import annotations

from tests.luxian_0609_identity_test_support import published_rule_ids

from datetime import datetime
from typing import Any

import pytest

from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER, FrozenTransfusionProtocolClient

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results


def _wrapper(rule_id: str) -> dict[str, str]:
    return {"rule_id": rule_id, "rule_name": rule_id}


async def _execute_and_aggregate(
    *,
    rule_ids: tuple[str, ...],
    rows_by_source: dict[str, list[dict[str, Any]]],
    failing_sources: frozenset[str] = frozenset(),
) -> tuple[object, tuple[object, ...], list[dict[str, Any]], object]:
    """走输血正式 worker 合同，并继续经过 Binding 与公共聚合投影。"""

    def read(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if source_key in failing_sources:
            raise SourceEvidenceQueryError("freeze-source-query-error")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rule_ids,
        institute_id="freeze-institute",
        patient_id="freeze-patient",
        visit_id="freeze-visit",
        source_schema=None,
        created_at="2026-09-06T10:00:00+08:00",
        row_reader=read,
    )
    execution = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=rule_ids,
        wrapper_rules=[_wrapper(rule_id) for rule_id in rule_ids],
        evidence_payload=None,
        institute_id="freeze-institute",
        patient_id="freeze-patient",
        visit_id="freeze-visit",
        source_schema=None,
        # 冻结用例的专用输血记录均为测试作者写成的实际输注过程。
        llm_client=FrozenTransfusionProtocolClient(default_course_label="record"),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=rule_ids,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    customer_results = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper(rule_id) for rule_id in rule_ids],
        execution_results=[],
        format_evidence=False,
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    return execution, reduced, customer_results, session


@pytest.mark.asyncio
async def test_transfusion_freeze_complete_multiple_events_keeps_customer_contract() -> None:
    """冻结多次输血的记录、规范性与效果评价，并锁定客户证据坐标。"""

    selected = ("LX0609-07-02-01", "LX0609-07-02-02", "LX0609-07-03-01")
    first_record = (
        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
        "2026-06-05 16:10输血结束。输血后复查血红蛋白较前改善。"
        "输血过程中严密观察，生命体征平稳，"
        "未见寒战、发热及其他输血不良反应。"
    )
    second_record = (
        "输血指征：凝血功能异常；开始时间18:00，输注血浆200ml，"
        "2026-06-05 19:00输血结束。输血后复查凝血功能改善。"
        "输注过程中严密观察，过程顺利，"
        "未见皮疹、胸闷及输血反应。"
    )
    execution, reduced, customer_results, session = await _execute_and_aggregate(
        rule_ids=selected,
        rows_by_source={
            # 045/046 按已开立且未取消的输血医嘱触发（用户已确认合同）。
            "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)],
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 6, 5, 14, 20)}
            ],
            "bloodtrans_record": [
                {
                    "document_id": "blood-freeze-1",
                    "record_content": first_record,
                    "record_time": "2026-06-05 16:20:00",
                },
                {
                    "document_id": "blood-freeze-2",
                    "record_content": second_record,
                    "record_time": "2026-06-05 19:10:00",
                },
            ],
            "daily_course_record": [
                {
                    "document_title": "输血后评价记录",
                    "document_id": "daily-freeze-1",
                    "record_content": "2026-06-05 16:10输血结束后复查血红蛋白上升，症状改善。",
                    "record_time": "2026-06-05 16:20:00",
                },
                {"document_title": "输血后评价记录", "document_id": "daily-freeze-2",
                 "record_content": "2026-06-05 19:00输血结束后复查凝血功能改善。", "record_time": "2026-06-05 19:10:00"},
            ],
        },
    )

    assert execution.results == ()
    assert [item.rule_id for item in execution.decisions] == list(selected)
    assert [item.final_state.value for item in reduced] == ["compliant"] * 3
    assert [item.reason_code for item in reduced] == ["requirement_satisfied"] * 3
    assert all(item.criterion_results == () for item in reduced)
    assert all(item.fact_refs for item in reduced)
    assert all(
        item.snapshot_hash == session.snapshot.snapshot_hash for item in execution.decisions
    )

    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-07-02-01"] == {
        "verification_kind": "transfusion_course_record_present",
        # 医嘱触发合同：只声明存在有效输血医嘱，不宣称已实际输血。
        "transfusion_order_present": True,
        "record_count": 2,
        "checked_sources": ["bloodtrans_record", "daily_course_record"],
        "source_document_ids": ["blood-freeze-1", "blood-freeze-2"],
    }
    assert facts["LX0609-07-02-02"]["verification_kind"] == "transfusion_course_record_complete"
    assert facts["LX0609-07-02-02"]["record_count"] == 2
    assert facts["LX0609-07-02-02"]["incomplete_record_count"] == 0
    assert facts["LX0609-07-02-02"]["source_document_ids"] == [
        "blood-freeze-1",
        "blood-freeze-2",
    ]
    assert facts["LX0609-07-03-01"] == {
        "verification_kind": "posttransfusion_evaluation_complete",
        "performed_transfusion_confirmed": True,
        "threshold_hours": 24,
        "checked_sources": ["bloodtrans_record", "daily_course_record"],
        "source_document_refs": [
            {"source_type": "bloodtrans_record", "source_document_id": "blood-freeze-1"},
            {"source_type": "bloodtrans_record", "source_document_id": "blood-freeze-2"},
            {"source_type": "daily_course_record", "source_document_id": "daily-freeze-1"},
            {"source_type": "daily_course_record", "source_document_id": "daily-freeze-2"},
        ],
        "transfusion_end_time": "2026-06-05 19:00:00",
        # 多次独立输血时，评价时间必须与最后一次输血结束关联，不能把前一次
        # 记录的评价时间投影为本次最终输血的评价并产生负间隔。
        "evaluation_time": "2026-06-05 19:10:00",
        "elapsed_hours": 0.17,
    }

    by_rule_id = {item["rule_id"]: item for item in customer_results}
    assert [item["rule_id"] for item in customer_results] == list(selected)
    assert [item["status"] for item in customer_results] == ["compliant"] * 3
    assert [item["reason_code"] for item in customer_results] == [
        "requirement_satisfied"
    ] * 3
    assert all(item["criterion_results"] == [] for item in customer_results)
    assert by_rule_id["LX0609-07-02-01"]["findings"] == "已找到可核对的输血病程记录（2 份）。"
    assert by_rule_id["LX0609-07-02-02"]["findings"] == (
        "输血病程已记录指征、起止时间、血液成分、输注量、过程观察及反应处理。"
    )
    assert by_rule_id["LX0609-07-03-01"]["findings"] == (
        "已在输血结束后 24 小时内完成效果评价，间隔 0.17 小时"
        "（结束时间 2026-06-05 19:00:00；评价时间 2026-06-05 19:10:00）。"
    )
    assert {
        (item["source_type"], item["source_document_id"])
        for item in by_rule_id["LX0609-07-02-01"]["customer_evidence"]
    } == {
        ("bloodtrans_record", "blood-freeze-1"),
        ("bloodtrans_record", "blood-freeze-2"),
        # 触发 045 的输血医嘱同属本条依据。
        ("inpat_nondrug_order", OPEN_TRANSFUSION_ORDER["order_id"]),
    }


@pytest.mark.asyncio
async def test_transfusion_freeze_no_event_and_source_error_keep_distinct_states() -> None:
    """无输血与触发来源技术错误必须保持可区分，且不产生伪造客户证据。"""

    selected = published_rule_ids(41, 49)
    absent_execution, absent_reduced, absent_results, _ = await _execute_and_aggregate(
        rule_ids=selected,
        rows_by_source={},
    )
    assert absent_execution.results == ()
    assert [item.final_state.value for item in absent_reduced] == ["not_applicable"] * 9
    assert [item.reason_code for item in absent_reduced] == [
        "trigger_absent_complete"
    ] * 9
    assert all(item.fact_refs for item in absent_reduced)
    assert [item["status"] for item in absent_results] == ["not_applicable"] * 9
    assert all(item["criterion_results"] == [] for item in absent_results)
    assert all("customer_evidence" not in item for item in absent_results)
    checks = absent_results[-1]["applicability_receipt"]["source_checks"]
    assert not any(item["depended_on"] for item in checks if item["source_key"] in {
        "inpat_registration.discharge_horizon", "evaluation_context.horizon",
    })
    assert any(item["depended_on"] and item["source_key"] == "bloodtrans_record" for item in checks)
    assert absent_results[0]["findings"] == "本次未实施输血，不要求形成输血知情同意书"

    error_execution, error_reduced, error_results, error_session = await _execute_and_aggregate(
        rule_ids=selected,
        rows_by_source={},
        failing_sources=frozenset({"bloodtrans_record"}),
    )
    assert error_execution.results == ()
    # 044–046 按输血医嘱触发，无医嘱时不执行实施核验；其余规则的实施门控查询失败必须是技术错误。
    order_rules = {"LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02"}
    expected_states = [
        ("not_applicable", "trigger_absent_complete")
        if rule_id in order_rules
        else ("technical_error", "source_query_error")
        for rule_id in selected
    ]
    assert [
        (item.final_state.value, item.reason_code) for item in error_reduced
    ] == expected_states
    error_ref = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in error_session.snapshot.observations
        if observation.source_key == "bloodtrans_record"
    )
    # 技术失败仍引用同一次 session 中发生异常的触发来源，供审计定位；不伪造文书坐标。
    error_items = [item for item in error_reduced if item.rule_id not in order_rules]
    assert all(error_ref in item.fact_refs for item in error_items)
    assert [
        (item["status"], item["reason_code"]) for item in error_results
    ] == expected_states
    assert all(item["criterion_results"] == [] for item in error_results)
    assert all("customer_evidence" not in item for item in error_results)
    assert error_results[0]["findings"] == "质控执行未完成"


@pytest.mark.asyncio
async def test_047_missing_evaluation_completion_time_stays_data_gap_through_aggregation() -> None:
    """评价正文缺权威完成时间时，展示事实不得把资料缺口伪装成临床缺项。"""

    execution, reduced, customer_results, _ = await _execute_and_aggregate(
        rule_ids=("LX0609-07-03-01",),
        rows_by_source={
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 6, 5, 14, 20)}
            ],
            "bloodtrans_record": [
                {
                    "document_id": "blood-gap-047",
                    "record_content": (
                        "2026-06-05 16:10输血结束。"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    ),
                }
            ],
            "daily_course_record": [],
        },
    )

    assert execution.results == ()
    assert [item.final_state.value for item in reduced] == ["data_gap"]
    assert [item.reason_code for item in reduced] == ["authoritative_time_missing"]
    assert [item["status"] for item in customer_results] == ["data_gap"]
    assert "customer_display_facts" not in customer_results[0]
    assert "未找到输血结束后 24 小时内的效果评价" not in customer_results[0]["findings"]
