from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
import inspect

import pytest

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.decision_reducer import (
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)


def _documents(**overrides: list[dict]) -> dict:
    documents = {
        "bloodtrans_record": [{"content": "输血记录正文，记录实际输注过程及观察情况。"}],
        "consent_form": [{"content": "输血治疗知情同意书，已完成风险告知及签名。"}],
        "labtest_master": [{"content": "输血前常规检查资料。"}],
        "labtest_item_report": [],
        "blood_application": [{"content": "输血前评估及申请资料。"}],
        "daily_course_record": [{"content": "输血过程及输血后评价记录。"}],
        "surgery_record": [{"content": "手术记录中的术中输血信息。"}],
        "anesthesia_record": [{"content": "麻醉记录中的术中输血信息。"}],
        "postsurg_firstcourse_record": [{"content": "术后首次病程中的输血信息。"}],
        "inpat_nondrug_order": [{"content": "输血医嘱中的成分和数量。"}],
        "inpat_bill_item": [{"content": "输血收费中的成分和数量。"}],
    }
    documents.update(overrides)
    return {"programmatic_timeline": {"documents": documents}}


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
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
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "_api_time": 0.2,
        }


def _reader(*, source_key: str, **_: object) -> list[dict]:
    if source_key == "mr_bloodtrans":
        return []
    if source_key == "bloodtrans_record":
        return [{"record_content": "输血记录正文，记录实际输注过程及观察情况。"}]
    raise AssertionError(source_key)


def _typed_decision_session(
    *,
    selected_rule_ids: tuple[str, ...],
    performed: bool = True,
    bloodtrans_content: str | None = None,
    daily_content: str | None = None,
):
    bloodtrans_material = (
        "输血前评估：患者具有输血指征，输血目的为纠正贫血，血红蛋白降低，"
        "既往无输血不良反应，生命体征平稳；"
        "开始时间14:20，输注去白悬浮红细胞2U，"
        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
        "未见寒战、发热及其他输血不良反应。"
        if bloodtrans_content is None
        else bloodtrans_content
    )
    daily_material = (
        "输血后继续观察，患者生命体征平稳。"
        if daily_content is None
        else daily_content
    )

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ] if performed else [],
            "bloodtrans_record": [
                {
                    "document_id": "typed-transfusion-document",
                    "record_content": bloodtrans_material,
                    "record_time": "2026-01-01 16:20:00",
                }
            ] if performed else [],
            "daily_course_record": [
                {
                    "document_id": "typed-daily-document",
                    "record_content": daily_material,
                    "record_time": "2026-01-01 17:00:00",
                }
            ] if performed else [],
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )


def test_typed_transfusion_core_does_not_reverse_engineer_customer_result_dto():
    execution_source = inspect.getsource(
        transfusion.execute_luxian_0609_native_transfusion_rules
    )
    decision_source = inspect.getsource(transfusion._typed_decision_from_outcome)

    assert "_typed_decision_from_result" not in execution_source
    assert "result.get" not in decision_source
    assert "metadata" not in decision_source
    assert "emit_outcome" in execution_source
    assert "_typed_documents_from_evidence_session" in execution_source
    assert "typed_material_by_rule[rule_id]" in execution_source
    assert "documents = legacy_documents" in execution_source


@pytest.mark.parametrize(
    ("status", "raw_reason", "canonical_reason"),
    (
        ("technical_error", "source_query_error", "source_query_error"),
        ("technical_error", "snapshot_mismatch", "snapshot_mismatch"),
        ("technical_error", "unexpected_internal_failure", "executor_exception"),
        ("data_gap", "transfusion_source_unavailable", "source_unavailable"),
    ),
)
def test_typed_transfusion_preserves_only_approved_canonical_reasons(
    status,
    raw_reason,
    canonical_reason,
):
    session = _typed_decision_session(selected_rule_ids=("LX0609-045",))

    decision = transfusion._typed_decision_from_outcome(
        outcome=transfusion._TransfusionRuleOutcome(
            rule_id="LX0609-045",
            status=status,
            reason_code=raw_reason,
            executor_type="program",
        ),
        snapshot=session.snapshot,
    )

    assert decision.reason_code == canonical_reason


@pytest.mark.asyncio
async def test_typed_045_uses_snapshot_material_not_conflicting_legacy_payload(
    monkeypatch,
):
    complete_session = _typed_decision_session(
        selected_rule_ids=("LX0609-045",),
    )
    incomplete_session = _typed_decision_session(
        selected_rule_ids=("LX0609-045",),
        bloodtrans_content="输血过程中患者生命体征平稳。",
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed path must use the supplied evidence session")
        ),
    )
    common = {
        "rule_ids": ("LX0609-045",),
        "wrapper_rules": [_wrapper("LX0609-045")],
        # 旧 payload 故意始终给出强合规材料；typed 结果必须随 snapshot material 改变。
        "evidence_payload": _documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                        "未见寒战、发热及其他输血不良反应。"
                    )
                }
            ]
        ),
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "llm_client": None,
        "decision_rule_ids": ("LX0609-045",),
    }

    complete = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        evidence_snapshot=complete_session.snapshot,
        evidence_materials=complete_session.materials,
    )
    incomplete = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        evidence_snapshot=incomplete_session.snapshot,
        evidence_materials=incomplete_session.materials,
    )

    assert reduce_luxian_0609_rule_decision(
        complete.decisions[0]
    ).final_state.value == "compliant"
    assert reduce_luxian_0609_rule_decision(
        incomplete.decisions[0]
    ).final_state.value == "data_gap"
    assert complete_session.snapshot.snapshot_hash != incomplete_session.snapshot.snapshot_hash
    assert complete.decisions[0].snapshot_hash == complete_session.snapshot.snapshot_hash
    assert incomplete.decisions[0].snapshot_hash == incomplete_session.snapshot.snapshot_hash
    assert complete.decisions[0].fact_refs != incomplete.decisions[0].fact_refs
    assert set(complete.decisions[0].fact_refs).issubset(
        {
            item.snapshot_ref.removeprefix("sha256:")
            for item in complete_session.snapshot.observations
        }
    )
    assert set(incomplete.decisions[0].fact_refs).issubset(
        {
            item.snapshot_ref.removeprefix("sha256:")
            for item in incomplete_session.snapshot.observations
        }
    )


