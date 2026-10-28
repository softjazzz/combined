from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from transfusion_order_test_support import (
    OPEN_TRANSFUSION_ORDER, FrozenTransfusionProtocolClient,
)

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.customer_evidence_enrichment import (
    project_selected_document_evidence,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


def _wrapper(rule_id: str) -> dict[str, str]:
    return {"rule_id": rule_id, "rule_name": rule_id}


@pytest.mark.asyncio
async def test_047_known_late_event_survives_unknown_and_publishes_only_defect_evidence():
    from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    rule = "LX0609-07-03-01"
    execution, decision, session = await _execute_typed(rule_id=rule, rows_by_source={
        "bloodtrans_record": [
            {"document_id": "LATE", "record_time": "2026-06-06 10:00:01", "record_content":
             "于2026-06-05 09:00开始输血，于2026-06-05 10:00输血结束；输血后复查血红蛋白较前改善。"},
            {"document_id": "UNKNOWN", "record_content":
             "于2026-06-10 09:00开始输血，于2026-06-10 10:00输血结束；输血后复查血红蛋白较前改善。"},
        ], "daily_course_record": [
            {"document_title": "输血后评价记录", "document_id": "EVAL-LATE", "record_time": "2026-06-06 10:00:01", "record_content": "于2026-06-05 10:00输血结束，输血后复查血红蛋白较前改善。"},
            {"document_title": "输血后评价记录", "document_id": "EVAL-UNKNOWN", "record_content": "于2026-06-10 10:00输血结束，输血后复查血红蛋白较前改善。"},
        ], "senior_course_record": [],
        "mr_bloodtrans": _trigger(),
    })
    assert decision.final_state.value == "non_compliant"
    assert ("bloodtrans_record", "LATE") in _coordinates(decision=decision, session=session)
    assert ("bloodtrans_record", "UNKNOWN") not in _coordinates(decision=decision, session=session)
    results = aggregate_luxian_0609_results(wrapper_rules=[_wrapper(rule)], reduced_decisions=(decision,),
        execution_results=[], format_evidence=False, customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials})
    assert results[0]["status"] == "non_compliant"
    envelope_item_from_rule_result(results[0], hmac_key="synthetic-confirmed-late-save-validation")


