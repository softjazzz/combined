"""会诊补核合同：合成材料、定向提示、隐私和冻结边界。"""

import json
from dataclasses import replace

import pytest

from app.services.luxian_0609 import consultation_disposition_record as record
from app.services.luxian_0609 import consultation_measure_check as measure
from app.services.luxian_0609 import native_consultation_episode_execution as episode
import test_luxian_0609_consultation_disposition_record as dr
import test_luxian_0609_consultation_measure_check as mc
import test_luxian_0609_native_consultation_episode_execution as ep


class Client:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    async def generate(self, prompt, temperature=None, **kwargs):
        self.prompts.append(prompt)
        response = self.responses[min(len(self.prompts) - 1, len(self.responses) - 1)]
        return {**response, "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}}


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["opinion", "action"])
@pytest.mark.parametrize("fixed", [True, False])
async def test_disposition_targeted_retry(stage, fixed):
    docs = dr.documents("建议完善痰培养。已完善痰培养。")
    good_roles = dr.opinions("建议完善痰培养", "已完善痰培养")
    good_actions = dr.response(dr.item("完善痰培养", "已完善痰培养", "performed"))
    if stage == "opinion":
        bad = dr.opinions("错误意见", "错误反馈")
        client = Client(bad, good_roles if fixed else bad, good_actions)
        retry_index, location = 1, "opinion_quotes"
    else:
        bad = dr.response(dr.item("完善痰培养", "错误反馈", "performed"))
        client = Client(good_roles, bad, good_actions if fixed else bad)
        retry_index, location = 2, "feedback_quote"
    result = await record.check_disposition_record(documents=docs, llm_client=client)
    expected = ("compliant", "requirement_satisfied") if fixed else (
        ("technical_error", "model_invalid_output") if stage == "opinion" else
        ("data_gap", "semantic_extraction_unresolved"))
    assert (result.status, result.reason) == expected
    assert result.llm_call_count == (3 if fixed or stage == "action" else 2)
    assert result.total_tokens == result.llm_call_count * 16
    retry = client.prompts[retry_index]
    assert "consultation_record-1" in retry and location in retry
    assert "错误反馈" in retry and "PREVIOUS_OUTPUT=" in retry
    if stage == "opinion":
        assert "错误意见" in retry


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["opinion", "action"])
async def test_disposition_escaped_identity_is_redacted(stage):
    good = dr.opinions("建议完善痰培养", "已完善痰培养")
    bad = (dr.opinions("住院号：ZY123456") if stage == "opinion" else
           dr.response(dr.item("完善痰培养", "住院号：ZY123456", "performed")))
    bad["content"] = json.dumps(json.loads(bad["content"]), ensure_ascii=True)
    client = Client(bad, bad) if stage == "opinion" else Client(good, bad, bad)
    await record.check_disposition_record(documents=dr.documents("建议完善痰培养。已完善痰培养。"), llm_client=client)
    assert "PREVIOUS_OUTPUT=" in client.prompts[-1]
    assert "ZY123456" not in client.prompts[-1]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["opinion", "action"])
async def test_disposition_length_retry_omits_previous(stage):
    bad = {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
    good = dr.opinions("建议完善痰培养", "已完善痰培养")
    client = Client(bad, bad) if stage == "opinion" else Client(good, bad)
    result = await record.check_disposition_record(documents=dr.documents("建议完善痰培养。已完善痰培养。"), llm_client=client)
    assert "截断" in client.prompts[-1] if stage == "opinion" else result.llm_call_count == 2
    assert "PREVIOUS_OUTPUT=" not in client.prompts[-1]


def measure_answer(completed, aliases, *, quote="电针", action="电针", evidence=None):
    return {"content": json.dumps({"schema_version": measure.SCHEMA_VERSION, "generic": [], "measures": [{
        "recommendation_ref": completed[0].recommendation.recommendation_ref, "measure": "电针",
        "quote": quote, "executed_action": action, "action_relation": "matched",
        "evidence_ref": evidence or next(iter(aliases.values()))}]}, ensure_ascii=True)}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["quote", "action", "evidence", "coverage", "measure", "generic"])
async def test_measure_retry_locates_all_failures(failure):
    completed, candidates, allowed, aliases = mc._setup(("电针",))
    completed = (replace(completed[0], recommendation=replace(completed[0].recommendation,
        source_quote="电针", normalized_action="电针")),)
    good = measure_answer(completed, aliases)
    bad = json.loads(good["content"])
    item = bad["measures"][0]
    if failure == "coverage":
        bad["measures"] = []
    elif failure == "generic":
        bad["generic"] = [{"recommendation_ref": item["recommendation_ref"], "text": "不存在的嘱咐"}]
    else:
        item[{"action": "executed_action", "evidence": "evidence_ref"}.get(failure, failure)] = "住院号：ZY123456"
    client = Client({"content": json.dumps(bad, ensure_ascii=True)}, good)
    result = await measure.check_consultation_measures(completed=completed, candidates=candidates,
        allowed_refs=allowed, alias_by_ref=aliases, llm_client=client)
    assert result.state == "ready" and result.llm_call_count == 2 and result.total_tokens == 32
    retry = client.prompts[1]
    assert "PREVIOUS_OUTPUT=" in retry and "ZY123456" not in retry
    assert completed[0].recommendation.recommendation_ref in retry
    assert "第1项" in retry or "覆盖" in retry


