"""补核协议使用合成资料验证，不代表真实模型语义验收。"""
import copy
import json

import pytest

from app.services.luxian_0609 import course_body_fact_extraction as body
from app.services.luxian_0609.extended_document import antimicrobial_effect_extraction as effect
from app.services.luxian_0609.extended_document import discharge_course_stages as stages
from app.services.luxian_0609.extended_document.discharge_course_content import evaluate_discharge_course_content
from tests.unit.test_luxian_0609_discharge_course_content import payload, TEXT, SURGERY
from tests.unit.test_luxian_0609_native_extended_document_execution import _session


class Client:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    async def generate(self, prompt, temperature=None, **kwargs):
        self.calls.append((prompt, temperature, kwargs))
        value = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        if callable(value):
            value = value(prompt)
        content, finish = value if isinstance(value, tuple) else (value, "stop")
        return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=True)},
                              "finish_reason": finish}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 13, "total_tokens": 24}, "_api_time": .25}


def body_payload(quote="病情平稳。"):
    return {"schema_version": body.SCHEMA_VERSION, "documents": [
        {"document_ref": f"c{i}", "clinical_body": {"state": "present", "quote": quote}}
        for i in (1, 2)]}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["repair", "failure", "structure", "length", "privacy"])
async def test_body_targeted_retry(mode):
    good = body_payload()
    bad = body_payload("住院号：ZY123456" if mode == "privacy" else "病情平稳，继续治疗。")
    if mode == "structure":
        bad["extra"] = True
    client = Client([(bad, "length" if mode == "length" else "stop"),
                     bad if mode in {"failure", "structure"} else good])
    result = await body.extract_course_body_facts([
        body.CourseBodyDocument("doc1", "course", "病情平稳。"),
        body.CourseBodyDocument("doc2", "course", "病情平稳。")], client)
    assert result.llm_call_count == len(client.calls) == 2
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (22, 26, 48)
    assert (result.state, result.reason_code) == (
        ("data_gap", "semantic_extraction_unresolved") if mode in {"failure", "structure"} else ("ready", ""))
    retry = client.calls[1][0]
    if mode == "length":
        assert "截断" in retry and "PREVIOUS_OUTPUT" not in retry
    elif mode != "structure":
        assert "document_ref=c1" in retry and "document_ref=c2" in retry
        assert "clinical_body.quote" in retry and "PREVIOUS_OUTPUT=" in retry
        assert "ZY123456" not in retry
        if mode != "privacy":
            assert "病情平稳，继续治疗。" in retry


def effect_item(row=0, quote="甲药疗效良好。", target=0):
    return dict(row_index=row, target_index=target, effect_state="present", safety_state="absent",
                quote=quote, target_quote="甲药")


def effect_payload(items):
    return {"schema_version": effect.SCHEMA_VERSION, "assertions": items}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["repair", "failure", "structure", "length", "privacy", "missing", "duplicate"])
async def test_effect_targeted_retry_preserves_accepted_pairs(mode):
    good = effect_payload([effect_item(1)])
    bad = effect_payload([effect_item(), effect_item(1, "住院号：ZY123456" if mode == "privacy" else "甲药疗效较好。")])
    if mode == "structure":
        bad["extra"] = True
    elif mode == "missing":
        bad["assertions"].pop()
    elif mode == "duplicate":
        bad["assertions"].append(effect_item(1))
    if mode in {"structure", "length"}:
        good = effect_payload([effect_item(), effect_item(1)])
    client = Client([(bad, "length" if mode == "length" else "stop"), bad if mode == "failure" else good])
    result = await effect.extract_antimicrobial_effects(
        [{"content": "甲药疗效良好。"}] * 2, ["甲药"], client,
        max_prompt_bytes=1_000_000, max_completion_tokens=1_000_000)
    assert result.llm_call_count == len(client.calls) == 2 and result.total_tokens == 48
    assert (result.state, result.reason_code) == (("technical_error", "model_invalid_output") if mode == "failure" else ("ready", ""))
    retry = client.calls[1][0]
    if mode == "length":
        assert "截断" in retry and "PREVIOUS_OUTPUT" not in retry
    elif mode != "structure":
        assert "row_index=1" in retry and "target_index=0" in retry and "PREVIOUS_OUTPUT=" in retry
        assert "ZY123456" not in retry
        previous = retry.split("PREVIOUS_OUTPUT=", 1)[1].split("\nINPUT_JSON=", 1)[0]
        assert '"row_index": 0' not in previous
        assert json.loads(retry.split("\nINPUT_JSON=")[1])["requested_pairs"] == [{"row_index": 1, "target_index": 0}]


