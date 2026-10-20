"""050受控协议替身测试；不作为真实模型语义通过证据。"""

import asyncio
import json

import pytest

from app.services.luxian_0609.extended_document.diagnosis_scope_extraction import (
    SCHEMA_VERSION, _is_self_qualified_repeat, _prompt, extract_diagnosis_scope,
)


BODY = "目前发热病因仍不明确。"


def test_scope_prompt_distinguishes_routine_effect_review_from_unresolved_plan():
    prompt = _prompt(["感染诊断明确，复查血象评估抗生素效果；影像建议结合职业史。"])
    assert "疗效评估不等于治疗方案未明确" in prompt
    assert "结合临床、职业史或随诊复查" in prompt
    assert "待检查结果指导后续诊疗" in prompt


def claim(quote=BODY, problem="发热病因", **changes):
    result = dict(scope="diagnosis", diagnosis_state="unresolved", polarity="affirmed",
                  temporal_scope="current", association="explicit", quote=quote, problem_quote=problem)
    result.update(changes)
    if "uncertainty_quote" not in result and (
        result["diagnosis_state"] in {"unresolved", "undetermined"}
        or (result["diagnosis_state"] == "explicit" and result["polarity"] == "negated")
    ):
        # 既有合成标签补齐新协议字段，原状态及断言不变。
        result["uncertainty_quote"] = quote
    return result


class Client:
    def __init__(self, documents=None, mutate=None, choices=False, finish="stop", usage=None, content=None):
        self.documents = documents
        self.mutate = mutate
        self.choices = choices
        self.finish = finish
        self.usage = usage
        self.content = content
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])
        documents = self.documents if self.documents is not None else [
            dict(row_index=d["row_index"], coverage="complete", assertions=[claim(d["body"])])
            for d in inputs["documents"]]
        payload = dict(schema_version=SCHEMA_VERSION, documents=documents)
        if self.mutate:
            self.mutate(payload)
        content = self.content if self.content is not None else json.dumps(payload, ensure_ascii=False)
        response = dict(content=content, finish_reason=self.finish,
                        usage=self.usage if self.usage is not None else
                        dict(prompt_tokens=11, completion_tokens=13, total_tokens=24), _api_time=.25)
        if self.choices:
            response["choices"] = [dict(message=dict(content=response.pop("content")),
                                        finish_reason=response.pop("finish_reason"))]
        return response


def run(client, bodies=None, **budgets):
    return asyncio.run(extract_diagnosis_scope(
        [{"record_content": BODY}] if bodies is None else bodies, client,
        max_prompt_bytes=budgets.get("max_prompt_bytes", 65536),
        max_completion_tokens=budgets.get("max_completion_tokens", 16384)))


@pytest.mark.parametrize("choices", [False, True])
def test_grounded_fact_positions_and_observed_usage(choices):
    client = Client(choices=choices)
    result = run(client)
    assert result.state == "ready"
    fact = result.documents[0].assertions[0]
    assert BODY[fact.quote_start:fact.quote_end] == fact.quote
    assert BODY[fact.problem_start:fact.problem_end] == "发热病因"
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens,
            result.total_tokens, result.api_time) == (1, 11, 13, 24, .25)
    assert client.calls[0][1] == dict(max_completion_tokens=16384, allow_length_retry=False)


def test_multi_problem_overlapping_contexts_do_not_cancel():
    body = "肺炎已明确；贫血病因仍未明确。"
    facts = [claim(body, "肺炎", diagnosis_state="explicit"), claim(body, "贫血病因")]
    result = run(Client([dict(row_index=0, coverage="complete", assertions=facts)]), [{"content": body}])
    assert result.state == "ready"
    assert [a.diagnosis_state for a in result.documents[0].assertions] == ["explicit", "unresolved"]


