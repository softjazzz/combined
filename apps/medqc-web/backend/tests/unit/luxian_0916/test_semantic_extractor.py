from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.luxian_0916.semantic_extractor import extract_luxian_0916_facts
from app.services.luxian_0916.surgery_consent_rules import execute_surgery_consent_rules


def _payload() -> dict[str, Any]:
    return {
        "programmatic_timeline": {
            "documents": {
                "first_course_record": [
                    {"document_id": "F-1", "content": "病例特点：发热三天。诊断依据：血常规异常。鉴别诊断：流感。诊疗计划：复查血常规。"}
                ],
                "daily_course_record": [
                    {"document_id": "D-1", "content": "病情稳定，继续治疗。"}
                ],
                "surgery_inform_consent": [
                    {"document_id": "S-1", "content": "手术同意书：术前诊断、手术名称、风险及签名。"}
                ],
                "labtest_master": [
                    {"document_id": "L-1", "content": "这是一份与本次规则无关的检验报告。"}
                ],
            }
        }
    }


def _content(*, extra: dict[str, Any] | None = None) -> str:
    facts: dict[str, Any] = {
        "semantic_facts": {"case_characteristic_quality": "adequate"},
        "event_facts": {},
        "document_facts": {},
        "discharge_facts": {},
    }
    if extra:
        facts.update(extra)
    return json.dumps(facts, ensure_ascii=False)


@pytest.mark.asyncio
async def test_extracts_only_minimal_target_documents_and_calls_model_once() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def generate(prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((prompt, kwargs))
        return {"choices": [{"message": {"content": _content()}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(),
        rule_ids=("LX0916-011", "LX0916-021"),
        generate=generate,
    )

    assert result["semantic_facts"] == {"case_characteristic_quality": "adequate"}
    assert result["diagnostic"]["llm_call_count"] == 1
    assert len(calls) == 1
    prompt, kwargs = calls[0]
    assert "F-1" in prompt and "S-1" in prompt
    assert "D-1" not in prompt and "L-1" not in prompt
    assert kwargs == {
        "max_completion_tokens": 4096,
        "allow_length_retry": False,
        "response_format": {"type": "json_object"},
    }
    assert "病例特点" in prompt and "诊断依据及鉴别诊断" in prompt
    assert "手术同意书" in prompt and "麻醉同意书" in prompt
    assert "合规" in prompt and "不合规" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [
        {"unexpected": {}},
        {"semantic_facts": {"case_characteristic_quality": "maybe"}},
        {"document_facts": {"surgery_consent": {"presence": "unknown"}}},
    ],
)
async def test_rejects_unknown_keys_and_illegal_enum_values(extra: dict[str, Any]) -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"choices": [{"message": {"content": _content(extra=extra)}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(), rule_ids=("LX0916-011",), generate=generate
    )

    assert result["semantic_facts"] == {}
    assert result["event_facts"] == {}
    assert result["document_facts"] == {}
    assert result["diagnostic"] == {
        "code": "semantic_extraction_invalid",
        "document_count": 1,
        "llm_call_count": 1,
    }


@pytest.mark.asyncio
async def test_parse_failure_returns_empty_facts_with_diagnostic() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "not json"}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(), rule_ids=("LX0916-011",), generate=generate
    )

    assert result["semantic_facts"] == {}
    assert result["event_facts"] == {}
    assert result["document_facts"] == {}
    assert result["discharge_facts"] == {}
    assert result["diagnostic"]["code"] == "semantic_extraction_invalid"


@pytest.mark.asyncio
async def test_missing_readable_target_document_does_not_call_model() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("无可读目标文书时不应调用模型")

    result = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        rule_ids=("LX0916-011",),
        generate=generate,
    )

    assert result["diagnostic"] == {
        "code": "readable_target_documents_missing",
        "document_count": 0,
        "llm_call_count": 0,
    }


@pytest.mark.asyncio
async def test_retains_admission_and_first_course_facts_for_realistic_document_lengths() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "semantic_facts": {
                                    "LX0916-003": {
                                        "state": "complete",
                                        "document_id": "A-1",
                                        "source_type": "admission_record",
                                    },
                                    "case_characteristic_quality": "adequate",
                                },
                                "event_facts": {},
                                "document_facts": {},
                                "discharge_facts": {},
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "admission_record": [
                        {"document_id": "A-1", "content": "现病史完整。" * 300}
                    ],
                    "first_course_record": [
                        {"document_id": "F-1", "content": "病例特点完整。" * 250}
                    ],
                }
            }
        },
        rule_ids=("LX0916-003", "LX0916-011"),
        generate=generate,
    )

    assert result["semantic_facts"]["LX0916-003"]["state"] == "complete"
    assert result["semantic_facts"]["case_characteristic_quality"] == "adequate"


