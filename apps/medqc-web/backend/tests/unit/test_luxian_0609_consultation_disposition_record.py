import json

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609 import consultation_disposition_record as record


def response(*items, medications=(), examinations=()):
    return {
        "content": json.dumps(
            {
                "schema_version": record.SCHEMA_VERSION,
                "documents": [
                    {
                        "ref": "consultation_record-1",
                        "medications": list(medications),
                        "examinations": list(examinations),
                        "therapies": list(items),
                        "other_actions": [],
                    }
                ],
            },
            ensure_ascii=False,
        )
    }


def item(action, feedback, kind, referent=""):
    return dict(
        action_quote=action,
        feedback_quote=feedback,
        feedback_kind=kind,
        referent_quote=referent,
    )


def opinions(opinion="", feedback="", scope="ordinary", state="present"):
    return {
        "content": json.dumps(
            {
                "schema_version": record.SCHEMA_VERSION + "-opinions",
                "documents": [
                    {
                        "ref": "consultation_record-1",
                        "scope": scope,
                        "suggestion_state": state,
                        "opinion_quotes": [opinion] if opinion else [],
                        "feedback_quotes": [feedback] if feedback else [],
                    }
                ],
            },
            ensure_ascii=False,
        )
    }


def documents(text):
    return [
        {
            "ref": "consultation_record-1",
            "time": "2026-07-20 15:59:00",
            "text": text,
            "document_id": "PRIVATE-ID-MUST-NOT-ENTER-PROMPT",
            "material_ref": "PRIVATE-MATERIAL",
        }
    ]


class Client:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    async def generate(self, prompt):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def parse(docs, opinion, feedback, *items, scope="ordinary", state="present"):
    frozen = record.parse_opinions(opinions(opinion, feedback, scope, state), docs)
    return record.parse_facts(response(*items), docs, frozen)


@pytest.mark.parametrize(
    "feedback", ["遵照执行", "以上已遵嘱执行", "其余遵会诊意见处理"]
)
def test_bare_following_advice_does_not_count(feedback):
    docs = documents("会诊建议：给予气压治疗。" + feedback)
    assert (
        parse(
            docs, "给予气压治疗", feedback, item("给予气压治疗", feedback, "generic")
        )[0]
        == "non_compliant"
    )


def test_each_action_requires_its_own_disposition():
    docs = documents("建议完善痰培养、调整药物。已完善痰培养，其余遵嘱。")
    assert (
        parse(
            docs,
            "建议完善痰培养、调整药物",
            "已完善痰培养，其余遵嘱",
            item("完善痰培养", "已完善痰培养", "performed"),
            item("调整药物", "其余遵嘱", "generic"),
        )[0]
        == "non_compliant"
    )


@pytest.mark.parametrize(
    "kind,feedback",
    [
        ("performed", "已停用原药并加用新药"),
        ("planned", "拟明日完善胸部CT"),
        ("declined", "患者拒绝检查，暂缓胸部CT"),
    ],
)
def test_specific_handling_arrangement_and_reasoned_refusal_count(kind, feedback):
    docs = documents("建议调整治疗并评估胸部CT。" + feedback)
    assert (
        parse(
            docs,
            "建议调整治疗并评估胸部CT",
            feedback,
            item("调整治疗并评估胸部CT", feedback, kind),
        )[0]
        == "compliant"
    )


def test_unique_above_medication_reference_counts():
    docs = documents("建议继续药物甲、药物乙治疗。遵会诊意见继续上述药物治疗。")
    assert (
        parse(
            docs,
            "建议继续药物甲、药物乙治疗",
            "遵会诊意见继续上述药物治疗",
            item(
                "继续药物甲、药物乙治疗",
                "遵会诊意见继续上述药物治疗",
                "performed",
                "药物甲、药物乙",
            ),
        )[0]
        == "compliant"
    )


def test_opinion_cannot_prove_its_own_disposition():
    docs = documents("建议给予气压治疗。遵照执行。")
    assert (
        parse(
            docs,
            "建议给予气压治疗",
            "给予气压治疗",
            item("给予气压治疗", "给予气压治疗", "performed"),
        )[0]
        == "data_gap"
    )


