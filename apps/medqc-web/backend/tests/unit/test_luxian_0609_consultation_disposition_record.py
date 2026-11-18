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


@pytest.mark.asyncio
async def test_verified_generic_disposition_survives_action_extraction_failure():
    docs = documents("建议给予合成治疗。以上已遵嘱执行。")
    client = Client(opinions("建议给予合成治疗", "以上已遵嘱执行"), RuntimeError("模拟抽取失败"))
    outcome = await record.check_disposition_record(documents=docs, llm_client=client)
    assert outcome.status == "non_compliant"
    assert outcome.fact_refs == ("consultation_record-1",)


@pytest.mark.asyncio
async def test_transport_failure_does_not_claim_patient_material_is_missing():
    outcome = await record.check_disposition_record(
        documents=documents("建议给予合成治疗。"), llm_client=Client(ConnectionError("模拟网络失败")),
    )
    assert (outcome.status, outcome.reason) == ("technical_error", "model_transport_error")


def test_valid_document_defect_survives_other_document_invalid_action_schema():
    docs = documents("建议给予合成治疗。遵照执行。")
    docs.append({"ref": "consultation_record-2", "text": "建议复查合成检查。"})
    roles = record.parse_opinions(opinions("建议给予合成治疗", "遵照执行"), docs[:1])
    roles["consultation_record-2"] = {
        "ref": "consultation_record-2", "scope": "ordinary", "suggestion_state": "present",
        "opinion_quotes": ["建议复查合成检查"], "feedback_quotes": [],
    }
    payload = json.loads(response(item("给予合成治疗", "遵照执行", "generic"))["content"])
    payload["documents"].append({"ref": "consultation_record-2", "medications": [],
                                 "examinations": [{}], "therapies": [], "other_actions": []})
    assert record.parse_facts({"content": json.dumps(payload)}, docs, roles) == (
        "non_compliant", "requirement_violated", ("consultation_record-1",),
    )


def parse(docs, opinion, feedback, *items, scope="ordinary", state="present", **kwargs):
    frozen = record.parse_opinions(opinions(opinion, feedback, scope, state), docs)
    return record.parse_facts(response(*items), docs, frozen, **kwargs)


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


def test_short_generic_acknowledgement_cannot_be_upgraded_by_referent():
    docs = documents("建议继续合成药物。遵执。")
    assert parse(docs, "建议继续合成药物", "遵执", item(
        "建议继续合成药物", "遵执", "generic", "建议继续合成药物",
    ))[0] == "non_compliant"


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
def test_generic_wording_labelled_specific_is_rechecked_then_follows_model(feedback):
    """笼统回应词表只触发补核，不推翻模型结论；补核后模型仍判具体处置则以模型为准。"""
    docs = documents("建议给予电针。" + feedback)
    fact = item("给予电针", feedback, "performed")
    issues = []
    assert parse(docs, "建议给予电针", feedback, fact, review_issues=issues)[0] == "data_gap"
    assert [issue.reason for issue in issues] == ["generic feedback hint"]
    assert parse(docs, "建议给予电针", feedback, fact, rechecked=True)[0] == "compliant"
    # 补核后模型改判为笼统回应时照常判缺陷。
    assert parse(
        docs, "建议给予电针", feedback, item("给予电针", feedback, "generic"), rechecked=True
    )[0] == "non_compliant"


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


def test_concrete_medication_plan_and_reasoned_refusal_are_dispositions():
    advice = "建议药物甲纠正贫血、药物乙补铁"
    feedback = "患者使用药物乙后腹泻，暂不使用，拟加用药物甲纠正贫血治疗"
    docs = documents(advice + "，" + feedback + "，续观。")
    assert (
        parse(
            docs,
            advice,
            feedback,
            item("药物甲纠正贫血", "拟加用药物甲纠正贫血治疗", "planned"),
            item("药物乙补铁", "患者使用药物乙后腹泻，暂不使用", "declined"),
        )[0]
        == "compliant"
    )


