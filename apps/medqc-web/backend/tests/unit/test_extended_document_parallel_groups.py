import asyncio
from dataclasses import replace

import pytest

from app.core.execution_timing import timing_scope
from app.services.luxian_0609 import native_extended_document_execution as module
from test_luxian_0609_native_extended_document_execution import _session
from test_luxian_0609_antimicrobial_order_reason import _ReasonClient, _order, _course


RULES = ("LX0609-05-01-02", "LX0609-08-01-01", "LX0609-05-01-05")


def arguments(rules=RULES):
    snapshot, materials = _session({})
    return dict(rule_ids=rules, decision_rule_ids=rules,
                evidence_snapshot=snapshot, evidence_materials=materials)


@pytest.mark.asyncio
async def test_independent_groups_overlap_but_shared_reason_rules_stay_together(monkeypatch):
    started = []
    both = asyncio.Event()

    async def core(**kwargs):
        selected = tuple(kwargs["rule_ids"])
        started.append(selected)
        if len(started) == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 2)
        assert kwargs["decision_rule_ids"] == selected
        return module.NativeExtendedDocumentExecutionResult(
            results=tuple({"rule_id": rule} for rule in selected),
            planned_rule_ids=selected, decisions=(),
            customer_display_facts=tuple((rule, {"fact": rule}) for rule in selected),
            llm_call_count=1, prompt_tokens=10, completion_tokens=5, total_tokens=15, api_time=1.5,
        )

    monkeypatch.setattr(module, "_execute_extended_document_group", core)
    with timing_scope() as collector:
        result = await module.execute_luxian_0609_native_extended_document_rules(**arguments())
    assert started == [("LX0609-05-01-02", "LX0609-05-01-05"), ("LX0609-08-01-01",)]
    assert result.planned_rule_ids == RULES
    assert tuple(row["rule_id"] for row in result.results) == RULES
    assert tuple(row[0] for row in result.customer_display_facts) == RULES
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (2, 20, 10, 30, 3.0)
    assert set(collector.snapshot()["units"]) == {"antimicrobial", "documents"}


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True], ids=["exception", "parent-cancel"])
async def test_exception_and_cancel_drain_sibling_tasks(monkeypatch, cancel):
    both = asyncio.Event()
    started = []
    cleaned = []

    async def core(**kwargs):
        label = tuple(kwargs["rule_ids"])
        started.append(label)
        if len(started) == 2:
            both.set()
        try:
            await both.wait()
            if not cancel and label[0] == "LX0609-05-01-02":
                raise ValueError("group failed")
            await asyncio.Event().wait()
        finally:
            cleaned.append(label)

    monkeypatch.setattr(module, "_execute_extended_document_group", core)
    task = asyncio.create_task(module.execute_luxian_0609_native_extended_document_rules(**arguments()))
    await asyncio.wait_for(both.wait(), 2)
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else ValueError):
        await asyncio.wait_for(task, 2)
    assert len(cleaned) == len(started) == 2


@pytest.mark.asyncio
async def test_invalid_scope_does_not_start_any_group(monkeypatch):
    async def forbidden(**kwargs):
        pytest.fail("invalid scope started execution")

    monkeypatch.setattr(module, "_execute_extended_document_group", forbidden)
    values = arguments()
    values["decision_rule_ids"] = RULES[:1]
    with pytest.raises(ValueError, match="typed decisions"):
        await module.execute_luxian_0609_native_extended_document_rules(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("sources", [
    {},
    {"inpat_registration": ({"admission_date": "2026-01-01", "discharge_date": "2026-01-05"},)},
])
async def test_real_kernel_sequential_parallel_decisions_facts_and_usage_are_equal(sources):
    snapshot, materials = _session(sources)
    rules = module.EXTENDED_DOCUMENT_RULE_IDS
    kwargs = dict(rule_ids=rules, decision_rule_ids=rules, evidence_snapshot=snapshot,
                  evidence_materials=materials)
    sequential = await module._execute_extended_document_group(**kwargs)
    parallel = await module.execute_luxian_0609_native_extended_document_rules(**kwargs)
    # 未触发模型的真实内核也必须保留精确证据引用和缺资料原因。
    assert parallel == sequential
    assert replace(parallel, api_time=0) == replace(sequential, api_time=0)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason_present", [False, True])
async def test_fixed_answers_keep_shared_reason_once_and_same_clinical_contract(monkeypatch, tmp_path, reason_present):
    reason = "考虑细菌感染，予头孢曲松抗感染。"
    sources = {
        "inpat_registration": ({"admission_date": "2026-01-01", "discharge_date": "2026-01-05"},),
        "inpat_drug_order": (_order("order-1", "头孢曲松", "2026-01-02 10:00:00"),),
        "daily_course_record": (_course("course-1", "2026-01-02 11:00:00", reason),),
        "evaluation_context.horizon": ({"horizon_date": "2026-01-06", "horizon_datetime": "2026-01-06 00:00:00"},),
    }
    snapshot, materials = _session(sources)
    kwargs = dict(rule_ids=RULES, decision_rule_ids=RULES,
                  evidence_snapshot=snapshot, evidence_materials=materials)
    clients = [_ReasonClient({"头孢曲松": {"infection_judgment": reason}} if reason_present else {}) for _ in range(2)]
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path / "sequential"))
    sequential = await module._execute_extended_document_group(**kwargs, llm_client=clients[0])
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path / "parallel"))
    parallel = await module.execute_luxian_0609_native_extended_document_rules(**kwargs, llm_client=clients[1])
    assert replace(parallel, api_time=0) == replace(sequential, api_time=0)
    assert len(clients[0].calls) == len(clients[1].calls) == 1
    assert clients[0].calls == clients[1].calls
    assert parallel.llm_call_count == 1
    assert parallel.total_tokens == 15
    reason_decision = next(item for item in parallel.decisions if item.rule_id == "LX0609-05-01-02")
    assert reason_decision.qc_direction.value == ("satisfied" if reason_present else "defect")