async def _execute_typed(
    *,
    rule_id: str,
    rows_by_source: dict[str, list[dict[str, Any]]],
    source_limit: int = 50,
    add_orders: bool = True,
    horizon_date: str | None = None,
) -> tuple[object, object, object]:
    """走输血 native→Binding→公共逐行证据投影所依赖的同一 Evidence Session。"""

    # 医嘱是独立冻结输入；模型替身只证明协议接线，不声称模型语义准确率。
    rows_by_source = dict(rows_by_source)
    governed = rule_id in {"LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02"}
    if governed and add_orders:
        rows_by_source["inpat_nondrug_order"] = [dict(OPEN_TRANSFUSION_ORDER, order_id="EVIDENCE-ORDER-1")]
        rows_by_source["inpat_drug_order"] = [dict(OPEN_TRANSFUSION_ORDER, order_id="EVIDENCE-ORDER-2")]
    client = FrozenTransfusionProtocolClient(course_labels={
        str(row["record_content"]): "record"
        for row in rows_by_source.get("bloodtrans_record", [])
    })

    def read(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=source_limit,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="selected-evidence-institute",
        patient_id="selected-evidence-patient",
        visit_id="selected-evidence-visit",
        source_schema=None,
        created_at="2026-09-06T10:00:00+08:00",
        evaluation_as_of_date=horizon_date,
        evaluation_horizon_policy="frozen_task_date" if horizon_date else "disabled",
        row_reader=read,
    )
    execution = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=(rule_id,),
        wrapper_rules=[_wrapper(rule_id)],
        evidence_payload=None,
        institute_id="selected-evidence-institute",
        patient_id="selected-evidence-patient",
        visit_id="selected-evidence-visit",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=(rule_id,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert len(reduced) == 1
    return execution, reduced[0], session


def _coordinates(*, decision: object, session: object) -> set[tuple[str, str]] | None:
    projected = project_selected_document_evidence(
        decision=decision,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    if projected is None:
        return None
    return {
        (str(item["source_type"]), str(item["source_document_id"]))
        for item in projected
    }


def _transfusion_record(
    *,
    document_id: str,
    content: str,
    record_time: str = "2026-06-05 16:20:00",
) -> dict[str, str]:
    return {
        "document_id": document_id,
        "record_content": content,
        "record_time": record_time,
    }


def _complete_course(*, end_time: str = "2026-06-05 16:10") -> str:
    return (
        f"输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，{end_time}输血结束。"
        "输血过程中严密观察，生命体征平稳，未见寒战、发热及其他输血不良反应。输血后复查血红蛋白改善。"
    )


def _trigger() -> list[dict[str, datetime]]:
    return [{"transfution_datetime": datetime(2026, 6, 5, 14, 20)}]


@pytest.mark.asyncio
@pytest.mark.parametrize("second_pre", [False, True])
async def test_044_each_event_association_survives_typed_binding(second_pre: bool) -> None:
    """逐次关联真正进入正式Evidence Session；未配齐时不发布整例合规。"""
    records = [_transfusion_record(document_id=f"EVENT-{day}",
        content=f"于2026-06-{day} 14:20开始输入红细胞，2026-06-{day} 16:10输血结束。",
        record_time=f"2026-06-{day} 16:20:00") for day in ("05", "06")]
    pre = [{"document_id": f"PRE-{day}", "document_title": "输血前评估",
            "record_time": f"2026-06-{day} 10:00:00",
            "record_content": "输血前评估：有输血指征，血红蛋白65g/L，已告知输血风险。"}
           for day in (("05", "06") if second_pre else ("05",))]
    execution, decision, session = await _execute_typed(rule_id="LX0609-07-01-02", rows_by_source={
        "bloodtrans_record": records, "daily_course_record": pre})
    assert decision.final_state.value == ("compliant" if second_pre else "non_compliant")
    if second_pre:
        refs = _coordinates(decision=decision, session=session)
        assert refs is not None and {("daily_course_record", "PRE-05"), ("daily_course_record", "PRE-06"),
                                     ("bloodtrans_record", "EVENT-05"), ("bloodtrans_record", "EVENT-06")} <= refs
    else:
        assert decision.reason_code == "requirement_violated"
        refs = _coordinates(decision=decision, session=session)
        assert refs is not None and ("bloodtrans_record", "EVENT-06") in refs
        assert ("bloodtrans_record", "EVENT-05") not in refs
        from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
        from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result
        results = aggregate_luxian_0609_results(wrapper_rules=[_wrapper("LX0609-07-01-02")],
            reduced_decisions=(decision,), execution_results=[], format_evidence=False,
            customer_display_facts=execution.customer_display_facts,
            audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials})
        assert results[0]["status"] == "non_compliant"
        assert results[0]["customer_display_facts"]["requirement"] == "pretransfusion_assessment"
        envelope_item_from_rule_result(results[0], hmac_key="synthetic-missing-pre-save-validation")


@pytest.mark.asyncio
async def test_045_selects_every_checked_blood_record_not_irrelevant_daily_record() -> None:
    """045 的逐条判定只核对专用输血记录，日常病程不得因旧来源推断混入。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-02-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-045-1", content=_complete_course()),
                _transfusion_record(
                    document_id="BLOOD-045-2",
                    content=_complete_course(end_time="2026-06-05 19:00"),
                    record_time="2026-06-05 19:10:00",
                ),
            ],
            "daily_course_record": [
                {
                    "document_id": "DAILY-045-NOISE",
                    "record_content": "护理记录：患者安静休息。",
                    "record_time": "2026-06-05 20:00:00",
                }
            ],
        },
    )

    assert decision.final_state.value == "compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("bloodtrans_record", "BLOOD-045-1"),
        ("bloodtrans_record", "BLOOD-045-2"),
        ("inpat_nondrug_order", "EVIDENCE-ORDER-1"),
        ("inpat_drug_order", "EVIDENCE-ORDER-2"),
    }


@pytest.mark.asyncio
async def test_046_selects_all_complete_records_or_only_incomplete_records() -> None:
    """046 合规逐笔核对全部记录；缺项结论只定位实际缺项记录。"""

    complete_execution, complete, complete_session = await _execute_typed(
        rule_id="LX0609-07-02-02",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-046-OK-1", content=_complete_course()),
                _transfusion_record(
                    document_id="BLOOD-046-OK-2",
                    content=_complete_course(end_time="2026-06-05 19:00"),
                    record_time="2026-06-05 19:10:00",
                ),
            ],
            "daily_course_record": [
                {
                    "document_id": "DAILY-046-NOISE",
                    "record_content": "护理记录：输血后观察。",
                }
            ],
        },
    )
    assert complete_execution.llm_call_count == 2
    assert complete.final_state.value == "compliant"
    assert _coordinates(decision=complete, session=complete_session) == {
        ("bloodtrans_record", "BLOOD-046-OK-1"),
        ("bloodtrans_record", "BLOOD-046-OK-2"),
        ("inpat_nondrug_order", "EVIDENCE-ORDER-1"),
        ("inpat_drug_order", "EVIDENCE-ORDER-2"),
    }

    incomplete_content = (
        "输血目的：纠正贫血；开始时间18:00，输注去白悬浮红细胞，"
        "2026-06-05 19:00输血结束。输血过程中严密观察，未见不良反应。"
    )
    _incomplete_execution, incomplete, incomplete_session = await _execute_typed(
        rule_id="LX0609-07-02-02",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-046-OK", content=_complete_course()),
                _transfusion_record(
                    document_id="BLOOD-046-MISSING-DOSE",
                    content=incomplete_content,
                    record_time="2026-06-05 19:10:00",
                ),
            ],
            "daily_course_record": [],
        },
    )
    assert incomplete.final_state.value == "non_compliant"
    assert _coordinates(decision=incomplete, session=incomplete_session) == {
        ("bloodtrans_record", "BLOOD-046-MISSING-DOSE"),
        ("inpat_nondrug_order", "EVIDENCE-ORDER-1"),
        ("inpat_drug_order", "EVIDENCE-ORDER-2"),
    }


@pytest.mark.asyncio
async def test_045_selects_every_material_row_for_a_duplicated_business_document_id() -> None:
    """公共投影要求同一业务 ID 的重复材料行被完整选择，不能只选其中一行。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-02-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-045-DUP", content=_complete_course()),
                _transfusion_record(
                    document_id="BLOOD-045-DUP",
                    content=_complete_course() + "补充：输注顺利。",
                ),
            ],
            "daily_course_record": [],
        },
    )

    expected_refs = {
        reference
        for reference, row in session.materials.document_rows(
            "bloodtrans_record", snapshot=session.snapshot
        )
        if row.get("document_id") == "BLOOD-045-DUP"
    }
    assert len(expected_refs) == 2
    for source in ("inpat_nondrug_order", "inpat_drug_order"):
        expected_refs.update(reference for reference, _row in session.materials.document_rows(
            source, snapshot=session.snapshot
        ))
    assert set(decision.fact_refs).intersection(session.snapshot.document_refs) == expected_refs
    assert _coordinates(decision=decision, session=session) == {
        ("bloodtrans_record", "BLOOD-045-DUP"),
        ("inpat_nondrug_order", "EVIDENCE-ORDER-1"),
        ("inpat_drug_order", "EVIDENCE-ORDER-2"),
    }