def test_ambiguous_owner_does_not_erase_known_existence():
    body = "肺炎和胸腔积液，其中一项仍未明确。"
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[
        claim(body, "", association="ambiguous")])]), [{"content": body}])
    fact = result.documents[0].assertions[0]
    assert fact.diagnosis_state == "unresolved" and fact.temporal_scope == "current"
    assert fact.association == "ambiguous" and fact.problem_start is None


def test_shared_ambiguous_context_can_preserve_different_states():
    body = "目前其中一项已明确，另一项尚未明确。"
    facts = [claim(body, "", association="ambiguous", diagnosis_state="explicit"),
             claim(body, "", association="ambiguous", diagnosis_state="unresolved")]
    result = run(Client([dict(row_index=0, coverage="complete", assertions=facts)]), [{"content": body}])
    assert result.state == "ready"
    assert [fact.diagnosis_state for fact in result.documents[0].assertions] == ["explicit", "unresolved"]
    assert all(fact.problem_start is None for fact in result.documents[0].assertions)


@pytest.mark.parametrize("association", ["ambiguous", "unknown"])
def test_unproven_owner_must_not_supply_even_a_present_problem_name(association):
    fact = claim(association=association)
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]))
    assert result.state == "technical_error" and result.reason_code == "model_invalid_output"


def test_fully_duplicate_ambiguous_fact_is_still_invalid():
    fact = claim(problem="", association="ambiguous")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact, dict(fact)])]))
    assert result.state == "technical_error" and result.reason_code == "model_invalid_output"


def test_unknown_and_complete_empty_coverage_are_distinct():
    documents = [dict(row_index=1, coverage="unknown", assertions=[]),
                 dict(row_index=0, coverage="complete", assertions=[])]
    result = run(Client(documents), [{"content": "查体正常。"}, {"content": "原文指代不清。"}])
    assert result.state == "ready"
    assert [(d.row_index, d.coverage, d.assertions) for d in result.documents] == [
        (0, "complete", ()), (1, "unknown", ())]


@pytest.mark.parametrize("scope,state,polarity,temporal,association", [
    ("diagnosis", "unresolved", "negated", "current", "explicit"),
    ("diagnosis", "unresolved", "affirmed", "future_conditional", "explicit"),
    ("diagnosis", "explicit", "affirmed", "historical", "explicit"),
    ("treatment_plan", "undetermined", "affirmed", "current", "explicit"),
    ("local_problem", "unknown", "unknown", "unknown", "unknown"),
])
def test_valid_semantic_enums_are_preserved(scope, state, polarity, temporal, association):
    fact = claim(scope=scope, diagnosis_state=state, polarity=polarity,
                 temporal_scope=temporal, association=association,
                 problem_quote="" if association == "unknown" else "发热病因")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]))
    assert result.state == "ready"
    assertion = result.documents[0].assertions[0]
    assert (assertion.scope, assertion.diagnosis_state, assertion.polarity,
            assertion.temporal_scope, assertion.association) == (scope, state, polarity, temporal, association)


@pytest.mark.parametrize("mutation", [
    lambda p: p["documents"].clear(),
    lambda p: p["documents"].append(p["documents"][0]),
    lambda p: p["documents"][0].update(row_index=True),
    lambda p: p["documents"][0].update(row_index=1),
    lambda p: p["documents"][0].update(coverage="absent"),
    lambda p: p["documents"][0].update(extra="field"),
    lambda p: p.update(extra="field"),
    lambda p: p.update(schema_version="other"),
    lambda p: p["documents"][0]["assertions"][0].update(problem_id="model-owner"),
    lambda p: p["documents"][0]["assertions"][0].update(scope="other"),
    lambda p: p["documents"][0]["assertions"][0].update(quote="另一份文书中的诊断。"),
    lambda p: p["documents"][0]["assertions"][0].update(problem_quote="另一问题"),
    lambda p: p["documents"][0]["assertions"].append(p["documents"][0]["assertions"][0]),
    lambda p: p["documents"][0]["assertions"][0].update(association="ambiguous"),
])
def test_bad_schema_binding_or_quotes_return_no_partial_facts(mutation):
    result = run(Client(mutate=mutation))
    # 协议违规重试 1 次后仍违规才拒收（用户口径 2026-10-11）。
    assert (result.state, result.reason_code, result.documents, result.llm_call_count) == (
        "technical_error", "model_invalid_output", (), 2)