def test_consultants_medication_plan_without_department_response_is_not_disposed():
    advice = "会诊意见：建议拟加用药物甲纠正贫血治疗"
    assert (
        parse(
            documents(advice),
            advice,
            "",
            item("拟加用药物甲纠正贫血治疗", "", "missing"),
        )[0]
        == "non_compliant"
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
    assert broken.status == "technical_error" and broken.llm_call_count == 2
    assert broken.reason == "model_invalid_output"


@pytest.mark.asyncio
async def test_first_stage_invalid_output_is_technical_error_after_one_retry():
    client = Client({"content": "bad"}, {"content": "bad"})
    result = await record.check_disposition_record(
        documents=documents("建议完善痰培养。"), llm_client=client
    )
    assert result.status == "technical_error" and result.llm_call_count == 2
    assert result.reason == "model_invalid_output"
    assert len(client.prompts) == 2 and client.prompts[0] != client.prompts[1]
    assert "上次校验失败" in client.prompts[1]


@pytest.mark.asyncio
async def test_first_stage_protocol_violation_is_retried_once_then_continues():
    docs = documents("建议完善痰培养。已完善痰培养。")
    client = Client(
        # 第一次复读原文，引文不能在原文中逐字找到。
        opinions("建议完善痰培养建议完善痰培养", "已完善痰培养"),
        opinions("建议完善痰培养", "已完善痰培养"),
        response(item("完善痰培养", "已完善痰培养", "performed")),
    )
    result = await record.check_disposition_record(documents=docs, llm_client=client)
    assert result.status == "compliant" and result.llm_call_count == 3


@pytest.mark.asyncio
async def test_second_stage_invalid_output_is_not_retried():
    docs = documents("建议完善痰培养。已完善痰培养。")
    client = Client(opinions("建议完善痰培养", "已完善痰培养"), {"content": "bad"}, {"content": "bad"})
    result = await record.check_disposition_record(documents=docs, llm_client=client)
    assert (result.status, result.reason, result.llm_call_count) == ("technical_error", "model_invalid_output", 2)
    assert len(client.prompts) == 2


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
            # 两阶段都不叠加 json_object：真实对照中它使第二阶段输出残缺对象。
            assert kwargs == {"enable_thinking": False}
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
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    result = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0],
        raw_customer_display_facts=dict(outcome.customer_display_facts).get(record.RULE_ID),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    if not tamper_reference:
        from app.services.qc_workspace.canonical_result_store import validated_customer_explanation
        facts, _ = validated_customer_explanation(result, rule_id=record.RULE_ID, status=result["status"])
        assert facts["unspecific_document_count"] == 1
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


@pytest.mark.parametrize("raw", [
    {"failure_kind": "consultation_disposition_unspecific", "unspecific_document_count": True},
    {"failure_kind": "consultation_disposition_unspecific", "unspecific_document_count": 0},
    {"failure_kind": "consultation_disposition_unspecific", "unspecific_document_count": 1, "patient_name": "合成患者"},
])
def test_disposition_explanation_rejects_invalid_counts_and_extra_fields(raw):
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts
    with pytest.raises(ValueError):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=record.RULE_ID, raw=raw, status="non_compliant", reason_code="requirement_violated",
        )


_LONG_OPINION = (
    "呼吸科会诊意见:病史敬悉。患者咳嗽咳痰,活动后呼吸困难明显,结合辅助检查考虑慢性阻塞性肺病急性加重,"
    "建议完善痰培养及药敏,继续抗感染、解痉平喘治疗,必要时转我科进一步治疗。"
)
_LONG_BODY = "患者高龄,目前持续经鼻高流量吸氧,故请呼吸科会诊。 " + _LONG_OPINION + " 遵会诊意见,已完善痰培养。"


def _anchored_opinions(opinion_quotes, feedback_quotes=("遵会诊意见,已完善痰培养。",)):
    return {
        "content": json.dumps({
            "schema_version": record.SCHEMA_VERSION + "-opinions",
            "documents": [{
                "ref": "consultation_record-1", "scope": "ordinary", "suggestion_state": "present",
                "opinion_quotes": list(opinion_quotes), "feedback_quotes": list(feedback_quotes),
            }],
        }, ensure_ascii=False)
    }


