import json

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609 import consultation_disposition_record as record


def response(*items):
    return {"content": json.dumps({"schema_version": record.SCHEMA_VERSION, "documents": [{
        "ref": "consultation_record-1", "items": list(items),
    }]}, ensure_ascii=False)}


def item(index, feedback, kind, referent=""):
    return dict(opinion_index=index, feedback_quote=feedback, feedback_kind=kind, referent_quote=referent)


def opinions(*quotes, scope="ordinary", state="present"):
    return {"content": json.dumps({"schema_version": record.SCHEMA_VERSION + "-opinions", "documents": [{
        "ref": "consultation_record-1", "scope": scope, "suggestion_state": state, "opinion_quotes": list(quotes),
    }]}, ensure_ascii=False)}


def documents(text):
    return [{"ref": "consultation_record-1", "time": "2026-07-20 15:59:00", "text": text,
             "document_id": "PRIVATE-ID-MUST-NOT-ENTER-PROMPT", "material_ref": "PRIVATE-MATERIAL"}]


class Client:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    async def generate(self, prompt):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def parse(docs, quotes, *items, scope="ordinary", state="present"):
    frozen = {"consultation_record-1": {
        "scope": scope, "suggestion_state": state, "opinion_quotes": quotes,
    }}
    return record.parse_facts(response(*items), docs, frozen)


@pytest.mark.parametrize("feedback", ["遵照执行", "以上已遵嘱执行", "其余遵会诊意见处理"])
def test_bare_following_advice_does_not_count(feedback):
    docs = documents("会诊建议：给予气压治疗。" + feedback)
    result = parse(docs, ["给予气压治疗"], item(1, feedback, "generic"))
    assert result == ("non_compliant", "requirement_violated", ("consultation_record-1",))


def test_every_recommendation_requires_its_own_specific_response():
    docs = documents("建议：完善痰培养、调整抗感染治疗。已完善痰培养，其余遵嘱。")
    result = parse(docs, ["完善痰培养", "调整抗感染治疗"],
        item(1, "已完善痰培养", "performed"), item(2, "其余遵嘱", "generic"))
    assert result[0] == "non_compliant"


@pytest.mark.parametrize("kind,feedback", [
    ("performed", "已停用原药并加用新药"),
    ("planned", "拟明日完善胸部CT"),
    ("declined", "患者拒绝检查，暂缓胸部CT"),
])
def test_concrete_handling_arrangement_and_reasoned_refusal_are_written_dispositions(kind, feedback):
    docs = documents("会诊建议：调整治疗并评估胸部CT。" + feedback)
    assert parse(docs, ["调整治疗并评估胸部CT"], item(1, feedback, kind))[0] == "compliant"


def test_unique_medication_reference_may_be_resolved_in_same_record():
    docs = documents("建议继续药物甲、药物乙治疗。遵会诊意见继续上述药物治疗。")
    result = parse(docs, ["继续药物甲、药物乙治疗"],
        item(1, "遵会诊意见继续上述药物治疗", "performed", "药物甲、药物乙"))
    assert result[0] == "compliant"


def test_opinion_cannot_be_claimed_as_concrete_feedback():
    docs = documents("建议给予气压治疗。遵照执行。")
    with pytest.raises(ValueError):
        parse(docs, ["建议给予气压治疗"], item(1, "给予气压治疗", "performed"))


@pytest.mark.parametrize("feedback", ["遵照执行", "已予具体用药，其余遵嘱执行"])
def test_generic_feedback_is_a_defect_even_if_model_labels_whole_paragraph_performed(feedback):
    docs = documents("建议完善痰培养、血气分析，给予祛痰治疗。" + feedback)
    assert parse(docs, ["完善痰培养"], item(1, feedback, "performed"))[0] == "non_compliant"


@pytest.mark.parametrize("quote_field", ["feedback_quote", "referent_quote"])
def test_all_feedback_quotes_must_be_grounded(quote_field):
    fact = item(1, "已完善痰培养", "performed")
    fact[quote_field] = "原文没有的内容"
    with pytest.raises(ValueError):
        parse(documents("建议完善痰培养。已完善痰培养。"), ["完善痰培养"], fact)


def test_first_stage_opinion_must_be_grounded():
    with pytest.raises(ValueError):
        record.parse_opinions(opinions("原文没有的建议"), documents("建议完善痰培养。"))


def test_missing_opinion_or_unknown_voice_is_data_gap_not_defect():
    docs = documents("遵照执行。")
    assert parse(docs, [], state="unavailable")[0] == "data_gap"
    assert parse(docs, [], scope="unknown", state="unavailable")[0] == "data_gap"
    assert parse(docs, [], scope="non_target", state="no_action")[0] == "not_applicable"


def test_shared_reason_and_parallel_actions_use_one_contiguous_feedback_sentence():
    text = "建议：血气分析、肺功能。现无气紧症状，暂不考虑血气分析、肺功能检查。"
    feedback = "现无气紧症状，暂不考虑血气分析、肺功能检查"
    result = parse(documents(text), ["血气分析", "肺功能"],
        item(1, feedback, "declined"), item(2, feedback, "declined"))
    assert result[0] == "compliant"


@pytest.mark.parametrize("indices", [(1, 1), (1, 3), (True, 2)])
def test_advice_indices_must_cover_the_frozen_list_exactly_once(indices):
    with pytest.raises(ValueError):
        parse(documents("建议：血气分析、肺功能。遵照执行。"), ["血气分析", "肺功能"],
            *(item(index, "遵照执行", "generic") for index in indices))