@pytest.mark.asyncio
async def test_044_structured_application_path_selects_the_actual_application_document() -> None:
    """044 的结构化申请单路径必须带出参与判断的申请单，而不是来源级猜测。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-01-02",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "blood_application": [
                {
                    "application_id": "APPLICATION-044-SELECTED",
                    "document_id": "APPLICATION-044-DOCUMENT",
                    "request_datetime": "2026-06-05 09:00:00",
                    "reason_for_blood": "纠正贫血",
                    "hemoglobin": "65",
                }
            ],
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-044-EVENT", content=_complete_course())
            ],
            "daily_course_record": [
                {
                    "document_id": "DAILY-044-NOISE",
                    "record_content": "护理记录：病情平稳。",
                }
            ],
        },
    )

    assert decision.final_state.value == "compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("blood_application", "APPLICATION-044-DOCUMENT"),
        ("bloodtrans_record", "BLOOD-044-EVENT"),
        ("inpat_nondrug_order", "EVIDENCE-ORDER-1"),
        ("inpat_drug_order", "EVIDENCE-ORDER-2"),
    }


@pytest.mark.asyncio
async def test_047_selects_daily_evaluation_document_when_daily_record_supplies_evaluation() -> None:
    """047 日常病程提供评价时，结束输血文书和实际评价文书都必须可定位。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-03-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(
                    document_id="BLOOD-047-END",
                    content="2026-06-05 16:10输血结束。输注过程顺利。",
                )
            ],
            "daily_course_record": [
                {"document_title": "输血后评价记录",
                    "document_id": "DAILY-047-EVALUATION",
                    "record_content": "输血后复查血红蛋白改善，未见输血不良反应。",
                    "record_time": "2026-06-05 20:00:00",
                },
                {"document_title": "输血后评价记录",
                    "document_id": "DAILY-047-NOISE",
                    "record_content": "患者夜间睡眠可。",
                    "record_time": "2026-06-05 21:00:00",
                },
            ],
        },
    )

    assert decision.final_state.value == "compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("bloodtrans_record", "BLOOD-047-END"),
        ("daily_course_record", "DAILY-047-EVALUATION"),
    }