def test_long_opinion_anchors_resolve_to_the_full_source_paragraph():
    roles = record.parse_opinions(
        _anchored_opinions([{"start": "呼吸科会诊意见:病史敬悉", "end": "必要时转我科进一步治疗。"}]),
        documents(_LONG_BODY),
    )
    assert roles["consultation_record-1"]["opinion_quotes"] == [_LONG_OPINION]
    assert roles["consultation_record-1"]["feedback_quotes"] == ["遵会诊意见,已完善痰培养。"]


@pytest.mark.parametrize("anchor", [
    {"start": "呼吸科会诊意见:病史知悉", "end": "必要时转我科进一步治疗。"},  # 开头不是原文
    {"start": "呼吸科会诊意见:病史敬悉", "end": "必要时转外科进一步治疗。"},  # 结尾不是原文
    {"start": "呼吸科", "end": "必要时转我科进一步治疗。"},  # 锚点过短
    {"start": "遵会诊意见,已完善", "end": "呼吸科会诊意见:病史敬悉"},  # 结尾在开头之前
    {"start": "呼吸科会诊意见:病史敬悉", "end": "必要时转我科进一步治疗。", "text": "多余字段"},
])
def test_invalid_anchor_is_rejected_as_ungrounded(anchor):
    with pytest.raises(ValueError, match="role quotes not grounded"):
        record.parse_opinions(_anchored_opinions([anchor]), documents(_LONG_BODY))


@pytest.mark.parametrize("anchor", [
    {"start": "呼吸科会诊意见:病史敬悉。患者咳嗽...建议完善痰培养及药敏", "end": "必要时转我科进一步治疗。"},
    {"start": "呼吸科会诊意见:病史敬悉……继续抗感染", "end": "建议完善……必要时转我科进一步治疗。"},
])
def test_anchor_ellipsis_keeps_only_the_verbatim_outer_parts(anchor):
    roles = record.parse_opinions(_anchored_opinions([anchor]), documents(_LONG_BODY))
    assert roles["consultation_record-1"]["opinion_quotes"] == [_LONG_OPINION]


@pytest.mark.parametrize("anchor", [
    {"start": "呼吸...建议完善痰培养及药敏", "end": "必要时转我科进一步治疗。"},  # 省略号前过短
    {"start": "呼吸科会诊意见:病史知悉...建议完善", "end": "必要时转我科进一步治疗。"},  # 省略号前非原文
    {"start": "呼吸科会诊意见:病史敬悉", "end": "必要时转我科进一步...治疗"},  # 省略号后过短
])
def test_anchor_ellipsis_parts_must_still_be_grounded(anchor):
    with pytest.raises(ValueError, match="role quotes not grounded"):
        record.parse_opinions(_anchored_opinions([anchor]), documents(_LONG_BODY))


def test_anchor_start_must_be_unique_in_the_document():
    body = "建议完善痰培养及药敏。另建议完善痰培养及药敏复查,继续抗感染治疗。遵照执行。"
    with pytest.raises(ValueError, match="role quotes not grounded"):
        record.parse_opinions(
            _anchored_opinions([{"start": "建议完善痰培养及药敏", "end": "继续抗感染治疗。"}], ["遵照执行。"]),
            documents(body),
        )


def test_opinion_prompt_asks_for_anchors_on_long_paragraphs():
    prompt = record.build_opinion_prompt(documents(_LONG_BODY))
    assert '"start"' in prompt and '"end"' in prompt and "60字" in prompt


@pytest.mark.asyncio
async def test_specific_item_beside_remainder_wording_is_rechecked_once_then_compliant():
    """“予某药，其余遵会诊意见”对该药本身是具体处置：词表命中只补核一次，不判缺陷。"""
    text = "建议头孢呋辛抗感染。我科处理：予头孢呋辛抗感染，其余遵会诊意见。"
    docs = documents(text)
    feedback = "予头孢呋辛抗感染，其余遵会诊意见"
    facts = response(medications=[item("头孢呋辛抗感染", feedback, "performed")])
    client = Client(opinions("建议头孢呋辛抗感染", feedback), facts, facts)
    outcome = await record.check_disposition_record(documents=docs, llm_client=client)
    assert (outcome.status, outcome.llm_call_count) == ("compliant", 3)
    assert "generic feedback hint" in client.prompts[2]
