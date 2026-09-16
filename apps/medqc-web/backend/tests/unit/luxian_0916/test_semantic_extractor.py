from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.luxian_0916.semantic_extractor import extract_luxian_0916_facts
from app.services.luxian_0916.surgery_consent_rules import execute_surgery_consent_rules


_COMPLETENESS_CASES = (
    (
        "LX0916-024",
        "anesthesia_record",
        "anesthesia_record",
        "AR-1",
        (
            "patient_general_information",
            "preoperative_medication",
            "preoperative_special_conditions",
            "preoperative_diagnosis",
            "intraoperative_diagnosis",
            "surgery_method",
            "anesthesia_method",
            "surgery_date",
            "anesthesia_induction_and_operation_times",
            "surgery_start_end_time",
            "anesthesia_medication_name",
            "anesthesia_medication_method",
            "anesthesia_medication_dose",
            "special_circumstance_management",
            "anesthesiologist_signature",
        ),
    ),
    (
        "LX0916-025",
        "surgery_record",
        "surgery_record",
        "SR-1",
        (
            "patient_general_information",
            "operation_datetime",
            "preoperative_diagnosis",
            "intraoperative_diagnosis",
            "operation_name",
            "operator_and_assistants",
            "anesthesia_method",
            "operation_procedure",
            "blood_loss",
            "transfusion_volume",
            "intraoperative_condition_and_management",
        ),
    ),
    (
        "LX0916-026",
        "surgery_safety_check",
        "surgery_safecheck_record",
        "SSC-1",
        (
            "before_anesthesia_identity_site_and_procedure",
            "before_anesthesia_risk_assessment",
            "before_anesthesia_three_party_signatures",
            "before_incision_identity_site_and_procedure",
            "before_incision_risk_and_equipment_confirmation",
            "before_incision_three_party_signatures",
            "before_exit_identity_and_actual_procedure_confirmation",
            "before_exit_instrument_and_material_count_confirmation",
            "before_exit_three_party_signatures",
        ),
    ),
)


def _completeness_payload(
    *, source_type: str, document_id: str, item_keys: tuple[str, ...]
) -> tuple[dict[str, Any], dict[str, str | None]]:
    required_items = {key: f"{key}原文" for key in item_keys}
    return (
        {
            "programmatic_timeline": {
                "documents": {
                    source_type: [
                        {
                            "document_id": document_id,
                            "content": "；".join(required_items.values()),
                        }
                    ]
                }
            }
        },
        required_items,
    )


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
@pytest.mark.parametrize(
    ("rule_id", "fact_key", "source_type", "document_id", "item_keys"),
    _COMPLETENESS_CASES,
)
async def test_derives_completeness_only_from_exact_bound_required_items(
    rule_id: str,
    fact_key: str,
    source_type: str,
    document_id: str,
    item_keys: tuple[str, ...],
) -> None:
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )
    calls = 0

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    fact_key: {
                                        "presence": "present",
                                        "document_id": document_id,
                                        "source_type": source_type,
                                        "required_items": required_items,
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )

    fact = result["document_facts"][fact_key]
    assert calls == 1
    assert result["diagnostic"]["llm_call_count"] == 1
    assert fact["required_items"] == required_items
    assert fact["missing_items"] == ()
    assert fact["completeness_basis"] == "grounded_required_items"
    assert fact["completeness"] == "complete"
    event_key = {
        "LX0916-024": "anesthesia_record_formed",
        "LX0916-025": "surgery_performed",
        "LX0916-026": "surgery_performed",
    }[rule_id]
    rule_result = execute_surgery_consent_rules(
        {"event_facts": {event_key: True}, "document_facts": result["document_facts"]},
        (rule_id,),
    )[0]
    assert rule_result.status == "compliant"


@pytest.mark.asyncio
async def test_derives_specific_missing_item_from_null_required_item() -> None:
    rule_id, fact_key, source_type, document_id, item_keys = _COMPLETENESS_CASES[2]
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )
    required_items["before_exit_three_party_signatures"] = None

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    fact_key: {
                                        "presence": "present",
                                        "document_id": document_id,
                                        "source_type": source_type,
                                        "required_items": required_items,
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )

    fact = result["document_facts"][fact_key]
    assert fact["completeness_basis"] == "grounded_required_items"
    assert fact["completeness"] == "incomplete"
    assert fact["missing_items"] == ("患者离开手术室前三方逐次确认签字",)
    rule_result = execute_surgery_consent_rules(
        {"event_facts": {"surgery_performed": True}, "document_facts": result["document_facts"]},
        (rule_id,),
    )[0]
    assert rule_result.status == "non_compliant"
    assert rule_result.diagnostics["missing_items"] == fact["missing_items"]