def episode_answer(quote="复查血常规"):
    return ep._payload(episodes=[ep._episode("consultation_record-1", ["consultation_record-1"], recommendations=[{
        "recommendation_ref": "consultation_record-1#r1", "action_type": "test", "source_quote": quote,
        "normalized_action": "复查血常规", "opinion_ref": "consultation_record-1"}])])


@pytest.mark.asyncio
@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("field,value", [("confidence", "medium"), ("opinion_state", "vague")])
@pytest.mark.parametrize("fixed", [False, True])
async def test_episode_inconsistent_recommendations_get_one_review(
    monkeypatch, tmp_path, compact, field, value, fixed,
):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: ep._rows("专科会诊意见"))
    if compact:
        original = episode._documents
        monkeypatch.setattr(episode, "_documents", lambda *a, **kw: tuple(
            {**doc, "event_identity_mode": "document", "event_group_ref": doc["ref"]}
            for doc in original(*a, **kw)))
        good = ep._document_payload(ep._document_fact("consultation_record-1"))
        key = "consultation_event_facts"
    else:
        good, key = episode_answer(), "episodes"
    bad = json.loads(json.dumps(good))
    bad[key][0][field] = value
    client = Client({"content": json.dumps(bad)}, {"content": json.dumps(good if fixed else bad)})
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-02", "LX0609-03-01-03"), institute_id="i", patient_id="p",
        visit_id="synthetic-consistency", source_schema=None, llm_client=client, opinion_freeze_dir=tmp_path)
    assert result.llm_call_count == 2 and result.total_tokens == 32
    assert {item["status"] for item in result.results} == ({"compliant"} if fixed else {"technical_error"})
    assert field in client.prompts[1] and "recommendations" in client.prompts[1]
    assert "不能直接提高置信度" in client.prompts[1]
    assert bool(list(tmp_path.glob("*.json"))) == fixed


@pytest.mark.asyncio
@pytest.mark.parametrize("fixed", [True, False])
async def test_episode_retry_is_grounded_before_freezing(monkeypatch, tmp_path, fixed):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: ep._rows("专科会诊意见"))
    bad = {"content": json.dumps(episode_answer("住院号：ZY123456"), ensure_ascii=True)}
    good = {"content": json.dumps(episode_answer(), ensure_ascii=False)}
    client = Client(bad, good if fixed else bad)
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-02", "LX0609-03-01-03"), institute_id="i", patient_id="p",
        visit_id="synthetic-retry", source_schema=None, llm_client=client, opinion_freeze_dir=tmp_path)
    assert result.llm_call_count == 2 and result.total_tokens == 32
    assert {item["status"] for item in result.results} == ({"compliant"} if fixed else {"technical_error"})
    retry = client.prompts[1]
    assert "source_quote" in retry and "consultation_record-1#r1" in retry and "PREVIOUS_OUTPUT=" in retry
    assert "ZY123456" not in retry
    assert bool(list(tmp_path.glob("*.json"))) == fixed
    if not fixed:
        assert {item["metadata"]["reason_code"] for item in result.results} == {"model_invalid_output"}
    else:
        frozen_client = Client(bad)
        reused = await episode.execute_luxian_0609_native_consultation_episode_rules(
            rule_ids=("LX0609-03-01-02", "LX0609-03-01-03"), institute_id="i", patient_id="p",
            visit_id="synthetic-retry", source_schema=None, llm_client=frozen_client, opinion_freeze_dir=tmp_path)
        assert reused.llm_call_count == 0 and not frozen_client.prompts
        assert {item["status"] for item in reused.results} == {"compliant"}


@pytest.mark.asyncio
@pytest.mark.parametrize("stage,calls", [("opinion", 2), ("action", 2)])
async def test_disposition_structure_keeps_existing_call_limit(stage, calls):
    good = dr.opinions("建议完善痰培养", "已完善痰培养")
    bad = {"content": "{}"}
    client = Client(bad) if stage == "opinion" else Client(good, bad)
    result = await record.check_disposition_record(documents=dr.documents("建议完善痰培养。已完善痰培养。"), llm_client=client)
    assert (result.status, result.reason, result.llm_call_count) == ("technical_error", "model_invalid_output", calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["structure", "length", "quote", "coverage"])