def test_a_consultants_generic_instruction_is_not_requesting_department_feedback():
    docs = documents("会诊医师要求遵照执行。")
    assert (
        parse(
            docs,
            "会诊医师要求遵照执行",
            "遵照执行",
            item("遵照执行", "遵照执行", "generic"),
        )[0]
        == "data_gap"
    )


@pytest.mark.parametrize(
    "feedback",
    ["遵照执行", "已予具体用药，其余遵嘱执行", "处理:予以康复理疗。", "对症康复治疗。"],
)
def test_generic_text_cannot_be_relabelled_as_specific(feedback):
    docs = documents("建议给予电针。" + feedback)
    assert (
        parse(docs, "建议给予电针", feedback, item("给予电针", feedback, "performed"))[
            0
        ]
        == "non_compliant"
    )


@pytest.mark.parametrize("field", ["feedback_quote", "referent_quote"])
def test_feedback_and_referents_must_be_source_grounded(field):
    docs = documents("建议完善痰培养。已完善痰培养。")
    fact = item("完善痰培养", "已完善痰培养", "performed")
    fact[field] = "原文没有的内容"
    assert parse(docs, "建议完善痰培养", "已完善痰培养", fact)[0] == "data_gap"


def test_feedback_cannot_become_a_consultant_recommendation():
    docs = documents("会诊建议完善痰培养。我科处理：拟加用药物甲。")
    assert (
        parse(
            docs,
            "会诊建议完善痰培养",
            "拟加用药物甲",
            item("拟加用药物甲", "", "missing"),
        )[0]
        == "data_gap"
    )


@pytest.mark.parametrize(
    "bad",
    [
        item("完善痰培养", "", "generic"),
        item("完善痰培养", "不存在的反馈", "performed"),
    ],
)
def test_unverified_item_does_not_erase_an_independent_defect(bad):
    docs = documents("建议完善痰培养、调整药物。已处理。")
    assert (
        parse(
            docs,
            "建议完善痰培养、调整药物",
            "已处理",
            bad,
            item("调整药物", "", "missing"),
        )[0]
        == "non_compliant"
    )


def test_only_unverified_feedback_is_data_gap():
    assert (
        parse(
            documents("建议完善痰培养。"),
            "建议完善痰培养",
            "",
            item("完善痰培养", "", "generic"),
        )[0]
        == "data_gap"
    )


def test_a_new_plan_only_in_department_feedback_is_outside_the_consultant_checklist():
    docs = documents("会诊建议完善动态心电图。处理：已完善动态心电图，建议动态随访。")
    assert (
        parse(
            docs,
            "会诊建议完善动态心电图",
            "已完善动态心电图，建议动态随访",
            item("完善动态心电图", "已完善动态心电图", "performed"),
            item("建议动态随访", "建议动态随访", "planned"),
        )[0]
        == "compliant"
    )


def test_overlapping_role_quotes_cannot_turn_a_requester_plan_into_a_defect():
    docs = documents("会诊建议完善痰培养。我科拟加用药物甲。")
    assert (
        parse(
            docs,
            "会诊建议完善痰培养。我科拟加用药物甲。",
            "我科拟加用药物甲。",
            item("拟加用药物甲", "", "missing"),
        )[0]
        == "data_gap"
    )


def test_role_quotes_must_be_grounded():
    with pytest.raises(ValueError):
        record.parse_opinions(opinions("不存在的原话"), documents("建议完善痰培养。"))


def test_source_gap_or_unknown_role_is_not_a_clinical_defect():
    docs = documents("遵照执行。")
    assert parse(docs, "", "", state="unavailable")[0] == "data_gap"
    assert parse(docs, "", "", scope="unknown", state="unavailable")[0] == "data_gap"
    assert (
        parse(docs, "", "", scope="non_target", state="no_action")[0]
        == "not_applicable"
    )


def test_missing_extracted_actions_is_unresolved_not_compliant():
    assert parse(documents("建议完善痰培养。"), "建议完善痰培养", "")[0] == "data_gap"


def test_treatment_purpose_punctuation_is_not_rejected():
    quote = "超声波治疗以舒经通络、促进恢复"
    docs = documents("建议" + quote + "。遵照执行。")
    assert (
        parse(docs, quote, "遵照执行", item(quote, "遵照执行", "generic"))[0]
        == "non_compliant"
    )


