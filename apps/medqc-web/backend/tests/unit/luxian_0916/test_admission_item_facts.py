"""入院专项反例：逐项事实必须经过真实抽取边界后再形成客户结果。"""
import json

import pytest

from app.services.luxian_0916.admission_rules import execute_admission_rules
from app.services.luxian_0916.admission_content_items import _locate_quote, item_retry_prompt
from app.services.luxian_0916.semantic_extractor import extract_luxian_0916_facts
from app.services.luxian_0916.semantic_extractor import _prompt


PAST_KEYS = (
    "general_health", "diseases", "infections", "vaccinations",
    "surgery", "trauma", "transfusion", "allergies",
)
NEGATIVE = "一般健康良好；否认疾病、传染病、手术、外伤、输血及过敏史；已按计划接种。"


def test_shared_prompt_has_one_admission_fact_shape_per_rule():
    prompt = _prompt(documents=[], rule_ids=["LX0916-003", "LX0916-005", "LX0916-006"])
    assert "LX0916-001 至 LX0916-009（每项必须有 state" not in prompt
    assert "005和006只返回document_id、source_type、items" in prompt
    assert "001、002、003、004、007、008、009" in prompt
    assert "明确不详优先于描述笼统" in prompt
    assert "四个顶层容器不得省略" in prompt
    assert '"event_facts":{},"document_facts":{},"discharge_facts":{}' in prompt


async def evaluate(rule_id, items, content=NEGATIVE, **overrides):
    fact = {"document_id": "A1", "source_type": "admission_record", "items": items}
    fact.update(overrides)

    async def generate(prompt, **kwargs):
        return {"choices": [{"message": {"content": json.dumps({
            "semantic_facts": {rule_id: fact}, "document_facts": {},
            "event_facts": {}, "discharge_facts": {},
        })}}]}

    extracted = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {
            "admission_record": [{"document_id": "A1", "content": content}],
        }}}, rule_ids=[rule_id], generate=generate,
    )
    return execute_admission_rules({
        "documents": {"admission_record": {"document_id": "A1", "content": content}},
        "semantic_facts": extracted["semantic_facts"],
    }, [rule_id])[0]


def negative_items():
    return {key: {"status": "recorded" if key in {"general_health", "vaccinations"}
                  else "denied", "quote": NEGATIVE} for key in PAST_KEYS}


@pytest.mark.asyncio
async def test_short_negative_history_is_complete_and_has_source_evidence():
    result = await evaluate("LX0916-006", negative_items())
    assert result.status == "compliant"
    assert NEGATIVE in "".join(result.evidence)
    assert result.decision_facts["item_states"]["allergies"] == "denied"


@pytest.mark.asyncio
async def test_confirmed_missing_names_specific_item_not_generic_incomplete():
    items = negative_items()
    items["vaccinations"] = {"status": "missing", "quote": ""}
    result = await evaluate("LX0916-006", items, content=NEGATIVE.replace("已按计划接种。", ""))
    # 其他引用也应使用当前真实原文。
    assert result.status == "data_quality_gap"
    for item in items.values():
        if item["quote"]:
            item["quote"] = NEGATIVE.replace("已按计划接种。", "")
    result = await evaluate("LX0916-006", items, content=NEGATIVE.replace("已按计划接种。", ""))
    assert result.status == "non_compliant"
    assert "预防接种史" in result.findings and "预防接种史" in result.suggestion


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["omitted", "unknown", "invalid_quote", "wrong_document", "truncated"])
async def test_unextracted_or_unverifiable_is_not_confirmed_missing(change):
    items = negative_items()
    overrides = {}
    content = NEGATIVE
    if change == "omitted":
        items.pop("vaccinations")
    elif change == "unknown":
        items["vaccinations"] = {"status": "unknown", "quote": ""}
    elif change == "invalid_quote":
        items["vaccinations"]["quote"] = "不存在的原文"
    elif change == "wrong_document":
        overrides["document_id"] = "other-admission"
    else:
        content = "甲" * 2600 + NEGATIVE
    result = await evaluate("LX0916-006", items, content, **overrides)
    assert result.status == "data_quality_gap"


