"""19例验收（b7dfb008）剩余四项技术失败的合成用例；不读取任务、材料、配置或真实模型。"""

import pytest

from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    DischargeApprovalInput,
    extract_discharge_approval,
)
from test_discharge_approval_safe_diagnostics import FixedReply, item, rejected_once


async def _approval(source, quote, opinion="approved"):
    client = FixedReply([item("doc_01", quote, opinion)])
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", source),), client,
    )
    return result, client


# ---- C22 · 08-02-02 第1类：意见完整、同文书唯一，仅排版/分句形式差异 ----

@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote,expected", [
    # 整句引用（含冒号标题和编号）；句末标点后的编号只是序号。
    ("上级医师意见：1、同意今日\n出院。", "上级医师意见：1、同意今日出院。", "上级医师意见：1、同意今日\n出院。"),
    ("查房意见如下。2. 主任医师同意\n出院。", "主任医师同意出院。", "主任医师同意\n出院。"),
    # 前一句已在引号/括号内以句末标点结束。
    ("患者诉“无不适。”主任医师同意\n出院。", "主任医师同意出院。", "主任医师同意\n出院。"),
    ("（生命体征平稳。）主任医师同意\n出院。", "主任医师同意出院。", "主任医师同意\n出院。"),
])
async def test_complete_opinion_after_list_marker_or_closed_sentence_is_restored(source, quote, expected):
    result, client = await _approval(source, quote)
    assert result.state == "ready" and result.assertions[0].quote == expected
    assert result.llm_call_count == len(client.prompts) == 1


# ---- 第2、3类：截取否定或去掉限定条件，必须继续拒绝 ----

@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote,boundary", [
    ("主任医师不\n同意出院。", "同意 出院。", "prefix"),  # 从“不同意”截出“同意”
    ("主任医师同意\n出院，前提是复查正常。", "主任医师同意出院", "suffix"),  # 截去后置条件
    ("若复查正常，主任医师同意\n出院。", "主任医师同意出院。", "prefix"),  # 截去前置条件
    ("（复查正常后）主任医师同意\n出院。", "主任医师同意出院。", "prefix"),  # 括号内条件
    ("如无发热\n主任医师同意 出院。", "主任医师同意出院。", "prefix"),  # 换行不能证明完整
    ("意见：1、如复查正常\n2、同意出院。", "同意 出院。", "prefix"),  # 编号前不是句末/冒号
    ("待复查结果正常后，\n主任医师同意出院，复查后再定。", "主任医师同意 出院", "both"),
])
async def test_truncated_negation_or_condition_still_rejected_with_boundary_diagnostic(source, quote, boundary, caplog):
    result, client = await _approval(source, quote)
    rejected_once(result, client)
    assert "reason=quote_whitespace_incomplete_span" in caplog.text
    assert f"boundary={boundary}" in caplog.text
    assert source not in caplog.text and quote not in caplog.text
    for text in ("同意", "复查", "出院"):
        assert text not in caplog.text.split("discharge_approval_rejected", 1)[1].split("\n", 1)[0]


# ---- C25 · 06-02-02 病理取材/结果抽取：拒绝子类别（仅诊断）与占位引文 ----

import json as _json

from app.services.luxian_0609.pathology_documentation_extraction import (
    SCHEMA_VERSION as PATHOLOGY_SCHEMA,
    PathologyDocument,
    PathologyEvent,
    extract_pathology_documentation_facts,
)

_PATH_BODY = "患者张三，男，79岁，术中取胃窦组织送病理检查。主刀医师：李四。"
_OTHER_BODY = "今日复查血常规，继续观察。"


