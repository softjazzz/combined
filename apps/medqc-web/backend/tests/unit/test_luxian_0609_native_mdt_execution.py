from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_mdt_execution


class _LLM:
    def __init__(self, state: str = "present", *, invalid: bool = False) -> None:
        self.state = state
        self.invalid = invalid
        self.calls = 0

    async def generate(self, prompt: str) -> dict:
        self.calls += 1
        assert "SC-083" not in prompt
        assert "CL-108" not in prompt
        content = (
            "not-json"
            if self.invalid
            else f'{{"state":"{self.state}","confidence":0.9}}'
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 12,
                "total_tokens": 132,
            },
            "_api_time": 0.25,
        }


def _reader(rows_by_source: dict[str, list[dict]]):
    def read(**kwargs):
        return [dict(row) for row in rows_by_source.get(kwargs["source_key"], [])]

    return read


@pytest.mark.asyncio
async def test_completed_mdt_strong_fact_short_circuits_llm(monkeypatch):
    marker = "SAFE_BODY_MARKER_MDT"
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "mr_surgery": [
                    {
                        "surgery_name": "测试手术",
                        "surgical_level": "四级",
                        "surgery_begin_datetime": "2026-01-02T09:00:00",
                    }
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "record_content": f"经多学科讨论后一致认为可实施手术。{marker}",
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "compliant"
    assert execution.result["metadata"]["reason_code"] == "completed_mdt_strong_fact"
    assert execution.llm_call_count == 0
    assert llm.calls == 0
    assert marker not in repr(execution)


@pytest.mark.asyncio
async def test_ordinary_preop_consult_uses_one_trimmed_llm_call(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "mr_surgery": [
                    {
                        "surgery_name": "测试手术",
                        "surgical_level": "4",
                        "surgery_begin_datetime": "2026-01-02T09:00:00",
                    }
                ],
                "presurg_discussion": [],
                "consultation_record": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "record_content": "请单一专科协助评估手术风险。",
                    }
                ],
            }
        ),
    )
    llm = _LLM("absent")

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "non_compliant"
    assert execution.result["metadata"]["execution_source"] == "lx0609_native"
    assert execution.result["metadata"]["reason_code"] == "mdt_llm_absent"
    assert execution.llm_call_count == 1
    assert execution.total_tokens == 132
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_missing_mdt_document_is_programmatic_non_compliant(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "mr_surgery": [
                    {
                        "surgical_level": "四级",
                        "surgery_begin_datetime": "2026-01-02T09:00:00",
                    }
                ],
                "presurg_discussion": [],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "non_compliant"
    assert execution.result["metadata"]["reason_code"] == "preoperative_mdt_absent"
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_non_level4_surgery_is_not_applicable(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "mr_surgery": [
                    {
                        "surgical_level": "三级",
                        "surgery_begin_datetime": "2026-01-02T09:00:00",
                    }
                ]
            }
        ),
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "not_applicable"
    assert execution.result["metadata"]["reason_code"] == "level4_surgery_absent"
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_ungraded_surgery_is_data_gap_not_not_applicable(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "mr_surgery": [
                    {
                        "surgical_level": "未定级",
                        "surgery_begin_datetime": "2026-01-02T09:00:00",
                    }
                ]
            }
        ),
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
    )

    assert execution.result["status"] == "data_gap"
    assert execution.result["metadata"]["reason_code"] == "surgery_level_unavailable"


@pytest.mark.asyncio
async def test_invalid_llm_output_stays_data_gap(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "mr_surgery": [
                    {
                        "surgical_level": "四级",
                        "surgery_begin_datetime": "2026-01-02T09:00:00",
                    }
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "record_content": "普通术前讨论。",
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM(invalid=True)

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "data_gap"
    assert execution.result["metadata"]["reason_code"] == "mdt_llm_unknown"
    assert execution.llm_call_count == 1


@pytest.mark.asyncio
async def test_source_failure_is_sanitized_data_gap(monkeypatch):
    def fail(**_):
        raise RuntimeError("Bearer secret 13800138000")

    monkeypatch.setattr(
        native_mdt_execution, "read_luxian_0609_native_source_rows", fail
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
    )

    assert execution.result["status"] == "data_gap"
    assert execution.result["metadata"]["reason_code"] == "surgery_source_unavailable"
    assert "Bearer" not in repr(execution)
    assert "13800138000" not in repr(execution)