async def test_measure_terminal_failure_and_truncation(kind):
    completed, candidates, allowed, aliases = mc._setup(("电针",))
    completed = (replace(completed[0], recommendation=replace(completed[0].recommendation,
        source_quote="电针、头皮针", normalized_action="电针、头皮针")),)
    if kind == "structure":
        bad = {"content": "{}"}
    elif kind == "length":
        bad = {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
    else:
        bad = measure_answer(completed, aliases, quote="错误引文" if kind == "quote" else "电针")
    client = Client(bad)
    result = await measure.check_consultation_measures(completed=completed, candidates=candidates,
        allowed_refs=allowed, alias_by_ref=aliases, llm_client=client)
    assert result.state == ("unresolved" if kind == "coverage" else "failed")
    assert result.llm_call_count == 2 and result.total_tokens == 32
    if kind == "length":
        assert "截断" in client.prompts[1] and "PREVIOUS_OUTPUT=" not in client.prompts[1]
    elif kind != "structure":
        assert "PREVIOUS_OUTPUT=" in client.prompts[1]
        assert "头皮针" in client.prompts[1] and "consultation_record-1#r1" in client.prompts[1]


@pytest.mark.asyncio
async def test_measure_collects_generic_quote_and_action_in_one_response():
    completed, candidates, allowed, aliases = mc._setup(("电针",))
    completed = (replace(completed[0], recommendation=replace(completed[0].recommendation,
        source_quote="电针", normalized_action="电针")),)
    bad = json.loads(measure_answer(completed, aliases, quote="错误引文", action="错误动作")["content"])
    bad["generic"] = [{"recommendation_ref": completed[0].recommendation.recommendation_ref, "text": "错误嘱咐"}]
    client = Client({"content": json.dumps(bad)}, measure_answer(completed, aliases))
    result = await measure.check_consultation_measures(completed=completed, candidates=candidates,
        allowed_refs=allowed, alias_by_ref=aliases, llm_client=client)
    assert result.state == "ready"
    hint = client.prompts[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert all(value in hint for value in ("错误引文", "错误动作", "错误嘱咐", ".quote", ".executed_action", ".generic"))


@pytest.mark.asyncio
async def test_disposition_collects_missing_document_and_all_role_quotes():
    docs = dr.documents("建议完善痰培养。已完善痰培养。")
    docs.append({"ref": "consultation_record-2", "text": "建议复查血常规。"})
    bad = dr.opinions("错误意见", "错误反馈")
    client = Client(bad)
    result = await record.check_disposition_record(documents=docs, llm_client=client)
    assert result.llm_call_count == 2 and result.reason == "model_invalid_output"
    hint = client.prompts[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert all(value in hint for value in ("错误意见", "错误反馈", "consultation_record-2", "opinion_quotes", "feedback_quotes"))


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["enum", "json", "quote_type"])
async def test_episode_structure_does_not_add_retry(monkeypatch, tmp_path, kind):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: ep._rows("专科会诊意见"))
    answer = episode_answer()
    if kind == "enum":
        answer["episodes"][0]["recommendations"][0]["action_type"] = "invalid"
    elif kind == "quote_type":
        answer["episodes"][0]["recommendations"][0]["source_quote"] = []
    client = Client({"content": "invalid" if kind == "json" else json.dumps(answer)})
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-02", "LX0609-03-01-03"), institute_id="i", patient_id="p",
        visit_id="synthetic-shape", source_schema=None, llm_client=client, opinion_freeze_dir=tmp_path)
    assert result.llm_call_count == 1 and result.total_tokens == 16
    assert {item["metadata"]["reason_code"] for item in result.results} == {"model_invalid_output"}
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.asyncio
async def test_episode_compact_retry_echoes_original_failed_quote(monkeypatch, tmp_path):
    rows = ep._rows("会诊意见：复查血常规", action_suffix=False)
    rows[0].update(document_id="synthetic-doc", event_identity_mode="document")
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: rows)
    # 直接提供独立文书身份，覆盖生产使用的紧凑协议。
    original_documents = episode._documents

    def compact_documents(*args, **kwargs):
        documents = original_documents(*args, **kwargs)
        return tuple({**document, "event_identity_mode": "document", "event_group_ref": document["ref"]}
                     for document in documents)

    monkeypatch.setattr(episode, "_documents", compact_documents)
    good = ep._document_payload(ep._document_fact("consultation_record-1"))
    bad = json.loads(json.dumps(good))
    bad["consultation_event_facts"][0]["recommendations"][0]["source_quote"] = "错误摘录"
    client = Client({"content": json.dumps(bad)}, {"content": json.dumps(good)})
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-03",), institute_id="i", patient_id="p", visit_id="synthetic-compact",
        source_schema=None, llm_client=client, opinion_freeze_dir=tmp_path)
    assert result.llm_call_count == 2
    assert result.results[0]["status"] == "compliant"
    hint = client.prompts[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert "错误摘录" in hint and "source_quote" in hint and "consultation_record-1#r1" in hint
