from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_transfusion_execution as transfusion


def _documents(**overrides: list[dict]) -> dict:
    documents = {
        "bloodtrans_record": [{"content": "输血记录正文，记录实际输注过程及观察情况。"}],
        "consent_form": [{"content": "输血治疗知情同意书，已完成风险告知及签名。"}],
        "labtest_master": [{"content": "输血前常规检查资料。"}],
        "labtest_item_report": [],
        "blood_application": [{"content": "输血前评估及申请资料。"}],
        "daily_course_record": [{"content": "输血过程及输血后评价记录。"}],
        "surgery_record": [{"content": "手术记录中的术中输血信息。"}],
        "anesthesia_record": [{"content": "麻醉记录中的术中输血信息。"}],
        "postsurg_firstcourse_record": [{"content": "术后首次病程中的输血信息。"}],
        "inpat_nondrug_order": [{"content": "输血医嘱中的成分和数量。"}],
        "inpat_bill_item": [{"content": "输血收费中的成分和数量。"}],
    }
    documents.update(overrides)
    return {"programmatic_timeline": {"documents": documents}}


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


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "_api_time": 0.2,
        }


def _reader(*, source_key: str, **_: object) -> list[dict]:
    if source_key == "mr_bloodtrans":
        return []
    if source_key == "bloodtrans_record":
        return [{"record_content": "输血记录正文，记录实际输注过程及观察情况。"}]
    raise AssertionError(source_key)


@pytest.mark.asyncio
async def test_no_dedicated_transfusion_source_rows_returns_not_applicable_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", lambda **_: [])
    client = _Client([])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=transfusion.TRANSFUSION_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(
            bloodtrans_record=[],
            daily_course_record=[{"content": "普通病程仅提到拟输血和备血。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 9
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_dedicated_record_keeps_customer_order_and_only_semantic_rules_call_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client(
        [{"is_compliant": index % 2 == 0} for index in range(len(transfusion.TRANSFUSION_RULE_IDS))]
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=tuple(reversed(transfusion.TRANSFUSION_RULE_IDS)),
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日16:10输注完毕。"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    )
                }
            ]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == list(transfusion.TRANSFUSION_RULE_IDS)
    assert [item["status"] for item in result.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "compliant",
        "non_compliant",
    ]
    assert result.llm_call_count == 8
    assert result.total_tokens == 880
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_typed_transfusion_event_triggers_but_shell_record_fails_closed(monkeypatch):
    def _typed_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "mr_bloodtrans":
            return [{"transfution_datetime": datetime(2026, 6, 5, 14, 20)}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _typed_reader)
    client = _Client([{"is_compliant": True}])
    typed = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(bloodtrans_record=[{"content": "空模板"}]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )
    assert typed.results[0]["status"] == "compliant"
    assert typed.llm_call_count == 1

    def _shell_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "bloodtrans_record":
            return [{"record_content": "空模板"}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _shell_reader)
    shell = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert shell.results[0]["status"] == "data_gap"
    assert shell.llm_call_count == 0


@pytest.mark.asyncio
async def test_missing_consent_projection_is_data_gap_and_other_rules_are_not_blocked(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041", "LX0609-042", "LX0609-045"),
        wrapper_rules=[_wrapper("LX0609-041"), _wrapper("LX0609-042"), _wrapper("LX0609-045")],
        evidence_payload=_documents(consent_form=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap", "compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_missing_daily_course_keeps_045_046_047_data_gap_without_model(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045", "LX0609-046", "LX0609-047"),
        wrapper_rules=[
            _wrapper("LX0609-045"),
            _wrapper("LX0609-046"),
            _wrapper("LX0609-047"),
        ],
        evidence_payload=_documents(daily_course_record=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 3
    assert {
        item["metadata"]["reason_code"] for item in result.results
    } == {"transfusion_rule_projection_incomplete"}
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_047_posttransfusion_evaluation_is_deterministic_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    same_record = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日16:10输注完毕。"
                        "输血后复查血红蛋白较前改善，未见输血不良反应。"
                    )
                }
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "普通病程：继续观察一般情况。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert same_record.results[0]["status"] == "compliant"
    assert same_record.results[0]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_complete"
    )
    assert same_record.results[0]["metadata"]["executor_type"] == "program"
    assert same_record.llm_call_count == 0

    later_course = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "2026-06-05 16:10输血结束，输注过程顺利。"}
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "输血后复查血红蛋白上升，症状改善。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert later_course.results[0]["status"] == "compliant"
    assert later_course.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "end_text",
    [
        "2026-06-05 16:10:00+08输血结束",
        "2026-06-05 16:10:00+08:00输血结束",
        "2026-06-05 16:10输血结束后",
        "2026年6月5日16:10输注完毕后",
    ],
)
async def test_047_accepts_controlled_timezone_and_postposition_forms(
    monkeypatch, end_text
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        f"{end_text}，复查血红蛋白较前改善，"
                        "未见输血不良反应。"
                    )
                }
            ],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "compliant"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected_status"),
    [
        (
            (
                "2026-06-05 10:00输血结束。未记录输血后评价。"
                "2026-06-05 16:00输血结束。输血后复查血红蛋白改善。"
            ),
            "non_compliant",
        ),
        (
            (
                "2026-06-05 10:00输血结束。输血后复查血红蛋白改善。"
                "2026-06-05 16:00输血结束。未记录输血后评价。"
            ),
            "non_compliant",
        ),
        (
            (
                "2026-06-05 10:00输血结束，过程顺利。"
                "2026-06-05 16:00输血结束。输血后复查血红蛋白改善。"
            ),
            "compliant",
        ),
    ],
)
async def test_047_allows_final_summary_but_preserves_explicit_missing_statement(
    monkeypatch, content, expected_status
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": content}],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evaluation_text", "expected_status"),
    [
        ("未见输血后评价异常。", "compliant"),
        ("无输血后评价异常。", "compliant"),
        ("输血后评价未见异常。", "compliant"),
        ("未记录输血后评价。", "non_compliant"),
        ("缺少输血后评价。", "non_compliant"),
        ("未书写输血后评价。", "non_compliant"),
    ],
)
async def test_047_distinguishes_normal_evaluation_from_missing_documentation(
    monkeypatch, evaluation_text, expected_status
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": f"2026-06-05 16:10输血结束。{evaluation_text}"}
            ],
            daily_course_record=[{"content": "普通病程：继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_rejects_pre_end_or_unrelated_observation_and_requires_end_time(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    no_post_evaluation = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "2026年6月5日15:30观察生命体征平稳，"
                        "2026年6月5日16:10输注完毕。"
                    )
                }
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "普通病程：生命体征平稳，继续观察。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert no_post_evaluation.results[0]["status"] == "non_compliant"
    assert no_post_evaluation.results[0]["metadata"]["reason_code"] == (
        "posttransfusion_evaluation_missing"
    )
    assert no_post_evaluation.llm_call_count == 0

    missing_end_time = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-047",),
        wrapper_rules=[_wrapper("LX0609-047")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {"content": "输注完毕后复查血红蛋白上升，症状改善。"}
            ],
            daily_course_record=[
                {
                    "record_time": datetime(2026, 6, 5, 18, 40),
                    "content": "输血后复查血红蛋白上升，症状改善。",
                }
            ],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert missing_end_time.results[0]["status"] == "data_gap"
    assert missing_end_time.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )
    assert missing_end_time.llm_call_count == 0