@pytest.mark.asyncio
async def test_rejects_legacy_complete_and_unbound_required_item_quote_for_024_to_026() -> None:
    rule_id, fact_key, source_type, document_id, item_keys = _COMPLETENESS_CASES[0]
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    fact_key: {
                                        "presence": "present",
                                        "completeness": "complete",
                                        "document_id": document_id,
                                        "source_type": source_type,
                                        "required_items": {
                                            **required_items,
                                            "anesthesiologist_signature": "绑定文书中不存在的引用",
                                        },
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )

    assert result["document_facts"][fact_key] == {
        "presence": "present",
        "document_id": document_id,
        "source_type": source_type,
        "evidence": (f"已核对来源文书：{source_type} · {document_id}。",),
        "anchors": (
            {
                "document_type": source_type,
                "document_id": document_id,
                "fields": ["presence"],
            },
        ),
    }
    rule_result = execute_surgery_consent_rules(
        {
            "event_facts": {"anesthesia_record_formed": True},
            "document_facts": result["document_facts"],
        },
        (rule_id,),
    )[0]
    assert rule_result.status == "data_quality_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rule_id", "fact_key", "source_type", "document_id", "item_keys", "malformed_items"),
    (
        (*_COMPLETENESS_CASES[0], None),
        (*_COMPLETENESS_CASES[1], {}),
        (*_COMPLETENESS_CASES[2], {"before_anesthesia_identity_site_and_procedure": ""}),
    ),
)
async def test_target_contract_malformed_at_fact_scope_preserves_anesthesia_record_presence(
    rule_id: str,
    fact_key: str,
    source_type: str,
    document_id: str,
    item_keys: tuple[str, ...],
    malformed_items: dict[str, str] | None,
) -> None:
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )
    model_fact: dict[str, Any] = {
        "presence": "present",
        "document_id": document_id,
        "source_type": source_type,
    }
    if malformed_items is None:
        model_fact["completeness"] = "complete"
    else:
        model_fact["required_items"] = malformed_items

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={"document_facts": {fact_key: model_fact}}
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )

    fact = result["document_facts"][fact_key]
    assert set(fact) == {"presence", "document_id", "source_type", "evidence", "anchors"}
    assert "completeness" not in fact
    assert "completeness_basis" not in fact

    if fact_key == "anesthesia_record":
        present_result, completeness_result = execute_surgery_consent_rules(
            {
                "event_facts": {
                    "anesthesia_performed": True,
                    "anesthesia_record_formed": True,
                },
                "document_facts": result["document_facts"],
            },
            ("LX0916-023", "LX0916-024"),
        )
        assert present_result.status == "compliant"
        assert completeness_result.status == "data_quality_gap"


@pytest.mark.asyncio
async def test_rejects_duplicate_and_cross_document_required_item_quotes() -> None:
    rule_id, fact_key, source_type, document_id, item_keys = _COMPLETENESS_CASES[1]
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )
    other_quote = "仅在另一份文书中的连续引用"
    payload["programmatic_timeline"]["documents"][source_type].append(
        {"document_id": "SR-2", "content": other_quote}
    )
    required_items[item_keys[0]] = other_quote

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    fact_key: {
                                        "presence": "present",
                                        "document_id": document_id,
                                        "source_type": source_type,
                                        "required_items": required_items,
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )

    assert "completeness" not in result["document_facts"][fact_key]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rule_id", "fact_key", "source_type", "document_id", "item_keys"),
    _COMPLETENESS_CASES,
)
async def test_truncated_target_document_never_produces_grounded_completeness(
    rule_id: str,
    fact_key: str,
    source_type: str,
    document_id: str,
    item_keys: tuple[str, ...],
) -> None:
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )
    documents = payload["programmatic_timeline"]["documents"][source_type]
    documents[0]["content"] += "补充记录。" * 1000

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    fact_key: {
                                        "presence": "present",
                                        "document_id": document_id,
                                        "source_type": source_type,
                                        "required_items": required_items,
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )

    assert "completeness" not in result["document_facts"][fact_key]


@pytest.mark.asyncio
async def test_rejects_reused_required_item_quote_and_duplicate_document_coordinate() -> None:
    rule_id, fact_key, source_type, document_id, item_keys = _COMPLETENESS_CASES[0]
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )
    shared_quote = required_items[item_keys[0]]
    required_items[item_keys[1]] = shared_quote

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    fact_key: {
                                        "presence": "present",
                                        "document_id": document_id,
                                        "source_type": source_type,
                                        "required_items": required_items,
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    reused = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )
    assert "completeness" not in reused["document_facts"][fact_key]

    payload["programmatic_timeline"]["documents"][source_type].append(
        {"document_id": document_id, "content": "另一份重复坐标文书。"}
    )
    unique_quotes = {key: f"{key}另一引用" for key in item_keys}
    payload["programmatic_timeline"]["documents"][source_type][0]["content"] = "；".join(
        unique_quotes.values()
    )

    async def generate_unique(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    fact_key: {
                                        "presence": "present",
                                        "document_id": document_id,
                                        "source_type": source_type,
                                        "required_items": unique_quotes,
                                    }
                                }
                            }
                        )
                    }
                }
            ]
        }

    duplicate_coordinate = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate_unique
    )
    assert fact_key not in duplicate_coordinate["document_facts"]


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
        "max_completion_tokens": 8192,
        "allow_length_retry": False,
        "response_format": {"type": "json_object"},
    }
    assert "病例特点" in prompt and "诊断依据及鉴别诊断" in prompt
    assert "手术同意书" in prompt and "麻醉同意书" in prompt
    assert "合规" in prompt and "不合规" in prompt