@pytest.mark.asyncio
async def test_two_stage_calls_are_bounded_and_unresolved_output_is_not_a_defect():
    docs = documents("建议完善痰培养。已完善痰培养。")
    client = Client(opinions("建议完善痰培养"), response(item(1, "已完善痰培养", "performed")))
    outcome = await record.check_disposition_record(documents=docs, llm_client=client)
    assert outcome.status == "compliant" and outcome.llm_call_count == 2
    assert "PRIVATE-ID" not in client.prompts[0] and "PRIVATE-MATERIAL" not in client.prompts[0]
    failed = await record.check_disposition_record(documents=docs, llm_client=Client(opinions("建议完善痰培养"), {"content": "bad"}))
    assert failed.status == "data_gap" and failed.llm_call_count == 2


@pytest.mark.asyncio
async def test_second_stage_cannot_drop_two_unrecorded_recommendations():
    docs = documents("建议完善痰培养、血气分析，给予祛痰治疗。已给予祛痰治疗，其余遵嘱。")
    client = Client(opinions("完善痰培养", "血气分析", "给予祛痰治疗"), response(
        item(3, "已给予祛痰治疗", "performed")))
    outcome = await record.check_disposition_record(documents=docs, llm_client=client)
    assert outcome.status == "data_gap" and outcome.reason == "semantic_extraction_unresolved"
    assert outcome.llm_call_count == 2 and "SUGGESTIONS_JSON" in client.prompts[1]


@pytest.mark.asyncio
async def test_first_stage_invalid_output_does_not_become_a_defect():
    outcome = await record.check_disposition_record(
        documents=documents("建议完善痰培养。"), llm_client=Client({"content": "bad"}))
    assert outcome.status == "data_gap" and outcome.llm_call_count == 1


def test_first_stage_rejects_a_whole_parallel_recommendation_list_as_one_action():
    docs = documents("建议完善痰培养、血气分析，给予祛痰治疗。已给予祛痰治疗。")
    with pytest.raises(ValueError):
        record.parse_opinions(opinions("完善痰培养、血气分析，给予祛痰治疗"), docs)


@pytest.mark.asyncio
async def test_new_rule_reads_only_execution_record_and_does_not_read_orders(monkeypatch):
    requested = []
    def read(*, source_key, **kwargs):
        requested.append(source_key)
        assert source_key == "consultation_record"
        return [{"document_title": "会诊执行记录", "record_time": "2026-07-20 15:59:00",
                 "record_content": "会诊建议给予气压治疗。以上已遵嘱执行。"}]
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", read)
    client = Client(opinions("给予气压治疗"), response(item(1, "以上已遵嘱执行", "generic")))
    execution = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=(record.RULE_ID,), institute_id="i", patient_id="p", visit_id="v",
        source_schema=None, llm_client=client)
    assert requested == ["consultation_record"]
    assert execution.results[0]["status"] == "non_compliant"
    assert execution.planned_rule_ids == (record.RULE_ID,)


def test_new_rule_is_registered_as_independent_writing_check():
    from app.services.luxian_0609.native_package import load_luxian_0609_dependency_inventory
    from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
    dependency = next(row for row in load_luxian_0609_dependency_inventory() if row.rule_id == record.RULE_ID)
    assert dependency.executor_key == "consultation_quality"
    assert dependency.applicable_documents == ("consultation_record",)
    contract = next(row for row in load_luxian_0609_rule_contracts() if row.rule_id == record.RULE_ID)
    assert contract.max_llm_calls_per_rule == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper_reference", [False, True])
async def test_new_rule_binds_record_evidence_and_renders_independent_customer_result(monkeypatch, tamper_reference):
    from app.services.luxian_0609.evidence_snapshot_provider import (
        SnapshotSourceRows, build_luxian_0609_evidence_read_session,
    )
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts

    source_keys = []
    def read(**kwargs):
        source_keys.append(kwargs["source_key"])
        assert kwargs["source_key"] == "consultation_record"
        return SnapshotSourceRows.create(source_key="consultation_record", rows=[{
            "document_id": "SYNTHETIC-DOCUMENT", "document_title": "会诊执行记录",
            "record_time": "2026-07-20 15:59:00", "record_content": "会诊建议给予气压治疗。以上已遵嘱执行。",
        }], truncated=False, limit_rows=48)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(record.RULE_ID,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-20T17:00:00+08:00", row_reader=read)
    if tamper_reference:
        real_documents = episode._documents
        def missing_material_reference(rows):
            result = real_documents(rows)
            for document in result:
                document.pop("material_ref", None)
            return result
        monkeypatch.setattr(episode, "_documents", missing_material_reference)
    outcome = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=(record.RULE_ID,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, evidence_materials=session.materials, evidence_snapshot=session.snapshot,
        decision_rule_ids=(record.RULE_ID,),
        llm_client=Client(opinions("给予气压治疗"), response(item(1, "以上已遵嘱执行", "generic"))))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=outcome.decisions, expected_rule_ids=(record.RULE_ID,), snapshot=session.snapshot,
        evidence_materials=session.materials)
    result = render_luxian_0609_customer_result(decision=reduced[0])
    assert source_keys == ["consultation_record"]
    assert result["status"] == ("technical_error" if tamper_reference else "non_compliant")
    if not tamper_reference:
        assert "处置记录不具体" in result["findings"] and reduced[0].fact_refs
    assert "SYNTHETIC-DOCUMENT" not in json.dumps(result, ensure_ascii=False)
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id=record.RULE_ID, raw=None, status="non_compliant", reason_code="requirement_violated") is None
