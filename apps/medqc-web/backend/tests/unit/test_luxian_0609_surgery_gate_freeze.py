from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.surgery_gate_result_mapping import (
    safe_surgery_gate_customer_display_facts,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results


RULE_IDS = ("LX0609-04-02-01", "LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01", "LX0609-04-02-05", "LX0609-11-01-01")


def test_surgery_gate_rules_do_not_return_to_result_aggregator() -> None:
    """迁移完成后，聚合器不得重新按本族规则号解释业务结果。"""

    aggregator = (
        Path(__file__).parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")

    assert all(rule_id not in aggregator for rule_id in RULE_IDS)


def test_surgery_gate_031_keeps_single_event_signer_failure_contract() -> None:
    assert safe_surgery_gate_customer_display_facts(
        rule_id="LX0609-04-02-05",
        raw={
            "failure_kind": "surgery_signer_not_qualified",
            "performed_surgery_confirmed": True,
            "surgeon_signature_matches": False,
        },
    ) == {
        "failure_kind": "surgery_signer_not_qualified",
        "performed_surgery_confirmed": True,
        "surgeon_signature_matches": False,
    }


def _wrapper(rule_id: str) -> dict[str, str]:
    return {"rule_id": rule_id, "rule_name": rule_id}


class _ControlledSurgeryFactClient:
    """冻结真实 surgery_gate 提示词的受控输出，非业务决策替身。"""

    def __init__(self, output: object) -> None:
        self.output = output
        self.prompts: list[str] = []

    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]:
        del max_completion_tokens, allow_length_retry
        self.prompts.append(prompt)
        if isinstance(self.output, Exception):
            raise self.output
        content = self.output if isinstance(self.output, str) else json.dumps(self.output, ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 101, "completion_tokens": 11, "total_tokens": 112},
            "_api_time": 0.2,
        }


def _success_output() -> dict[str, object]:
    return {
        "schema_version": "lx0609-surgery-text-facts-v2",
        "events": [
            {
                "event_ref": "EV1",
                "evidence_refs": ["S01-01", "S08-01"],
                "surgery_occurrence": "performed",
                "malignant_relation": "qualifying",
                "lymph_node_documentation": "documented",
                "implant_use": "actual_permanent_implant",
                "implant_name": "present",
                "implant_items": [
                    {"name": "人工硬脑膜", "use_kind": "permanent_implant", "evidence_ref": "S01-01"}
                ],
                "implant_type": "present",
                "implant_specification": "present",
                "implant_material": "present",
                "implant_quantity": "present",
                "incision_class": "unknown",
                "antimicrobial_intent": "unknown",
                "start_time_ref": None,
                "start_time_role": "unknown",
                "end_time_ref": None,
                "end_time_role": "unknown",
                "interval_scope": "unknown",
                "special_extension_reason": "unknown",
                "consent_role": "surgery_informed_consent",
                "consent_linkage": "current_surgery",
                "patient_signature": "present",
                "surgeon_signature": "present",
            }
        ],
    }


def _rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "surgery_record": [
            {
                "document_id": "surgery-gate-1",
                "surgery_begin_time": "2026-01-01 08:00:00+08:00",
                "surgery_end_time": "2026-01-01 10:00:00+08:00",
                "record_time": "2026-01-01 12:00:00+08:00",
                "surgeon": "术者甲",
                "surgeon_sign": "术者甲",
                "record_content": "实施手术并置入人工硬脑膜。",
            }
        ],
        "mr_surgery": [
            {
                "surgery_name": "手术甲",
                "surgery_begin_datetime": "2026-01-01 08:00:00+08:00",
                "surgery_end_datetime": "2026-01-01 10:00:00",
                "surgeon": "术者甲",
                "main_surgery_sign": "术者甲",
            }
        ],
        "pathology_exam_master": [{"specimen_name": "病理标本"}],
        "pathology_exam_report": [{"diagnosis": "恶性肿瘤"}],
        "diagnosis": [{"diagnosis_name": "恶性肿瘤"}],
        "inpat_drug_order": [{"generic_name": "头孢唑啉", "order_status": "执行"}],
        "daily_course_record": [{"document_id": "course-gate-1", "record_content": "术后病程记录"}],
        "surgery_inform_consent": [
            {
                "document_id": "consent-gate-1",
                "record_content": "手术知情同意书",
                "patient_sign": "已签名",
                "surgeon_sign": "已签名",
            }
        ],
    }