class _PathologyClient:
    def __init__(self, content=None, *, finish="stop", build=None):
        self.content, self.finish, self.build = content, finish, build
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        content = self.content
        if self.build is not None:
            documents = _json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["documents"]
            content = _json.dumps(self.build({doc["document"]: doc["body"] for doc in documents}), ensure_ascii=False)
        return {"choices": [{"finish_reason": self.finish, "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _payload(state="documented", document="d1", quote="术中取胃窦组织送病理检查。", event="P1", **extra):
    item = {"event": event, "state": state, "document": document, "quote": quote}
    item.update(extra)
    return {"schema_version": PATHOLOGY_SCHEMA, "events": [item]}


async def _pathology(client):
    return await extract_pathology_documentation_facts(
        sampling=True, events=[PathologyEvent("P1", "胃窦组织")],
        documents=[PathologyDocument("doc-key-1", "手术记录", "2026-01-01 10:00:00", _PATH_BODY),
                   PathologyDocument("doc-key-2", "日常病程", "2026-01-02 10:00:00", _OTHER_BODY)],
        llm_client=client,
    )


@pytest.mark.asyncio
async def test_pathology_valid_response_stays_ready():
    result = await _pathology(_PathologyClient(_json.dumps(_payload(), ensure_ascii=False)))
    assert result.state == "ready" and result.events["P1"].document_key == "doc-key-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("content,finish,category,quote_kind", [
    ("{not json", "stop", "json_syntax", "-"),
    (_json.dumps({"schema_version": "x", "events": []}), "stop", "schema", "-"),
    (_json.dumps({"schema_version": PATHOLOGY_SCHEMA, "events": []}), "stop", "event_coverage", "-"),
    (_json.dumps(_payload(event="P9"), ensure_ascii=False), "stop", "event_identity", "-"),
    (_json.dumps(_payload(state="maybe"), ensure_ascii=False), "stop", "event_state", "-"),
    (_json.dumps(_payload(document="d9"), ensure_ascii=False), "stop", "document_reference", "-"),
    (_json.dumps(_payload(quote="术中取胃体组织送冰冻。"), ensure_ascii=False), "stop", "same_document_quote", "not_in_sent_body"),
    (_json.dumps(_payload(quote="今日复查血常规"), ensure_ascii=False), "stop", "same_document_quote", "other_document"),
    # 拆开数字词元（79 -> 7 9）的空白差异仍必须拒绝并保留 whitespace_difference 诊断类别。
    (_json.dumps(_payload(quote="7 9岁，术中取胃窦组织送病理检查"), ensure_ascii=False), "stop", "same_document_quote", "whitespace_difference"),
    (_json.dumps(_payload(state="not_documented"), ensure_ascii=False), "stop", "unexpected_quote", "-"),
    (_json.dumps(_payload(), ensure_ascii=False), "length", "incomplete_response", "-"),
])
async def test_pathology_rejection_keeps_safe_subcategory(caplog, content, finish, category, quote_kind):
    with caplog.at_level("WARNING"):
        result = await _pathology(_PathologyClient(content, finish=finish))
    assert (result.state, result.reason_code) == ("technical_error", "tumor_llm_invalid_output")
    assert result.llm_call_count == 2
    line = next(r.getMessage() for r in caplog.records if "pathology_documentation parse rejected" in r.getMessage())
    assert f"category={category} " in line and f"quote_kind={quote_kind} " in line
    for text in ("张三", "胃窦", "血常规", "doc-key", "李四", "not json"):
        assert text not in line


@pytest.mark.asyncio
async def test_pathology_quote_with_redaction_placeholder_is_grounded():
    client = _PathologyClient(build=lambda bodies: _payload(quote=bodies["d1"].split("。")[0] + "。"))
    result = await _pathology(client)
    assert "张三" not in client.prompts[0]
    assert result.state == "ready" and result.events["P1"].document_key == "doc-key-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", [
    "[患者姓名已脱敏]，男，79岁，术中取胃体组织送病理检查。",  # 改写
    "[就诊标识已脱敏]，男，79岁，术中取胃窦组织送病理检查。",  # 占位类别不符
    "[患者姓名已脱敏]",  # 只有占位
])
async def test_pathology_placeholder_quote_protections_still_reject(quote):
    result = await _pathology(_PathologyClient(_json.dumps(_payload(quote=quote), ensure_ascii=False)))
    assert (result.state, result.reason_code) == ("technical_error", "tumor_llm_invalid_output")


# ---- C03 · 03-02-01 定位失败安全摘要（仅诊断，判定与尝试上限不变） ----

from app.services.luxian_0609.extended_document.diagnosis_scope_extraction import (
    SCHEMA_VERSION as SCOPE_SCHEMA,
    extract_diagnosis_scope,
)

_SCOPE_TEXT = "发热原因待查，发热原因考虑感染，继续观察。"


