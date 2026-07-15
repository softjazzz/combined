from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_course_quality_execution as course


def _row(content: str, record_time: str = "2026-06-01 09:00:00") -> dict:
    return {"record_content": content, "record_time": record_time}


def _payload(
    *,
    documents: dict[str, list[dict]] | None = None,
    facts: list[dict] | None = None,
) -> dict:
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": dict(documents or {})},
    }


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _strong_fact(fact_type: str, *, state: str = "present") -> dict:
    return {
        "fact_type": fact_type,
        "state": state,
        "source_key": "inpat_nondrug_order",
        "current_visit_bound": True,
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 5, "total_tokens": 45},
            "_api_time": 0.1,
        }


@pytest.mark.asyncio
async def test_selected_rules_keep_customer_catalog_order_and_missing_projection_is_data_gap():
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018", "LX0609-007", "LX0609-016"),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=None,
    )

    assert course.COURSE_QUALITY_RULE_IDS == (
        "LX0609-007",
        "LX0609-008",
        "LX0609-009",
        "LX0609-016",
        "LX0609-017",
        "LX0609-018",
    )
    assert course.EXECUTOR_KEY == "course_quality"
    assert [item["rule_id"] for item in result.results] == [
        "LX0609-007",
        "LX0609-016",
        "LX0609-018",
    ]
    assert [item["status"] for item in result.results] == ["data_gap"] * 3
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("senior_time", "expected_status"),
    [
        (datetime(2026, 6, 4, 9, 0), "compliant"),
        (datetime(2026, 6, 4, 9, 0, 1), "non_compliant"),
    ],
)
async def test_007_uses_only_daily_and_senior_record_time_without_model(
    monkeypatch, senior_time: datetime, expected_status: str
):
    reader_calls: list[str] = []

    def fake_reader(**kwargs):
        source_key = kwargs["source_key"]
        reader_calls.append(source_key)
        if source_key == "daily_course_record":
            return [
                {"record_time": datetime(2026, 6, 1, 9, 0)},
                {"record_time": None},
            ]
        if source_key == "senior_course_record":
            return [{"record_time": senior_time}]
        raise AssertionError(source_key)

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", fake_reader)
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: False
    )
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(
            documents={
                "first_course_record": [_row("不得计入007", "2026-06-02 09:00:00")],
                "rescue_record": [_row("不得计入007", "2026-06-03 09:00:00")],
            }
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [expected_status]
    assert reader_calls == ["daily_course_record", "senior_course_record"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []
    assert "不得计入007" not in repr(result)


@pytest.mark.asyncio
async def test_007_unstable_order_is_not_applicable_without_reading_course_rows(
    monkeypatch,
):
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: True
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_: (_ for _ in ()).throw(AssertionError("course rows must not be read")),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["not_applicable"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_007_missing_authoritative_record_times_is_data_gap_without_model(
    monkeypatch,
):
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: False
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_: [{"record_time": None, "update_time": datetime(2026, 6, 1, 9, 0)}],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "authoritative_course_time_unavailable"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_008_009_require_current_visit_serious_or_critical_strong_fact():
    documents = {
        "daily_course_record": [
            _row("病重患者日常病程记录。"),
            _row("上级医师查房记录。", "2026-06-02 09:00:00"),
        ]
    }
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order"),
                _strong_fact("current_visit_critical_order", state="absent"),
            ],
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "not_applicable",
    ]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "当前就诊存在病重医嘱" in client.prompts[0]

    critical_client = _Client([{"is_compliant": True}])
    critical = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order", state="absent"),
                _strong_fact("current_visit_critical_order"),
            ],
        ),
        llm_client=critical_client,
    )
    assert [item["status"] for item in critical.results] == [
        "not_applicable",
        "compliant",
    ]
    assert critical.llm_call_count == 1
    assert "当前就诊存在病危医嘱" in critical_client.prompts[0]

    silence = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(documents=documents),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in silence.results] == ["data_gap"] * 2
    assert silence.llm_call_count == 0

    explicit_negative = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order", state="absent"),
                _strong_fact("current_visit_critical_order", state="absent"),
            ],
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in explicit_negative.results] == [
        "not_applicable",
        "not_applicable",
    ]
    assert explicit_negative.llm_call_count == 0