async def _execute_and_aggregate(
    *,
    rows_by_source: dict[str, list[dict[str, Any]]],
    client: _ControlledSurgeryFactClient | None,
    failing_sources: frozenset[str] = frozenset(),
    rule_ids: tuple[str, ...] = RULE_IDS,
) -> tuple[object, tuple[object, ...], list[dict[str, Any]], object]:
    """走 session、typed executor、Binding 和公共文书投影的正式链路。"""

    def read(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if source_key in failing_sources:
            raise SourceEvidenceQueryError("surgery-gate-freeze-query-error")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rule_ids,
        institute_id="surgery-freeze-institute",
        patient_id="surgery-freeze-patient",
        visit_id="surgery-freeze-visit",
        source_schema=None,
        created_at="2026-09-06T10:00:00+08:00",
        row_reader=read,
    )
    execution = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        wrapper_rules=[_wrapper(rule_id) for rule_id in rule_ids],
        evidence_payload=None,
        institute_id="surgery-freeze-institute",
        patient_id="surgery-freeze-patient",
        visit_id="surgery-freeze-visit",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    customer_results = _aggregate(
        reduced=reduced,
        customer_display_facts=execution.customer_display_facts,
        session=session,
        rule_ids=rule_ids,
    )
    return execution, reduced, customer_results, session


def _aggregate(
    *,
    reduced: tuple[object, ...],
    customer_display_facts: object,
    session: object,
    rule_ids: tuple[str, ...] = RULE_IDS,
) -> list[dict[str, Any]]:
    return aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper(rule_id) for rule_id in rule_ids],
        execution_results=[],
        format_evidence=False,
        reduced_decisions=reduced,
        customer_display_facts=customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )


@pytest.mark.asyncio
async def test_surgery_gate_freeze_real_chain_locks_states_facts_copy_and_evidence() -> None:
    """单台手术走完整主链，冻结六条规则的真实可达合同。"""

    client = _ControlledSurgeryFactClient(_success_output())
    execution, reduced, customer_results, session = await _execute_and_aggregate(
        rows_by_source=_rows(), client=client
    )

    assert execution.results == ()
    assert [item.rule_id for item in execution.decisions] == list(RULE_IDS)
    assert all(item.snapshot_hash == session.snapshot.snapshot_hash for item in execution.decisions)
    assert [item.final_state.value for item in reduced] == [
        "compliant", "compliant", "compliant", "data_gap", "compliant", "compliant"
    ]
    assert [item.reason_code for item in reduced] == [
        "requirement_within_threshold", "requirement_satisfied", "requirement_satisfied",
        "required_field_missing", "requirement_satisfied", "requirement_satisfied",
    ]
    assert all(item.criterion_results == () for item in reduced)
    assert all(item.fact_refs for item in reduced)
    assert execution.llm_call_count == 1
    assert execution.prompt_tokens == 101
    assert execution.total_tokens == 112
    assert len(client.prompts) == 1
    assert all(rule_id in client.prompts[0] for rule_id in RULE_IDS if rule_id not in {"LX0609-04-02-01", "LX0609-04-02-05"})

    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-04-02-01"] == {
        "failure_kind": "surgery_record_within_threshold",
        "performed_surgery_confirmed": True,
        "surgery_end_time": "2026-01-01 10:00:00",
        "record_time": "2026-01-01 12:00:00",
        "elapsed_seconds": 7200.0,
        "elapsed_hours": 2.0,
        "threshold_hours": 24,
        "source_label": "手术记录",
        "source_document_id": "surgery-gate-1",
    }
    assert facts["LX0609-04-02-04"]["checked_fields"] == [
        "implant_name", "implant_type", "implant_specification", "implant_material", "implant_quantity"
    ]
    assert facts["LX0609-04-02-04"]["source_document_id"] == "surgery-gate-1"
    assert facts["LX0609-04-02-05"] == {
        "verification_kind": "surgery_signature_confirmed",
        "performed_surgery_confirmed": True,
        "surgeon_signature_matches": True,
        "first_assistant_exception_used": False,
    }

    by_rule_id = {item["rule_id"]: item for item in customer_results}
    assert [item["rule_id"] for item in customer_results] == list(RULE_IDS)
    assert [item["status"] for item in customer_results] == [
        "compliant", "compliant", "compliant", "data_gap", "compliant", "compliant"
    ]
    assert all(item["criterion_results"] == [] for item in customer_results)
    assert "24 小时内" in by_rule_id["LX0609-04-02-01"]["findings"]
    assert "植入物" in by_rule_id["LX0609-04-02-04"]["findings"]
    assert "术者" in by_rule_id["LX0609-04-02-05"]["findings"]
    assert {
        (item["source_type"], item["source_document_id"])
        for item in by_rule_id["LX0609-11-01-01"]["customer_evidence"]
    } == {
        ("surgery_record", "surgery-gate-1"),
        ("surgery_inform_consent", "consent-gate-1"),
    }