@pytest.mark.asyncio
async def test_explicit_unknown_medication_does_not_become_missing():
    content = "外院CT提示结石，予解痉治疗，具体用药不详，疼痛缓解。"
    items = {
        "examination": {"status": "recorded", "quote": "外院CT提示结石"},
        "treatment": {"status": "unknown", "quote": "予解痉治疗，具体用药不详"},
        "effect": {"status": "recorded", "quote": "疼痛缓解"},
    }
    result = await evaluate("LX0916-005", items, content)
    assert result.status == "data_quality_gap"
    assert "入院前治疗经过" in result.findings
    assert "确认缺失" not in result.findings


@pytest.mark.asyncio
async def test_documented_unknown_is_distinct_from_unextracted_information():
    content = "外院CT提示结石，予解痉治疗，具体用药不详，疼痛缓解。"
    items = {
        "examination": {"status": "recorded", "quote": "外院CT提示结石"},
        "treatment": {"status": "documented_unknown", "quote": "予解痉治疗，具体用药不详"},
        "effect": {"status": "recorded", "quote": "疼痛缓解"},
    }
    result = await evaluate("LX0916-005", items, content)
    # 未冻结医学合格性前保留待复核，不能冒称系统原文缺失或自动判合规。
    assert result.status == "data_quality_gap"
    assert result.reason_code == "recorded_information_unknown"
    assert result.decision_facts["documented_unknown_items"] == ["入院前治疗经过"]
    assert result.decision_facts["unknown_items"] == []
    assert result.decision_facts["missing_items"] == []
    assert "原文已明确记载信息不详" in result.findings
    assert "抽取未确定" not in result.findings
    assert "具体用药不详" in "".join(result.evidence)
    assert "补齐" not in result.suggestion

    items["treatment"] = {"status": "unknown", "quote": ""}
    unextracted = await evaluate("LX0916-005", items, content)
    assert unextracted.reason_code == "semantic_fact_unavailable"
    assert unextracted.decision_facts.get("documented_unknown_items", []) == []
    assert unextracted.decision_facts["unknown_items"] == ["入院前治疗经过"]


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["", "原文没有的患者无法提供说明"])
async def test_documented_unknown_requires_verifiable_source_quote(quote):
    content = "患者不能提供院前诊疗资料。"
    items = {key: {"status": "documented_unknown", "quote": quote}
             for key in ("examination", "treatment", "effect")}
    result = await evaluate("LX0916-005", items, content)
    assert result.status == "data_quality_gap"
    assert result.reason_code == "semantic_fact_unavailable"


@pytest.mark.asyncio
async def test_documented_unknown_does_not_hide_a_separate_confirmed_missing_item():
    content = "院前检查不详，曾输液治疗。"
    result = await evaluate("LX0916-005", {
        "examination": {"status": "documented_unknown", "quote": "院前检查不详"},
        "treatment": {"status": "missing", "quote": "曾输液治疗"},
        "effect": {"status": "unknown", "quote": ""},
    }, content)
    assert result.status == "non_compliant"
    assert result.decision_facts["missing_items"] == ["入院前治疗经过"]
    assert result.decision_facts["documented_unknown_items"] == ["入院前检查及结果"]
    assert result.decision_facts["unknown_items"] == ["入院前治疗效果"]
    assert "原文已明确记载信息不详" in result.findings
    assert "入院前检查及结果" not in result.suggestion


@pytest.mark.asyncio
async def test_new_005_information_state_does_not_change_006_contract():
    items = negative_items()
    items["vaccinations"] = {"status": "documented_unknown", "quote": NEGATIVE}
    result = await evaluate("LX0916-006", items)
    assert result.status == "data_quality_gap"
    assert result.reason_code == "semantic_fact_unavailable"


def test_005_prompt_separates_information_unknown_from_model_uncertainty():
    prompt = _prompt(documents=[], rule_ids=["LX0916-005", "LX0916-006"])
    assert "documented_unknown" in prompt
    assert "明确不详不自动判合规或确认缺失" in prompt
    assert "不能仅因出现输液或口服药等治疗方式就用recorded" in prompt


@pytest.mark.asyncio
async def test_explicit_no_prior_care_does_not_require_invented_treatment():
    content = "本次发病后未行任何检查或治疗。"
    items = {key: {"status": "not_applicable", "quote": content}
             for key in ("examination", "treatment", "effect")}
    assert (await evaluate("LX0916-005", items, content)).status == "not_applicable"


@pytest.mark.asyncio
async def test_bare_legacy_state_cannot_report_new_defect():
    result = await evaluate("LX0916-006", {}, state="incomplete")
    assert result.status == "data_quality_gap"


