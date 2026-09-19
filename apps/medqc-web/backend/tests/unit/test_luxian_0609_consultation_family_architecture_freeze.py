from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.luxian_0609 import execution
from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609 import consultation_opinion_freeze
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_package import (
    build_luxian_0609_package_plan_from_settings,
    load_luxian_0609_dependency_inventory,
)
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY


CONSULTATION_RULE_IDS = (
    "LX0609-020",
    "LX0609-021",
    "LX0609-022",
    "LX0609-023",
)


class RecordingClient:
    """只记录正式 executor 送入模型的 prompt，不访问任何真实模型。"""

    def __init__(self, *responses: object) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        content = (
            response
            if isinstance(response, str)
            else json.dumps(response, ensure_ascii=False)
        )
        return {
            "content": content,
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 5,
                "total_tokens": 16,
            },
        }


def _formal_settings() -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED=True,
    )


def _session(
    *,
    selected_rule_ids: tuple[str, ...],
    rows_by_source: dict[str, list[dict[str, str]]] | None = None,
    unavailable_sources: frozenset[str] = frozenset(),
    error_sources: frozenset[str] = frozenset(),
    evaluation_horizon_policy: str | None = None,
    horizon_unavailable_reason: str | None = None,
):
    rows_by_source = rows_by_source or {}

    def read(**kwargs: str) -> SnapshotSourceRows:
        source_key = kwargs["source_key"]
        if source_key in unavailable_sources:
            raise SourceEvidenceUnavailable("synthetic source unavailable")
        if source_key in error_sources:
            raise SourceEvidenceQueryError("synthetic source query failed")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="freeze-institute",
        patient_id="freeze-patient",
        visit_id="freeze-visit",
        source_schema=None,
        created_at="2026-09-05T12:00:00+08:00",
        evaluation_as_of_date="2026-07-05",
        evaluation_horizon_policy=evaluation_horizon_policy,
        horizon_unavailable_reason=horizon_unavailable_reason,
        row_reader=read,
        additional_source_keys=("consultation_record",),
    )


async def _run_formal_chain(
    monkeypatch: pytest.MonkeyPatch,
    *,
    selected_rule_ids: tuple[str, ...],
    session: object,
    client: RecordingClient | None,
) -> tuple[execution.Luxian0609ExecutionContext, dict[str, Any]]:
    monkeypatch.setattr(
        execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: session,
    )
    executable_rules, context = await execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="freeze-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=client,
        settings=_formal_settings(),
        institute_id="freeze-institute",
        patient_id="freeze-patient",
        selected_customer_rule_ids=selected_rule_ids,
        evaluation_as_of_date="2026-07-05",
    )
    assert executable_rules == []
    delivered = execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="freeze-visit",
        model_name="recording-stub",
        evidence_payload={},
    )
    return context, delivered


def _consultation_row(
    document_id: str,
    record_time: str,
    content: str,
) -> dict[str, str]:
    return {
        "document_id": document_id,
        "document_title": "会诊记录",
        "record_time": record_time,
        "record_content": content,
    }


def _episode_facts(*facts: dict[str, object]) -> dict[str, object]:
    return {"consultation_event_facts": list(facts)}


def _fact(
    ref: str,
    *,
    opinion_state: str,
) -> dict[str, object]:
    return {
        "ref": ref,
        "scope": "ordinary",
        "application_state": "clear",
        "opinion_state": opinion_state,
        "confidence": "high",
        "recommendations": [],
    }