@pytest.mark.asyncio
async def test_typed_044_uses_same_session_material_and_ignores_stale_payload(
    monkeypatch,
):
    session = _typed_decision_session(selected_rule_ids=("LX0609-044",))
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed path must use the supplied evidence session")
        ),
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        # 与同一 session 材料冲突：旧 payload 明确声称缺少输血前评估。
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "明确未记录输血前评估。"}],
            blood_application=[],
            daily_course_record=[],
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-044",),
    )

    assert result.results == ()
    assert result.llm_call_count == 0
    assert [item.rule_id for item in result.decisions] == ["LX0609-044"]
    assert (
        reduce_luxian_0609_rule_decision(result.decisions[0]).final_state.value
        == "compliant"
    )
    assert result.decisions[0].snapshot_hash == session.snapshot.snapshot_hash
    assert "明确未记录输血前评估" not in repr(result)


@pytest.mark.asyncio
async def test_typed_044_material_change_changes_state_snapshot_and_refs(monkeypatch):
    complete_session = _typed_decision_session(selected_rule_ids=("LX0609-044",))
    missing_session = _typed_decision_session(
        selected_rule_ids=("LX0609-044",),
        bloodtrans_content="输血过程中患者生命体征平稳。",
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    common = {
        "rule_ids": ("LX0609-044",),
        "wrapper_rules": [_wrapper("LX0609-044")],
        "evidence_payload": _documents(
            bloodtrans_record=[{"content": "输血前评估完整且风险已说明。"}]
        ),
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "llm_client": None,
        "decision_rule_ids": ("LX0609-044",),
    }

    complete = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        evidence_snapshot=complete_session.snapshot,
        evidence_materials=complete_session.materials,
    )
    missing = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        evidence_snapshot=missing_session.snapshot,
        evidence_materials=missing_session.materials,
    )

    assert reduce_luxian_0609_rule_decision(
        complete.decisions[0]
    ).final_state.value == "compliant"
    assert reduce_luxian_0609_rule_decision(
        missing.decisions[0]
    ).final_state.value == "non_compliant"
    assert complete.decisions[0].snapshot_hash != missing.decisions[0].snapshot_hash
    assert complete.decisions[0].fact_refs != missing.decisions[0].fact_refs


@pytest.mark.parametrize(
    ("source_mode", "expected_state", "expected_reason"),
    (
        ("available", "non_compliant", "requirement_violated"),
        ("empty", "not_applicable", "trigger_absent_complete"),
        ("unavailable", "data_gap", "source_unavailable"),
        ("error", "technical_error", "source_query_error"),
    ),
)
@pytest.mark.asyncio
async def test_typed_044_dedicated_fact_precedes_auxiliary_source_four_states(
    monkeypatch,
    source_mode,
    expected_state,
    expected_reason,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "daily_course_record" and source_mode == "unavailable":
            raise SourceEvidenceUnavailable("private unavailable detail")
        if source_key == "daily_course_record" and source_mode == "error":
            raise SourceEvidenceQueryError("private query detail")
        if source_mode == "empty" and source_key in {
            "mr_bloodtrans",
            "bloodtrans_record",
        }:
            rows = []
        else:
            rows = {
                "mr_bloodtrans": [
                    {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
                ],
                "bloodtrans_record": [
                    {
                        "record_content": (
                            "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                            "结束时间16:10。输血过程中严密观察，未见不良反应。"
                        )
                    }
                ],
                "daily_course_record": [
                    {"record_content": "输血后继续观察，生命体征平稳。"}
                ],
            }[source_key]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-044",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no fallback")),
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-044",),
    )
    decision = result.decisions[0]

    assert reduce_luxian_0609_rule_decision(decision).final_state.value == expected_state
    assert decision.reason_code == expected_reason
    assert result.llm_call_count == 0
    assert "private unavailable detail" not in repr(result)
    assert "private query detail" not in repr(result)


@pytest.mark.asyncio
async def test_typed_044_optional_llm_keeps_raw_call_token_and_state_semantics(
    monkeypatch,
):
    grey_content = "输血前评估记录：患者存在输血指征，其他风险资料待结合判断。"
    session = _typed_decision_session(
        selected_rule_ids=("LX0609-044",),
        bloodtrans_content=grey_content,
        daily_content="输血后继续观察。",
    )
    payload = _documents(
        bloodtrans_record=[{"content": grey_content}],
        blood_application=[],
        daily_course_record=[{"content": "输血后继续观察。"}],
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    raw_client = _Client([{"is_compliant": False}])
    typed_client = _Client([{"is_compliant": False}])
    common = {
        "rule_ids": ("LX0609-044",),
        "wrapper_rules": [_wrapper("LX0609-044")],
        "evidence_payload": payload,
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
    }

    raw = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        llm_client=raw_client,
    )
    typed = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        llm_client=typed_client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-044",),
    )

    assert raw.results[0]["status"] == "non_compliant"
    assert reduce_luxian_0609_rule_decision(
        typed.decisions[0]
    ).final_state.value == "non_compliant"
    assert typed.results == ()
    assert raw.llm_call_count == typed.llm_call_count == 1
    assert raw.total_tokens == typed.total_tokens == 110
    assert raw_client.prompts == typed_client.prompts