@pytest.mark.asyncio
async def test_047_rejects_planned_time_weak_context_and_unresolved_end_rows(
    monkeypatch,
):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    async def _execute(
        *, blood_rows: list[dict], daily_rows: list[dict]
    ) -> transfusion.NativeTransfusionExecutionResult:
        return await transfusion.execute_luxian_0609_native_transfusion_rules(
            rule_ids=("LX0609-047",),
            wrapper_rules=[_wrapper("LX0609-047")],
            evidence_payload=_documents(
                bloodtrans_record=blood_rows,
                daily_course_record=daily_rows,
            ),
            institute_id="safe-institute",
            patient_id="safe-patient",
            visit_id="safe-visit",
            source_schema=None,
            llm_client=_Client([]),
        )

    planned = await _execute(
        blood_rows=[
            {"content": "预计2026-06-05 16:10输血结束。生命体征平稳。"}
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert planned.results[0]["status"] == "data_gap"
    assert planned.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )

    document_time = await _execute(
        blood_rows=[
            {"content": "2026-06-05 16:10记录：输血结束。生命体征平稳。"}
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert document_time.results[0]["status"] == "data_gap"

    weak_context = await _execute(
        blood_rows=[{"content": "2026-06-05 16:10输血结束，输注过程顺利。"}],
        daily_rows=[
            {
                "record_time": datetime(2026, 6, 5, 18, 40),
                "content": "复查血小板正常，生命体征平稳。",
            }
        ],
    )
    assert weak_context.results[0]["status"] == "non_compliant"

    unresolved_row = await _execute(
        blood_rows=[
            {
                "content": (
                    "2026-06-05 10:00输血结束。"
                    "输血后复查血红蛋白改善。"
                )
            },
            {"content": "16:00输血结束。未记录输血后评价。"},
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert unresolved_row.results[0]["status"] == "data_gap"
    assert unresolved_row.results[0]["metadata"]["reason_code"] == (
        "transfusion_end_time_unavailable"
    )

    one_of_two_missing = await _execute(
        blood_rows=[
            {
                "content": (
                    "2026-06-05 10:00输血结束。"
                    "输血后复查血红蛋白改善。"
                )
            },
            {
                "content": (
                    "2026-06-05 16:00输血结束。"
                    "未记录输血后评价。"
                )
            },
        ],
        daily_rows=[{"content": "普通病程：继续观察。"}],
    )
    assert one_of_two_missing.results[0]["status"] == "non_compliant"
    assert planned.llm_call_count == weak_context.llm_call_count == 0
    assert document_time.llm_call_count == unresolved_row.llm_call_count == 0
    assert one_of_two_missing.llm_call_count == 0


@pytest.mark.asyncio
async def test_044_clear_pretransfusion_assessment_truth_is_deterministic_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)

    missing = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[
                {
                    "content": (
                        "输血记录：患者拟输注红细胞，输血过程中生命体征平稳，"
                        "记录血红蛋白检查结果，但未形成输血前评估。"
                    )
                }
            ],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：输血结束后继续观察。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert missing.results[0]["status"] == "non_compliant"
    assert missing.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_missing"
    assert missing.results[0]["metadata"]["executor_type"] == "program"
    assert missing.llm_call_count == 0

    complete = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：按评估及医嘱完成输注。"}],
            blood_application=[
                {
                    "document_title": "输血前评估记录",
                    "content": (
                        "患者贫血，血红蛋白降低，具有输血指征及必要性；"
                        "既往无输血不良反应，已评估输血风险和生命体征。"
                    )
                }
            ],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert complete.results[0]["status"] == "compliant"
    assert complete.results[0]["metadata"]["reason_code"] == "pretransfusion_assessment_complete"
    assert complete.results[0]["metadata"]["executor_type"] == "program"
    assert complete.llm_call_count == 0

    gray_client = _Client([{"is_compliant": True}])
    gray = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：已记录输血指征，输注过程平稳。"}],
            blood_application=[],
            daily_course_record=[{"content": "病程记录：患者贫血，拟输注红细胞。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=gray_client,
    )
    assert gray.results[0]["status"] == "compliant"
    assert gray.results[0]["metadata"]["reason_code"] == "transfusion_customer_prompt"
    assert gray.llm_call_count == 1
    assert len(gray_client.prompts) == 1

    split_client = _Client([{"is_compliant": False}])
    split = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血前评估：患者具有输血指征。"}],
            blood_application=[{"content": "患者贫血，血红蛋白降低。"}],
            daily_course_record=[{"content": "既往无输血不良反应，已说明风险。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=split_client,
    )
    assert split.results[0]["status"] == "non_compliant"
    assert split.results[0]["metadata"]["reason_code"] == "transfusion_customer_prompt"
    assert split.llm_call_count == 1

    application_client = _Client([{"is_compliant": True}])
    application_gray = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-044",),
        wrapper_rules=[_wrapper("LX0609-044")],
        evidence_payload=_documents(
            bloodtrans_record=[{"content": "输血记录：按医嘱完成输注。"}],
            blood_application=[
                {
                    "document_title": "输血申请单",
                    "content": (
                        "患者血红蛋白降低，拟输红细胞；既往无不良反应，生命体征平稳。"
                    ),
                }
            ],
            daily_course_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=application_client,
    )
    assert application_gray.results[0]["status"] == "compliant"
    assert application_gray.results[0]["metadata"]["reason_code"] == "transfusion_customer_prompt"
    assert application_gray.llm_call_count == 1


@pytest.mark.asyncio
async def test_source_error_and_invalid_model_output_fail_closed_without_echo(monkeypatch):
    secret = "Bearer_secret_13800138000"

    def _failed_reader(**_: object) -> list[dict]:
        raise RuntimeError(secret)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _failed_reader)
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041", "LX0609-049"),
        wrapper_rules=[_wrapper("LX0609-041"), _wrapper("LX0609-049")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert secret not in repr(result)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    invalid = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-049",),
        wrapper_rules=[_wrapper("LX0609-049")],
        evidence_payload=_documents(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([f"not-json {secret}"]),
    )
    assert invalid.results[0]["status"] == "data_gap"
    assert secret not in repr(invalid)
