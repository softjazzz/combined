"""047后评价按完整文书分批；固定应答只验证协议和索引，不调用真实模型。"""
import json

import pytest

from app.services.luxian_0609 import posttransfusion_effect_extraction as effect
from test_luxian_0609_047_evaluation_window import _session, _execute_with_effect_labels, _canonical_state


class FixedEffects:
    def __init__(self, *, bad_batch=None, bad_quote_once=False):
        self.calls = []
        self.bad_batch = bad_batch
        self.bad_quote_once = bad_quote_once

    async def generate(self, prompt, **kwargs):
        items = json.loads(prompt.split("INPUT_JSON=", 1)[1])["items"]
        self.calls.append((items, kwargs))
        rows = [{"index": row["index"], "state": "evaluated", "quote": row["content"][-8:]} for row in items]
        if self.bad_batch == len(self.calls):
            rows[0]["index"] = -1
        if self.bad_quote_once and len(self.calls) == 1:
            rows[0]["quote"] = "原文不存在的引文"
        return {"choices": [{"message": {"content": json.dumps({"schema_version": effect.SCHEMA_VERSION,
            "items": rows}, ensure_ascii=False)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def candidates(count, size=24):
    return [effect.PosttransfusionEffectCandidate("daily_course_record", f"DOC-{i}",
            f"第{i}份病程。" + "合成正文" * size + "输血后乏力减轻。") for i in range(count)]


@pytest.mark.asyncio
@pytest.mark.parametrize("count,size", [(27, 24), (12, 500)])
async def test_complete_candidates_are_split_by_count_and_characters_without_losing_identity(count, size):
    client = FixedEffects()
    docs = candidates(count, size)
    result = await effect.confirm_posttransfusion_effects(docs, client)
    assert result.state == "ready"
    assert result.confirmed == frozenset((doc.source_key, doc.document_id) for doc in docs)
    assert result.llm_call_count == len(client.calls) > 1
    assert result.total_tokens == 15 * len(client.calls)
    sent = [row for batch, _ in client.calls for row in batch]
    assert [row["index"] for row in sent] == list(range(count))
    for batch, _ in client.calls:
        assert len(batch) <= effect.MAX_CANDIDATES
        assert len(json.dumps(batch, ensure_ascii=False)) <= effect.MAX_BATCH_CHARS
    assert [row["content"] for row in sent] == [doc.text for doc in docs]


@pytest.mark.asyncio
async def test_bad_binding_in_later_batch_is_not_published_as_complete():
    client = FixedEffects(bad_batch=2)
    result = await effect.confirm_posttransfusion_effects(candidates(15), client)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")
    assert result.llm_call_count == len(client.calls) == 2


@pytest.mark.asyncio
async def test_quote_recheck_stays_inside_failed_batch_and_keeps_global_indices():
    client = FixedEffects(bad_quote_once=True)
    result = await effect.confirm_posttransfusion_effects(candidates(15), client)
    assert result.state == "ready"
    assert result.llm_call_count == len(client.calls) == 3
    assert [row["index"] for row in client.calls[0][0]] == [row["index"] for row in client.calls[1][0]]
    assert [row["index"] for row in client.calls[2][0]] == [12, 13, 14]


@pytest.mark.asyncio
async def test_single_oversize_document_is_not_silently_cut():
    client = FixedEffects()
    result = await effect.confirm_posttransfusion_effects(candidates(1, effect.MAX_BATCH_CHARS), client)
    assert (result.state, result.reason_code) == ("data_gap", "candidate_scope_incomplete")
    assert not client.calls


@pytest.mark.asyncio
async def test_dedicated_evaluation_covers_event_before_unrelated_window_notes_are_sent():
    quote = "输血后患者头晕乏力较前减轻"
    rows = [{"document_id": f"NOTE-{i}", "record_time": "2026-01-02 08:00:00",
             "document_title": "日常病程记录", "record_content": "今日患者精神可，继续观察病情。"} for i in range(30)]
    rows.append({"document_id": "EVALUATION", "record_time": "2026-01-02 09:00:00",
                 "document_title": "输血后疗效评价记录", "record_content": quote + "，继续观察。"})
    session = _session(horizon_date="2026-01-03", bloodtrans_rows=[
        {"document_id": "BT", "record_content": "2026-01-01 16:00:00输血结束。"}], daily_rows=rows)
    result, client = await _execute_with_effect_labels(session, {quote: ("evaluated", quote)})
    assert _canonical_state(result=result, session=session)[0] == "compliant"
    effects = [json.loads(prompt.split("INPUT_JSON=", 1)[1])["items"] for prompt in client.protocol_prompts
               if effect.SCHEMA_VERSION in prompt]
    assert len(effects) == 1 and len(effects[0]) == 1
    assert quote in effects[0][0]["content"]


@pytest.mark.asyncio
async def test_ordinary_course_cannot_replace_dedicated_evaluation_for_other_event():
    first = "输血后患者头晕乏力较前减轻"
    second = "输血后患者呼吸困难较前减轻"
    session = _session(horizon_date="2026-01-04", bloodtrans_rows=[
        {"document_id": "BT-1", "record_content": "2026-01-01 16:00:00输血结束。"},
        {"document_id": "BT-2", "record_content": "2026-01-02 16:00:00输血结束。"}], daily_rows=[
        {"document_id": "EVAL-1", "record_time": "2026-01-02 08:00:00", "document_title": "输血后评价记录", "record_content": first},
        {"document_id": "COURSE-2", "record_time": "2026-01-03 08:00:00", "document_title": "日常病程记录", "record_content": second}])
    result, client = await _execute_with_effect_labels(session, {first: ("evaluated", first), second: ("evaluated", second)})
    assert _canonical_state(result=result, session=session)[0] == "non_compliant"
    prompts = [prompt for prompt in client.protocol_prompts if effect.SCHEMA_VERSION in prompt]
    assert len(prompts) == 1
    assert second not in prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["日常病程记录", "上级医师查房记录", "", None])
async def test_lab_improvement_in_ordinary_or_untitled_note_does_not_count(title):
    text = "输血后复查血红蛋白由60g/L升至90g/L，疗效好。"
    session = _session(horizon_date="2026-01-03", bloodtrans_rows=[
        {"document_id": "BT", "record_content": "2026-01-01 16:00:00输血结束。"}], daily_rows=[
        {"document_id": "NOTE", "document_title": title, "record_time": "2026-01-02 09:00:00", "record_content": text}])
    result, client = await _execute_with_effect_labels(session, {text: ("evaluated", text)})
    assert _canonical_state(result=result, session=session)[0] == "non_compliant"
    assert not any(effect.SCHEMA_VERSION in prompt for prompt in client.protocol_prompts)


@pytest.mark.asyncio
async def test_inline_effect_in_transfusion_record_does_not_replace_dedicated_document():
    session = _session(horizon_date="2026-01-03", bloodtrans_rows=[{
        "document_id": "BT", "record_time": "2026-01-02 09:00:00",
        "record_content": "2026-01-01 16:00:00输血结束。输血后复查血红蛋白由60g/L升至90g/L，疗效好。"}])
    result, client = await _execute_with_effect_labels(session, {})
    assert _canonical_state(result=result, session=session)[0] == "non_compliant"
    assert not any(effect.SCHEMA_VERSION in prompt for prompt in client.protocol_prompts)


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["输血后评价", "输血后评价记录", "输血后效果评价记录", "输血后疗效评价记录"])
async def test_explicit_dedicated_titles_are_accepted(title):
    quote = "输血后患者头晕乏力较前减轻"
    session = _session(horizon_date="2026-01-03", bloodtrans_rows=[
        {"document_id": "BT", "record_content": "2026-01-01 16:00:00输血结束。"}], daily_rows=[
        {"document_id": "EVAL", "document_title": title, "record_time": "2026-01-02 09:00:00", "record_content": quote}])
    result, _ = await _execute_with_effect_labels(session, {quote: ("evaluated", quote)})
    assert _canonical_state(result=result, session=session)[0] == "compliant"