@pytest.mark.asyncio
async def test_effect_batches_have_independent_retry_context():
    def response(prompt):
        target = json.loads(prompt.split("\nINPUT_JSON=")[1])["targets"][0]["name"]
        quote = f"{target}疗效{'良好' if 'PREVIOUS_OUTPUT=' in prompt else '较好'}。"
        item = effect_item(quote=quote)
        item["target_quote"] = target
        return effect_payload([item])
    client = Client([response] * 4)
    result = await effect.extract_antimicrobial_effect_pairs(
        [{"content": "甲药疗效良好。乙药疗效良好。"}], ["甲药", "乙药"], [(0, 0), (0, 1)], client,
        max_prompt_bytes=1_000_000, max_completion_tokens=1_000_000)
    assert result.state == "ready" and result.llm_call_count == 4 and result.total_tokens == 96
    assert "PREVIOUS_OUTPUT" not in client.calls[2][0]
    assert "甲药" not in client.calls[3][0].split("PREVIOUS_OUTPUT=")[1].split("\nINPUT_JSON=")[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["A", "C"])
@pytest.mark.parametrize("mode", ["repair", "failure", "structure", "privacy", "coverage"])
async def test_discharge_stages_targeted_retry(stage, mode):
    good = payload(surgery=True)
    bad = copy.deepcopy(good)
    if stage == "A":
        atoms = list(bad[stage]["discharges"][0]["fields"].values())
    else:
        atoms = bad[stage]["events"][0]["matches"]
    for atom in atoms:
        atom.update(span_id=999, conflict_span_id=999)
    if mode == "structure":
        bad[stage]["extra"] = True
    elif mode == "privacy":
        # 非法编号仍按原合同拒收，回显须先解码再脱敏。
        atoms[0]["span_id"] = "住院号：ZY123456"
    elif mode == "coverage":
        bad[stage]["discharges" if stage == "A" else "events"] = []
    seen = {"A": 0, "C": 0}

    def response(prompt):
        current = prompt.splitlines()[0][-1]
        seen[current] += 1
        return (bad if current == stage and (seen[current] == 1 or mode in {"failure", "structure"}) else good)[current]

    client = Client([response] * 4)
    snapshot, materials = _session({"discharge_record": [{"document_id": "d", "treatment_course": TEXT + SURGERY}],
                                    "surgery_record": [{"document_id": "s", "surgery_name": SURGERY}]})
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=client)
    assert result.llm_call_count == 3 and result.total_tokens == 72
    assert (result.state, result.reason) == (("data_gap", "source_readiness_unproven") if mode in {"failure", "structure"} else ("compliant", "requirement_satisfied"))
    prompts = [p for p, _, _ in client.calls if p.startswith("阶段" + stage)]
    retry = prompts[1]
    assert "PREVIOUS_OUTPUT=" in retry
    assert "ZY123456" not in retry
    if mode not in {"structure", "coverage"}:
        assert "document_index" in retry and "span_id" in retry and "999" in retry
        if stage == "A":
            assert all(field in retry.split("上一次输出未通过校验")[1] for field in stages.FIELDS)


def test_stages_collect_state_inconsistencies():
    docs = [{"document_index": 1, "source": "discharge_record", "text": TEXT}]
    bad = payload()["A"]
    for atom in bad["discharges"][0]["fields"].values():
        atom["conflict_span_id"] = 1
    with pytest.raises(ValueError) as caught:
        stages.validate_response("A", bad, docs, [])
    retry = stages.retry_prompt(stages.prompt("A", docs, []), caught.value, json.dumps(bad))
    assert all(field in retry.split("上一次输出未通过校验")[1] for field in stages.FIELDS)
    assert "PREVIOUS_OUTPUT=" in retry


def test_empty_issue_violations_keep_generic_reason():
    from app.services.luxian_0609 import course_body_fact_extraction
    from app.services.luxian_0609.extended_document import antimicrobial_effect_extraction
    for cls in (course_body_fact_extraction._BodyViolation, antimicrobial_effect_extraction._EffectViolation):
        error = cls([])
        assert str(error) == "incomplete coverage" and error.issues == ()