def test_repeated_quote_cannot_manufacture_original_coordinate():
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[claim()])]),
                 [{"content": BODY + BODY}])
    assert result.reason_code == "model_invalid_output"


def test_private_prefix_is_redacted_and_original_quote_position_is_located():
    body = "患者姓名：张三。" + BODY
    client = Client([dict(row_index=0, coverage="complete", assertions=[claim()])])
    result = run(client, [{"content": body}])
    assert result.state == "ready"
    assert "张三" not in client.calls[0][0]
    assert result.documents[0].assertions[0].quote_start == len("患者姓名：张三。")


@pytest.mark.parametrize("usage", [
    {}, dict(prompt_tokens=1, completion_tokens=2, total_tokens=4),
    dict(prompt_tokens=True, completion_tokens=2, total_tokens=3),
    dict(prompt_tokens=1, completion_tokens=16385, total_tokens=16386),
])
def test_invalid_or_overbudget_usage_is_technical_failure(usage):
    assert run(Client(usage=usage)).reason_code == "model_invalid_output"


@pytest.mark.parametrize("finish", ["length", "content_filter", None])
def test_incomplete_output_is_not_semantic_unknown(finish):
    assert run(Client(finish=finish)).reason_code == "model_invalid_output"


def test_duplicate_json_keys_are_invalid():
    client = Client(content='{"schema_version":"x","schema_version":"x","documents":[]}')
    assert run(client).reason_code == "model_invalid_output"


def test_input_capacity_is_zero_call_gap_and_exact_boundary_is_allowed():
    size = len(_prompt([BODY]).encode("utf-8"))
    client = Client()
    result = run(client, max_prompt_bytes=size - 1)
    assert (result.state, result.reason_code, result.llm_call_count) == (
        "data_gap", "candidate_scope_incomplete", 0)
    assert client.calls == []
    assert run(client, max_prompt_bytes=size).state == "ready"


@pytest.mark.parametrize("body", [None, 123, "", " "])
def test_unreadable_source_body_is_separate_from_output_failure(body):
    client = Client()
    result = run(client, [{"record_content": body}])
    assert result.reason_code == "required_field_missing" and result.llm_call_count == 0
    assert client.calls == []


def test_missing_client_and_transport_failure_are_technical_errors():
    class Broken:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("synthetic transport failure")
    assert run(None).reason_code == "model_transport_error"
    result = run(Broken())
    assert result.reason_code == "model_transport_error" and result.llm_call_count == 1


def test_empty_input_does_not_invent_document_coverage():
    client = Client()
    result = run(client, [])
    assert result.state == "ready" and result.documents == () and result.llm_call_count == 0
    assert client.calls == []


def test_protocol_violation_is_retried_once_and_second_valid_answer_is_used():
    """用户口径（2026-10-11）：协议违规可确定识别，重试 1 次；第二次合规即采用。"""
    calls = []

    def mutate_first(payload):
        calls.append(1)
        if len(calls) == 1:
            payload["documents"][0]["assertions"][0].update(problem_quote="另一问题")

    result = run(Client(mutate=mutate_first))
    assert result.state == "ready"
    assert result.llm_call_count == 2
    assert result.total_tokens == 48