@pytest.mark.asyncio
async def test_016_requires_admission_and_first_course_before_model():
    missing = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(documents={"admission_record": [_row("入院记录现病史。")]}),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in missing.results] == ["data_gap"]
    assert missing.llm_call_count == 0

    client = _Client([{"is_compliant": False}])
    complete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("入院记录现病史与病例特点。")],
                "first_course_record": [_row("首次病程病例特点与诊断依据。")],
            }
        ),
        llm_client=client,
    )
    assert [item["status"] for item in complete.results] == ["non_compliant"]
    assert complete.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_course_row",
    [
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "content_preview": "首次病程病例特点、诊断依据和诊疗计划已经完整记录。",
            "text_preview": "首次病程记录预览",
        },
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "source_table": "first_course_record",
            "assembled_fields": ["record_time", "document_title"],
        },
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "content": (
                "source_table:first_course_record；文书类型：首次病程记录；"
                "记录时间：2026年06月01日09时00分00秒；assembly_status:partial"
            ),
        },
    ],
)
async def test_016_preview_or_assembly_shell_is_data_gap_without_model(
    first_course_row: dict,
):
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("入院记录现病史与病例特点。")],
                "first_course_record": [first_course_row],
            }
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "首次病程病例特点、诊断依据和诊疗计划已经完整记录" not in repr(result)


@pytest.mark.asyncio
async def test_016_admission_preview_shell_is_data_gap_without_model():
    client = _Client([{"is_compliant": True}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [
                    {
                        "title": "入院记录",
                        "record_time": "2026-06-01 08:00:00",
                        "text_preview": "入院记录预览",
                    }
                ],
                "first_course_record": [_row("首次病程病例特点与诊断依据。")],
            }
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_017_requires_two_comparable_records_and_never_outputs_review_pending():
    one_record = course._copy_result(
        {"daily_course_record": [_row("患者病情稳定，继续观察治疗。")]},
        source_complete=True,
    )
    assert one_record["status"] == "not_applicable"
    assert "复核" not in repr(one_record)

    copied = "患者神志清楚，咳嗽咳痰，双肺呼吸音粗，继续抗感染平喘化痰治疗，观察病情变化。"
    similar = course._copy_result(
        {
            "daily_course_record": [
                _row(copied),
                _row(copied, "2026-06-02 09:00:00"),
            ]
        },
        source_complete=True,
    )
    assert similar["status"] == "non_compliant"
    assert "复核" not in repr(similar)

    different = course._copy_result(
        {
            "daily_course_record": [
                _row("患者胸痛缓解，复查心肌酶阴性，计划完善冠脉CTA检查并调整药物。"),
                _row(
                    "冠脉CTA提示前降支狭窄，活动后仍有胸闷，已请介入组会诊评估造影。",
                    "2026-06-02 09:00:00",
                ),
            ]
        },
        source_complete=True,
    )
    assert different["status"] == "compliant"
    assert "复核" not in repr(different)

    exact_threshold = course._copy_result(
        {
            "daily_course_record": [
                _row("a" * 21 + "b" * 9),
                _row("a" * 21 + "c" * 9, "2026-06-02 09:00:00"),
            ]
        },
        source_complete=True,
    )
    assert exact_threshold["metadata"]["maximum_similarity"] == 0.7
    assert exact_threshold["status"] == "compliant"


@pytest.mark.asyncio
async def test_017_uses_complete_current_visit_sources_instead_of_truncated_bundle(
    monkeypatch,
):
    bundle_rows = [
        _row(f"第{index}次病程内容各不相同，仅用于证明旧投影不完整。")
        for index in range(1, 4)
    ]
    copied = "患者神志清楚，生命体征平稳，继续原治疗方案并密切观察病情变化。"
    source_rows = {
        "daily_course_record": [
            _row(
                f"完整来源中的日常病程记录第{index}次，患者症状、检查结果、"
                f"治疗方案和后续观察计划均按当日实际情况记录。"
            )
            for index in range(1, 10)
        ],
        "senior_course_record": [
            _row(copied, "2026-06-10 09:00:00"),
            _row(copied, "2026-06-11 09:00:00"),
        ],
    }
    reader_calls: list[str] = []

    def _read(**kwargs):
        source_key = str(kwargs["source_key"])
        reader_calls.append(source_key)
        return list(source_rows[source_key])

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", _read)

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={"daily_course_record": bundle_rows}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert reader_calls == ["daily_course_record", "senior_course_record"]
    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 0
    metadata = result.results[0]["metadata"]
    assert metadata["comparable_document_count"] == 11
    assert metadata["maximum_similarity"] == 1.0
    assert metadata["similarity_threshold"] == 0.7
    assert metadata["best_match_source_types"] == [
        "senior_course_record",
        "senior_course_record",
    ]
    assert copied not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reader_result", "expected_status", "expected_reason"),
    [
        ([], "not_applicable", "insufficient_comparable_course_records"),
        (
            RuntimeError("raw SQL Bearer_secret 13800138000"),
            "data_gap",
            "course_comparison_source_unavailable",
        ),
    ],
)
async def test_017_complete_source_empty_or_failure_keeps_controlled_state(
    monkeypatch,
    reader_result,
    expected_status: str,
    expected_reason: str,
):
    def _read(**_kwargs):
        if isinstance(reader_result, Exception):
            raise reader_result
        return list(reader_result)

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", _read)

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={"daily_course_record": [_row("旧投影内容不应兜底。")]}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == [expected_status]
    assert result.results[0]["metadata"]["reason_code"] == expected_reason
    assert result.llm_call_count == 0
    assert "Bearer_secret" not in repr(result)
    assert "13800138000" not in repr(result)