@pytest.mark.asyncio
async def test_remaining_transfusion_typed_scope_is_ordered_and_fails_closed(
    monkeypatch,
):
    selected = (
        "LX0609-041",
        "LX0609-042",
        "LX0609-043",
        "LX0609-044",
        "LX0609-048",
        "LX0609-049",
    )

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ],
            "bloodtrans_record": [
                {
                    "record_content": (
                        "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，未见不良反应。"
                    )
                }
            ],
            "daily_course_record": [
                {"record_content": "输血后继续观察，生命体征平稳。"}
            ],
        }.get(source_key, [])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no legacy read")),
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([{"is_compliant": True}] * len(selected)),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert result.planned_rule_ids == selected
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    states = {
        item.rule_id: reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    }
    assert states == {
        "LX0609-041": "data_gap",
        "LX0609-042": "data_gap",
        "LX0609-043": "data_gap",
        "LX0609-044": "non_compliant",
        "LX0609-048": "not_applicable",
        "LX0609-049": "data_gap",
    }
    bound = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )
    assert all(item.final_state.value != "technical_error" for item in bound)
    assert "输血目的" not in repr(result)


@pytest.mark.asyncio
async def test_remaining_typed_rules_do_not_promote_proxy_sources_or_call_model():
    selected = (
        "LX0609-041",
        "LX0609-042",
        "LX0609-043",
        "LX0609-048",
        "LX0609-049",
    )
    private_marker = "PRIVATE_TRANSFUSION_PROXY_MARKER"

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ],
            "bloodtrans_record": [
                {
                    "record_content": (
                        "输注去白悬浮红细胞2U，过程平稳。"
                        f"{private_marker}"
                    )
                }
            ],
            # 该条是手术同意书代理来源，不得当作输血同意书。
            "consent_form": [
                {"record_content": "手术治疗知情同意书，患者已签字。"}
            ],
            "exam_item_report": [
                {"record_content": "检验结果摘要，无版本化输血九项清单。"}
            ],
            "daily_course_record": [
                {"record_content": "病程中记录了输血后观察。"}
            ],
            "postsurg_firstcourse_record": [{"record_content": "首次病程记录。"}],
            "mr_surgery": [{"record_content": "手术结构化摘要。"}],
            "first_course_record": [
                {"record_content": "术后首次病程记录。"}
            ],
            "presurg_discussion": [{"record_content": "术前讨论。"}],
            "presurg_summary": [{"record_content": "术前小结。"}],
            "senior_course_record": [{"record_content": "上级医师查房。"}],
            "surgery_record": [{"record_content": "手术记录。"}],
            "medical_order": [{"record_content": "通用医嘱投影。"}],
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{"is_compliant": True}] * len(selected))

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["data_gap", "data_gap", "data_gap", "not_applicable", "data_gap"]
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []
    assert private_marker not in repr(result)


@pytest.mark.asyncio
async def test_remaining_typed_rules_are_not_applicable_only_after_complete_no_transfusion():
    selected = (
        "LX0609-041",
        "LX0609-042",
        "LX0609-043",
        "LX0609-048",
        "LX0609-049",
    )

    def read(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["not_applicable"] * len(selected)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_remaining_typed_rules_surface_shared_trigger_query_error_without_echo():
    selected = (
        "LX0609-041",
        "LX0609-042",
        "LX0609-043",
        "LX0609-048",
        "LX0609-049",
    )
    private_error = "PRIVATE SQL Bearer_secret 13800138000"

    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "mr_bloodtrans":
            raise SourceEvidenceQueryError(private_error)
        rows = (
            [{"record_content": "实际输血记录，输注红细胞2U。"}]
            if source_key == "bloodtrans_record"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=selected,
    )

    assert result.results == ()
    assert [
        reduce_luxian_0609_rule_decision(item).final_state.value
        for item in result.decisions
    ] == ["technical_error"] * len(selected)
    assert all(item.reason_code == "source_query_error" for item in result.decisions)
    assert result.llm_call_count == result.total_tokens == 0
    assert private_error not in repr(result)


@pytest.mark.parametrize(
    ("failure_mode", "expected_state", "expected_reason"),
    (
        ("truncated", "data_gap", "source_unavailable"),
        ("query_error", "technical_error", "source_query_error"),
    ),
)
@pytest.mark.asyncio
async def test_typed_transfusion_material_failures_do_not_fallback_to_payload(
    monkeypatch,
    failure_mode,
    expected_state,
    expected_reason,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "bloodtrans_record" and failure_mode == "query_error":
            raise SourceEvidenceQueryError("private query failure")
        rows_by_source = {
            "mr_bloodtrans": [
                {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
            ],
            "bloodtrans_record": [
                {"record_content": "输血过程中患者生命体征平稳。"}
            ],
            "daily_course_record": [
                {"record_content": "输血后继续观察，患者生命体征平稳。"}
            ],
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source[source_key],
            truncated=(
                failure_mode == "truncated" and source_key == "bloodtrans_record"
            ),
            limit_rows=1,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-045",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no fallback read")),
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-045",),
    )
    reduced = reduce_luxian_0609_rule_decision(result.decisions[0])

    assert reduced.final_state.value == expected_state
    assert result.decisions[0].reason_code == expected_reason
    assert result.llm_call_count == 0
    assert "private query failure" not in repr(result)


@pytest.mark.asyncio
async def test_transfusion_trigger_consumes_shared_material_without_live_reader(
    monkeypatch,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                {
                    "document_id": "private-transfusion-id",
                    "record_content": "输血记录正文，记录实际输注过程及观察情况。",
                    "record_time": "2026-01-01 10:00:00",
                }
            ]
            if source_key == "bloodtrans_record"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-041",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("mr_bloodtrans", "bloodtrans_record"),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared material path must not query")
        ),
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041",),
        wrapper_rules=[_wrapper("LX0609-041")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
    )

    assert result.results[0]["status"] == "data_gap"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "consent_source_unavailable"
    )