class _ScopeClient:
    def __init__(self, assertions):
        self.assertions = assertions
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        documents = [{"row_index": 0, "coverage": "complete", "assertions": self.assertions}]
        return {"content": _json.dumps({"schema_version": SCOPE_SCHEMA, "documents": documents}, ensure_ascii=False),
                "finish_reason": "stop", "usage": {"prompt_tokens": 11, "completion_tokens": 13, "total_tokens": 24}}


def _scope_claim(quote, problem, uncertainty):
    return {"scope": "diagnosis", "diagnosis_state": "unresolved", "polarity": "affirmed", "temporal_scope": "current",
            "association": "explicit", "quote": quote, "problem_quote": problem, "uncertainty_quote": uncertainty}


@pytest.mark.asyncio
async def test_scope_grounding_summary_separates_zero_multiple_and_same_assertion(caplog):
    # 同一断言：病名在引文中出现两次且无标记、不确定性引文零命中；另一断言的引文在正文零命中。
    client = _ScopeClient([_scope_claim(_SCOPE_TEXT, "发热原因", "未明确"),
                           _scope_claim("体温正常。", "发热", "待查")])
    with caplog.at_level("WARNING"):
        result = await extract_diagnosis_scope([{"record_content": _SCOPE_TEXT}], client,
                                               max_prompt_bytes=65536, max_completion_tokens=16384)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")
    assert result.llm_call_count == len(client.prompts) == 2  # 既有尝试上限不变
    lines = [r.getMessage() for r in caplog.records if "diagnosis_scope_invalid" in r.getMessage()]
    assert len(lines) == 2
    for line in lines:
        assert "grounding=problem:multiple:r0:a0" in line or "grounding=uncertainty:zero:r0:a0" in line
        assert "quote:zero:r0:a1" in line
        for text in ("发热", "感染", "体温", "未明确"):
            assert text not in line


@pytest.mark.asyncio
async def test_scope_valid_response_unchanged():
    client = _ScopeClient([_scope_claim("发热原因待查，", "发热原因", "待查")])
    result = await extract_diagnosis_scope([{"record_content": _SCOPE_TEXT}], client,
                                           max_prompt_bytes=65536, max_completion_tokens=16384)
    assert result.state == "ready" and result.llm_call_count == 1


# ---- C05 · 01-02-02 从冻结正文选片段，解析及保存不信任模型引文 ----

from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client


class _RelationClient:
    def __init__(self, choose):
        self.choose = choose
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        fields = self.choose(prompt)
        return {"content": _json.dumps({"relation_state": "unrelated", "rationale_code": "no_related_item",
                                        "medical_analysis": "鉴别诊断所列胆囊炎与第一诊断急性胰腺炎不属同一临床问题的鉴别。",
                                        **fields}, ensure_ascii=False)}


_077_ROWS = {
    "first_course_record": [{"document_id": "course",
                             "diagnose_based_on": "1、急性胰腺炎：患者张三，男，79岁，\n腹痛伴淀粉酶升高。",
                             "source_version_key": "synthetic-first-course-v1",
                             "differential_diagnosis": "胆囊炎：也可上腹疼痛。"}],
    "first_course_record_diagnosis": [
        {"document_id": "course", "diagnosis_type": "初步诊断", "diagnosis_main": "是", "diagnosis_name": "急性胰腺炎"}],
}


async def _077(choose):
    from test_luxian_0609_course_quality_freeze import _run_chain
    client = _RelationClient(choose)
    wrapped = wrap_luxian_0609_llm_client(client, identity_values=("张三",))
    _, _, reduced, result = await _run_chain("LX0609-01-02-02", _077_ROWS, client=wrapped)
    return client, reduced, result


@pytest.mark.asyncio
async def test_077_numbered_passage_returns_frozen_text_with_privacy():
    client, reduced, result = await _077(lambda prompt: {"evidence_id": "p02"})
    prompt, = client.prompts
    assert "张三" not in prompt
    assert "[p02]" in prompt and "[患者姓名已脱敏]" in prompt
    assert (result["status"], reduced.reason_code) == ("non_compliant", "requirement_violated")
    analysis = result["criterion_results"][0]["medical_analysis"]
    assert "原文依据：1、急性胰腺炎：患者[患者姓名已脱敏]，男，79岁，\n腹痛伴淀粉酶升高。" in analysis
    assert "张三" not in analysis
    course_evidence, = [item for item in result["customer_evidence"] if item["source_type"] == "first_course_record"]
    assert course_evidence["source_document_id"] == "synthetic-first-course-v1"


