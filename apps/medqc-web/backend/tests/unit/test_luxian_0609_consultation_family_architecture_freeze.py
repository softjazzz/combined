from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.luxian_0609 import execution
from app.services.luxian_0609 import native_consultation_episode_execution as episode
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
    "LX0609-03-01-01",
    "LX0609-03-01-02",
    "LX0609-03-01-03",
    "LX0609-03-01-04",
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
        selected_rule_ids=(*CONSULTATION_RULE_IDS, "LX0609-04-02-07"),
        settings=_formal_settings(),
    )

    assert tuple(dependencies) == CONSULTATION_RULE_IDS
    assert {item.executor_key for item in dependencies.values()} == {
        "consultation_quality"
    }
    # 020/021/022 因会诊来源缺失暂停，本族只派发 023。
    assert plan.native_rule_ids_for_executor("consultation_quality") == ("LX0609-03-01-04",)
    assert plan.not_executed_rule_ids == (
        "LX0609-03-01-01",
        "LX0609-03-01-02",
        "LX0609-03-01-03",
    )
    assert "LX0609-04-02-07" not in plan.native_rule_ids_for_executor(
        "consultation_quality"
    )
    assert "LX0609-04-02-07" not in episode.CONSULTATION_EPISODE_RULE_IDS
    assert execution.execute_luxian_0609_native_consultation_episode_rules is (
        episode.execute_luxian_0609_native_consultation_episode_rules
    )


@pytest.mark.asyncio
async def test_formal_unified_chain_delivers_paused_consultation_rules_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正式链必须在执行器之前交付020至022的暂停结果。"""

    client = RecordingClient(RuntimeError("paused rules must not call the model"))
    selected_rule_ids = ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03")
    context, delivered = await _run_formal_chain(
        monkeypatch,
        selected_rule_ids=selected_rule_ids,
        session=_session(
            selected_rule_ids=selected_rule_ids,
            rows_by_source={
                "consultation_record": [
                    _consultation_row(
                        "CONSULT-PAUSED-1",
                        "2026-07-02 09:30:00",
                        "暂停规则不应读取或评价这份正文。",
                    )
                ]
            },
            error_sources=frozenset({"consultation_record"}),
        ),
        client=client,
    )

    assert context.reduced_decisions == ()
    assert [item["rule_id"] for item in context.native_results] == list(
        selected_rule_ids
    )
    assert context.native_llm_call_count == 0
    assert client.prompts == []
    assert [
        (
            item["rule_id"],
            item["status"],
            item["metadata"]["reason_code"],
            item["metadata"]["pending_reason_code"],
        )
        for item in delivered["results"]
    ] == [
        (
            rule_id,
            "not_executed",
            "policy_definition_pending",
            "consultation_source_document_unavailable_customer_scope",
        )
        for rule_id in selected_rule_ids
    ]
    assert delivered["executor_breakdown"] == {}
