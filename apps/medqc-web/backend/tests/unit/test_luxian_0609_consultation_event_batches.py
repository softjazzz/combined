"""长住院会诊逐事件投递，完整校验后再合并判定。"""

import json
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from test_luxian_0609_native_consultation_episode_execution import (
    _episode, _payload, _window_session, _materialize_recommendation_quotes,
)


def test_capacity_preflight_uses_same_shared_order_mode_as_execution(monkeypatch):
    modes = []

    def prompt(*, completed, candidates, share_visible_order_refs=False):
        modes.append(share_visible_order_refs)
        if share_visible_order_refs and len(completed) > 2:
            raise episode._SourceGap()
        return 'synthetic', {}

    monkeypatch.setattr(episode, '_execution_prompt', prompt)
    completed = tuple(SimpleNamespace(episode_ref=f'E{i}', recommendation=SimpleNamespace(opinion_ref=f'D{i}'))
                      for i in range(4))
    batches = episode._execution_event_batches(completed=completed,candidates=(),share_visible_order_refs=True)
    assert [len(batch) for batch in batches] == [2, 2]
    assert tuple(item for batch in batches for item in batch) == completed
    assert modes and all(modes)


class _EventClient:
    def __init__(self, payload, *, invalid_batch=None):
        self.payload = payload
        self.prompts = []
        self.recommendation_refs = []
        self.invalid_batch = invalid_batch

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            payload = _materialize_recommendation_quotes(self.payload, prompt)
        else:
            body = json.loads(prompt.split("输入：", 1)[1])
            self.recommendation_refs.extend(item["recommendation_ref"] for item in body["recommendations"])
            payload = {"executions": [
                {"recommendation_ref": item["recommendation_ref"],
                 "execution_state": "absent", "structured_action_refs": [],
                 "execution_record_state": "no_trace", "trace_refs": [],
                 "confidence": "high", "recommendation_coverage_state": "no_trace",
                 "coverage_confidence": "high", "uncovered_source_quotes": []}
                for item in body["recommendations"]
            ]}
            if len(self.prompts) - 1 == self.invalid_batch:
                payload["executions"][0]["trace_refs"] = ["outside-batch"]
        return {"content": payload if isinstance(payload, str) else json.dumps(payload),
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}


def _event_session(*, oversize=False):
    opinions = []
    events = []
    for index in range(1, 5):
        ref = f"consultation_record-{index}"
        quotes = [f"复查合成指标{number}" for number in range(1, 9)]
        opinions.append({"document_id": f"synthetic-opinion-{index}",
                         "record_time": f"2026-07-01 {index + 8:02d}:00:00",
                         "record_content": "会诊意见：" + "；".join(quotes)})
        events.append(_episode(ref, [ref], application="absent", recommendations=[
            {"recommendation_ref": f"{ref}#r{number}", "action_type": "test",
             "source_quote": quote, "normalized_action": quote, "opinion_ref": ref}
            for number, quote in enumerate(quotes, 1)
        ]))
    courses = [{"document_id": f"synthetic-course-{index}",
                "record_time": "2026-07-02 10:00:00", "document_title": "日常病程记录",
                "record_content": "合成病程内容。" * (10000 if oversize else 170)}
               for index in range(1 if oversize else 45)]
    return _window_session(rows_by_source={"consultation_record": opinions,
                                          "daily_course_record": courses}), _payload(episodes=events)


class _Result:
    """只取 023 结果；020 同批选入以保留病程候选（023 单独运行时二阶段只投医嘱）。"""

    def __init__(self, raw):
        self._raw = raw
        self.results = tuple(item for item in raw.results if item["rule_id"] == "LX0609-03-01-04")

    def __getattr__(self, name):
        return getattr(self._raw, name)


async def _run(session, client, tmp_path):
    return _Result(await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-01", "LX0609-03-01-04"), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, opinion_freeze_dir=tmp_path,
    ))


@pytest.mark.asyncio
async def test_consultation_complete_events_batch_and_merge_every_recommendation(tmp_path):
    session, payload = _event_session()
    client = _EventClient(payload)
    result = await _run(session, client, tmp_path)
    assert result.results[0]["status"] == "non_compliant"
    assert len(client.prompts) > 2
    assert len(client.recommendation_refs) == 32
    assert len(set(client.recommendation_refs)) == 32
    assert result.total_tokens == 10 * len(client.prompts)
    for prompt in client.prompts[1:]:
        body = prompt.split("输入：", 1)[1]
        assert len(body) <= 64000
        assert len(json.loads(body)["candidate_documents"]) == 45


@pytest.mark.asyncio
async def test_consultation_invalid_later_event_cannot_publish_partial_batch(tmp_path):
    session, payload = _event_session()
    client = _EventClient(payload, invalid_batch=2)
    result = await _run(session, client, tmp_path)
    assert result.results[0]["status"] == "technical_error"
    assert result.results[0]["metadata"]["reason_code"] == "model_invalid_output"
    assert result.llm_call_count == 3
    assert result.total_tokens == 30


@pytest.mark.asyncio
async def test_consultation_single_oversize_material_stays_incomplete(tmp_path):
    session, payload = _event_session(oversize=True)
    client = _EventClient(payload)
    result = await _run(session, client, tmp_path)
    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == "candidate_scope_incomplete"
    assert len(client.prompts) == 1
