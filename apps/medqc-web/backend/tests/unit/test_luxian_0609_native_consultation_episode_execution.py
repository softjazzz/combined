from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.prompts: list[str] = []

    async def generate(self, prompt: str):
        self.prompts.append(prompt)
        return {"content": self.payload, "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}}


def _rows(*contents: str):
    return [{"document_title": "会诊记录", "record_time": f"2026-07-20 0{index}:00:00", "record_content": content} for index, content in enumerate(contents, 1)]


def _payload(*, episodes, non_target=(), unresolved=()):
    return {"episodes": list(episodes), "non_target_refs": list(non_target), "unresolved_refs": list(unresolved)}


def _episode(ref: str, members: list[str], application="clear", opinion="clear", confidence="high"):
    return {"episode_ref": ref, "member_refs": members, "application_state": application, "opinion_state": opinion, "confidence": confidence}


@pytest.mark.asyncio
async def test_two_rows_can_merge_into_one_real_episode(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("申请会诊", "专科会诊意见"))
    client = _Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1", "consultation_record-2"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 1
    assert "专科会诊意见" in client.prompts[0]
    assert all("consultation_record-1" not in repr(item) for item in result.results)


@pytest.mark.asyncio
async def test_duplicate_sync_and_non_target_do_not_create_extra_episode(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("申请", "同步申请", "非会诊文书"))
    client = _Client(_payload(
        episodes=[_episode("consultation_record-1", ["consultation_record-1", "consultation_record-2"], opinion="absent")],
        non_target=["consultation_record-3"],
    ))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "not_applicable"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application", "opinion", "expected"),
    [
        ("clear", "clear", ("compliant", "compliant")),
        ("vague", "clear", ("non_compliant", "compliant")),
        ("absent", "absent", ("not_applicable", "not_applicable")),
        ("unknown", "clear", ("data_gap", "compliant")),
    ],
)
async def test_021_022_state_table(monkeypatch, application, opinion, expected):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    client = _Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], application, opinion)]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert tuple(item["status"] for item in result.results) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("confidence", ("medium", "low"))
async def test_medium_or_low_confidence_is_data_gap(monkeypatch, confidence):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    client = _Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], confidence=confidence)]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"data_gap"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        _payload(episodes=[_episode("forged", ["consultation_record-1"])]),
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], confidence="low")]),
    ],
)
async def test_invalid_or_low_confidence_episode_fails_closed(monkeypatch, payload):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("一", "二"))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=_Client(payload),
    )
    assert {item["status"] for item in result.results} == {"data_gap"}


@pytest.mark.asyncio
async def test_zero_input_does_not_call_model_and_source_error_is_technical(monkeypatch):
    client = _Client(_payload(episodes=[]))
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: [])
    empty = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert empty.llm_call_count == 0
    assert {item["status"] for item in empty.results} == {"not_applicable"}
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: (_ for _ in ()).throw(SourceEvidenceQueryError("safe")))
    failed = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert failed.results[0]["status"] == "technical_error"


@pytest.mark.asyncio
async def test_parse_failure_is_data_gap_and_model_failure_is_technical(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    parsed = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client("not-json"),
    )
    assert parsed.results[0]["status"] == "data_gap"

    class _BrokenClient:
        async def generate(self, _prompt):
            raise RuntimeError("MODEL_SECRET")

    broken = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_BrokenClient(),
    )
    assert broken.results[0]["status"] == "technical_error"
    assert "MODEL_SECRET" not in repr(broken)


@pytest.mark.asyncio
async def test_output_does_not_leak_text_time_or_model_response(monkeypatch):
    secret = "CONSULTATION_BODY_SECRET_20260720"
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows(secret))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])])),
    )
    rendered = repr(result)
    assert secret not in rendered
    assert "2026-07-20" not in rendered
    assert "consultation_documents" not in rendered
    assert "model_raw_response" not in rendered