@pytest.mark.asyncio
async def test_047_inline_effect_does_not_satisfy_dedicated_evaluation_requirement() -> None:
    """输血记录内写有评价，仍须另有专门后评价；不借用普通病程。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-03-01",
        horizon_date="2026-09-06",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(
                    document_id="BLOOD-047-EVALUATION",
                    content=(
                        "2026-06-05 16:10输血结束。输血后复查血红蛋白改善，"
                        "未见输血不良反应。"
                    ),
                )
            ],
            "daily_course_record": [
                {"document_title": "日常病程记录",
                    "document_id": "DAILY-047-NOISE",
                    "record_content": "护理记录：病情平稳。",
                    "record_time": "2026-06-05 20:00:00",
                }
            ],
        },
    )

    assert decision.final_state.value == "non_compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("bloodtrans_record", "BLOOD-047-EVALUATION"),
    }


@pytest.mark.asyncio
async def test_045_stale_selected_document_id_becomes_technical_error_not_data_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """执行器声明的 source+ID 未绑定到同一快照材料时，必须技术失败。"""

    original = transfusion._programmatic_transfusion_display_facts

    def stale_selected_id(**kwargs: object):
        facts = original(**kwargs)
        if kwargs.get("rule_id") != "LX0609-07-02-01" or not isinstance(facts, dict):
            return facts
        stale = dict(facts)
        stale["source_document_ids"] = ["BLOOD-045-NOT-IN-SNAPSHOT"]
        return stale

    monkeypatch.setattr(
        transfusion,
        "_programmatic_transfusion_display_facts",
        stale_selected_id,
    )
    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-02-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-045-REAL", content=_complete_course())
            ],
            "daily_course_record": [],
        },
    )

    assert decision.final_state.value == "technical_error"
    assert decision.reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
async def test_045_too_many_selected_documents_becomes_one_rule_technical_error() -> None:
    """RuleDecision 的128条引用上限不得靠截断规避或中断整个规则族。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-02-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(
                    document_id=f"BLOOD-045-MANY-{index}",
                    content=_complete_course(),
                )
                for index in range(129)
            ],
            "daily_course_record": [],
        },
        source_limit=129,
    )

    assert decision.final_state.value == "technical_error"
    assert decision.reason_code == "executor_exception"
    assert _execution.customer_display_facts == ()
    assert _coordinates(decision=decision, session=session) is None


@pytest.mark.asyncio
async def test_044_nonstructured_daily_assessment_selects_matched_daily_and_blood_anchor() -> None:
    """非结构化 044 由日常病程命中评估时，仅选择命中文书及输血锚点。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-01-02",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-044-ANCHOR", content="输血过程顺利。")
            ],
            "blood_application": [],
            "daily_course_record": [
                {
                    "document_id": "DAILY-044-MATCHED",
                    "record_time": "2026-06-05 09:00:00",
                    "record_content": "输血前评估：有输血指征，血红蛋白65g/L，已告知输血风险。",
                },
                {
                    "document_id": "DAILY-044-NOISE",
                    "record_content": "患者一般情况可。",
                },
            ],
        },
    )

    assert decision.final_state.value == "compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("bloodtrans_record", "BLOOD-044-ANCHOR"),
        ("daily_course_record", "DAILY-044-MATCHED"),
        ("inpat_nondrug_order", "EVIDENCE-ORDER-1"),
        ("inpat_drug_order", "EVIDENCE-ORDER-2"),
    }


@pytest.mark.asyncio
async def test_044_complete_text_without_document_id_keeps_clinical_status() -> None:
    """不可定位的命中文本不能反向改变 044 的既有临床判定。"""

    _execution, decision, _session = await _execute_typed(
        rule_id="LX0609-07-01-02",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-044-ANCHOR", content="输血过程顺利。")
            ],
            "blood_application": [],
            "daily_course_record": [
                {
                    "record_time": "2026-06-05 09:00:00",
                    "record_content": "输血前评估：有输血指征，血红蛋白65g/L，已告知输血风险。"
                }
            ],
        },
    )

    assert decision.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_041_selects_transfusion_consent_not_unrelated_surgical_consent() -> None:
    """041 已找到输血同意书时，证据只能指向实际参与核对的输血同意书。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-11-03-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(document_id="BLOOD-041-ANCHOR", content="输血过程顺利。")
            ],
            "consent_form": [
                {
                    "document_id": "CONSENT-041-TRANSFUSION",
                    "consent_type": "blood_transfusion",
                    "document_title": "输血治疗知情同意书",
                },
                {
                    "document_id": "CONSENT-041-SURGERY-NOISE",
                    "consent_type": "surgery",
                    "document_title": "手术知情同意书",
                },
            ],
        },
    )

    assert decision.final_state.value == "compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("consent_form", "CONSENT-041-TRANSFUSION"),
    }