@pytest.mark.asyncio
async def test_quote_punctuation_variation_returns_original_not_model_rewrite():
    items = negative_items()
    items["vaccinations"]["quote"] = "已按计划接种，"
    result = await evaluate("LX0916-006", items)
    assert result.status == "compliant"
    assert "预防接种史：已按计划接种" in result.evidence
    assert "预防接种史：已按计划接种，" not in result.evidence


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["否认疾病史", "否认疾病；已按计划接种。", "已按规范接种"])
async def test_semantic_rewrite_and_joined_nonadjacent_quotes_rejected(quote):
    items = negative_items()
    items["vaccinations"]["quote"] = quote
    assert (await evaluate("LX0916-006", items)).status == "data_quality_gap"


def test_quote_alignment_does_not_erase_decimal_or_negative_sign():
    assert _locate_quote("剂量35mg。", "剂量3.5mg，") is None
    assert _locate_quote("测量值-3.5，", "测量值3.5。") is None
    assert _locate_quote("已接种。", "已接种，后又记已接种；") is None


@pytest.mark.parametrize("rule_id", ["LX0916-005", "LX0916-006"])
@pytest.mark.parametrize("state", ["complete", "incomplete", "not_applicable"])
def test_new_execution_does_not_consume_legacy_global_verdict(rule_id, state):
    result = execute_admission_rules({
        "documents": {"admission_record": {"document_id": "A1", "content": NEGATIVE}},
        "semantic_facts": {rule_id: {"state": state}},
    }, [rule_id])[0]
    assert result.status == "data_quality_gap"


@pytest.mark.asyncio
async def test_missing_and_unknown_are_reported_separately():
    items = negative_items()
    items["vaccinations"] = {"status": "missing", "quote": ""}
    items["transfusion"] = {"status": "unknown", "quote": ""}
    content = "一般健康良好；否认疾病、传染病、手术、外伤及过敏史。"
    for key, item in items.items():
        if item["quote"]:
            item["quote"] = content
    result = await evaluate("LX0916-006", items, content)
    assert result.status == "non_compliant"
    assert result.decision_facts["missing_items"] == ["预防接种史"]
    assert result.decision_facts["unknown_items"] == ["输血史"]
    assert "输血史" not in result.suggestion


@pytest.mark.asyncio
@pytest.mark.parametrize("with_other_source", [False, True])
async def test_omitted_auxiliary_containers_only_tolerated_for_admission_only_input(with_other_source):
    calls = []
    payload = {"semantic_facts": {"LX0916-006": {
        "document_id": "A1", "source_type": "admission_record", "items": negative_items(),
    }}}

    async def generate(prompt, **kwargs):
        calls.append(prompt)
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    documents = {"admission_record": [{"document_id": "A1", "content": NEGATIVE}]}
    rules = ["LX0916-006"]
    if with_other_source:
        documents["first_course_record"] = [{"document_id": "F1", "content": "首次病程材料"}]
        rules.append("LX0916-010")
    facts = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": documents}},
        rule_ids=rules, generate=generate,
    )
    if with_other_source:
        assert facts["diagnostic"]["code"] == "semantic_extraction_invalid"
        assert len(calls) == 2
    else:
        result = execute_admission_rules({"documents": {"admission_record": documents["admission_record"][0]},
                                          "semantic_facts": facts["semantic_facts"]}, ["LX0916-006"])[0]
        assert result.status == "compliant"
        assert len(calls) == 1
        assert facts["event_facts"] == facts["document_facts"] == facts["discharge_facts"] == {}
        payload.update({"event_facts": {}, "document_facts": {}, "discharge_facts": {}})
        complete = await extract_luxian_0916_facts(
            evidence_payload={"programmatic_timeline": {"documents": documents}},
            rule_ids=rules, generate=generate,
        )
        assert complete == facts


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"event_facts": {}}, {"semantic_facts": None},
    {"semantic_facts": {}, "event_facts": None},
    {"semantic_facts": {}, "unexpected": {}},
    {"semantic_facts": {"unknown_fact": True}},
])
async def test_admission_only_tolerance_still_rejects_invalid_shape_and_facts(payload):
    async def generate(prompt, **kwargs):
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    facts = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {
            "admission_record": [{"document_id": "A1", "content": NEGATIVE}],
        }}}, rule_ids=["LX0916-006"], generate=generate,
    )
    assert facts["diagnostic"]["code"] == "semantic_extraction_invalid"
    assert facts["semantic_facts"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("repair", ["valid", "invalid", "exception", "extra_rule", "truncated_reply", "wrong_type"])
async def test_item_source_failure_retries_once_without_replacing_other_rules(repair):
    good = {"document_id": "A1", "source_type": "admission_record", "items": negative_items()}
    bad = json.loads(json.dumps(good))
    bad["items"]["allergies"]["quote"] = "原文没有这句话"
    original = {"state": "complete", "document_id": "A1", "source_type": "admission_record"}
    calls = []

    async def generate(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 2 and repair == "exception":
            raise TimeoutError()
        if len(calls) == 2 and repair == "truncated_reply":
            return {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        if len(calls) == 2 and repair == "wrong_type":
            return {"choices": [{"message": {"content": None}}]}
        semantic = {"LX0916-006": bad if len(calls) == 1 or repair == "invalid" else good}
        if len(calls) == 1:
            semantic["LX0916-003"] = original
        elif repair == "extra_rule":
            semantic["LX0916-003"] = {**original, "state": "incomplete"}
        return {"choices": [{"message": {"content": json.dumps({
            "semantic_facts": semantic, "event_facts": {}, "document_facts": {}, "discharge_facts": {},
        })}}]}

    facts = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {
            "admission_record": [{"document_id": "A1", "content": NEGATIVE}],
        }}}, rule_ids=["LX0916-003", "LX0916-006"], generate=generate,
    )
    assert len(calls) == facts["diagnostic"]["llm_call_count"] == 2
    assert facts["semantic_facts"]["LX0916-003"] == original
    assert ("LX0916-006" in facts["semantic_facts"]) == (repair == "valid")
    assert facts["diagnostic"]["grounding_retry_applied"] is True


