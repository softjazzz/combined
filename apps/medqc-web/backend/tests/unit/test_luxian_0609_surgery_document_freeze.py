"""Freeze the current surgery-document family through the real native chain.

These tests intentionally record the current public behaviour before the family is
moved out of ``luxian_0609_result_aggregator``.  They are not a specification for
fixing known reason-code semantics; see the matching acceptance note.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Mapping, Sequence

import pytest
from luxian_0609_anesthesia_test_facts import ExplicitAnesthesiaFactClient

from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_surgery_document_execution import (
    SURGERY_DOCUMENT_RULE_IDS,
    execute_luxian_0609_native_surgery_document_rules,
)
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
    safe_luxian_0609_customer_display_facts,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError


_RULE_NAMES = {
    "LX0609-04-01-01": "术前小结",
    "LX0609-11-02-01": "麻醉知情同意书存在",
    "LX0609-11-02-02": "麻醉知情同意书填写完整",
    "LX0609-04-04-01": "麻醉术前及术后访视存在",
    "LX0609-04-04-02": "麻醉访视填写完整",
    "LX0609-04-04-03": "麻醉记录单存在",
    "LX0609-04-01-02": "术前讨论及术者参加",
}


class _NoLlmClient:
    async def generate(self, **_kwargs: Any) -> str:
        raise AssertionError("surgery_document typed 主链不得调用 LLM")


def _wrapper(rule_id: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "name": _RULE_NAMES[rule_id],
        "description": _RULE_NAMES[rule_id],
        "severity": "major",
        "category": "surgery_anesthesia",
        "applicable": True,
    }


def _rows(*items: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(items)


def _surgery(
    document_id: str = "surgery-1",
    *,
    begin: datetime = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
    surgeon: str = "王医生",
    anesthesia_method: str = "全身麻醉",
) -> Mapping[str, Any]:
    return {
        "document_id": document_id,
        "surgery_name": "腹腔镜阑尾切除术",
        "surgery_begin_time": begin,
        "surgery_end_time": begin.replace(hour=9),
        "surgeon_name": surgeon,
        "surgeon": surgeon,
        "anesthesia_method": anesthesia_method,
        "surgical_level": "三级",
    }


def _mr_surgery(surgery_id: str = "mr-surgery-1") -> Mapping[str, Any]:
    """MR权威时间使用医院naive墙钟；保留原UTC08/09的同一绝对时刻。"""
    row = dict(_surgery(surgery_id))
    begin = row.pop("surgery_begin_time")
    end = row.pop("surgery_end_time")
    hospital_timezone = ZoneInfo("Asia/Shanghai")
    row.update(
        surgery_id=surgery_id,
        surgery_begin_datetime=begin.astimezone(hospital_timezone).replace(tzinfo=None),
        surgery_end_datetime=end.astimezone(hospital_timezone).replace(tzinfo=None),
    )
    return row


def _anesthesia_record(document_id: str = "anesthesia-1") -> Mapping[str, Any]:
    return {
        "document_id": document_id,
        "anesthesia_method": "全身麻醉",
        "record_content": "麻醉诱导、维持及复苏记录完整",
    }


def _consent(*, complete: bool) -> Mapping[str, Any]:
    row: dict[str, Any] = {
        "document_id": "consent-1",
        "document_title": "麻醉知情同意书",
        "record_content": "已说明麻醉方式、风险和替代方案",
        "physician_sign": "麻醉医生",
        "physician_sign_datetime": datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc),
    }
    if complete:
        row.update(
            {
                "patient_sign": "患者",
                "patient_sign_datetime": datetime(2026, 9, 1, 7, 10, tzinfo=timezone.utc),
            }
        )
    return row


def _visit(document_id: str, *, post: bool) -> Mapping[str, Any]:
    return {
        "document_id": document_id,
        "document_title": "麻醉术后访视记录" if post else "麻醉术前访视记录",
        "record_content": (
            "神志清楚，呼吸循环稳定，无恶心呕吐及麻醉并发症"
            if post
            else "ASA II级，气道评估正常，禁食已确认，无麻醉史，已评估麻醉风险"
        ),
        "anesthetist_sign": "麻醉医生",
        "record_time": datetime(2026, 9, 1, 10 if post else 7, 0, tzinfo=timezone.utc),
    }


def _discussion(*, participants: str) -> Mapping[str, Any]:
    return {
        "document_id": "discussion-1",
        "document_title": "术前讨论记录",
        "discussion_time": datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc),
        "discuss_staff": participants,
        "record_content": "讨论手术指征、方案、风险及应对措施",
    }


def _session(
    rule_id: str,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    error_sources: frozenset[str] = frozenset(),
):
    def _reader(*, source_key: str, **_kwargs: Any) -> SnapshotSourceRows:
        if source_key in error_sources:
            raise SourceEvidenceQueryError()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=tuple(rows_by_source.get(source_key, ())),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="freeze-institute",
        patient_id="freeze-patient",
        visit_id="freeze-visit",
        source_schema=None,
        created_at="2026-09-07T08:00:00+08:00",
        row_reader=_reader,
        additional_source_keys=tuple(rows_by_source),
    )


async def _run_chain(
    rule_id: str,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    error_sources: frozenset[str] = frozenset(),
    anesthesia_facts: str | None = None,
) -> tuple[Any, Any, Any, Any]:
    assert anesthesia_facts is None or rule_id == "LX0609-04-04-02"
    session = _session(rule_id, rows_by_source, error_sources=error_sources)
    execution = await execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule_id,),
        wrapper_rules=(_wrapper(rule_id),),
        evidence_payload=None,
        llm_client=_NoLlmClient() if anesthesia_facts is None else ExplicitAnesthesiaFactClient(anesthesia_facts),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=(rule_id,),
    )
    assert execution.results == ()
    assert len(execution.decisions) == 1

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert len(reduced) == 1
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=(_wrapper(rule_id),),
        execution_results=(),
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    assert len(aggregated) == 1
    return session, execution, reduced[0], aggregated[0]


def _evidence_coordinates(result: Mapping[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(item.get("source_type")), str(item.get("source_document_id")))
        for item in result.get("customer_evidence") or ()
    }


def _fact_ref_coordinates(session: Any, fact_refs: Sequence[str]) -> tuple[tuple[Any, ...], ...]:
    """将 Fact / source observation / material ref 还原为可读且精确的坐标。

    ``fact_refs`` 本身是内容寻址引用，冻结测试不把摘要常量写进用例；但不能
    因此退化为只核对来源类型。本函数保留每个引用实际代表的事实类型、查询状态、
    来源和材料文书 ID，兼顾稳定性与证据选择精度。
    """

    coordinates: dict[str, tuple[Any, ...]] = {
        fact.fact_id: (
            "fact",
            fact.fact_type,
            fact.source_key,
            fact.assertion.value,
            fact.event_status.value,
        )
        for fact in session.snapshot.facts
    }
    coordinates.update(
        {
            str(observation.snapshot_ref).removeprefix("sha256:"): (
                "observation",
                observation.source_key,
                observation.query_state.value,
                observation.record_count,
            )
            for observation in session.snapshot.observations
        }
    )
    for source_key in session.materials.safe_summary()["sources"]:
        for document_ref, row in session.materials.document_rows(
            source_key,
            snapshot=session.snapshot,
        ):
            document_id = next(
                (
                    str(row.get(field) or "").strip()
                    for field in ("order_id", "document_id", "id")
                    if str(row.get(field) or "").strip()
                ),
                "",
            )
            coordinates[document_ref] = ("material", source_key, document_id)
    return tuple(coordinates.get(str(ref), ("unknown", str(ref))) for ref in fact_refs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "rule_id",
        "rows_by_source",
        "status",
        "reason_code",
        "display_facts",
        "fact_ref_coordinates",
        "evidence",
        "findings",
    ),
    (
        (
            "LX0609-04-01-01",
            {
                "surgery_record": _rows(_surgery()),
                "mr_surgery": _rows(_mr_surgery("mr-surgery-1")),
                "presurg_summary": _rows(
                    {
                        "document_id": "summary-1",
                        "document_title": "术前小结",
                        "record_content": "拟行腹腔镜阑尾切除术",
                    }
                ),
            },
            "compliant",
            "requirement_satisfied",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "presurg_summary",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
            (
                ("material", "presurg_summary", "summary-1"),
                ("fact", "current_visit_surgery_confirmed", "surgery_record", "affirmed", "performed"),
                ("material", "surgery_record", "surgery-1"),
            ),
            {
                ("presurg_summary", "summary-1"),
                ("surgery_record", "surgery-1"),
            },
            "已确认本次实施手术具备术前小结。",
        ),
        (
            "LX0609-11-02-01",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "mr_surgery": _rows(_surgery("mr-surgery-1")),
            },
            "non_compliant",
            "required_document_missing",
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
            },
            (("material", "mr_surgery", "mr-surgery-1"),),
            {("mr_surgery", "mr-surgery-1")},
            "已实施麻醉，但未找到对应的麻醉知情同意书",
        ),
        (
            "LX0609-11-02-02",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "mr_surgery": _rows(_surgery("mr-surgery-1")),
                "consent_form": _rows(_consent(complete=False)),
            },
            "non_compliant",
            "requirement_violated",
            {
                "failure_kind": "anesthesia_consent_incomplete",
                "performed_anesthesia_confirmed": True,
                "missing_fields": ["patient_signature", "patient_signature_time"],
            },
            (
                ("material", "mr_surgery", "mr-surgery-1"),
                ("material", "consent_form", "consent-1"),
            ),
            {
                ("consent_form", "consent-1"),
                ("mr_surgery", "mr-surgery-1"),
            },
            "发现质控问题",
        ),
        (
            "LX0609-04-04-01",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "mr_surgery": _rows(_surgery("mr-surgery-1")),
                "preane_surveil_record": _rows(_visit("pre-visit-1", post=False)),
            },
            "non_compliant",
            "required_document_missing",
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": ["postane_surveil_record"],
            },
            (
                ("material", "mr_surgery", "mr-surgery-1"),
                ("material", "preane_surveil_record", "pre-visit-1"),
            ),
            {
                ("mr_surgery", "mr-surgery-1"),
                ("preane_surveil_record", "pre-visit-1"),
            },
            "已实施麻醉，但缺少麻醉术前或术后访视记录",
        ),
        (
            "LX0609-04-04-02",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "mr_surgery": _rows(_mr_surgery("mr-surgery-1")),
                "preane_surveil_record": _rows(_visit("pre-visit-1", post=False)),
                "postane_surveil_record": _rows(_visit("post-visit-1", post=True)),
            },
            "compliant",
            "requirement_satisfied",
            {
                "verification_kind": "anesthesia_visits_complete",
                "performed_anesthesia_confirmed": True,
                "checked_sources": ["preane_surveil_record", "postane_surveil_record"],
                "checked_fields_by_visit": {
                    "preanesthesia_visit": [
                        "general_condition",
                        "brief_history",
                        "relevant_examinations",
                        "planned_procedure_and_anesthesia",
                        "anesthesia_indication",
                        "precautions",
                        "preoperative_orders",
                        "anesthetist_signature",
                        "record_time",
                    ],
                    "postanesthesia_visit": [
                        "visit_within_48h",
                        "recovery_status",
                        "consciousness_status",
                        "extubation_status",
                        "postoperative_orders",
                        "special_situations",
                        "anesthetist_signature",
                        "record_time",
                    ],
                },
            },
            (
                # 内容寻址引用按摘要排序；病案首页手术行带权威结束时间后摘要随之变化。
                ("material", "preane_surveil_record", "pre-visit-1"),
                ("material", "mr_surgery", "mr-surgery-1"),
                ("material", "postane_surveil_record", "post-visit-1"),
            ),
            {
                ("mr_surgery", "mr-surgery-1"),
                ("postane_surveil_record", "post-visit-1"),
                ("preane_surveil_record", "pre-visit-1"),
            },
            (
                "麻醉术前访视已核对：一般情况、简要病史、相关检查、拟行手术和麻醉方式、适应证、注意事项、"
                "术前医嘱、麻醉医师签名、记录时间；麻醉术后访视已核对：术后48小时内访视、恢复情况、"
                "清醒情况、拔管情况、术后医嘱、特殊情况、麻醉医师签名、记录时间。"
            ),
        ),
        (
            "LX0609-04-04-03",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "mr_surgery": _rows(_surgery("mr-surgery-1")),
            },
            "compliant",
            "requirement_satisfied",
            {
                "verification_kind": "anesthesia_record_present",
                "performed_anesthesia_confirmed": True,
                "checked_sources": ["anesthesia_record"],
            },
            (("material", "anesthesia_record", "anesthesia-1"),),
            {("anesthesia_record", "anesthesia-1")},
            "已确认本次麻醉具备麻醉记录单。",
        ),
        (
            "LX0609-04-01-02",
            {
                "surgery_record": _rows(
                    {
                        **_surgery("surgery-1"),
                        "surgery_begin_time": "2026-09-01 08:00:00+08",
                        "record_content": "本次手术不属于紧急抢救手术。",
                    },
                    {
                        **_surgery(
                            "surgery-2",
                            begin=datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc),
                        ),
                        "surgery_begin_time": "2026-09-02 08:00:00+08",
                        "record_content": "本次手术不属于紧急抢救手术。",
                    },
                ),
            },
            "non_compliant",
            "required_document_missing",
            {
                "failure_kind": "preop_discussion_missing",
                "performed_surgery_confirmed": True,
                "emergency_rescue_exception_absent": True,
                "checked_sources": ["presurg_discussion"],
            },
            (
                ("fact", "current_visit_emergency_rescue_surgery", "surgery_record", "negated", "unknown"),
                ("material", "surgery_record", "surgery-1"),
                ("fact", "current_visit_surgery_confirmed", "surgery_record", "affirmed", "performed"),
                ("material", "surgery_record", "surgery-2"),
            ),
            {("surgery_record", "surgery-1"), ("surgery_record", "surgery-2")},
            "发现质控问题",
        ),
    ),
)
async def test_surgery_document_family_freezes_native_binding_aggregate_outputs(
    rule_id: str,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    status: str,
    reason_code: str,
    display_facts: Mapping[str, Any],
    fact_ref_coordinates: tuple[tuple[Any, ...], ...],
    evidence: set[tuple[str, str]],
    findings: str,
) -> None:
    session, execution, reduced, result = await _run_chain(rule_id, rows_by_source, anesthesia_facts="freeze_complete" if rule_id == "LX0609-04-04-02" else None)

    decision = execution.decisions[0]
    assert decision.reason_code == reason_code
    assert rule_id in dict(execution.customer_display_facts)
    assert reduced.final_state.value == status
    assert reduced.reason_code == reason_code
    assert reduced.fact_refs == decision.fact_refs
    assert result["status"] == status
    assert result["reason_code"] == reason_code
    assert result["customer_display_facts"] == display_facts
    assert result["findings"] == findings
    assert _evidence_coordinates(result) == evidence
    assert _fact_ref_coordinates(session, decision.fact_refs) == fact_ref_coordinates

    if rule_id == "LX0609-04-04-02":
        assert execution.llm_call_count == 1
        assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (10, 5, 15)
    else:
        assert execution.llm_call_count == 0
        assert execution.prompt_tokens == 0
        assert execution.completion_tokens == 0
        assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_lx029_order_only_trigger_freezes_mutually_exclusive_facts_and_coordinates() -> None:
    """029 的手术医嘱触发不得伪称手术已经实施。"""

    session, execution, reduced, result = await _run_chain(
        "LX0609-04-01-01",
        {
            "inpat_nondrug_order": _rows(
                {
                    "order_id": "operation-order-1",
                    "order_type": "手术",
                    "order_status": "新开",
                    "order_name": "腹腔镜阑尾切除术",
                }
            ),
            "presurg_summary": _rows(
                {
                    "document_id": "summary-order-1",
                    "document_title": "术前小结",
                    "record_content": "拟行腹腔镜阑尾切除术",
                }
            ),
        },
    )

    decision = execution.decisions[0]
    expected_facts = {
        "verification_kind": "surgery_document_present",
        "target_document": "presurg_summary",
        "surgery_trigger_kind": "surgery_order",
        "surgery_order_confirmed": True,
    }
    assert decision.reason_code == "requirement_satisfied"
    assert (reduced.final_state.value, reduced.reason_code) == (
        "compliant",
        "requirement_satisfied",
    )
    assert result["customer_display_facts"] == expected_facts
    assert "performed_surgery_confirmed" not in expected_facts
    assert result["findings"] == "已发现手术医嘱，术前小结已完整记录。"
    assert _fact_ref_coordinates(session, decision.fact_refs) == (
        (
            "fact",
            "current_visit_surgery_order_confirmed",
            "inpat_nondrug_order",
            "affirmed",
            "ordered",
        ),
        ("material", "inpat_nondrug_order", "operation-order-1"),
        ("material", "presurg_summary", "summary-order-1"),
    )
    assert _evidence_coordinates(result) == {
        ("inpat_nondrug_order", "operation-order-1"),
        ("presurg_summary", "summary-order-1"),
    }
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_surgery_document_family_freezes_not_applicable_data_gap_and_technical_error() -> None:
    cases = (
        (
            "LX0609-04-01-01",
            {},
            frozenset(),
            "not_applicable",
            "performed_event_absent",
        ),
        (
            "LX0609-04-01-01",
            {
                "surgery_record": _rows(
                    _surgery("surgery-1"),
                    _surgery(
                        "surgery-2",
                        begin=datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc),
                    ),
                ),
                "presurg_summary": _rows(
                    {
                        "document_id": "summary-1",
                        "document_title": "术前小结",
                        "record_content": "拟行腹腔镜阑尾切除术",
                    }
                ),
            },
            frozenset(),
            "data_gap",
            "association_failed",
        ),
        (
            "LX0609-11-02-01",
            {},
            frozenset({"anesthesia_record"}),
            "technical_error",
            "source_query_error",
        ),
    )

    for rule_id, rows_by_source, error_sources, status, reason_code in cases:
        _session_value, execution, reduced, result = await _run_chain(
            rule_id,
            rows_by_source,
            error_sources=error_sources,
        )
        decision = execution.decisions[0]
        assert decision.reason_code == reason_code
        assert (reduced.final_state.value, reduced.reason_code) == (status, reason_code)
        assert (result["status"], result["reason_code"]) == (status, reason_code)
        assert result.get("customer_display_facts") == dict(execution.customer_display_facts).get(rule_id)
        assert execution.llm_call_count == 0
        assert execution.total_tokens == 0


def test_surgery_document_family_rule_set_and_aggregator_ownership_is_zero() -> None:
    assert SURGERY_DOCUMENT_RULE_IDS == (
            "LX0609-04-01-01",
            "LX0609-11-02-01",
            "LX0609-11-02-02",
            "LX0609-04-04-01",
            "LX0609-04-04-02",
            "LX0609-04-04-03",
            "LX0609-04-01-02",
            "LX0609-04-01-04",
            "LX0609-04-01-05",
    )

    # 迁移完成后，聚合器不得再按本族规则号解释事实、状态或证据。
    aggregator_source = (
        Path(__file__).parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")
    assert all(rule_id not in aggregator_source for rule_id in SURGERY_DOCUMENT_RULE_IDS)

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-04-04-03",
        raw={
            "failure_kind": "anesthesia_record_missing",
            "performed_anesthesia_confirmed": True,
            "checked_sources": ["anesthesia_record"],
        },
    ) == {
        "failure_kind": "anesthesia_record_missing",
        "performed_anesthesia_confirmed": True,
        "checked_sources": ["anesthesia_record"],
    }