@pytest.mark.asyncio
async def test_surgery_gate_freeze_absent_and_source_error_remain_distinct() -> None:
    """完整空来源与查询异常不能在 Binding 或投影中混同。"""

    # 先锁定真实 executor/Binding 输出：无手术不能伪造 implant_not_used，
    # performed_event_absent 的 025 应可在无客户事实时完成客户投影。
    def empty_read(**kwargs: object) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=str(kwargs["source_key"]), rows=(), truncated=False, limit_rows=50
        )

    absent_session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULE_IDS,
        institute_id="surgery-freeze-institute",
        patient_id="surgery-freeze-patient",
        visit_id="surgery-freeze-visit",
        source_schema=None,
        created_at="2026-09-06T10:00:00+08:00",
        row_reader=empty_read,
    )
    absent = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=RULE_IDS,
        decision_rule_ids=RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in RULE_IDS],
        evidence_payload=None,
        institute_id="surgery-freeze-institute",
        patient_id="surgery-freeze-patient",
        visit_id="surgery-freeze-visit",
        source_schema=None,
        llm_client=None,
        evidence_materials=absent_session.materials,
        evidence_snapshot=absent_session.snapshot,
    )
    absent_reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=absent.decisions,
        expected_rule_ids=RULE_IDS,
        snapshot=absent_session.snapshot,
        evidence_materials=absent_session.materials,
    )
    assert absent.results == ()
    assert [item.final_state.value for item in absent_reduced] == ["not_applicable"] * len(RULE_IDS)
    assert [item.reason_code for item in absent_reduced] == [
        "performed_event_absent"
    ] * len(RULE_IDS)
    assert [item.evaluator_version for item in absent_reduced] == [
        "surgery-timeliness-003-ruledecision-v1",
        *["surgery-gate-ruledecision-shadow-v2"] * 5,
    ]
    assert absent.llm_call_count == absent.total_tokens == 0
    absent_results = _aggregate(
        reduced=absent_reduced,
        customer_display_facts=absent.customer_display_facts,
        session=absent_session,
        rule_ids=RULE_IDS,
    )
    assert [item["status"] for item in absent_results] == ["not_applicable"] * len(RULE_IDS)
    assert [item["reason_code"] for item in absent_results] == ["performed_event_absent"] * len(RULE_IDS)
    absent_by_rule_id = {item["rule_id"]: item for item in absent_results}
    assert "customer_display_facts" not in absent_by_rule_id["LX0609-04-02-04"]

    errored, errored_reduced, errored_results, _ = await _execute_and_aggregate(
        rows_by_source={}, client=None, failing_sources=frozenset({"surgery_record"})
    )
    assert errored.results == ()
    assert [item.final_state.value for item in errored_reduced] == ["technical_error"] * len(RULE_IDS)
    assert [item.reason_code for item in errored_reduced] == ["source_query_error"] * len(RULE_IDS)
    assert [item["status"] for item in errored_results] == ["technical_error"] * len(RULE_IDS)
    assert all("customer_evidence" not in item for item in errored_results)


@pytest.mark.asyncio
async def test_surgery_gate_freeze_two_surgeries_do_not_hide_an_unsigned_event() -> None:
    """031 逐台签名：一台已签不得覆盖另一台签名事实缺失。"""

    rows = _rows()
    rows["surgery_record"] = [
        {
            "document_id": "surgery-gate-1",
            "surgery_begin_time": "2026-01-01 08:00:00+08:00",
            "surgery_end_time": "2026-01-01 10:00:00+08:00",
            "surgeon": "术者甲",
            "surgeon_sign": "术者甲",
        },
        {
            "document_id": "surgery-gate-2",
            "surgery_begin_time": "2026-01-02 08:00:00+08:00",
            "surgery_end_time": "2026-01-02 10:00:00+08:00",
            "surgeon": "术者乙",
            "surgeon_sign": "",
        },
    ]
    rows["mr_surgery"] = [
        {"surgeon": "术者甲", "main_surgery_sign": "术者甲"},
        {"surgeon": "术者乙", "main_surgery_sign": ""},
    ]
    execution, reduced, customer_results, _ = await _execute_and_aggregate(
        rows_by_source=rows, client=None, rule_ids=("LX0609-04-02-05",)
    )

    assert execution.llm_call_count == execution.total_tokens == 0
    assert [item.final_state.value for item in reduced] == ["data_gap"]
    assert [item.reason_code for item in reduced] == ["required_field_missing"]
    assert [item["status"] for item in customer_results] == ["data_gap"]
    assert "surgery-gate-2" not in repr(customer_results)


