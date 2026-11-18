"""19例复验（b32f45a7）残留失败的合成反例；不读取任务、患者材料、配置或真实模型。

每组都经过实际出错边界：执行器事实 -> Finalizer、真实提示词装配 -> 隐私包装、
模型替身输出 -> 同文书引用校验。
"""

import json
import re
from datetime import date, timedelta

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.course_body_fact_extraction import (
    CourseBodyDocument, SCHEMA_VERSION, extract_course_body_facts,
)
from app.services.luxian_0609.course_quality_result_mapping import validate_published_course_quality_facts
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.discharge_result_mapping import validate_published_discharge_facts
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from test_luxian_0609_native_course_quality_execution import _row, _run_typed_severity, _severity_session
from test_luxian_0609_native_extended_document_execution import _session as _extended_session


# ---- 08-01-02：正式处方存在、出院记录整组漏写带药 ----

async def _discharge_medication_final(rows):
    snapshot, materials = _extended_session(rows)
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-08-01-02",), evidence_snapshot=snapshot, evidence_materials=materials,
        decision_rule_ids=("LX0609-08-01-02",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=("LX0609-08-01-02",),
        snapshot=snapshot, evidence_materials=materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts).get("LX0609-08-01-02"),
        evidence_snapshot=snapshot, evidence_materials=materials,
    )


@pytest.mark.asyncio
async def test_all_prescribed_discharge_drugs_omitted_is_delivered_not_technical_error():
    final = await _discharge_medication_final({
        "discharge_record": ({"document_id": "discharge", "discharge_order": "规律作息，定期复诊。"},),
        "inpat_prescription": ({"prescription_id": "rx", "order_type": "出院带药", "order_status": "完成"},),
        "inpat_prescription_item": ({"prescription_id": "rx", "prescription_item_id": "rx-1", "generic_name": "阿司匹林"},),
    })
    assert (final["status"], final["reason_code"]) == ("non_compliant", "requirement_violated")
    facts = final["customer_display_facts"]
    assert facts["medication_count"] == 0
    assert facts["prescription_medication_count"] == 1
    assert facts["missing_drug_names"] == ["阿司匹林"]
    assert "drug_name" in facts["missing_fields"]
    assert final["findings"] == "出院记录漏写正式出院处方药物：阿司匹林。"


_ZERO_BASE = {"verification_kind": "discharge_medication_completeness_check", "medication_count": 0,
              "required_fields": ["drug_name", "dose", "route", "duration"], "missing_fields": ["drug_name"]}


@pytest.mark.parametrize("facts", [
    _ZERO_BASE,  # 无正式处方核对时，0项不能证明任何结论
    {**_ZERO_BASE, "prescription_medication_count": 0, "missing_drug_names": []},
    {**_ZERO_BASE, "prescription_medication_count": 2, "missing_drug_names": []},
    {**_ZERO_BASE, "missing_fields": [], "prescription_medication_count": 1, "missing_drug_names": ["阿司匹林"]},
    {**_ZERO_BASE, "missing_fields": ["dose", "drug_name"], "prescription_medication_count": 1,
     "missing_drug_names": ["阿司匹林"]},
    {**_ZERO_BASE, "medication_count": -1, "prescription_medication_count": 1, "missing_drug_names": ["阿司匹林"]},
])
def test_zero_medication_count_still_rejected_without_proven_prescription_omission(facts):
    result, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": "LX0609-08-01-02", "status": "non_compliant", "reason_code": "requirement_violated"},
        raw_facts=facts,
    )
    assert handled and result["status"] == "technical_error"
    assert validate_published_discharge_facts(rule_id="LX0609-08-01-02", raw=facts) is None


# ---- 02-01-04：长期病重病例记录日期超过展示上限 ----

def _course_rows(start: date, days: int, *, skip: set[int] = frozenset()):
    """测试读取器每个来源上限50行；日常与上级病程分摊，合计日期超过展示上限64。"""
    rows = [_row("合成病程正文", (start + timedelta(days=offset)).isoformat() + " 08:00:00")
            for offset in range(days) if offset not in skip]
    return {"daily_rows": rows[0::2], "senior_rows": rows[1::2]}