def test_repeated_problem_mention_retry_explains_which_binding_must_be_unique():
    body = "患者诉右下肢肿胀。查体右下肢肿胀，病因待查。"
    class CorrectingClient(Client):
        async def generate(self, prompt, **kwargs):
            problem = "患者诉右下肢肿胀" if "problem_quote「右下肢肿胀」出现2次" in prompt else "右下肢肿胀"
            self.documents = [dict(row_index=0, coverage="complete", assertions=[claim(body, problem)])]
            return await super().generate(prompt, **kwargs)
    client = CorrectingClient()
    result = run(client, [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 2
    fact = result.documents[0].assertions[0]
    assert body[fact.problem_start:fact.problem_end] == "患者诉右下肢肿胀"


def test_retry_names_every_grounding_failure_with_its_quote_and_previous_output():
    """补核须一次指明全部失败项（行、引文、出现次数）并附上次输出；定位规则本身不放宽。"""
    bodies = [{"content": "不排除尿崩症，复查尿比重，明确是否存在尿崩症。"},
              {"content": "肠壁肿厚，考虑炎症可能，合并梗阻？必要时进一步检查。"}]
    first = [dict(row_index=0, coverage="complete", assertions=[
                 claim("不排除尿崩症，复查尿比重，明确是否存在尿崩症", "尿崩症")]),
             dict(row_index=1, coverage="complete", assertions=[
                 claim("肠壁肿厚...合并梗阻？", "肠壁肿厚")])]
    fixed = [dict(row_index=0, coverage="complete", assertions=[
                 claim("不排除尿崩症，复查尿比重，明确是否存在尿崩症", "不排除尿崩症")]),
             dict(row_index=1, coverage="complete", assertions=[
                 claim("肠壁肿厚，考虑炎症可能，合并梗阻？", "肠壁肿厚")])]

    class TwoStep(Client):
        async def generate(self, prompt, **kwargs):
            self.documents = first if not self.calls else fixed
            return await super().generate(prompt, **kwargs)

    client = TwoStep()
    result = run(client, bodies)
    assert result.state == "ready" and result.llm_call_count == 2
    retry = client.calls[1][0]
    hint = retry[retry.index("上次校验失败"):retry.index("PREVIOUS_OUTPUT=")]
    assert "row_index=0的quote「不排除尿崩症，复查尿比重，明确是否存在尿崩症」中problem_quote「尿崩症」出现2次" in hint
    assert "row_index=1的quote「肠壁肿厚...合并梗阻？」不是该正文逐字连续原文" in hint
    # quote 失败时 problem_quote 未经核验，须提示随新 quote 一并修正。
    assert "problem_quote须同步改为新quote内只出现一次的逐字连续原文" in hint
    assert "不得任取第一个位置" in hint
    previous = retry[retry.index("PREVIOUS_OUTPUT="):retry.index("\nINPUT_JSON=")]
    assert SCHEMA_VERSION in previous
    # 首次提示词不变，只在补核时追加。
    assert "上次校验失败" not in client.calls[0][0]
    fact = result.documents[0].assertions[0]
    assert bodies[0]["content"][fact.problem_start:fact.problem_end] == "不排除尿崩症"


def test_retry_echo_is_redacted_and_bounded():
    long_quote = "目前发热病因仍不明确" * 10
    leak = "患者姓名：张三。" + long_quote

    class Leaky(Client):
        async def generate(self, prompt, **kwargs):
            self.documents = [dict(row_index=0, coverage="complete", assertions=[claim(leak, "发热病因")])]
            return await super().generate(prompt, **kwargs)

    client = Leaky()
    result = run(client, [{"content": BODY}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    retry = client.calls[1][0]
    assert "张三" not in retry
    hint = retry[retry.index("上次校验失败"):retry.index("PREVIOUS_OUTPUT=")]
    assert "开头的quote" in hint and long_quote not in hint


def test_schema_failure_keeps_generic_retry_without_previous_output():
    calls = []

    def mutate(payload):
        calls.append(1)
        if len(calls) == 1:
            payload["documents"][0].update(coverage="absent")

    client = Client(mutate=mutate)
    result = run(client)
    assert result.state == "ready" and result.llm_call_count == 2
    assert "PREVIOUS_OUTPUT=" not in client.calls[1][0]
    assert "请逐项检查完整覆盖" in client.calls[1][0]


@pytest.mark.parametrize("state,polarity", [
    ("unresolved", "affirmed"), ("undetermined", "affirmed"), ("explicit", "negated"),
])
def test_symptoms_without_uncertainty_quote_never_become_unresolved_evidence(state, polarity):
    body = "局部皮肤发红，已安排会诊及复查。"
    fact = claim(body, "局部皮肤发红", scope="local_problem", diagnosis_state=state, polarity=polarity)
    fact.pop("uncertainty_quote", None)
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": body}])
    assert (result.state, result.reason_code, result.documents, result.llm_call_count) == (
        "technical_error", "model_invalid_output", (), 2)
    assert "uncertainty_quote" in client.calls[1][0].split("上次校验失败：", 1)[1]


@pytest.mark.parametrize("body,problem,uncertainty", [
    ("皮疹病因待查。", "皮疹病因", "待查"),
    ("不排除低钾血症。", "低钾血症", "不排除"),
    ("贫血原因待排。", "贫血原因", "待排"),
    ("肿块性质待定。", "肿块", "性质待定"),
    ("发热原因不明。", "发热", "原因不明"),
    ("考虑药物热可能。", "药物热", "考虑药物热可能"),
    ("目前该病因仍待明确。", "病因", "待明确"),
    ("诊疗方案难以确定。", "诊疗方案", "难以确定"),
    ("病因未明。", "病因", "未明"),
    ("病因不明确。", "病因", "不明确"),
    ("诊断不明。", "诊断", "不明"),
    ("病因未查明。", "病因", "未查明"),
    ("病因无法确定。", "病因", "无法确定"),
    ("治疗方案未确定。", "治疗方案", "未确定"),
    ("病因不确定。", "病因", "不确定"),
    ("病因未能明确。", "病因", "未能明确"),
    ("病因未能确定。", "病因", "未能确定"),
])
def test_verbatim_unique_uncertainty_marker_is_accepted(body, problem, uncertainty):
    fact = claim(body, problem, uncertainty_quote=uncertainty,
                 diagnosis_state="undetermined" if problem == "诊疗方案" else "unresolved")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1
    assert result.documents[0].assertions[0].uncertainty_quote == uncertainty


@pytest.mark.parametrize("uncertainty", [None, "", 123, "未查清", "待…查", "皮疹"])
def test_bad_uncertainty_quote_gets_targeted_retry_then_accepts_only_corrected_evidence(uncertainty):
    body = "皮疹病因待查，伴随关节痛待查。"
    fact = claim(body, "皮疹病因", uncertainty_quote=uncertainty)
    if uncertainty is None:
        fact.pop("uncertainty_quote")
    calls = []

    def correct_second(payload):
        calls.append(1)
        if len(calls) == 2:
            payload["documents"][0]["assertions"][0]["uncertainty_quote"] = "皮疹病因待查"

    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])], mutate=correct_second)
    result = run(client, [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 2
    hint = client.calls[1][0].split("上次校验失败：", 1)[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert "row_index=0" in hint and "uncertainty_quote" in hint
    assert "皮疹病因待查，伴随关节痛待查。" in hint
    assert "PREVIOUS_OUTPUT=" in client.calls[1][0]
    assert result.documents[0].assertions[0].uncertainty_quote == "皮疹病因待查"


def test_invalid_uncertainty_after_retry_rejects_whole_result_including_valid_diagnosis():
    body = "肺炎诊断已明确；仍有咳嗽，安排复查。"
    facts = [claim("肺炎诊断已明确", "肺炎", diagnosis_state="explicit"),
             claim("仍有咳嗽，安排复查。", "咳嗽", scope="local_problem", uncertainty_quote="安排复查")]
    client = Client([dict(row_index=0, coverage="complete", assertions=facts)])
    result = run(client, [{"content": body}])
    assert (result.state, result.reason_code, result.documents, result.llm_call_count) == (
        "technical_error", "model_invalid_output", (), 2)
    assert "不确定性标记" in client.calls[1][0].split("上次校验失败：", 1)[1]


def test_uncertainty_quote_must_be_inside_its_own_quote():
    body = "皮疹原因待查；局部红肿，安排会诊。"
    fact = claim("局部红肿，安排会诊。", "局部红肿", scope="local_problem", uncertainty_quote="待查")
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": body}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    assert "uncertainty_quote" in client.calls[1][0].split("上次校验失败：", 1)[1]


def test_explicit_diagnosis_still_accepts_original_fields_without_uncertainty_evidence():
    body = "当前诊断已明确为肺炎。"
    fact = claim(body, "肺炎", diagnosis_state="explicit")
    fact.pop("uncertainty_quote", None)
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1


def test_negated_explicit_state_also_requires_valid_uncertainty_evidence():
    body = "目前不能确定诊断已明确。"
    fact = claim(body, "诊断", diagnosis_state="explicit", polarity="negated", uncertainty_quote="不能确定")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1


def test_uncertainty_retry_names_all_affected_assertions():
    bodies = [{"content": "皮疹病因待查。"}, {"content": "贫血病因待查。"}]
    documents = [dict(row_index=i, coverage="complete", assertions=[claim(d["content"], problem, uncertainty_quote="")])
                 for i, (d, problem) in enumerate(zip(bodies, ("皮疹病因", "贫血病因")))]
    client = Client(documents)
    result = run(client, bodies)
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    hint = client.calls[1][0].split("上次校验失败：", 1)[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert "row_index=0" in hint and "row_index=1" in hint
    assert hint.count("uncertainty_quote") >= 2


@pytest.mark.parametrize("uncertainty", [
    "考虑", "可能", "安排复查", "?", "？",
    # 跨分句的“考虑…可能”与情态“可能按…”不是不确定性表述。
    "考虑目前治疗有效，可能按原方案继续",
])
def test_isolated_consideration_or_routine_plan_is_not_an_uncertainty_marker(uncertainty):
    # 问号前为标点，不能连同问题名称延伸核验。
    body = "考虑目前治疗有效，可能按原方案继续，安排复查，?？"
    fact = claim(body, "治疗", uncertainty_quote=uncertainty)
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": body}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2


@pytest.mark.parametrize("body,problem,uncertainty", [
    # 带问号的诊断（半角、全角），问号须连同问题名称引用。
    ("出院诊断：1、肺炎，2、淋巴瘤?，3、贫血", "淋巴瘤", "淋巴瘤?"),
    ("肝脏高密度，考虑：钙化？", "肝脏高密度", "钙化？"),
    # 名称后缀式“X可能”及“可能性大”。
    ("气管内少许粘液栓可能。", "粘液栓", "粘液栓可能"),
    ("胸痛，冠心病可能性大，", "冠心病", "冠心病可能性大"),
    ("疑似肺栓塞，复查CT。", "肺栓塞", "疑似肺栓塞"),
    ("发热待除外结核。", "结核", "待除外"),
    ("考虑存在糖尿病可能，拟复查。", "糖尿病", "考虑存在糖尿病可能"),
])
def test_question_mark_and_suffix_possibility_are_explicit_uncertainty(body, problem, uncertainty):
    fact = claim(body, problem, uncertainty_quote=uncertainty)
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1
    assert result.documents[0].assertions[0].uncertainty_quote == uncertainty


def test_missing_marker_retry_echoes_evidence_and_lists_accepted_forms():
    body = "完善铁代谢检查了解有无其他贫血原因。"
    fact = claim(body, "贫血原因", uncertainty_quote="了解有无其他")
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": body}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    hint = client.calls[1][0].split("上次校验失败：", 1)[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert "uncertainty_quote「了解有无其他」不含显式不确定性标记" in hint
    assert "X可能" in hint and "X？" in hint and "不得输出未明确状态" in hint


def test_repeated_problem_is_anchored_only_by_its_unique_uncertainty_evidence():
    body = "不排除尿崩症，复查尿比重，明确是否存在尿崩症。"
    quote = "不排除尿崩症，复查尿比重，明确是否存在尿崩症"
    fact = claim(quote, "尿崩症", uncertainty_quote="不排除尿崩症")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1
    assertion = result.documents[0].assertions[0]
    # 坐标取未明确依据内的那一处，而不是任取第一个位置的结果巧合。
    assert (assertion.problem_start, assertion.problem_end) == (3, 6)


@pytest.mark.parametrize("uncertainty", [
    "不排除尿崩症，复查尿比重，明确是否存在尿崩症",  # 依据内同样重复，仍不能唯一定位
    "尿崩症",  # 依据本身在 quote 内重复
])
def test_ambiguous_uncertainty_evidence_cannot_anchor_repeated_problem(uncertainty):
    body = "不排除尿崩症，复查尿比重，明确是否存在尿崩症。"
    quote = "不排除尿崩症，复查尿比重，明确是否存在尿崩症"
    fact = claim(quote, "尿崩症", uncertainty_quote=uncertainty)
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": body}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    assert "problem_quote「尿崩症」出现2次" in client.calls[1][0]



@pytest.mark.parametrize("quote,uncertainty,expected", [
    ("气管内少许粘液栓可能。", "可能", "气管内少许粘液栓可能"),
    ("出院诊断：淋巴瘤?，贫血", "?", "出院诊断：淋巴瘤?"[5:]),
])
def test_bare_suffix_marker_is_verified_with_adjacent_problem_name(quote, uncertainty, expected):
    fact = claim(quote, expected.rstrip("可能?"), uncertainty_quote=uncertainty)
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": quote}])
    assert result.state == "ready" and result.llm_call_count == 1
    assert result.documents[0].assertions[0].uncertainty_quote == expected


@pytest.mark.parametrize("quote", ["，可能按原方案继续。", "，可能。"])
def test_bare_suffix_marker_without_unique_named_position_still_needs_retry(quote):
    fact = claim(quote, "", association="ambiguous", uncertainty_quote="可能")
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": quote}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2

def test_retry_lists_more_than_eight_failures_so_each_row_can_be_corrected():
    bodies = [{"content": f"第{i}项病因待查。"} for i in range(12)]
    documents = [dict(row_index=i, coverage="complete", assertions=[
        claim(d["content"], "病因", uncertainty_quote="病因")]) for i, d in enumerate(bodies)]
    client = Client(documents)
    result = run(client, bodies)
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    hint = client.calls[1][0].split("上次校验失败：", 1)[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert all(f"row_index={i}的" in hint for i in range(12))


def test_misspelled_quote_retry_shows_nearest_verbatim_text_without_relaxing_grounding():
    body = "腹腔肠壁肿厚，考虑炎症可能，合并梗阻？请结合临床。"
    wrong = "腹部肠壁肿厚，考虑炎症可能，合并梗阻？"
    right = "腹腔肠壁肿厚，考虑炎症可能，合并梗阻？"
    first = [dict(row_index=0, coverage="complete", assertions=[claim(wrong, "合并梗阻", uncertainty_quote="合并梗阻？")])]
    fixed = [dict(row_index=0, coverage="complete", assertions=[claim(right, "合并梗阻", uncertainty_quote="合并梗阻？")])]

    class TwoStep(Client):
        async def generate(self, prompt, **kwargs):
            self.documents = first if not self.calls else fixed
            return await super().generate(prompt, **kwargs)

    client = TwoStep()
    result = run(client, [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 2
    hint = client.calls[1][0].split("上次校验失败：", 1)[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert f"最接近的逐字原文为「{right}」" in hint
    # 首次错字引文本身仍被拒收，没有按相似度放宽定位。
    assert result.documents[0].assertions[0].quote == right



def test_repeated_uncertainty_evidence_only_needs_verbatim_presence():
    """主控代定口径（2026-10-18）：作为未明确证据，逐字存在于所属 quote 即可，不要求唯一。"""
    body = "皮疹病因待查，伴随关节痛待查。"
    fact = claim(body, "皮疹病因", uncertainty_quote="待查")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1
    assert result.documents[0].assertions[0].uncertainty_quote == "待查"


def test_repeated_bare_suffix_marker_is_verified_at_a_named_occurrence():
    body = "粘液栓可能，结节可能。"
    fact = claim(body, "", association="ambiguous", uncertainty_quote="可能")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1
    assert result.documents[0].assertions[0].uncertainty_quote == "粘液栓可能"


def test_uncertainty_evidence_absent_from_its_quote_still_needs_retry():
    body = "皮疹病因待查；局部红肿。"
    fact = claim("局部红肿。", "局部红肿", uncertainty_quote="病因待查")
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": body}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    assert "中找不到uncertainty_quote「病因待查」" in client.calls[1][0]


def test_repeated_uncertainty_evidence_still_cannot_anchor_repeated_problem():
    """作定位坐标时仍须唯一：依据在 quote 内重复时不能用来唯一化重复病名。"""
    body = "不排除尿崩症，复查，不排除尿崩症。"
    quote = "不排除尿崩症，复查，不排除尿崩症"
    fact = claim(quote, "尿崩症", uncertainty_quote="不排除尿崩症")
    client = Client([dict(row_index=0, coverage="complete", assertions=[fact])])
    result = run(client, [{"content": body}])
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 2
    assert "problem_quote「尿崩症」出现2次" in client.calls[1][0]


@pytest.mark.parametrize("text, expected", [
    ("患者现肾功能衰竭合并心力衰竭可能大", True),
    ("考虑肺部感染可能较大。", True),
    ("可能大量出血，需密切观察", False),
])
def test_suffix_possibility_variants_count_as_uncertainty(text, expected):
    """C06（2026-10-19）：“X可能大/可能较大”与“可能性大”同义；“可能大量”等非后缀用法不算。"""
    from app.services.luxian_0609.extended_document.diagnosis_scope_extraction import _has_uncertainty_marker

    assert _has_uncertainty_marker(text) is expected


def test_prompt_treats_cause_speculation_of_a_finding_as_not_unresolved():
    """用户口径（2026-10-19）：主要诊断已明确时，“考虑…所致可能/考虑与…有关”不算诊断未明确（C06）。"""
    from app.services.luxian_0609.extended_document.diagnosis_scope_extraction import _prompt

    prompt = _prompt(["病程正文"])
    assert "‘考虑重症感染所致可能’" in prompt and "不是诊断尚未明确，不输出unresolved" in prompt
    assert "病因待查、原因不明或诊断待明确的仍按上文保留" in prompt


def test_self_qualified_repeated_problem_is_anchored_to_first_occurrence():
    # C08：报告结论“…粘液栓可能”粘贴后在分析里再复述，problem 自带不确定性标记时取首处。
    body = "气管内少许粘液栓可能。右肺结节，建议随诊。请会诊协助诊治；气管内少许粘液栓可能，注意排痰。"
    quote = body[:-1]
    problem = "气管内少许粘液栓可能"
    assert _is_self_qualified_repeat(quote, problem)
    fact = claim(quote, problem, scope="local_problem", uncertainty_quote=problem)
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]), [{"content": body}])
    assert result.state == "ready" and result.llm_call_count == 1
    assert result.documents[0].assertions[0].problem_start == 0
    # 不带标记、靠上下文定性的病名重复仍须唯一定位。
    assert not _is_self_qualified_repeat("不排除尿崩症，复查尿比重，明确是否存在尿崩症", "尿崩症")