@pytest.mark.asyncio
async def test_two_stages_remain_bounded_and_do_not_send_internal_identity():
    docs = documents("建议完善痰培养。已完善痰培养。")
    client = Client(
        opinions("建议完善痰培养", "已完善痰培养"),
        response(item("完善痰培养", "已完善痰培养", "performed")),
    )
    result = await record.check_disposition_record(documents=docs, llm_client=client)
    assert result.status == "compliant" and result.llm_call_count == 2
    assert all(
        "PRIVATE-ID" not in p and "PRIVATE-MATERIAL" not in p for p in client.prompts
    )
    broken = await record.check_disposition_record(
        documents=docs,
        llm_client=Client(opinions("建议完善痰培养"), {"content": "bad"}),
    )
    assert broken.status == "data_gap" and broken.llm_call_count == 2


@pytest.mark.asyncio
async def test_first_stage_invalid_output_is_unresolved():
    result = await record.check_disposition_record(
        documents=documents("建议完善痰培养。"), llm_client=Client({"content": "bad"})
    )
    assert result.status == "data_gap" and result.llm_call_count == 1


@pytest.mark.asyncio
async def test_source_redaction_and_quote_verification_use_the_same_text():
    body = "建议完善痰培养。已向家属（电话：13900000000）说明，遵照执行。"
    feedback = "已向家属（电话：[手机号已脱敏]）说明，遵照执行。"
    client = Client(
        opinions("建议完善痰培养", feedback),
        response(item("完善痰培养", feedback, "generic")),
    )
    result = await record.check_disposition_record(
        documents=documents(body), llm_client=client
    )
    assert result.status == "non_compliant"
    assert all("13900000000" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_medication_and_followup_are_checked_in_separate_groups():
    docs = documents("建议给予药物甲抗感染一周后复查胸部CT。处理：已加用药物甲。")
    client = Client(
        opinions("给予药物甲抗感染一周后复查胸部CT", "已加用药物甲"),
        response(
            medications=[item("给予药物甲抗感染", "已加用药物甲", "performed")],
            examinations=[item("复查胸部CT", "", "missing")],
        ),
    )
    result = await record.check_disposition_record(documents=docs, llm_client=client)
    assert result.status == "non_compliant" and result.llm_call_count == 2


@pytest.mark.parametrize("group", ["medications", "examinations"])
def test_a_merged_medication_and_followup_cannot_be_passed_by_medication_feedback(
    group,
):
    opinion = "给予药物甲抗感染一周后复查胸部CT"
    feedback = "已加用药物甲"
    docs = documents("建议" + opinion + "。" + feedback + "。")
    roles = record.parse_opinions(opinions(opinion, feedback), docs)
    result = record.parse_facts(
        response(**{group: [item(opinion, feedback, "performed")]}), docs, roles
    )
    assert result[0] == "data_gap"


def test_an_omitted_explicit_followup_is_unresolved_even_if_medication_is_specific():
    opinion = "给予药物甲抗感染，一周后复查胸部CT"
    docs = documents(opinion + "。已加用药物甲。")
    roles = record.parse_opinions(opinions(opinion, "已加用药物甲"), docs)
    assert (
        record.parse_facts(
            response(
                medications=[item("给予药物甲抗感染", "已加用药物甲", "performed")]
            ),
            docs,
            roles,
        )[0]
        == "data_gap"
    )


@pytest.mark.parametrize("prefix", ["必要时", "无需", "无须", "不必"])
def test_a_conditional_or_negated_followup_is_not_mandatory(prefix):
    opinion = "给予药物甲抗感染，" + prefix + "复查胸部CT"
    docs = documents(opinion + "。已加用药物甲。")
    roles = record.parse_opinions(opinions(opinion, "已加用药物甲"), docs)
    assert (
        record.parse_facts(
            response(
                medications=[item("给予药物甲抗感染", "已加用药物甲", "performed")]
            ),
            docs,
            roles,
        )[0]
        == "compliant"
    )


@pytest.mark.asyncio
async def test_supported_client_uses_existing_output_options_without_extra_calls():
    class StructuredClient(Client):
        def supports_strict_json_schema(self):
            return True

        async def generate(self, prompt, **kwargs):
            expected = {"enable_thinking": False}
            if self.prompts:
                expected["response_format"] = {"type": "json_object"}
            assert kwargs == expected
            return await super().generate(prompt)

    client = StructuredClient(
        opinions("给予气压治疗", "遵照执行"),
        response(item("给予气压治疗", "遵照执行", "generic")),
    )
    result = await record.check_disposition_record(
        documents=documents("建议给予气压治疗。遵照执行。"), llm_client=client
    )
    assert result.status == "non_compliant" and len(client.prompts) == 2


@pytest.mark.asyncio
async def test_new_rule_reads_only_execution_record_and_does_not_read_orders(
    monkeypatch,
):
    requested = []

    def read(*, source_key, **kwargs):
        requested.append(source_key)
        assert source_key == "consultation_record"
        return [
            {
                "document_title": "会诊执行记录",
                "record_time": "2026-07-20 15:59:00",
                "record_content": "会诊建议给予气压治疗。以上已遵嘱执行。",
            }
        ]

    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", read)
    client = Client(
        opinions("给予气压治疗", "以上已遵嘱执行"),
        response(item("给予气压治疗", "以上已遵嘱执行", "generic")),
    )
    execution = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=(record.RULE_ID,),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )
    assert requested == ["consultation_record"]
    assert execution.results[0]["status"] == "non_compliant"
    assert execution.planned_rule_ids == (record.RULE_ID,)