@pytest.mark.asyncio
async def test_surgery_gate_freeze_031_only_projects_the_selected_signature_source() -> None:
    """031 采用主表签名时，不得同时展示未参与判定的矛盾手术记录。"""

    rows = _rows()
    rows["surgery_record"][0].update(
        {
            "surgeon": "术者甲",
            "surgeon_sign": "其他医师",
        }
    )
    rows["mr_surgery"][0].update(
        {
            "document_id": "mr-surgery-gate-1",
            "surgeon": "术者甲",
            "main_surgery_sign": "术者甲",
        }
    )

    execution, reduced, customer_results, _ = await _execute_and_aggregate(
        rows_by_source=rows,
        client=None,
        rule_ids=("LX0609-04-02-05",),
    )

    assert execution.llm_call_count == execution.total_tokens == 0
    assert [item.final_state.value for item in reduced] == ["compliant"]
    assert {
        (item["source_type"], item["source_document_id"])
        for item in customer_results[0]["customer_evidence"]
    } == {("mr_surgery", "mr-surgery-gate-1")}


@pytest.mark.asyncio
async def test_surgery_gate_freeze_missing_consent_keeps_every_trigger_coordinate() -> None:
    """033 完整空同意书来源时，每台已实施手术都是独立缺失触发事件。"""

    rows = _rows()
    rows["surgery_record"] = [
        {
            "document_id": "surgery-gate-1",
            "surgery_begin_time": "2026-01-01 08:00:00+08:00",
            "surgery_end_time": "2026-01-01 10:00:00+08:00",
            "record_time": "2026-01-01 12:00:00+08:00",
            "surgeon": "术者甲",
            "surgeon_sign": "术者甲",
            "record_content": "实施手术甲。",
        },
        {
            "document_id": "surgery-gate-2",
            "surgery_begin_time": "2026-01-02 08:00:00+08:00",
            "surgery_end_time": "2026-01-02 10:00:00+08:00",
            "record_time": "2026-01-02 12:00:00+08:00",
            "surgeon": "术者乙",
            "surgeon_sign": "术者乙",
            "record_content": "实施手术乙。",
        },
    ]
    rows["surgery_inform_consent"] = []

    execution, reduced, customer_results, _ = await _execute_and_aggregate(
        rows_by_source=rows,
        client=None,
        rule_ids=("LX0609-11-01-01",),
    )

    assert execution.llm_call_count == execution.total_tokens == 0
    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert [item.reason_code for item in reduced] == ["requirement_violated"]
    assert customer_results[0]["customer_display_facts"]["failure_kind"] == (
        "surgery_consent_document_missing"
    )
    assert {
        (item["source_type"], item["source_document_id"])
        for item in customer_results[0]["customer_evidence"]
    } == {
        ("surgery_record", "surgery-gate-1"),
        ("surgery_record", "surgery-gate-2"),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output", "expected_state", "expected_reason"),
    [
        ("not-json", "technical_error", "model_invalid_output"),
        (
            {**_success_output(), "events": [{**_success_output()["events"][0], "malignant_relation": "unknown"}]},
            "data_gap",
            "required_field_missing",
        ),
        (TimeoutError("controlled-timeout"), "technical_error", "model_transport_error"),
    ],
)
async def test_surgery_gate_freeze_controlled_llm_failure_semantics(
    output: object, expected_state: str, expected_reason: str
) -> None:
    """非法、unknown 与超时输出仍经真实 native/Binding/聚合链收敛。"""

    client = _ControlledSurgeryFactClient(output)
    execution, reduced, customer_results, _ = await _execute_and_aggregate(
        rows_by_source=_rows(), client=client
    )
    by_rule_id = {item.rule_id: item for item in reduced}
    by_customer_rule_id = {item["rule_id"]: item for item in customer_results}

    assert execution.llm_call_count == 1
    if isinstance(output, Exception):
        assert execution.prompt_tokens == execution.total_tokens == 0
    else:
        assert execution.prompt_tokens == 101
        assert execution.total_tokens == 112
    assert by_rule_id["LX0609-04-02-03"].final_state.value == expected_state
    assert by_rule_id["LX0609-04-02-03"].reason_code == expected_reason
    assert by_customer_rule_id["LX0609-04-02-03"]["status"] == expected_state
    assert by_customer_rule_id["LX0609-04-02-03"]["reason_code"] == expected_reason