@pytest.mark.asyncio
async def test_long_serious_interval_gap_survives_delivery_beyond_date_display_cap():
    start = date(2026, 1, 1)
    session = _severity_session(
        rows=[{"severity": "serious", "prescribed_datetime": "2026-01-01 07:00:00", "row_ref": "s" * 64}],
        **_course_rows(start, 80, skip={40, 41, 42}), evaluation_as_of_date=None,
    )
    execution, reduced = await _run_typed_severity(session)
    raw = dict(execution.customer_display_facts)["LX0609-02-01-04"]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0], raw_customer_display_facts=raw,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert (final["status"], final["reason_code"]) == ("non_compliant", "threshold_exceeded")
    facts = final["customer_display_facts"]
    assert facts["gap_days"] == 4 and facts["evaluation_scope"] == "confirmed_interval"
    assert "recorded_dates" not in facts
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_long_serious_interval_satisfied_survives_delivery_beyond_date_display_cap():
    session = _severity_session(
        rows=[{"severity": "serious", "prescribed_datetime": "2026-01-01 07:00:00", "row_ref": "s" * 64}],
        **_course_rows(date(2026, 1, 1), 80), evaluation_as_of_date="2026-03-21",
    )
    execution, reduced = await _run_typed_severity(session)
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0], raw_customer_display_facts=dict(execution.customer_display_facts)["LX0609-02-01-04"],
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert (final["status"], final["reason_code"]) == ("compliant", "requirement_within_threshold")
    assert final["customer_display_facts"]["maximum_gap_days"] <= 2


def test_oversized_or_invalid_recorded_dates_still_rejected():
    base = {"failure_kind": "severity_course_gap_exceeded", "severity": "serious", "threshold_days": 2,
            "anchor_date": "2026-01-01", "horizon_date": "2026-04-01",
            "gap_start_date": "2026-01-01", "gap_end_date": "2026-01-05", "gap_days": 4}
    oversized = {**base, "recorded_dates": [(date(2026, 1, 5) + timedelta(days=i)).isoformat() for i in range(65)]}
    malformed = {**base, "recorded_dates": ["2026/01/06"]}
    for facts in (oversized, malformed):
        result, _ = finalize_luxian_0609_executor_customer_display_facts(
            result={"rule_id": "LX0609-02-01-04", "status": "non_compliant"}, raw_facts=facts)
        assert result["status"] == "technical_error"
        valid, _ = validate_published_course_quality_facts(rule_id="LX0609-02-01-04", raw=facts, status="non_compliant")
        assert not valid


# ---- C25：正文清洗把换行压成空格后，人口学介绍中的已知姓名 ----

class _Capture:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        raise RuntimeError("capture_only_no_network")


async def _pathology_prompt(body: str):
    capture = _Capture()
    client = wrap_luxian_0609_llm_client(capture, identity_values=("张三", "PID-0001"))
    outcome = await tumor._typed_pathology_documentation(
        rule_id="LX0609-06-02-02",
        master=tumor.SourceMaterial("present", ({"pathology_exam_id": "p1", "specimen_name": "肺组织"},)),
        report=tumor.SourceMaterial("present", ({"pathology_exam_id": "p1", "report_datetime": "2026-01-03 10:00:00",
                                                 "diagnosis": "腺癌"},)),
        targets={"surgery_record": tumor.SourceMaterial("present", ({
            "document_id": "s1", "record_time": "2026-01-01 12:00:00",
            "surgery_begin_time": "2026-01-01 09:00:00", "record_content": body,
        },))},
        llm_client=client,
    )
    return outcome, capture.prompts


@pytest.mark.asyncio
@pytest.mark.parametrize("separator", ["\n", "\r\n", "\n  "])
async def test_known_patient_intro_after_collapsed_line_break_is_redacted_before_client(separator):
    body = ("2026-01-01 12:00 手术记录" + separator + "张三，男，79岁，因肺占位入院。"
            "术中取肺组织送病理，血钠135mmol/L。主刀医师：李四。")
    outcome, prompts = await _pathology_prompt(body)
    assert outcome.reason_code != "privacy_guard_blocked"
    assert len(prompts) == 1
    sent = prompts[0]
    assert "张三" not in sent and "PID-0001" not in sent
    assert "[患者姓名已脱敏]" in sent
    assert "79岁" in sent and "135mmol/L" in sent and "李四" in sent


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    "2026-01-01 12:00 手术记录 术后张三家属已知情。术中取肺组织送病理。",
    "2026-01-01 12:00 手术记录 患者编号PID-0001，术中取肺组织送病理。",
])
async def test_unredactable_identity_residue_still_blocks_before_client(body):
    outcome, prompts = await _pathology_prompt(body)
    assert (outcome.status, outcome.reason_code) == ("technical_error", "privacy_guard_blocked")
    assert prompts == []


# ---- 08-02-01：模型只看到脱敏正文，引用含脱敏占位 ----

