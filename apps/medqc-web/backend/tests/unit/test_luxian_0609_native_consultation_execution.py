from __future__ import annotations

import json

import pytest

from types import SimpleNamespace

from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609 import native_consultation_execution as consultation


class _Client:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.calls.append(prompt)
        return {
            "choices": [{"message": {"content": json.dumps(self.payload)}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 20, "total_tokens": 140},
            "_api_time": 0.25,
        }


_LEGACY_RULE_IDS = ("LX-017", "CL-250", "SC-068", "LX-015", "SC-069", "CL-248", "CL-071")


def _settings(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=enabled,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )


def _reader(rows_by_source: dict[str, list[dict]]):
    def read(**kwargs):
        return rows_by_source.get(kwargs["source_key"], [])

    return read


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_consultation_short_circuits_all_four_without_llm(monkeypatch):
    client = _Client({})
    monkeypatch.setattr(consultation, "read_luxian_0609_native_source_rows", _reader({}))

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert client.calls == []
    assert execution.llm_call_count == 0
    assert [item["status"] for item in execution.results] == ["not_applicable"] * 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_four_rules_share_one_trimmed_llm_call_and_controlled_codes(monkeypatch):
    rows = {
        "consultation_record": [
            {
                "document_title": "会诊记录",
                "record_time": "2026-06-01 10:00:00",
                "record_content": "申请目的明确，会诊意见包含具体治疗建议。",
            }
        ],
        "daily_course_record": [
            {
                "document_title": "日常病程",
                "record_time": "2026-06-01 12:00:00",
                "record_content": "归纳会诊意见并记录具体执行措施。",
            }
        ],
        "senior_course_record": [],
    }
    client = _Client(
        {
            "results": {
                "LX0609-021": {"reason_code": "purpose_vague"},
                "LX0609-022": {"reason_code": "opinion_clear"},
            },
            "execution_links": [
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "daily_course_record-1",
                    "quality": "vague",
                }
            ],
        }
    )
    monkeypatch.setattr(
        consultation, "read_luxian_0609_native_source_rows", _reader(rows)
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert len(client.calls) == 1
    assert "admission_record" not in client.calls[0]
    assert tuple(item["rule_id"] for item in execution.results) == consultation.CONSULTATION_RULE_IDS
    assert [item["status"] for item in execution.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
    ]
    assert execution.llm_call_count == 1
    assert execution.total_tokens == 140
    assert all("record_content" not in repr(item) for item in execution.results)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_020_alone_requests_023_fact_and_derives_consistent_result(monkeypatch):
    client = _Client(
        {
            "results": {
                "LX0609-020": {"reason_code": "execution_specific"},
            }
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {"document_title": "会诊记录", "record_content": "会诊内容"}
                ],
                "daily_course_record": [],
                "senior_course_record": [],
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert len(client.calls) == 1
    assert "LX0609-023" in client.calls[0]
    assert tuple(item["rule_id"] for item in execution.results) == ("LX0609-020",)
    assert execution.results[0]["status"] == "data_gap"
    assert execution.results[0]["metadata"]["reason_code"] == "execution_source_incomplete"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_execution_record_separates_020_defect_from_023_applicability(monkeypatch):
    client = _Client(
        {
            "results": {},
            "execution_links": [],
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {"document_title": "会诊记录", "record_content": "会诊内容"}
                ],
                "daily_course_record": [],
                "senior_course_record": [],
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in execution.results] == [
        "non_compliant",
        "not_applicable",
    ]
    assert [item["metadata"]["reason_code"] for item in execution.results] == [
        "execution_missing",
        "execution_record_missing",
    ]
    assert "未发现可供评价的后续会诊意见执行记录" in execution.results[1]["findings"]
    assert "未发现会诊记录" not in execution.results[1]["findings"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_output_fails_closed_without_echo(monkeypatch):
    marker = "Bearer_secret_13800138000"

    class InvalidClient:
        async def generate(self, prompt: str) -> dict:
            return {"content": marker}

    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {"document_title": "会诊记录", "record_content": "会诊正文"}
                ]
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=InvalidClient(),
    )

    assert [item["status"] for item in execution.results] == ["data_gap"] * 4
    assert marker not in repr(execution)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_llm_request_is_still_counted(monkeypatch):
    class FailingClient:
        async def generate(self, prompt: str) -> dict:
            raise RuntimeError("provider failed")

    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {"document_title": "会诊记录", "record_content": "会诊正文"}
                ]
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=FailingClient(),
    )

    assert execution.llm_call_count == 1
    assert execution.total_tokens == 0
    assert [item["status"] for item in execution.results] == ["data_gap"] * 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consultation_only_execution_claim_cannot_substitute_for_course_ref(monkeypatch):
    client = _Client(
        {
            "results": {},
            "execution_links": [
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "consultation_record-1",
                    "quality": "specific",
                }
            ],
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {
                        "document_title": "会诊记录",
                        "record_content": "会诊单内写已遵嘱执行。",
                    }
                ],
                "daily_course_record": [],
                "senior_course_record": [],
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in execution.results] == [
        "non_compliant",
        "not_applicable",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_source_budgets_keep_senior_course_execution_evidence(monkeypatch):
    client = _Client(
        {
            "results": {},
            "execution_links": [
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "senior_course_record-1",
                    "quality": "specific",
                }
            ],
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {
                        "document_title": "会诊记录",
                        "record_time": "2026-06-01 10:00:00",
                        "record_content": "申请目的和会诊意见。" * 600,
                    }
                ],
                "daily_course_record": [
                    {
                        "document_title": "日常病程",
                        "record_time": "2026-06-01 11:00:00",
                        "record_content": "日常病情。" * 600,
                    }
                    for _ in range(6)
                ],
                "senior_course_record": [
                    {
                        "document_title": "上级查房",
                        "record_time": "2026-06-01 11:00:00",
                        "record_content": "常规病情。" * 300,
                    }
                    for _ in range(3)
                ]
                + [
                    {
                        "document_title": "上级查房",
                        "record_time": "2026-06-01 12:00:00",
                        "record_content": "常规病情。" * 300
                        + "结合心内科会诊意见，调整具体药物剂量。",
                    }
                ],
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert "结合心内科会诊意见" in client.calls[0]
    assert [item["status"] for item in execution.results] == [
        "compliant",
        "compliant",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pre_consultation_course_cannot_be_used_as_execution_evidence(monkeypatch):
    client = _Client(
        {
            "results": {},
            "execution_links": [
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "daily_course_record-1",
                    "quality": "specific",
                }
            ],
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {
                        "document_title": "会诊记录",
                        "record_time": "2026-06-01 12:00:00",
                        "record_content": "申请目的和会诊意见。",
                    }
                ],
                "daily_course_record": [
                    {
                        "document_title": "日常病程",
                        "record_time": "2026-06-01 11:00:00",
                        "record_content": "遵会诊意见，调整具体治疗。",
                    }
                ],
                "senior_course_record": [],
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in execution.results] == ["data_gap"] * 2
    assert [item["metadata"]["reason_code"] for item in execution.results] == [
        "execution_source_incomplete",
        "execution_time_unresolved",
    ]


@pytest.mark.unit
def test_consultation_projection_separates_application_from_opinion():
    projected = consultation._project_row(
        "consultation_record",
        {
            "document_title": "会诊记录",
            "record_time": "2026-06-01 10:00:00",
            "record_content": "心血管内科，协助诊治，病史敬悉，患者胸闷，建议复查心电图。",
        },
        1,
    )

    assert "申请段=心血管内科，协助诊治" in projected
    assert "会诊意见段=病史敬悉，患者胸闷" in projected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_each_consultation_requires_its_own_later_course_link(monkeypatch):
    client = _Client(
        {
            "results": {},
            "execution_links": [
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "daily_course_record-1",
                    "quality": "specific",
                }
            ],
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {
                        "record_time": "2026-06-01 10:00:00",
                        "record_content": "第一次会诊。",
                    },
                    {
                        "record_time": "2026-06-02 10:00:00",
                        "record_content": "第二次会诊。",
                    },
                ],
                "daily_course_record": [
                    {
                        "record_time": "2026-06-01 12:00:00",
                        "record_content": "遵会诊意见，记录具体执行措施。",
                    }
                ],
                "senior_course_record": [],
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in execution.results] == [
        "non_compliant",
        "compliant",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_one_consultation_can_have_multiple_later_execution_records(monkeypatch):
    client = _Client(
        {
            "results": {},
            "execution_links": [
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "daily_course_record-1",
                    "quality": "specific",
                },
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "senior_course_record-1",
                    "quality": "specific",
                },
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "daily_course_record-1",
                    "quality": "vague",
                },
            ],
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {
                        "record_time": "2026-06-01 10:00:00",
                        "record_content": "会诊申请和意见。",
                    }
                ],
                "daily_course_record": [
                    {
                        "record_time": "2026-06-01 12:00:00",
                        "record_content": "结合会诊意见，调整具体治疗。",
                    }
                ],
                "senior_course_record": [
                    {
                        "record_time": "2026-06-02 12:00:00",
                        "record_content": "遵会诊意见执行。",
                    }
                ],
            }
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in execution.results] == [
        "compliant",
        "non_compliant",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_context_overflow_fails_closed_instead_of_ignoring_documents(monkeypatch):
    client = _Client({"results": {}, "execution_links": []})
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {
                        "record_time": f"2026-06-{index:02d} 10:00:00",
                        "record_content": "会诊申请和意见。",
                    }
                    for index in range(1, 14)
                ],
                "daily_course_record": [],
                "senior_course_record": [],
            }
        ),
    )

    overflow = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert client.calls == []
    assert [item["status"] for item in overflow.results] == ["data_gap"] * 4
    assert all(
        item["metadata"]["reason_code"] == "consultation_context_overflow"
        for item in overflow.results
    )

    client = _Client(
        {
            "results": {
                "LX0609-021": {"reason_code": "purpose_clear"},
                "LX0609-022": {"reason_code": "opinion_clear"},
            },
            "execution_links": [],
        }
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "consultation_record": [
                    {
                        "record_time": "2026-06-01 10:00:00",
                        "record_content": "会诊申请和意见。",
                    }
                ],
                "daily_course_record": [
                    {
                        "record_time": f"2026-06-0{index} 12:00:00",
                        "record_content": "遵会诊意见，调整具体治疗。",
                    }
                    for index in range(1, 5)
                ],
                "senior_course_record": [],
            }
        ),
    )

    course_overflow = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert len(client.calls) == 1
    assert [item["status"] for item in course_overflow.results] == [
        "data_gap",
        "compliant",
        "compliant",
        "data_gap",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_package_entry_runs_consultation_once_and_bypasses_seven_legacy_ids(monkeypatch):
    rows = {
        "consultation_record": [
            {
                "document_title": "会诊记录",
                "record_time": "2026-06-01 10:00:00",
                "record_content": "会诊目的及意见明确。",
            }
        ],
        "daily_course_record": [
            {
                "document_title": "日常病程",
                "record_time": "2026-06-01 12:00:00",
                "record_content": "遵会诊意见，已记录具体执行措施。",
            }
        ],
        "senior_course_record": [],
    }
    client = _Client(
        {
            "results": {
                "LX0609-021": {"reason_code": "purpose_clear"},
                "LX0609-022": {"reason_code": "opinion_clear"},
            },
            "execution_links": [
                {
                    "consultation_ref": "consultation_record-1",
                    "course_ref": "daily_course_record-1",
                    "quality": "specific",
                }
            ],
        }
    )
    monkeypatch.setattr(
        consultation, "read_luxian_0609_native_source_rows", _reader(rows)
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1",
        prepared_rules=[{"rule_id": rule_id} for rule_id in _LEGACY_RULE_IDS],
        visit_id="V",
        medical_text="",
        evidence_payload={},
        llm_client=client,
        settings=_settings(enabled=True),
        institute_id="I",
        patient_id="P",
        selected_customer_rule_ids=consultation.CONSULTATION_RULE_IDS,
    )

    assert executable == []
    assert context.legacy_wrapper_rules == []
    assert tuple(item["rule_id"] for item in context.native_results) == consultation.CONSULTATION_RULE_IDS
    assert context.native_llm_call_count == 1
    assert context.native_total_tokens == 140
    assert len(client.calls) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consultation_flag_off_preserves_legacy_rules(monkeypatch):
    raw_rules = [{"rule_id": rule_id} for rule_id in _LEGACY_RULE_IDS]

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1",
        prepared_rules=raw_rules,
        visit_id="V",
        medical_text="",
        evidence_payload={},
        llm_client=None,
        settings=_settings(enabled=False),
        institute_id="I",
        patient_id="P",
        selected_customer_rule_ids=consultation.CONSULTATION_RULE_IDS,
    )

    assert executable == raw_rules
    assert context.native_results == []