@pytest.mark.asyncio
async def test_transfusion_truncated_shared_trigger_source_is_data_gap(monkeypatch):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        truncated = source_key == "mr_bloodtrans"
        rows = ([{"transfution_datetime": None}] if truncated else [])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=truncated,
            limit_rows=1 if truncated else 50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-041",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("mr_bloodtrans", "bloodtrans_record"),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared material path must not query")
        ),
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041",),
        wrapper_rules=[_wrapper("LX0609-041")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_materials=session.materials,
    )

    assert result.results[0]["status"] == "data_gap"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "transfusion_source_unavailable"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_no_dedicated_transfusion_source_rows_returns_not_applicable_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", lambda **_: [])
    client = _Client([])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=transfusion.TRANSFUSION_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(
            bloodtrans_record=[],
            daily_course_record=[{"content": "普通病程仅提到拟输血和备血。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 9
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_dedicated_record_keeps_customer_order_and_only_semantic_rules_call_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client(
        [
            {"is_compliant": True},
            {"is_compliant": False},
            {"is_compliant": True},
            {"is_compliant": True},
            {"is_compliant": False},
            {"is_compliant": True},
        ]
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=tuple(reversed(transfusion.TRANSFUSION_RULE_IDS)),
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日16:10输注完毕。"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    )
                }
            ]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == list(transfusion.TRANSFUSION_RULE_IDS)
    assert [item["status"] for item in result.results] == [
        "data_gap",
        "data_gap",
        "data_gap",
        "compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "not_applicable",
        "data_gap",
    ]
    assert result.llm_call_count == 1
    assert result.total_tokens == 110
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_typed_transfusion_event_triggers_but_shell_record_fails_closed(monkeypatch):
    def _typed_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "mr_bloodtrans":
            return [{"transfution_datetime": datetime(2026, 6, 5, 14, 20)}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _typed_reader)
    client = _Client([{"is_compliant": True}])
    typed = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(bloodtrans_record=[{"content": "空模板"}]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )
    assert typed.results[0]["status"] == "compliant"
    assert typed.llm_call_count == 1

    def _shell_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "bloodtrans_record":
            return [{"record_content": "空模板"}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _shell_reader)
    shell = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert shell.results[0]["status"] == "data_gap"
    assert shell.llm_call_count == 0


@pytest.mark.asyncio
async def test_045_substantive_dedicated_course_record_is_compliant_without_model(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": False}])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                        "未见寒战、发热及其他输血不良反应。"
                    )
                }
            ],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_course_record_present"
    )
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_045_typed_shadow_returns_bound_decision_instead_of_raw_result(
    monkeypatch,
):
    session = _typed_decision_session(selected_rule_ids=("LX0609-045",))
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed path must reuse the evidence session")
        ),
    )
    client = _Client([])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                        "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                        "未见寒战、发热及其他输血不良反应。"
                    )
                }
            ]
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-045",),
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == ["LX0609-045"]
    assert result.decisions[0].snapshot_hash == session.snapshot.snapshot_hash
    assert result.decisions[0].reason_code == "requirement_satisfied"
    assert result.decisions[0].fact_refs
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.parametrize(
    ("rule_id", "payload", "outputs", "performed", "expected_status"),
    (
        (
            "LX0609-045",
            _documents(
                bloodtrans_record=[
                    {
                        "content": (
                            "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                            "结束时间16:10。输血过程中严密观察，未见不良反应。"
                        )
                    }
                ]
            ),
            [],
            True,
            "compliant",
        ),
        (
            "LX0609-045",
            _documents(
                bloodtrans_record=[
                    {"content": "患者已完成输血治疗，过程资料记录较为简略。"}
                ]
            ),
            [{"is_compliant": False}],
            True,
            "non_compliant",
        ),
        (
            "LX0609-045",
            _documents(daily_course_record=[]),
            [],
            True,
            "data_gap",
        ),
        (
            "LX0609-046",
            _documents(
                bloodtrans_record=[
                    {
                        "content": (
                            "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
                            "结束时间16:10。输血过程中严密观察，未见不良反应。"
                        )
                    }
                ]
            ),
            [],
            True,
            "compliant",
        ),
        (
            "LX0609-046",
            _documents(
                bloodtrans_record=[
                    {"content": "输血目的：纠正贫血；输注红细胞，过程平稳。"}
                ]
            ),
            [{"is_compliant": False}],
            True,
            "non_compliant",
        ),
        (
            "LX0609-046",
            _documents(daily_course_record=[]),
            [],
            True,
            "data_gap",
        ),
        (
            "LX0609-047",
            _documents(
                bloodtrans_record=[
                    {
                        "content": (
                            "2026-01-01 16:10 输血结束后评价未见异常，"
                            "生命体征平稳，无输血不良反应。"
                        )
                    }
                ]
            ),
            [],
            True,
            "compliant",
        ),
        (
            "LX0609-047",
            _documents(
                bloodtrans_record=[
                    {"content": "2026-01-01 16:10 输血结束。"}
                ],
                daily_course_record=[{"content": "患者继续观察治疗。"}],
            ),
            [],
            True,
            "non_compliant",
        ),
        (
            "LX0609-047",
            _documents(
                bloodtrans_record=[{"content": "输血结束，继续观察。"}],
            ),
            [],
            True,
            "data_gap",
        ),
        (
            "LX0609-047",
            _documents(bloodtrans_record=[], daily_course_record=[]),
            [],
            False,
            "not_applicable",
        ),
    ),
)
@pytest.mark.asyncio
async def test_typed_045_047_preserves_raw_state_order_and_model_usage(
    monkeypatch,
    rule_id,
    payload,
    outputs,
    performed,
    expected_status,
):
    payload_documents = payload["programmatic_timeline"]["documents"]

    def first_content(source_key: str) -> str:
        rows = payload_documents.get(source_key) or ()
        return str(rows[0].get("content") or "") if rows else ""

    session = _typed_decision_session(
        selected_rule_ids=(rule_id,),
        performed=performed,
        bloodtrans_content=first_content("bloodtrans_record"),
        daily_content=first_content("daily_course_record"),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("same evidence session must serve both paths")
        ),
    )
    raw_client = _Client(list(outputs))
    typed_client = _Client(list(outputs))
    common = {
        "rule_ids": (rule_id,),
        "wrapper_rules": [_wrapper(rule_id)],
        "evidence_payload": payload,
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "evidence_materials": session.materials,
    }

    raw = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        llm_client=raw_client,
    )
    typed = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        llm_client=typed_client,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=(rule_id,),
    )
    reduced = reduce_luxian_0609_rule_decision(typed.decisions[0])

    assert [item["status"] for item in raw.results] == [expected_status]
    assert typed.results == ()
    assert [item.rule_id for item in typed.decisions] == [rule_id]
    assert reduced.final_state.value == expected_status
    assert typed.planned_rule_ids == raw.planned_rule_ids == (rule_id,)
    assert typed.llm_call_count == raw.llm_call_count
    assert typed.prompt_tokens == raw.prompt_tokens
    assert typed.completion_tokens == raw.completion_tokens
    assert typed.total_tokens == raw.total_tokens
    assert typed.api_time == raw.api_time
    assert typed_client.prompts == raw_client.prompts
    assert "private" not in repr(typed.decisions).lower()
    assert "输血目的" not in repr(typed.decisions)