def test_item_retry_prompt_has_an_unambiguous_target_only_shape():
    document = {"document_id": "A1", "source_type": "admission_record", "content": NEGATIVE}
    prompt = item_retry_prompt(document, ["LX0916-006"])
    marker = "示例的unknown只展示结构，不是判定答案；逐项核对原文后填写实际状态与引用。"
    example = json.loads(prompt.split(marker)[1].split("\nquote必须")[0])
    assert set(example) == {"semantic_facts", "event_facts", "document_facts", "discharge_facts"}
    assert set(example["semantic_facts"]) == {"LX0916-006"}
    fact = example["semantic_facts"]["LX0916-006"]
    assert set(fact) == {"document_id", "source_type", "items"}
    assert set(fact["items"]) == set(PAST_KEYS)
    assert "LX0916-005" not in prompt


@pytest.mark.asyncio
async def test_item_source_failure_does_not_retry_a_third_time():
    calls = []
    async def generate(prompt, **kwargs):
        calls.append(prompt)
        content = {} if len(calls) == 1 else {"semantic_facts": {"LX0916-006": {
            "document_id": "A1", "source_type": "admission_record", "items": {
                "allergies": {"status": "denied", "quote": "不存在的引用"},
            },
        }}, "event_facts": {}, "document_facts": {}, "discharge_facts": {}}
        return {"choices": [{"message": {"content": json.dumps(content)}}]}
    facts = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {
            "admission_record": [{"document_id": "A1", "content": NEGATIVE}],
        }}}, rule_ids=["LX0916-006"], generate=generate,
    )
    assert len(calls) == facts["diagnostic"]["llm_call_count"] == 2
    assert "LX0916-006" not in facts["semantic_facts"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["no_fact", "truncated", "empty"])
async def test_source_retry_requires_complete_source_and_an_explicit_rejected_fact(change):
    calls = []
    content = "甲" * 2600 + NEGATIVE if change == "truncated" else NEGATIVE
    if change == "empty":
        content = ""
    async def generate(prompt, **kwargs):
        calls.append(prompt)
        semantic = {} if change == "no_fact" else {"LX0916-006": {
            "document_id": "A1", "source_type": "admission_record", "items": {
                "allergies": {"status": "denied", "quote": "不存在的引用"},
            },
        }}
        return {"choices": [{"message": {"content": json.dumps({"semantic_facts": semantic,
            "event_facts": {}, "document_facts": {}, "discharge_facts": {}})}}]}
    facts = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {
            "admission_record": [{"document_id": "A1", "content": content}],
        }}}, rule_ids=["LX0916-006"], generate=generate,
    )
    assert len(calls) == (0 if change == "empty" else 1)
    assert "LX0916-006" not in facts["semantic_facts"]
    assert not facts["diagnostic"].get("grounding_retry_applied", False)