@pytest.mark.asyncio
async def test_skips_idless_rows_and_selects_later_real_document_within_source_limit() -> None:
    prompts: list[str] = []

    async def generate(prompt: str, **_kwargs: Any) -> dict[str, Any]:
        prompts.append(prompt)
        return {"choices": [{"message": {"content": _content()}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "inpat_drug_order": [
                        {"content": "无主键的医嘱回退副本。"},
                        {"document_id": "ORDER-STALE", "content": "不属于本次病历的旧医嘱。"},
                        {"id": "ORDER-REAL", "content": "有主键的真实医嘱。"},
                    ],
                },
                "locatable_document_coordinates": (
                    ("INPAT_DRUG_ORDER", "ORDER-REAL"),
                ),
            }
        },
        rule_ids=("LX0916-017",),
        generate=generate,
    )

    assert result["diagnostic"]["document_count"] == 1
    assert len(prompts) == 1
    assert "ORDER-REAL" in prompts[0]
    assert "ORDER-STALE" not in prompts[0]
    assert "inpat_drug_order-1" not in prompts[0]


@pytest.mark.asyncio
async def test_idless_target_documents_do_not_call_model_and_report_not_selected() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("仅有无主键文书时不应调用模型")

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "exam_master": [{"content": "无主键的检查报告回退副本。"}],
                    "inpat_drug_order": [{"content": "无主键的医嘱回退副本。"}],
                }
            }
        },
        rule_ids=("LX0916-017",),
        generate=generate,
    )

    assert result["diagnostic"] == {
        "code": "readable_target_documents_missing",
        "document_count": 0,
        "llm_call_count": 0,
    }
    assert result["event_source_state_by_rule"] == {"LX0916-017": "not_selected"}


@pytest.mark.asyncio
async def test_unlocatable_target_documents_do_not_call_model_and_report_not_selected() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("仅有未命中目录的文书时不应调用模型")

    result = await extract_luxian_0916_facts(
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "exam_master": [
                        {"document_id": "EXAM-STALE", "content": "旧检查报告。"}
                    ]
                },
                "locatable_document_coordinates": (("exam_master", "EXAM-REAL"),),
            }
        },
        rule_ids=("LX0916-017",),
        generate=generate,
    )

    assert result["diagnostic"] == {
        "code": "readable_target_documents_missing",
        "document_count": 0,
        "llm_call_count": 0,
    }
    assert result["event_source_state_by_rule"] == {"LX0916-017": "not_selected"}


@pytest.mark.asyncio
async def test_grounding_drops_event_facts_bound_to_unlocatable_document_id() -> None:
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
                                            "event_id": "event-legacy-id",
                                            "document_id": "D-STALE",
                                            "source_type": "daily_course_record",
                                            "trigger_confirmed": True,
                                            "evaluation_window_mature": True,
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
                        {"document_id": "D-1", "content": "真实病程文书。"}
                    ]
                },
                "locatable_document_coordinates": (("daily_course_record", "D-1"),),
            }
        },
        rule_ids=("LX0916-015",),
        generate=generate,
    )

    event = result["event_facts"]["disease_changes"][0]
    assert event == {
        "event_type": "disease_changes",
        "event_id": "event-legacy-id",
        "document_id": "D-STALE",
        "source_type": "daily_course_record",
    }


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
        "failure_stage": "contract_validation",
    }


@pytest.mark.asyncio
async def test_normalizes_confirmed_discharge_field_misplacement_and_null_appropriateness() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "event_facts": {
                                    "discharge_arranged": True,
                                    "discharge_record_formed": False,
                                    "disease_changes": [
                                        {
                                            "event_type": "disease_changes",
                                            "appropriateness": None,
                                        }
                                    ],
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(), rule_ids=("LX0916-011",), generate=generate
    )

    assert result["event_facts"] == {"disease_changes": [{"event_type": "disease_changes"}]}
    assert result["discharge_facts"] == {
        "discharge_arranged": True,
        "discharge_record_formed": False,
    }
    assert result["diagnostic"]["code"] == "semantic_extraction_ready"