def test_consultation_family_registry_is_episode_executor_and_excludes_069() -> None:
    """四个会诊客户规则只能形成一个 consultation_quality 正式批次。"""

    inventory = load_luxian_0609_dependency_inventory()
    dependencies = {
        item.rule_id: item
        for item in inventory
        if item.rule_id in CONSULTATION_RULE_IDS
    }
    plan = build_luxian_0609_package_plan_from_settings(
        inventory=inventory,
        selected_rule_ids=(*CONSULTATION_RULE_IDS, "LX0609-069"),
        settings=_formal_settings(),
    )

    assert tuple(dependencies) == CONSULTATION_RULE_IDS
    assert {item.executor_key for item in dependencies.values()} == {
        "consultation_quality"
    }
    # 020/021/022 因会诊来源缺失暂停，本族只派发 023。
    assert plan.native_rule_ids_for_executor("consultation_quality") == ("LX0609-023",)
    assert plan.not_executed_rule_ids == (
        "LX0609-020",
        "LX0609-021",
        "LX0609-022",
    )
    assert "LX0609-069" not in plan.native_rule_ids_for_executor(
        "consultation_quality"
    )
    assert "LX0609-069" not in episode.CONSULTATION_EPISODE_RULE_IDS
    assert execution.execute_luxian_0609_native_consultation_episode_rules is (
        episode.execute_luxian_0609_native_consultation_episode_rules
    )


@pytest.mark.asyncio
async def test_formal_unified_chain_freezes_explicit_022_with_locatable_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _consultation_row(
        "CONSULT-022-1",
        "2026-07-02 09:30:00",
        "感染科医师会诊后指出：考虑既往感染，继续保肝治疗，我科随访。",
    )
    client = RecordingClient()
    context, delivered = await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=("LX0609-022",),
        session=_session(
            selected_rule_ids=("LX0609-022",),
            rows_by_source={"consultation_record": [row]},
        ),
        client=client,
    )

    assert [(item.final_state.value, item.reason_code) for item in context.reduced_decisions] == [
        ("compliant", "requirement_satisfied")
    ]
    assert context.native_results == []
    assert context.native_llm_call_count == 0
    assert client.prompts == []
    assert [(item["status"], item["reason_code"]) for item in delivered["results"]] == [
        ("compliant", "requirement_satisfied")
    ]
    raw_facts = dict(context.customer_display_facts)["LX0609-022"]
    assert "source_document_ids" not in raw_facts
    assert "source_document_id" not in raw_facts["episode_results"][0]
    assert len(context.reduced_decisions[0].fact_refs) == 1
    facts = delivered["results"][0]["customer_display_facts"]
    assert "source_document_ids" not in facts
    assert facts["episode_results"] == [
        {
            "episode_index": 1,
            "semantic_state": "clear",
            "record_time": "2026-07-02 09:30:00",
            "document_title": "会诊记录单",
        }
    ]
    assert [
        (item["source_type"], item["source_document_id"])
        for item in delivered["results"][0]["customer_evidence"]
    ] == [("consultation_record", "CONSULT-022-1")]
    assert "sha" not in repr(facts).lower()