class _QuoteClient:
    def __init__(self, choose):
        self.choose = choose
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        documents = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])["documents"]
        items = [{"document_ref": doc["document_ref"],
                  "clinical_body": {"state": "present", "quote": self.choose(doc["body"], documents)}}
                 for doc in documents]
        content = json.dumps({"schema_version": SCHEMA_VERSION, "documents": items}, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _first_sentence(body, _documents):
    return re.split(r"(?<=。)", body)[0]


_BODY = "患者张三，男，79岁，今日精神可，咳嗽减轻。查体：双肺呼吸音清。主治医师：李四。"


@pytest.mark.asyncio
async def test_quote_containing_redaction_placeholder_is_grounded_in_same_material():
    client = _QuoteClient(_first_sentence)
    result = await extract_course_body_facts([CourseBodyDocument("doc-a", "daily_course_record", _BODY)], client)
    assert "张三" not in client.prompts[0]
    assert (result.state, result.states) == ("ready", {"doc-a": "present"})
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("choose", [
    lambda body, docs: "[患者姓名已脱敏]，男，79岁，今日精神好，咳嗽减轻。",  # 改写
    lambda body, docs: "[患者姓名已脱敏]，女，79岁，今日精神可，咳嗽减轻。",  # 占位旁改写
    lambda body, docs: "[患者姓名已脱敏]",  # 只有占位，没有原文内容
    lambda body, docs: "[就诊标识已脱敏]，男，79岁，今日精神可，咳嗽减轻。",  # 占位类别不符
    lambda body, docs: "查体：双肺呼吸音清。[患者姓名已脱敏]，男，79岁",  # 打乱顺序拼接
])
async def test_placeholder_quotes_that_are_not_the_sent_span_are_still_rejected(choose):
    client = _QuoteClient(choose)
    result = await extract_course_body_facts([CourseBodyDocument("doc-a", "daily_course_record", _BODY)], client)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")


@pytest.mark.asyncio
async def test_placeholder_quote_from_other_material_is_still_rejected():
    other = "患者张三，男，79岁，今日诉腹痛。主治医师：李四。"

    def borrow(body, documents):
        return _first_sentence(documents[1]["body"], documents) if body == documents[0]["body"] else _first_sentence(body, documents)

    client = _QuoteClient(borrow)
    result = await extract_course_body_facts([
        CourseBodyDocument("doc-a", "daily_course_record", _BODY),
        CourseBodyDocument("doc-b", "daily_course_record", other),
    ], client)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")


# ---- 08-02-01：引文失配安全诊断（仅类别与字数，不改变通过判定） ----

_MULTILINE = "今日查房：\n患者咳嗽减轻，  精神可。\n查体：体温36.5℃，双肺呼吸音清，未闻及啰音。"


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", [
    "患者咳嗽减轻，精神可。",  # 删去行内空格
    "今日查房：患者咳嗽减轻，精神可。",  # 合并换行
    "患者 咳嗽减轻，  精神可。",  # 汉字间多加空格
    "查体：体温 36.5℃，双肺呼吸音清",  # 汉字与数字之间的排版空格
])
async def test_layout_whitespace_quote_is_restored_to_same_material_span(quote):
    client = _QuoteClient(lambda body, docs: quote)
    result = await extract_course_body_facts([CourseBodyDocument("doc-a", "daily_course_record", _MULTILINE)], client)
    assert (result.state, result.states) == ("ready", {"doc-a": "present"})
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body,quote", [
    (_MULTILINE, "查体：体温3 6.5℃"),  # 空白拆开数字词元
    ("精神可。\n精神可。", "精 神可。"),  # 同份正文两处，不能唯一定位
    (_MULTILINE, "患者咳嗽减轻 精神可"),  # 删去标点不是空白差异
])
async def test_whitespace_restoration_keeps_token_and_uniqueness_protection(body, quote):
    client = _QuoteClient(lambda _body, docs: quote)
    result = await extract_course_body_facts([CourseBodyDocument("doc-a", "daily_course_record", body)], client)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")


@pytest.mark.asyncio
@pytest.mark.parametrize("quote,kind", [
    ("查体：体温3 6.5℃", "whitespace_difference"),
    ("患者咳嗽减轻  精神可", "punctuation_difference"),
    ("患者咳嗽减轻，未闻及啰音", "fragments_spliced"),
    ("患者咳嗽明显好转。", "not_in_sent_body"),
    ("今日诉腹痛。", "other_document"),
])
async def test_quote_mismatch_is_classified_without_logging_text(caplog, quote, kind):
    client = _QuoteClient(lambda body, docs: quote if "查房" in body else body)
    with caplog.at_level("WARNING"):
        result = await extract_course_body_facts([
            CourseBodyDocument("doc-a", "daily_course_record", _MULTILINE),
            CourseBodyDocument("doc-b", "daily_course_record", "今日诉腹痛。"),
        ], client)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")
    assert f"quote_kinds={kind},{kind}" not in caplog.text  # 每次尝试只记一份失配文书
    assert f"quote_kinds={kind} quote_chars={len(quote)}" in caplog.text
    for text in (quote, "咳嗽", "腹痛", "doc-a"):
        assert text not in caplog.text