@pytest.mark.asyncio
async def test_normalizes_confirmed_surgery_safety_check_document_alias() -> None:
    rule_id, _fact_key, source_type, document_id, item_keys = _COMPLETENESS_CASES[2]
    payload, required_items = _completeness_payload(
        source_type=source_type, document_id=document_id, item_keys=item_keys
    )
    alias_fact = {
        "presence": "present",
        "document_id": document_id,
        "source_type": "surgery_safecheck_record",
        "required_items": required_items,
    }

    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": _content(
                            extra={
                                "document_facts": {
                                    "surgery_safecheck_record": alias_fact,
                                    "surgery_safety_check": dict(alias_fact),
                                }
                            }
                        )
                    }
                }
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=payload, rule_ids=(rule_id,), generate=generate
    )

    fact = result["document_facts"]["surgery_safety_check"]
    assert "surgery_safecheck_record" not in result["document_facts"]
    assert fact["source_type"] == "surgery_safecheck_record"
    assert fact["required_items"] == required_items
    assert result["diagnostic"]["code"] == "semantic_extraction_ready"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [
        {
            "event_facts": {"discharge_arranged": True},
            "discharge_facts": {"discharge_arranged": False},
        },
        {"event_facts": {"discharge_arranged": "true"}},
        {"event_facts": {"unexpected": True}},
        {
            "event_facts": {
                "disease_changes": [
                    {"event_type": "disease_changes", "appropriateness": "unknown"}
                ]
            }
        },
    ],
)
async def test_rejects_unconfirmed_normalization_variants(extra: dict[str, Any]) -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"choices": [{"message": {"content": _content(extra=extra)}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(), rule_ids=("LX0916-011",), generate=generate
    )

    assert result["semantic_facts"] == {}
    assert result["event_facts"] == {}
    assert result["discharge_facts"] == {}
    assert result["diagnostic"]["code"] == "semantic_extraction_invalid"
    assert result["diagnostic"]["failure_stage"] == "contract_validation"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "document_facts",
    [
        {
            "surgery_safecheck_record": {
                "presence": "present",
                "document_id": "SSC-1",
                "source_type": "surgery_record",
            }
        },
        {"surgery_safecheck_record": []},
        {
            "surgery_safecheck_record": {
                "presence": "present",
                "document_id": "SSC-1",
                "source_type": "surgery_safecheck_record",
            },
            "surgery_safety_check": {
                "presence": "present",
                "document_id": "SSC-2",
                "source_type": "surgery_safecheck_record",
            },
        },
    ],
)
async def test_rejects_invalid_surgery_safety_check_document_alias(
    document_facts: dict[str, Any],
) -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {"message": {"content": _content(extra={"document_facts": document_facts})}}
            ]
        }

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(), rule_ids=("LX0916-011",), generate=generate
    )

    assert result["document_facts"] == {}
    assert result["diagnostic"]["code"] == "semantic_extraction_invalid"
    assert result["diagnostic"]["failure_stage"] == "contract_validation"


@pytest.mark.asyncio
async def test_model_generation_failure_keeps_safe_failure_stage() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise TimeoutError("private endpoint detail must not be persisted")

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(), rule_ids=("LX0916-011",), generate=generate
    )

    assert result["diagnostic"] == {
        "code": "semantic_extraction_invalid",
        "document_count": 1,
        "llm_call_count": 1,
        "failure_stage": "generation",
    }
    assert "private endpoint detail" not in json.dumps(result, ensure_ascii=False)


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
    assert result["diagnostic"]["failure_stage"] == "json_syntax"


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
async def test_returns_event_source_state_for_normal_extraction() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"choices": [{"message": {"content": _content()}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(),
        rule_ids=("LX0916-015",),
        generate=generate,
    )

    assert result["diagnostic"]["code"] == "semantic_extraction_ready"
    assert result["event_source_state_by_rule"] == {"LX0916-015": "selected"}


@pytest.mark.asyncio
async def test_returns_event_source_state_when_semantic_extraction_is_invalid() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "not json"}}]}

    result = await extract_luxian_0916_facts(
        evidence_payload=_payload(),
        rule_ids=("LX0916-015",),
        generate=generate,
    )

    assert result["diagnostic"]["code"] == "semantic_extraction_invalid"
    assert result["event_source_state_by_rule"] == {"LX0916-015": "selected"}


@pytest.mark.asyncio
async def test_returns_not_selected_event_source_state_without_readable_documents() -> None:
    async def generate(_prompt: str, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("无可读目标文书时不应调用模型")

    result = await extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        rule_ids=("LX0916-015",),
        generate=generate,
    )

    assert result["diagnostic"]["code"] == "readable_target_documents_missing"
    assert result["event_source_state_by_rule"] == {"LX0916-015": "not_selected"}


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