@pytest.mark.asyncio
async def test_formal_unified_chain_freezes_mixed_022_episodes_and_prompt_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _consultation_row("CONSULT-MIX-1", "2026-07-02 09:00:00", "第一次会诊意见。"),
        _consultation_row("CONSULT-MIX-2", "2026-07-02 10:00:00", "第二次会诊意见。"),
        _consultation_row("CONSULT-MIX-3", "2026-07-02 11:00:00", "第三次会诊意见。"),
    ]
    client = RecordingClient(
        {
            "episodes": [
                {
                    "episode_ref": f"consultation_record-{index}",
                    "member_refs": [f"consultation_record-{index}"],
                    "application_refs": [],
                    "opinion_refs": [f"consultation_record-{index}"],
                    "application_state": "absent",
                    "opinion_state": state,
                    "confidence": "high",
                    "recommendations": [],
                }
                for index, state in enumerate(("clear", "vague", "missing"), 1)
            ],
            "non_target_refs": [],
            "unresolved_refs": [],
        }
    )
    context, delivered = await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=("LX0609-022",),
        session=_session(
            selected_rule_ids=("LX0609-022",),
            rows_by_source={"consultation_record": rows},
        ),
        client=client,
    )

    assert [(item.final_state.value, item.reason_code) for item in context.reduced_decisions] == [
        ("non_compliant", "requirement_violated")
    ]
    assert context.native_llm_call_count == 1
    assert (
        context.native_prompt_tokens,
        context.native_completion_tokens,
        context.native_total_tokens,
    ) == (11, 5, 16)
    assert context.native_prompt_tokens + context.native_completion_tokens == (
        context.native_total_tokens
    )
    assert len(client.prompts) == 1
    assert "member_refs" in client.prompts[0]
    assert "consultation_event_facts" not in client.prompts[0]
    assert all(
        f'"ref": "consultation_record-{index}"' in client.prompts[0]
        and row["record_content"] in client.prompts[0]
        and row["document_id"] not in client.prompts[0]
        for index, row in enumerate(rows, start=1)
    )
    assert (
        delivered["total_prompt_tokens"],
        delivered["total_completion_tokens"],
        delivered["total_tokens"],
    ) == (11, 5, 16)
    assert delivered["total_prompt_tokens"] + delivered["total_completion_tokens"] == (
        delivered["total_tokens"]
    )
    assert delivered["executor_breakdown"] == {"llm": 1}
    raw_facts = dict(context.customer_display_facts)["LX0609-022"]
    assert "source_document_ids" not in raw_facts
    assert all(
        "source_document_id" not in item
        for item in raw_facts["episode_results"]
    )
    assert len(context.reduced_decisions[0].fact_refs) == 3
    facts = delivered["results"][0]["customer_display_facts"]
    assert "source_document_ids" not in facts
    assert facts["episode_results"] == [
        {
            "episode_index": 1,
            "semantic_state": "clear",
            "record_time": "2026-07-02 09:00:00",
            "document_title": "会诊记录单",
        },
        {
            "episode_index": 2,
            "semantic_state": "vague",
            "record_time": "2026-07-02 10:00:00",
            "document_title": "会诊记录单",
        },
        {
            "episode_index": 3,
            "semantic_state": "missing",
            "record_time": "2026-07-02 11:00:00",
            "document_title": "会诊记录单",
        },
    ]
    assert {
        (item["source_type"], item["source_document_id"])
        for item in delivered["results"][0]["customer_evidence"]
    } == {
        ("consultation_record", "CONSULT-MIX-1"),
        ("consultation_record", "CONSULT-MIX-2"),
        ("consultation_record", "CONSULT-MIX-3"),
    }
    rerun_client = RecordingClient(
        _episode_facts(
            _fact("consultation_record-1", opinion_state="clear"),
            _fact("consultation_record-2", opinion_state="vague"),
            _fact("consultation_record-3", opinion_state="missing"),
        )
    )
    # 本用例比较两次运行各自构建的提示词，必须先清除第一阶段事实冻结，
    # 否则第二次运行复用冻结结果、不会再产生提示词。
    consultation_opinion_freeze.reset_opinion_freeze(visit_id="freeze-visit")
    await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=("LX0609-022",),
        session=_session(
            selected_rule_ids=("LX0609-022",),
            rows_by_source={"consultation_record": rows},
        ),
        client=rerun_client,
    )
    assert client.prompts == rerun_client.prompts


@pytest.mark.asyncio
async def test_formal_unified_chain_empty_complete_consultation_is_not_applicable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = RecordingClient()
    context, delivered = await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=("LX0609-022",),
        session=_session(selected_rule_ids=("LX0609-022",)),
        client=client,
    )

    assert [(item.final_state.value, item.reason_code) for item in context.reduced_decisions] == [
        ("not_applicable", "trigger_absent_complete")
    ]
    assert context.native_llm_call_count == 0
    assert client.prompts == []
    assert [(item["status"], item["reason_code"]) for item in delivered["results"]] == [
        ("not_applicable", "trigger_absent_complete")
    ]