def test_new_rule_is_registered_as_independent_writing_check():
    from app.services.luxian_0609.native_package import (
        load_luxian_0609_dependency_inventory,
    )
    from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts

    dependency = next(
        row
        for row in load_luxian_0609_dependency_inventory()
        if row.rule_id == record.RULE_ID
    )
    assert dependency.executor_key == "consultation_quality"
    assert dependency.applicable_documents == ("consultation_record",)
    contract = next(
        row
        for row in load_luxian_0609_rule_contracts()
        if row.rule_id == record.RULE_ID
    )
    assert contract.max_llm_calls_per_rule == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper_reference", [False, True])
async def test_new_rule_binds_record_evidence_and_renders_independent_customer_result(
    monkeypatch, tamper_reference
):
    from app.services.luxian_0609.evidence_snapshot_provider import (
        SnapshotSourceRows,
        build_luxian_0609_evidence_read_session,
    )
    from app.services.luxian_0609.decision_binding import (
        bind_and_reduce_luxian_0609_rule_decisions,
    )
    from app.services.luxian_0609.customer_renderer import (
        render_luxian_0609_customer_result,
    )
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_published_customer_display_facts,
    )

    source_keys = []

    def read(**kwargs):
        source_keys.append(kwargs["source_key"])
        assert kwargs["source_key"] == "consultation_record"
        return SnapshotSourceRows.create(
            source_key="consultation_record",
            rows=[
                {
                    "document_id": "SYNTHETIC-DOCUMENT",
                    "document_title": "会诊执行记录",
                    "record_time": "2026-07-20 15:59:00",
                    "record_content": "会诊建议给予气压治疗。以上已遵嘱执行。",
                }
            ],
            truncated=False,
            limit_rows=48,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(record.RULE_ID,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-20T17:00:00+08:00",
        row_reader=read,
    )
    if tamper_reference:
        real_documents = episode._documents

        def missing_material_reference(rows):
            result = real_documents(rows)
            for document in result:
                document.pop("material_ref", None)
            return result

        monkeypatch.setattr(episode, "_documents", missing_material_reference)
    outcome = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=(record.RULE_ID,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=(record.RULE_ID,),
        llm_client=Client(
            opinions("给予气压治疗", "以上已遵嘱执行"),
            response(item("给予气压治疗", "以上已遵嘱执行", "generic")),
        ),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=outcome.decisions,
        expected_rule_ids=(record.RULE_ID,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    result = render_luxian_0609_customer_result(decision=reduced[0])
    assert source_keys == ["consultation_record"]
    assert result["status"] == (
        "technical_error" if tamper_reference else "non_compliant"
    )
    if not tamper_reference:
        assert "处置记录不具体" in result["findings"] and reduced[0].fact_refs
    assert "SYNTHETIC-DOCUMENT" not in json.dumps(result, ensure_ascii=False)
    assert (
        validate_luxian_0609_published_customer_display_facts(
            rule_id=record.RULE_ID,
            raw=None,
            status="non_compliant",
            reason_code="requirement_violated",
        )
        is None
    )