@pytest.mark.asyncio
@pytest.mark.parametrize("fields", [
    {"evidence_id": "p99"},
    {"evidence_id": "p01,p02"},
    {"evidence_id": ""},
    {"evidence_id": "p01", "evidence_quote": "腹痛伴淀粉酶升高。胆囊炎：也可上腹疼痛"},
])
async def test_077_rejects_unbound_or_spliced_passage(fields):
    client, _, result = await _077(lambda _: fields)
    assert (result["status"], result["reason_code"]) == ("technical_error", "model_invalid_output")
    assert len(client.prompts) == 1


def test_077_keeps_adjacent_short_sentences_in_one_frozen_field():
    from app.services.luxian_0609.course_quality.rule_077 import _evidence_passages

    first = "急性阑尾炎。急性胆囊炎。"
    second = "影像检查提示异常。"
    passages = _evidence_passages([("first", first), ("second", second)])
    assert [(part.document_ref, part.text) for part in passages.values()] == [
        ("first", first), ("second", second),
    ]


# ---- Codex 复审反例（ad02cb1b8）：编号标题条件、逐字命中边界、断言原始序号 ----

@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote", [
    ("仅在复查正常后可执行以下计划：1、主任医师同意\n出院。", "主任医师同意出院。"),  # 复审反例1
    ("仅在复查正常后可执行以下计划：1、主任医师同意出院。", "主任医师同意出院。"),  # 同一前提，逐字命中路径
    ("若体温平稳：主任医师同意\n出院。", "主任医师同意出院。"),  # 冒号标题本身是条件
    ("复查结果未回报前暂不安排以下事项：2. 主任医师同意出院。", "主任医师同意出院。"),
])
async def test_list_or_colon_item_cannot_drop_governing_heading_condition(source, quote):
    result, client = await _approval(source, quote)
    rejected_once(result, client)


@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote", [
    ("主任医师不同意出院。", "同意出院。"),  # 复审反例2：逐字命中但截出否定
    ("若复查正常，主任医师同意出院。", "主任医师同意出院。"),  # 删掉前置条件
    ("主任医师同意出院，前提是复查正常。", "主任医师同意出院"),  # 删掉后置条件
])
async def test_verbatim_approved_quote_still_checks_negation_and_condition_boundaries(source, quote):
    result, client = await _approval(source, quote)
    rejected_once(result, client)


@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote,expected", [
    ("主任医师同意出院。", "主任医师同意出院。", "主任医师同意出院。"),
    ("主任医师同意出院。", "主任医师同意出院", "主任医师同意出院"),
    ("上级医师意见：1、同意今日\n出院。", "上级医师意见：1、同意今日出院。", "上级医师意见：1、同意今日\n出院。"),
    ("上级医师意见：1、同意今日出院。", "上级医师意见：1、同意今日出院。", "上级医师意见：1、同意今日出院。"),
    ("主任医师查房意见：同意出院。", "主任医师查房意见：同意出院。", "主任医师查房意见：同意出院。"),
])
async def test_complete_verbatim_or_labelled_opinion_still_accepted(source, quote, expected):
    result, _ = await _approval(source, quote)
    assert result.state == "ready"
    assert (result.assertions[0].role, result.assertions[0].opinion, result.assertions[0].quote) == (
        "senior", "approved", expected)


@pytest.mark.asyncio
async def test_scope_grounding_uses_original_assertion_index(caplog):
    # 第0条成功；第1、2条主引文与病名相同，不确定性引文不同，均零命中。
    text = "发热原因待查，继续观察。"
    client = _ScopeClient([
        _scope_claim("发热原因待查，", "发热原因", "待查"),
        _scope_claim("发热原因待查，", "发热原因", "未明确"),
        _scope_claim("发热原因待查，", "发热原因", "不清楚"),
    ])
    with caplog.at_level("WARNING"):
        result = await extract_diagnosis_scope([{"record_content": text}], client,
                                               max_prompt_bytes=65536, max_completion_tokens=16384)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")
    assert result.llm_call_count == len(client.prompts) == 2
    lines = [r.getMessage() for r in caplog.records if "diagnosis_scope_invalid" in r.getMessage()]
    assert len(lines) == 2
    for line in lines:
        assert "grounding=uncertainty:zero:r0:a1,uncertainty:zero:r0:a2 " in line
        for word in ("发热", "待查", "未明确", "不清楚", "观察"):
            assert word not in line