@pytest.mark.asyncio
async def test_047_selects_earliest_qualified_daily_evaluation_only() -> None:
    """047 多份合格日常评价按既有最早时间规则选择对应文书，不能全量投影。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-03-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(
                    document_id="BLOOD-047-END-EARLIEST",
                    content="2026-06-05 16:10输血结束。输注过程顺利。",
                )
            ],
            "daily_course_record": [
                {"document_title": "输血后评价记录",
                    "document_id": "DAILY-047-FIRST",
                    "record_content": "输血后复查血红蛋白改善，未见输血不良反应。",
                    "record_time": "2026-06-05 18:00:00",
                },
                {"document_title": "输血后评价记录",
                    "document_id": "DAILY-047-LATER",
                    "record_content": "输血后复查血红蛋白改善，未见输血不良反应。",
                    "record_time": "2026-06-05 20:00:00",
                },
            ],
        },
    )

    assert decision.final_state.value == "compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("bloodtrans_record", "BLOOD-047-END-EARLIEST"),
        ("daily_course_record", "DAILY-047-FIRST"),
    }


@pytest.mark.asyncio
async def test_044_keeps_two_source_coordinates_when_application_and_blood_share_id() -> None:
    """相同业务 ID 不等于同一文书：044 必须保留申请与输血两种来源坐标。"""

    _execution, decision, session = await _execute_typed(
        rule_id="LX0609-07-01-02",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "blood_application": [
                {
                    "application_id": "SHARED-044-ID",
                    "request_datetime": "2026-06-05 09:00:00",
                    "reason_for_blood": "纠正贫血",
                    "hemoglobin": "65",
                }
            ],
            "bloodtrans_record": [
                _transfusion_record(document_id="SHARED-044-ID", content=_complete_course())
            ],
            "daily_course_record": [],
        },
    )

    assert decision.final_state.value == "compliant"
    assert _coordinates(decision=decision, session=session) == {
        ("blood_application", "SHARED-044-ID"),
        ("bloodtrans_record", "SHARED-044-ID"),
        ("inpat_nondrug_order", "EVIDENCE-ORDER-1"),
        ("inpat_drug_order", "EVIDENCE-ORDER-2"),
    }


@pytest.mark.asyncio
async def test_045_whitespace_normalized_stale_document_id_is_technical_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """声明文书 ID 的尾部控制字符必须直接拒绝，不能被 strip 后误绑。"""

    original = transfusion._programmatic_transfusion_display_facts

    def stale_selected_id(**kwargs: object):
        facts = original(**kwargs)
        if kwargs.get("rule_id") != "LX0609-07-02-01" or not isinstance(facts, dict):
            return facts
        stale = dict(facts)
        stale["source_document_ids"] = ["BLOOD-045-REAL\\n"]
        return stale

    monkeypatch.setattr(
        transfusion,
        "_programmatic_transfusion_display_facts",
        stale_selected_id,
    )
    _execution, decision, _session = await _execute_typed(
        rule_id="LX0609-07-02-01",
        rows_by_source={
            "mr_bloodtrans": _trigger(),
            "bloodtrans_record": [
                _transfusion_record(
                    document_id="BLOOD-045-REAL", content=_complete_course()
                )
            ],
            "daily_course_record": [],
        },
    )

    assert decision.final_state.value == "technical_error"
    assert decision.reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02"])
async def test_order_contract_without_order_does_not_select_performed_record(rule_id: str) -> None:
    """v2医嘱触发合同：完整输血文书与结构化执行信息也不能代替开立医嘱。"""
    execution, decision, session = await _execute_typed(
        rule_id=rule_id,
        rows_by_source={"mr_bloodtrans": _trigger(), "bloodtrans_record": [
            _transfusion_record(document_id="NO-ORDER-COMPLETE", content=_complete_course())
        ]},
        add_orders=False,
    )
    assert decision.final_state.value == "not_applicable"
    assert execution.llm_call_count == 0
    assert not _coordinates(decision=decision, session=session)