@pytest.mark.asyncio
async def test_typed_transfusion_session_and_refs_fail_closed(monkeypatch):
    session = _typed_decision_session(selected_rule_ids=("LX0609-045",))
    other_session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-045",),
        institute_id="OTHER-I",
        patient_id="OTHER-P",
        visit_id="OTHER-V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=lambda **kwargs: SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=[],
            truncated=False,
            limit_rows=50,
        ),
    )
    monkeypatch.setattr(
        transfusion,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    common = {
        "rule_ids": ("LX0609-045",),
        "wrapper_rules": [_wrapper("LX0609-045")],
        "evidence_payload": _documents(),
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "source_schema": None,
        "llm_client": _Client([]),
        "decision_rule_ids": ("LX0609-045",),
    }

    with pytest.raises(ValueError, match="one evidence session"):
        await transfusion.execute_luxian_0609_native_transfusion_rules(
            **common,
            evidence_snapshot=session.snapshot,
            evidence_materials=other_session.materials,
        )

    typed = await transfusion.execute_luxian_0609_native_transfusion_rules(
        **common,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    forged = replace(typed.decisions[0], fact_refs=("f" * 64,))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(forged,),
        expected_rule_ids=("LX0609-045",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state.value == "technical_error"
    assert reduced[0].reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
async def test_046_each_complete_dedicated_record_is_compliant_without_model(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": False}])

    complete_rows = [
        {
            "content": (
                "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
                "结束时间16:10。输血过程中严密观察，生命体征平稳，"
                "未见寒战、发热及其他输血不良反应。"
            )
        },
        {
            "content": (
                "输血指征：凝血功能异常；开始时间18:00，输注血浆200ml，"
                "结束时间19:00。输注过程中严密观察，过程顺利，"
                "未见皮疹、胸闷及输血反应。"
            )
        },
    ]
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-046",),
        wrapper_rules=[_wrapper("LX0609-046")],
        evidence_payload=_documents(
            bloodtrans_record=complete_rows,
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_course_record_complete"
    )
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_046_incomplete_or_cross_record_fields_keep_exactly_one_cropped_model_call(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-046",),
        wrapper_rules=[_wrapper("LX0609-046")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；开始时间14:20，结束时间16:10。"
                        "输血过程中严密观察，未见寒战及输血不良反应。"
                    )
                },
                {
                    "content": (
                        "输注去白悬浮红细胞2U，开始时间18:00，结束时间19:00。"
                        "过程顺利，未见皮疹及输血反应。"
                    )
                },
            ],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_customer_prompt"
    )
    assert result.results[0]["metadata"]["executor_type"] == "llm"
    assert result.llm_call_count == 1
    assert result.total_tokens == 110
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_missing_consent_projection_is_data_gap_and_other_rules_are_not_blocked(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041", "LX0609-042", "LX0609-045"),
        wrapper_rules=[_wrapper("LX0609-041"), _wrapper("LX0609-042"), _wrapper("LX0609-045")],
        evidence_payload=_documents(consent_form=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap", "compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_dedicated_record_precedes_missing_daily_projection_for_044_047(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])

    complete_record = {
        "content": (
            "输血目的：纠正贫血；输血前评估：患者血红蛋白下降，存在输血指征，"
            "已说明输血风险。2026年6月5日14:20开始输注红细胞2U，"
            "2026年6月5日16:10输血结束。输血过程中严密观察，生命体征平稳，"
            "未见发热及输血不良反应。输血后复查血红蛋白改善。"
        )
    }

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044", "LX0609-045", "LX0609-046", "LX0609-047"),
        wrapper_rules=[
            _wrapper("LX0609-044"),
            _wrapper("LX0609-045"),
            _wrapper("LX0609-046"),
            _wrapper("LX0609-047"),
        ],
        evidence_payload=_documents(
            bloodtrans_record=[complete_record],
            blood_application=[],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant"] * 4
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_dedicated_record_proves_044_046_defects_before_daily_projection(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])
    record_without_purpose = {
        "content": (
            "2026年6月5日14:20开始输注红细胞2U，"
            "2026年6月5日16:10输血结束。"
            "输血过程中严密观察，生命体征平稳，未见发热及输血不良反应。"
        )
    }

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044", "LX0609-046", "LX0609-047"),
        wrapper_rules=[
            _wrapper("LX0609-044"),
            _wrapper("LX0609-046"),
            _wrapper("LX0609-047"),
        ],
        evidence_payload=_documents(
            bloodtrans_record=[record_without_purpose],
            blood_application=[],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results[:2]] == [
        "non_compliant",
        "non_compliant",
    ]
    assert result.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert result.results[1]["metadata"]["reason_code"] == (
        "transfusion_purpose_or_indication_missing"
    )
    assert result.results[2]["status"] == "non_compliant"
    assert result.results[2]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_missing"
    )
    assert dict(result.customer_display_facts) == {
        "LX0609-044": {
            "failure_kind": "transfusion_requirement_not_documented",
            "requirement": "pretransfusion_assessment",
            "checked_sources": [
                "bloodtrans_record", "blood_application", "course_record",
            ],
        },
        "LX0609-046": {
            "failure_kind": "transfusion_requirement_not_documented",
            "requirement": "purpose_or_indication",
            "checked_sources": ["bloodtrans_record"],
        },
        "LX0609-047": {
            "failure_kind": "transfusion_requirement_not_documented",
            "requirement": "posttransfusion_evaluation",
            "checked_sources": ["bloodtrans_record", "course_record"],
        },
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_047_missing_authoritative_end_stays_data_gap_without_daily_projection(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血结束，继续观察，未见输血不良反应。"}],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_043_incomplete_test_contract_is_data_gap_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": False}])

    for lab_documents in (
        {
            "labtest_master": [
                {"content": "仅有检验主单和检验科室，缺少项目、结果和报告时间。"}
            ],
            "labtest_item_report": [],
        },
        {
            "labtest_master": [{"content": "输血前检验主单。"}],
            "labtest_item_report": [
                {
                    "content": (
                        "叙述声称输血前九项齐全，但没有版本化项目清单、"
                        "结构化结果和可比报告时间。"
                    )
                }
            ],
        },
    ):
        result = await transfusion.execute_luxian_0609_native_transfusion_rules(
            rule_ids=("LX0609-043",),
            wrapper_rules=[_wrapper("LX0609-043")],
            evidence_payload=_documents(**lab_documents),
            institute_id="safe-institute",
            patient_id="safe-patient",
            visit_id="safe-visit",
            source_schema=None,
            llm_client=client,
        )

        assert result.results[0]["status"] == "data_gap"
        assert (
            result.results[0]["metadata"]["reason_code"]
            == "pretransfusion_item_contract_unavailable"
        )
        assert result.results[0]["metadata"]["executor_type"] == "program"
        assert result.llm_call_count == 0
        assert result.total_tokens == 0

    assert client.prompts == []


@pytest.mark.asyncio
async def test_047_posttransfusion_evaluation_is_deterministic_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    same_record = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日16:10输注完毕。"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    )
                }
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "普通病程：继续观察一般情况。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert same_record.results[0]["status"] == "compliant"
    assert same_record.results[0]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_complete"
    )
    assert same_record.results[0]["metadata"]["executor_type"] == "program"
    assert same_record.llm_call_count == 0

    later_course = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "2026-06-05 16:10输血结束，输注过程顺利。"}
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "输血后复查血红蛋白上升，症状改善。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert later_course.results[0]["status"] == "compliant"
    assert later_course.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "end_text",
    [
        "2026-06-05 16:10:00+08输血结束",
        "2026-06-05 16:10:00+08:00输血结束",
        "2026-06-05 16:10输血结束后",
        "2026年6月5日16:10输注完毕后",
    ],
)
async def test_047_accepts_controlled_timezone_and_postposition_forms(
    monkeypatch, end_text
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        f"{end_text}，复查血红蛋白较前改善，"
                        "未见输血不良反应。"
                    )
                }
            ],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "compliant"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected_status"),
    [
        (
            (
                "2026-06-05 10:00输血结束。未记录输血后评价。"
                "2026-06-05 16:00输血结束。输血后复查血红蛋白改善。"
            ),
            "non_compliant",
        ),
        (
            (
                "2026-06-05 10:00输血结束。输血后复查血红蛋白改善。"
                "2026-06-05 16:00输血结束。未记录输血后评价。"
            ),
            "non_compliant",
        ),
        (
            (
                "2026-06-05 10:00输血结束，过程顺利。"
                "2026-06-05 16:00输血结束。输血后复查血红蛋白改善。"
            ),
            "compliant",
        ),
    ],
)
async def test_047_allows_final_summary_but_preserves_explicit_missing_statement(
    monkeypatch, content, expected_status
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": content}],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evaluation_text", "expected_status"),
    [
        ("未见输血后评价异常。", "compliant"),
        ("无输血后评价异常。", "compliant"),
        ("输血后评价未见异常。", "compliant"),
        ("未记录输血后评价。", "non_compliant"),
        ("缺少输血后评价。", "non_compliant"),
        ("未书写输血后评价。", "non_compliant"),
    ],
)
async def test_047_distinguishes_normal_evaluation_from_missing_documentation(
    monkeypatch, evaluation_text, expected_status
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": f"2026-06-05 16:10输血结束。{evaluation_text}"}
            ],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_rejects_pre_end_or_unrelated_observation_and_requires_end_time(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    no_post_evaluation = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日15:30观察生命体征平稳，"
                        "2026年6月5日16:10输注完毕。"
                    )
                }
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "普通病程：生命体征平稳，继续观察。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert no_post_evaluation.results[0]["status"] == "non_compliant"
    assert no_post_evaluation.results[0]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_missing"
    )
    assert no_post_evaluation.llm_call_count == 0

    missing_end_time = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "输注完毕后复查血红蛋白上升，症状改善。"}
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "输血后复查血红蛋白上升，症状改善。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert missing_end_time.results[0]["status"] == "data_gap"
    assert missing_end_time.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )
    assert missing_end_time.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_rejects_planned_time_weak_context_and_unresolved_end_rows(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    async def _execute(
        *, blood_rows: list[dict], daily_rows: list[dict]
    ) -> transfusion.NativeTransfusionExecutionResult:
        return await transfusion.execute_luxian_0609_native_transfusion_rules(
            rule_ids=("LX0609-047",),
            wrapper_rules=[_wrapper("LX0609-047")],
            evidence_payload=_documents(
                bloodtrans_record=blood_rows,
                daily_course_record=daily_rows,
            ),
            institute_id="safe-institute",
            patient_id="safe-patient",
            visit_id="safe-visit",
            source_schema=None,
            llm_client=_Client([]),
        )

    planned = await _execute(
        blood_rows=[
            {"content": "预计2026-06-05 16:10输血结束。生命体征平稳。"}
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert planned.results[0]["status"] == "data_gap"
    assert planned.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )

    document_time = await _execute(
        blood_rows=[
            {"content": "2026-06-05 16:10记录：输血结束。生命体征平稳。"}
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert document_time.results[0]["status"] == "data_gap"

    weak_context = await _execute(
        blood_rows=[{"content": "2026-06-05 16:10输血结束，输注过程顺利。"}],
        daily_rows=[
            {
                "record_time": datetime(2026, 6, 5, 18, 40),
                "content": "复查血小板正常，生命体征平稳。",
            }
        ],
    )
    assert weak_context.results[0]["status"] == "non_compliant"

    unresolved_row = await _execute(
        blood_rows=[
            {
                "content": (
                    "2026-06-05 10:00输血结束。"
                    "输血后复查血红蛋白改善。"
                )
            },
            {"content": "16:00输血结束。未记录输血后评价。"},
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert unresolved_row.results[0]["status"] == "data_gap"
    assert unresolved_row.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )

    one_of_two_missing = await _execute(
        blood_rows=[
            {
                "content": (
                    "2026-06-05 10:00输血结束。"
                    "输血后复查血红蛋白改善。"
                )
            },
            {
                "content": (
                    "2026-06-05 16:00输血结束。"
                    "未记录输血后评价。"
                )
            },
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert one_of_two_missing.results[0]["status"] == "non_compliant"
    assert planned.llm_call_count == weak_context.llm_call_count == 0
    assert document_time.llm_call_count == unresolved_row.llm_call_count == 0
    assert one_of_two_missing.llm_call_count == 0


@pytest.mark.asyncio
async def test_044_clear_pretransfusion_assessment_truth_is_deterministic_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    missing = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血记录：患者拟输注红细胞，输血过程中生命体征平稳，"
                        "记录血红蛋白检查结果，但未形成输血前评估。"
                    )
                }
            ],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：输血结束后继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert missing.results[0]["status"] == "non_compliant"
    assert missing.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_missing"
    assert missing.results[0]["metadata"]["executor_type"] == "program"
    assert missing.llm_call_count == 0

    complete = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：按评估及医嘱完成输注。"}],
            blood_application=[
                {
                    "document_title": "输血前评估记录",
                    "content": (
                        "患者贫血，血红蛋白降低，具有输血指征及必要性；"
                        "既往无输血不良反应，已评估输血风险和生命体征。"
                    )
                }
            ],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert complete.results[0]["status"] == "compliant"
    assert complete.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_complete"
    assert complete.results[0]["metadata"]["executor_type"] == "program"
    assert complete.llm_call_count == 0

    gray_client = _Client([{"is_compliant": True}])
    gray = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：已记录输血指征，输注过程平稳。"}],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：患者贫血，拟输注红细胞。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=gray_client,
    )
    assert gray.results[0]["status"] == "non_compliant"
    assert gray.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert gray.llm_call_count == 0
    assert gray_client.prompts == []

    split_client = _Client([{"is_compliant": False}])
    split = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血前评估：患者具有输血指征。"}],
            blood_application=[{"content": "患者贫血，血红蛋白降低。"}],
            daily_course_record=[{"content": "既往无输血不良反应，已说明风险。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=split_client,
    )
    assert split.results[0]["status"] == "non_compliant"
    assert split.results[0]["metadata"]["reason_code"] == "transfusion_customer_prompt"
    assert split.llm_call_count == 1

    application_client = _Client([{"is_compliant": True}])
    application_gray = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：按医嘱完成输注。"}],
            blood_application=[
                {
                    "document_title": "输血申请单",
                    "content": (
                        "患者血红蛋白降低，拟输红细胞；既往无不良反应，生命体征平稳。"
                    ),
                }
            ],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=application_client,
    )
    assert application_gray.results[0]["status"] == "compliant"
    assert application_gray.results[0]["metadata"]["reason_code"] == "transfusion_customer_prompt"
    assert application_gray.llm_call_count == 1


@pytest.mark.asyncio
async def test_044_same_record_purpose_without_assessment_marker_is_non_compliant(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血目的：纠正贫血；患者血红蛋白降低，"
                        "既往无输血不良反应，输注前生命体征平稳。"
                    )
                }
            ],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_044_transfusion_purpose_without_preassessment_is_non_compliant_without_llm(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "输血目的：纠正贫血；患者血红蛋白降低。"}
            ],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：继续观察治疗。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "pretransfusion_assessment_missing"
    )
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_048_dedicated_postop_course_omits_surgical_transfusion_is_defect(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-048",),
        wrapper_rules=[_wrapper("LX0609-048")],
        evidence_payload=_documents(
            surgery_record=[
                {"surgery_process": "术中出血约800ml，输注红细胞2U。"}
            ],
            anesthesia_record=[{"record_content": ""}],
            postsurg_firstcourse_record=[
                {"record_content": "术后患者生命体征平稳，切口敷料干燥。"}
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.results[0]["metadata"]["reason_code"] == (
        "postop_first_course_transfusion_omitted"
    )
    assert result.customer_display_facts == ((
        "LX0609-048",
        {
            "failure_kind": "transfusion_requirement_not_documented",
            "requirement": "postop_first_course_transfusion",
            "checked_sources": ["surgery_record", "postsurg_firstcourse_record"],
        },
    ),)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_048_without_credible_intraoperative_transfusion_is_not_applicable(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-048",),
        wrapper_rules=[_wrapper("LX0609-048")],
        evidence_payload=_documents(
            surgery_record=[{"record_content": "中心静脉置管术，过程顺利。"}],
            anesthesia_record=[],
            postsurg_firstcourse_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "not_applicable"
    assert result.results[0]["metadata"]["reason_code"] == (
        "intraoperative_transfusion_fact_absent"
    )
    assert result.results[0]["findings"] == "未发现可信的术中输血事实，本规则不适用。"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_conservative_transfusion_gaps_explain_missing_material_not_patient_defect(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    selected = ("LX0609-041", "LX0609-042", "LX0609-043", "LX0609-049")
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload=_documents(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 4
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "consent_source_unavailable",
        "consent_signature_contract_unavailable",
        "pretransfusion_item_contract_unavailable",
        "billing_linkage_source_unavailable",
    ]
    assert all(
        item["metadata"]["data_gap_kind"] == "system_data_contract_gap"
        and item["metadata"]["gap_owner"] == "system_integration"
        for item in result.results
    )
    customer_copy = " ".join(
        str(item[field])
        for item in result.results
        for field in ("findings", "suggestion")
    )
    assert "请补充患者资料" not in customer_copy
    assert "数据源" not in customer_copy
    assert "字段映射" not in customer_copy
    assert "契约" not in customer_copy
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_source_error_and_invalid_model_output_fail_closed_without_echo(monkeypatch):
    secret = "Bearer_secret_13800138000"

    def _failed_reader(**_: object) -> list[dict]:
        raise RuntimeError(secret)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _failed_reader)
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041", "LX0609-049"),
        wrapper_rules=[_wrapper("LX0609-041"), _wrapper("LX0609-049")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert secret not in repr(result)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    invalid = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-049",),
        wrapper_rules=[_wrapper("LX0609-049")],
        evidence_payload=_documents(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([f"not-json {secret}"]),
    )
    assert invalid.results[0]["status"] == "data_gap"
    assert secret not in repr(invalid)


def test_transfusion_consent_sources_never_alias_surgery_consent() -> None:
    for rule_id in ("LX0609-041", "LX0609-042"):
        assert "surgery_inform_consent" not in transfusion._typed_rule_source_keys(
            rule_id
        )