@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote,accepted", [
    # 程序只按句末标点核对整句，不看词义：半句不论前文是什么都拒绝，整句交模型判断。
    ("经主任医师查房，同意今日出院。", "同意今日出院。", False),
    ("经主任医师查房，同意今日出院。", "经主任医师查房，同意今日出院。", True),
    ("复查血常规未见异常，主任医师同意出院。", "主任医师同意出院。", False),
    ("复查血常规未见异常，主任医师同意出院。", "复查血常规未见异常，主任医师同意出院。", True),
    ("体温平稳后可出院，经主任医师查房同意今日出院。", "经主任医师查房同意今日出院。", False),
    ("主任医师同意出院，但家属要求继续观察。", "主任医师同意出院", False),
    ("主任医师暂缓出院。", "出院。", False),
    ("病情稳定。2、主任医师同意\n出院。", "主任医师同意出院。", True),  # 句末后的编号只是序号
])
async def test_approved_quote_must_be_whole_sentence_without_keyword_semantics(source, quote, accepted):
    result, client = await _approval(source, quote)
    if accepted:
        assert result.state == "ready" and result.assertions[0].opinion == "approved"
    else:
        rejected_once(result, client)


# ---- 08-02-02 复审 P2：整句引文首尾排版空白；角色补核提示与整句要求一致 ----

@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote,expected", [
    ("主任医师同意出院。\n继续观察。", "主任医师同意出院。\n", "主任医师同意出院。\n"),  # 逐字命中带尾随换行
    ("主任医师同意出院。\n继续观察。", "主任医师同意出院。", "主任医师同意出院。"),
    ("病情稳定。\n主任医师同意出院。", "\n主任医师同意出院。", "\n主任医师同意出院。"),  # 前导换行
    ("主任医师同意\n出院。\n继续观察。", "主任医师同意出院。 ", "主任医师同意\n出院。"),  # 空白还原带尾随空格
])
async def test_whole_sentence_with_edge_layout_whitespace_is_accepted(source, quote, expected):
    result, _ = await _approval(source, quote)
    assert result.state == "ready" and result.assertions[0].quote == expected
    assert result.assertions[0].opinion == "approved"


@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote", [
    ("主任医师不\n同意出院。", "\n同意出院。"),  # 换行不是断句依据，截掉否定仍拒绝
    ("若复查正常，\n主任医师同意出院。", "\n主任医师同意出院。"),  # 截掉前置条件
    ("主任医师同意出院\n，前提是复查正常。", "主任医师同意出院\n"),  # 截掉后置条件
])
async def test_edge_whitespace_never_turns_half_sentence_into_whole(source, quote):
    result, client = await _approval(source, quote)
    rejected_once(result, client)


_ROLE_TEXT = "患者要求出院，主任医师评估后同意出院。"


@pytest.mark.asyncio
async def test_role_recheck_prompt_keeps_whole_sentence_and_unknown_role():
    from test_discharge_approval_subject_condition_contract import SequencedClient, _payload as _seq_payload
    client = SequencedClient(_seq_payload("approved", _ROLE_TEXT), _seq_payload("approved", _ROLE_TEXT))
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "daily_course_record", _ROLE_TEXT),), client,
    )
    assert result.llm_call_count == len(client.calls) == 2
    second = client.calls[1][0]
    assert "纠正上一轮多个主体" in second
    assert "返回approved时仍须引用完整原句" in second
    assert "不得为单独摘出" in second
    assert result.state == "ready"
    assert (result.assertions[0].opinion, result.assertions[0].role) == ("approved", "unknown")


@pytest.mark.asyncio
async def test_role_recheck_half_sentence_is_rejected_without_extra_call():
    from test_discharge_approval_subject_condition_contract import SequencedClient, _payload as _seq_payload
    client = SequencedClient(_seq_payload("approved", _ROLE_TEXT), _seq_payload("approved", "主任医师评估后同意出院。"))
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "daily_course_record", _ROLE_TEXT),), client,
    )
    assert result.llm_call_count == len(client.calls) == 2
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")