@pytest.mark.asyncio
async def test_real_timeline_sources_feed_anesthesia_consent_and_discharge_order_rules() -> None:
    prompts: list[str] = []

    async def generate(prompt: str, **_kwargs: Any) -> dict[str, Any]:
        prompts.append(prompt)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "semantic_facts": {},
                                "event_facts": {},
                                "document_facts": {},
                                "discharge_facts": {},
                            }
                        )
                    }
                }
            ]
        }

    payload = {
        "programmatic_timeline": {
            "documents": {
                "surgery_inform_consent": [
                    {"document_id": "SC-1", "title": "手术知情同意书", "content": "拟行手术。"}
                ],
                "consent_form": [
                    {"document_id": "AC-1", "title": "麻醉知情同意书", "content": "拟行全身麻醉。"}
                ],
                "discharge_record": [
                    {"document_id": "DR-1", "content": "出院记录。出院医嘱：门诊复查。"}
                ],
                "daily_course_record": [],
            }
        }
    }

    await extract_luxian_0916_facts(
        evidence_payload=payload,
        rule_ids=("LX0916-022", "LX0916-032"),
        generate=generate,
    )

    assert len(prompts) == 1
    assert "AC-1" in prompts[0]
    assert "SC-1" in prompts[0]
    assert "麻醉知情同意书" in prompts[0]
    assert "DR-1" in prompts[0]
    assert "不得仅凭输入缺项输出 presence=missing" in prompts[0]


@pytest.mark.asyncio
async def test_drops_model_injected_missing_anesthesia_consent_fact() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    "anesthesia_consent": {
                                        "presence": "missing",
                                        "document_id": "AC-1",
                                        "source_type": "consent_form",
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "consent_form": [
                        {"document_id": "AC-1", "content": "麻醉知情同意书正文。"}
                    ]
                }
            }
        },
        rule_ids=("LX0916-022",),
        generate=generate,
    )

    assert result["document_facts"] == {}
    assert result["diagnostic"]["code"] == "semantic_extraction_ready"
    rule_result = execute_surgery_consent_rules(
        {
            "event_facts": {"anesthesia_arranged": True},
            "document_facts": result["document_facts"],
        },
        ("LX0916-022",),
    )[0]
    assert rule_result.status == "data_quality_gap"
    assert rule_result.reason_code == "semantic_fact_unavailable"


@pytest.mark.asyncio
async def test_drops_incomplete_fact_from_truncated_document() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    "anesthesia_consent": {
                                        "presence": "present",
                                        "completeness": "incomplete",
                                        "document_id": "AC-1",
                                        "source_type": "consent_form",
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "consent_form": [{"document_id": "AC-1", "content": "麻醉知情同意书。" * 1000}]
                }
            }
        },
        rule_ids=("LX0916-022",),
        generate=generate,
    )

    fact = result["document_facts"]["anesthesia_consent"]
    assert fact["presence"] == "present"
    assert "completeness" not in fact
    assert fact["anchors"] == (
        {
            "document_type": "consent_form",
            "document_id": "AC-1",
            "fields": ["presence"],
        },
    )


@pytest.mark.asyncio
async def test_retains_bound_incomplete_fact_and_builds_anchor_for_complete_document() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    "anesthesia_consent": {
                                        "presence": "present",
                                        "completeness": "incomplete",
                                        "document_id": "AC-1",
                                        "source_type": "consent_form",
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "consent_form": [{"document_id": "AC-1", "content": "麻醉知情同意书正文。"}]
                }
            }
        },
        rule_ids=("LX0916-022",),
        generate=generate,
    )

    assert result["document_facts"]["anesthesia_consent"] == {
        "presence": "present",
        "completeness": "incomplete",
        "document_id": "AC-1",
        "source_type": "consent_form",
        "evidence": ("已核对来源文书：consent_form · AC-1。",),
        "anchors": (
            {
                "document_type": "consent_form",
                "document_id": "AC-1",
                "fields": ["presence", "completeness"],
            },
        ),
    }


@pytest.mark.asyncio
async def test_removes_first_course_quality_when_its_only_selected_document_is_truncated() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"choices": [{"message": {"content": _content()}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "first_course_record": [
                        {"document_id": "F-1", "content": "首次病程记录。" * 1000}
                    ]
                }
            }
        },
        rule_ids=("LX0916-011",),
        generate=generate,
    )

    assert result["semantic_facts"] == {}


@pytest.mark.asyncio
async def test_removes_course_documentation_and_rationality_from_truncated_document() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "event_facts": {
                                    "disease_changes": [
                                        {
                                            "event_type": "disease_changes",
                                            "event_id": "event-1",
                                            "document_id": "D-1",
                                            "source_type": "daily_course_record",
                                            "trigger_confirmed": True,
                                            "documentation": {
                                                "analysis_recorded": False,
                                                "specific_management_recorded": False,
                                            },
                                            "appropriateness": "unreasonable",
                                        }
                                    ]
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "daily_course_record": [
                        {"document_id": "D-1", "content": "日常病程记录。" * 1000}
                    ]
                }
            }
        },
        rule_ids=("LX0916-015",),
        generate=generate,
    )

    event = result["event_facts"]["disease_changes"][0]
    assert "trigger_confirmed" not in event
    assert "documentation" not in event
    assert "appropriateness" not in event
