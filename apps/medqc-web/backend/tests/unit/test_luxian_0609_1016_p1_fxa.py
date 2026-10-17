"""1016 P1：合成材料覆盖诊断关系与完整空查房来源。"""

import json

import pytest

from tests.unit.test_luxian_0609_course_quality_freeze import _run_chain


class AtomicClient:
    def __init__(self, **overrides):
        self.facts = {
            "chief_signal_kind": "localized_symptom_or_sign",
            "anatomic_relation": "nonspecific",
            "laterality_relation": "not_applicable",
            "symptom_relation": "nonspecific",
            "disease_course_relation": "not_applicable",
            "disease_direction_relation": "supports",
            "medical_analysis": "症状组合提供疾病方向。",
            **overrides,
        }

    async def generate(self, prompt, **kwargs):
        return {"content": json.dumps(self.facts, ensure_ascii=False)}


@pytest.mark.asyncio
async def test_018_disease_direction_support_is_sufficient():
    rows = {
        "admission_record": [{"document_id": "admission", "chief_complaint": "胸痛半日",
                              "record_content": "主诉：胸痛半日。"}],
        "admission_record_diagnosis": [{"document_id": "admission", "diagnosis_type": "初步诊断",
                                        "diagnosis_main": "是", "diagnosis_name": "冠心病"}],
    }
    _, _, reduced, result = await _run_chain("LX0609-01-01-02", rows, client=AtomicClient())
    assert reduced.final_state.value == result["status"] == "compliant"


class RelationClient:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return {"content": '{"relation_state":"related","rationale_code":"same_clinical_problem"}'}


@pytest.mark.asyncio
@pytest.mark.parametrize("split", [False, True])
async def test_077_primary_diagnosis_survives_multiple_diagnosis_rows(split):
    rows = {
        "first_course_record": [{"document_id": "course", "diagnose_based_on": "1、急性胰腺炎：腹痛伴淀粉酶升高。",
                                 "differential_diagnosis": "胆囊炎：也可上腹疼痛。"}],
        "first_course_record_diagnosis": [
            {"document_id": "course", "diagnosis_type": "初步诊断", "diagnosis_main": "是", "diagnosis_name": "急性胰腺炎"},
            {"document_id": "course", "diagnosis_type": "初步诊断", "diagnosis_name": "高血压"},
            {"document_id": "irrelevant", "diagnosis_type": "出院诊断", "diagnosis_name": "高血压"},
        ],
    }
    if split:
        rows["first_course_record"].append({"document_id": "shell", "case_characteristic": "既往体健。"})
        rows["first_course_record_diagnosis"].append({"document_id": "shell", "diagnosis_type": "初步诊断", "diagnosis_name": "高血压"})
    client = RelationClient()
    _, _, reduced, result = await _run_chain("LX0609-01-02-02", rows, client=client)
    assert reduced.final_state.value == result["status"] == "compliant"
    assert "第一诊断：急性胰腺炎" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,reason", [(TimeoutError, "model_timeout"), (ConnectionError, "model_transport_error")])
async def test_077_transport_failure_is_retryable_technical_error(failure, reason):
    class FailedClient:
        async def generate(self, prompt, **kwargs):
            raise failure("上游不可用")

    rows = {"first_course_record": [{"document_id": "course", "first_diagnosis": "肺炎",
                                      "differential_diagnosis": "肺结核"}]}
    _, execution, reduced, result = await _run_chain("LX0609-01-02-02", rows, client=FailedClient())
    assert reduced.final_state.value == result["status"] == "technical_error"
    assert result["reason_code"] == reason
    assert execution.llm_call_count == 1


def test_018_prompt_preserves_combination_direction_without_specific_diagnosis():
    from app.services.luxian_0609.course_quality.rule_018 import _lx018_prompt

    prompt = _lx018_prompt(context="主诉：反复咳嗽伴血痰数周；第一诊断：肺部占位。")
    assert "症状组合应整体" in prompt
    assert "不要求特异性确诊" in prompt


@pytest.mark.asyncio
async def test_077_unavailable_client_is_technical_error_without_attempt():
    rows = {"first_course_record": [{"document_id": "course", "first_diagnosis": "肺炎",
                                      "differential_diagnosis": "肺结核"}]}
    _, execution, reduced, result = await _run_chain("LX0609-01-02-02", rows)
    assert reduced.final_state.value == result["status"] == "technical_error"
    assert result["reason_code"] == "model_transport_error"
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("basis,expected", [
    ("1、急性胰腺炎：依据为腹痛和酶升高。2、高血压：既往史支持。", "compliant"),
    ("病史与检查待完善。", "data_gap"),
])
async def test_077_body_order_resolves_unordered_candidates_without_guessing(basis, expected):
    rows = {
        "first_course_record": [{"document_id": "course", "diagnose_based_on": basis, "differential_diagnosis": "胆囊炎"}],
        "first_course_record_diagnosis": [
            {"document_id": "course", "diagnosis_type": "初步诊断", "diagnosis_name": "高血压"},
            {"document_id": "course", "diagnosis_type": "初步诊断", "diagnosis_name": "急性胰腺炎"},
        ],
    }
    client = RelationClient()
    _, _, reduced, result = await _run_chain("LX0609-01-02-02", rows, client=client)
    assert reduced.final_state.value == result["status"] == expected
    if expected == "compliant":
        assert "第一诊断：急性胰腺炎" in client.prompts[0]
    else:
        assert client.prompts == []


@pytest.mark.asyncio
async def test_018_structured_present_illness_reaches_laterality_check():
    class SideClient(AtomicClient):
        def __init__(self):
            super().__init__(laterality_relation="conflicts")
            self.prompt = ""

        async def generate(self, prompt, **kwargs):
            self.prompt = prompt
            return await super().generate(prompt, **kwargs)

    client = SideClient()
    history = "入院前影像提示右侧输尿管病灶，右肾积水。"
    rows = {
        "admission_record": [{"document_id": "admission", "record_content": "",
                              "chief_complaint": "左腰痛半日", "history_of_present_illness": history}],
        "admission_record_diagnosis": [{"document_id": "admission", "diagnosis_type": "初步诊断",
                                        "diagnosis_main": "是", "diagnosis_name": "输尿管结石"}],
    }
    _, _, reduced, result = await _run_chain("LX0609-01-01-02", rows, client=client)
    assert history in client.prompt
    assert reduced.final_state.value == result["status"] == "non_compliant"