@pytest.mark.asyncio
async def test_formal_unified_chain_non_target_consultation_keeps_excluding_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _consultation_row(
        "CONSULT-NON-TARGET-1",
        "2026-07-02 09:30:00",
        "术前麻醉风险评估。",
    )
    client = RecordingClient()

    context, delivered = await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=("LX0609-021",),
        session=_session(
            selected_rule_ids=("LX0609-021",),
            rows_by_source={"consultation_record": [row]},
        ),
        client=client,
    )

    assert [(item.final_state.value, item.reason_code) for item in context.reduced_decisions] == [
        ("not_applicable", "eligibility_not_met")
    ]
    assert len(context.reduced_decisions[0].fact_refs) == 1
    assert client.prompts == []
    assert [(item["status"], item["reason_code"]) for item in delivered["results"]] == [
        ("not_applicable", "eligibility_not_met")
    ]
    assert [
        (item["source_type"], item["source_document_id"])
        for item in delivered["results"][0]["customer_evidence"]
    ] == [("consultation_record", "CONSULT-NON-TARGET-1")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rule_id", "rows_by_source", "unavailable_sources", "expected_reason"),
    [
        ("LX0609-022", {}, frozenset({"consultation_record"}), "source_unavailable"),
        (
            "LX0609-020",
            {
                "consultation_record": [
                    _consultation_row(
                        "CONSULT-LINK-1",
                        "2026-07-02 09:00:00",
                        "请感染科会诊并提出诊疗意见。",
                    )
                ]
            },
            frozenset(),
            "linkage_unresolved",
        ),
    ],
)
async def test_formal_unified_chain_source_or_linkage_gap_stays_data_gap(
    monkeypatch: pytest.MonkeyPatch,
    rule_id: str,
    rows_by_source: dict[str, list[dict[str, str]]],
    unavailable_sources: frozenset[str],
    expected_reason: str,
) -> None:
    client = RecordingClient()
    context, delivered = await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=(rule_id,),
        session=_session(
            selected_rule_ids=(rule_id,),
            rows_by_source=rows_by_source,
            unavailable_sources=unavailable_sources,
            evaluation_horizon_policy=(
                "disabled" if rule_id == "LX0609-020" else None
            ),
            horizon_unavailable_reason=(
                "authoritative_time_missing"
                if rule_id == "LX0609-020"
                else None
            ),
        ),
        client=client,
    )

    assert [(item.final_state.value, item.reason_code) for item in context.reduced_decisions] == [
        ("data_gap", expected_reason)
    ]
    assert context.native_llm_call_count == 0
    assert client.prompts == []
    assert [(item["status"], item["reason_code"]) for item in delivered["results"]] == [
        ("data_gap", expected_reason)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    ["not-json", RuntimeError("synthetic transport failure")],
    ids=("invalid_model_structure", "transport_error"),
)
async def test_formal_unified_chain_model_failures_are_technical_errors(
    monkeypatch: pytest.MonkeyPatch,
    response: object,
) -> None:
    client = RecordingClient(response)
    context, delivered = await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=("LX0609-022",),
        session=_session(
            selected_rule_ids=("LX0609-022",),
            rows_by_source={
                "consultation_record": [
                    _consultation_row(
                        "CONSULT-ERROR-1",
                        "2026-07-02 09:00:00",
                        "会诊记录：请相关专科协助评估。",
                    )
                ]
            },
        ),
        client=client,
    )

    expected_reason = (
        "model_transport_error"
        if isinstance(response, BaseException)
        else "model_invalid_output"
    )
    assert [(item.final_state.value, item.reason_code) for item in context.reduced_decisions] == [
        ("technical_error", expected_reason)
    ]
    assert context.native_llm_call_count == 1
    assert len(client.prompts) == 1
    assert '"ref": "consultation_record-1"' in client.prompts[0]
    assert "会诊记录：请相关专科协助评估。" in client.prompts[0]
    assert "CONSULT-ERROR-1" not in client.prompts[0]
    assert [(item["status"], item["reason_code"]) for item in delivered["results"]] == [
        ("technical_error", expected_reason)
    ]
    assert all(item["status"] not in {"data_gap", "uncertain"} for item in delivered["results"])