@pytest.mark.asyncio
async def test_017_without_complete_coordinates_or_with_source_limit_is_data_gap(
    monkeypatch,
):
    reader_calls: list[str] = []

    def _read(**kwargs):
        reader_calls.append(str(kwargs["source_key"]))
        return [
            {
                **_row(f"完整来源第{index}条病程记录，患者病情和治疗计划均有详细描述。"),
                "document_id": f"safe-{index}",
            }
            for index in range(200)
        ]

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", _read)

    no_coordinates = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(
            documents={
                "daily_course_record": [
                    _row("a" * 40),
                    _row("a" * 40, "2026-06-02 09:00:00"),
                ]
            }
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in no_coordinates.results] == ["data_gap"]
    assert reader_calls == []

    truncated = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in truncated.results] == ["data_gap"]
    assert truncated.results[0]["metadata"]["reason_code"] == (
        "course_comparison_source_truncated"
    )
    assert reader_calls == ["daily_course_record"]


@pytest.mark.asyncio
async def test_017_does_not_treat_duplicate_database_rows_as_two_course_records(
    monkeypatch,
):
    row = {
        **_row("患者病情稳定，继续当前治疗方案并观察症状、体征及复查指标变化。"),
        "document_id": "safe-document-ref",
    }

    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [dict(row), dict(row)]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["not_applicable"]
    assert result.results[0]["metadata"]["comparable_document_count"] == 1
    assert "safe-document-ref" not in repr(result)


@pytest.mark.asyncio
async def test_018_requires_complaint_and_primary_diagnosis_material():
    client = _Client([])
    incomplete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={"admission_record": [_row("主诉：腹痛2天。现病史待查。")]}
        ),
        llm_client=client,
    )
    assert [item["status"] for item in incomplete.results] == ["data_gap"]
    assert incomplete.llm_call_count == 0

    client = _Client([{"is_compliant": True}])
    complete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={"admission_record": [_row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。")]}
        ),
        llm_client=client,
    )
    assert [item["status"] for item in complete.results] == ["compliant"]
    assert complete.llm_call_count == 1


@pytest.mark.asyncio
async def test_model_failure_and_invalid_json_are_isolated_and_safe():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), f"not-json {secret}"])
    payload = _payload(
        documents={
            "admission_record": [_row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。")],
            "first_course_record": [_row("首次病程病例特点与诊断依据。")],
        }
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016", "LX0609-018"),
        wrapper_rules=[_wrapper("LX0609-016"), _wrapper("LX0609-018")],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 2
    assert secret not in repr(result)
