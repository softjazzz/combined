"""第三轮业务回退：仅合成材料与本地模型替身。"""
import json
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import native_course_quality_execution as course
from app.services.luxian_0609 import native_extended_document_execution as extended
from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.course_quality import rule_018
from app.services.luxian_0609.extended_document import transfusion_performance_extraction as performance
from app.services.luxian_0609.extended_document.transfusion_performance_extraction import PerformanceExtraction
from app.services.luxian_0609.evidence_material import EvidenceMaterialTruncated
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result as finalize
from tests.unit.test_luxian_0609_course_quality_freeze import _run_chain
from tests.unit.test_luxian_0609_native_extended_document_execution import _evaluate_selected
from test_luxian_0609_transfusion_performance_043_047 import _run as run_transfusion
from transfusion_order_test_support import FrozenTransfusionProtocolClient

R018 = "LX0609-01-01-02"
R043 = "LX0609-07-01-01"
R070 = "LX0609-07-01-03"


def complaint_rows(complaint="头痛、头晕不适1天"):
    return {
        "admission_record": [{"document_id": "synthetic-admission", "chief_complaint": complaint,
                              "history_of_present_illness": "伴左手乏力", "record_content": "主诉：" + complaint}],
        "admission_record_diagnosis": [{"document_id": "synthetic-admission", "diagnosis_type": "初步诊断",
                                        "diagnosis_main": "是", "diagnosis_name": "脑梗死"}],
    }


def atomic(signals, kind="localized_symptom_or_sign"):
    return {"chief_signal_kind": kind, "chief_complaint_signals": signals,
            **{field: "not_applicable" for field in rule_018.LX018_ATOMIC_RELATION_FIELDS},
            "symptom_relation": "supports" if kind == "localized_symptom_or_sign" else "nonspecific"}


class Client:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if isinstance(self.payload, Exception):
            raise self.payload
        return {"content": json.dumps(self.payload, ensure_ascii=False)}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,reason", [(None, "model_transport_error"),
    (RuntimeError("synthetic transport"), "model_transport_error"), ({}, "model_invalid_output")])
@pytest.mark.parametrize("long", [False, True])
async def test_018_model_failure_survives_finalizer(failure, reason, long):
    session, execution, reduced, final = await _run_chain(
        R018, complaint_rows("头痛" * 11 if long else "头痛1天"),
        client=None if failure is None else Client(failure))
    assert final["status"] == ("non_compliant" if long else "technical_error")
    assert final["reason_code"] == ("requirement_violated" if long else reason)
    assert len(execution.decisions[0].criterion_results) == 2
    final = finalize(decision=reduced, raw_customer_display_facts=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final["status"] == ("non_compliant" if long else "technical_error")


@pytest.mark.asyncio
@pytest.mark.parametrize("complaint,signals,kind,status", [
    ("头痛、头晕不适1天", ["左手乏力"], "localized_symptom_or_sign", "technical_error"),
    ("头痛、头晕不适1天", ["头痛", "头晕"], "nonspecific_symptom_or_sign", "non_compliant"),
    ("左侧肢体无力2小时", ["左侧肢体无力"], "localized_symptom_or_sign", "compliant"),
])
async def test_018_only_complaint_signals(complaint, signals, kind, status):
    client = Client(atomic(signals, kind))
    _, _, _, final = await _run_chain(R018, complaint_rows(complaint), client=client)
    assert final["status"] == status
    if status == "technical_error":
        assert final["reason_code"] == "model_invalid_output"
    assert "chief_complaint_signals" not in final.get("customer_display_facts", {})
    assert f"[主诉原文] {complaint}" in client.prompts[0]
    assert "只按主诉原文" in client.prompts[0]
    assert "仅供核实病灶侧别、识别规范例外、理解术语" in client.prompts[0]


@pytest.mark.parametrize("signals", [None, "头痛", [], [1], ["左手乏力"], [""], ["头痛"] * 7, ["头" * 21], ["， 。"]])
def test_018_invalid_signal_contract(signals):
    payload = atomic(signals)
    if signals is None:
        payload.pop("chief_complaint_signals")
    assert rule_018._parse_lx018_atomic_facts({"content": json.dumps(payload)}, chief_complaint="头痛1天") is None


def test_018_unknown_empty_and_punctuation():
    assert rule_018._parse_lx018_atomic_facts(
        {"content": json.dumps(atomic([], "unknown"))}, chief_complaint="头痛1天") is not None
    assert rule_018._parse_lx018_atomic_facts(
        {"content": json.dumps(atomic(["头痛头晕"]))}, chief_complaint="头痛、头晕1天") is not None


LAB_NAMES = ["*ABO血型鉴定", "*Rh血型鉴定", "不规则抗体筛查", "乙肝表面抗原", "乙肝表面抗体",
             "乙肝e抗原", "乙肝e抗体", "乙肝核心抗体", "丙肝抗体", "HIV抗体", "梅毒抗体"]


def transfusion_rows(names=LAB_NAMES):
    return {
        "bloodtrans_record": [{"document_id": "synthetic-event", "record_time": "2026-06-05 14:20:00",
                               "record_content": "已输注红细胞2U。"}],
        "inpat_registration": [{"document_id": "synthetic-registration", "admission_datetime": "2026-06-01 08:00:00"}],
        "labtest_item_report": [{"document_id": f"synthetic-lab-{i}", "item_name": name,
                                  "result": "阴性", "report_datetime": "2026-06-05 10:00:00"}
                                 for i, name in enumerate(names)],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", [R043, R070])
async def test_empty_lab_source_is_data_gap(rule):
    rows = transfusion_rows([])
    if rule == R043:
        final = (await run_transfusion(rule, rows, {}, client=FrozenTransfusionProtocolClient(
            default_course_label="record", performance_state="performed")))["final"]
    else:
        snapshot, materials, execution, reduced = await _evaluate_selected(
            (rule,), rows, llm_client=FrozenTransfusionProtocolClient(performance_state="performed"))
        final = finalize(decision=reduced[0], evidence_snapshot=snapshot, evidence_materials=materials,
                         raw_customer_display_facts=dict(execution.customer_display_facts).get(rule))
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_unavailable"
    assert "未取得" in final["findings"] or "未读取到" in final["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("names,status", [(LAB_NAMES, "compliant"),
    ([n for n in LAB_NAMES if n != "不规则抗体筛查"], "non_compliant"),
    ([n for n in LAB_NAMES if not n.startswith("乙肝")], "non_compliant")])
async def test_043_eleven_items_without_alt(names, status):
    result = await run_transfusion(R043, transfusion_rows(names), {}, client=FrozenTransfusionProtocolClient(
        default_course_label="record", performance_state="performed"))
    assert result["final"]["status"] == status
    if status == "compliant":
        assert len(result["facts"]["checked_items"]) == 11
        assert "alt" not in result["facts"]["checked_items"]
    else:
        assert "alt" not in result["facts"]["missing_items"]


@pytest.mark.parametrize("name,expected", [("*Rh血型鉴定", "rh"), ("Rh(D)", "rh"),
    ("RhD 血型鉴定", "rh"), ("rh无关项目", None), ("parathyroid hormone", None)])
def test_043_rh_alias_is_specific(name, expected):
    assert transfusion.resolve_pretransfusion_required_item(
        {"item_name": name}, required_items=transfusion._PRETRANSFUSION_REGULAR_ITEMS) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("state,reason,status", [("technical_error", "model_transport_error", "technical_error"),
    ("technical_error", "", "technical_error"), ("data_gap", "source_unavailable", "data_gap")])
async def test_070_course_extraction_failure(monkeypatch, state, reason, status):
    async def classify(*args, **kwargs):
        return SimpleNamespace(state=state, reason_code=reason, llm_call_count=0,
                               prompt_tokens=0, completion_tokens=0, total_tokens=0, api_time=0)
    monkeypatch.setattr(extended, "classify_transfusion_course_records", classify)
    rows = {"daily_course_record": [{"document_id": "synthetic-course", "record_content": "今日输注红细胞2U。"}]}
    snapshot, materials, _, reduced = await _evaluate_selected((R070,), rows)
    final = finalize(decision=reduced[0], raw_customer_display_facts=None, evidence_snapshot=snapshot, evidence_materials=materials)
    assert final["status"] == status
    assert final["reason_code"] == ((reason or "model_invalid_output") if state == "technical_error" else "semantic_extraction_unresolved")


@pytest.mark.asyncio
async def test_070_performance_technical_failure(monkeypatch):
    async def extract(*args, **kwargs):
        return PerformanceExtraction(("unknown",), "model_invalid_output", event_times=(None,))
    monkeypatch.setattr(extended, "extract_transfusion_performance", extract)
    snapshot, materials, _, reduced = await _evaluate_selected((R070,), {
        "bloodtrans_record": [{"document_id": "synthetic-performance", "record_content": "今日输注红细胞2U。"}]})
    final = finalize(decision=reduced[0], raw_customer_display_facts=None, evidence_snapshot=snapshot, evidence_materials=materials)
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_invalid_output"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,reason", [(None, "model_transport_error"),
    (RuntimeError("synthetic transport"), "model_transport_error"), ({}, "model_invalid_output")])
@pytest.mark.parametrize("long", [False, True])
async def test_018_legacy_model_failure(failure, reason, long):
    execution = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=(R018,), wrapper_rules=({"rule_id": R018},),
        evidence_payload={"programmatic_timeline": {"documents": complaint_rows("头痛" * 11 if long else "头痛1天")}},
        llm_client=None if failure is None else Client(failure))
    result = execution.results[0]
    assert result["status"] == ("non_compliant" if long else "technical_error")
    assert result["metadata"]["reason_code"] == ("requirement_violated" if long else reason)
    assert len(result["criterion_results"]) == 2


@pytest.mark.asyncio
async def test_043_does_not_require_current_stay():
    rows = transfusion_rows()
    rows["inpat_registration"][0]["admission_datetime"] = "2026-06-05 12:00:00"
    result = await run_transfusion(R043, rows, {}, client=FrozenTransfusionProtocolClient(
        default_course_label="record", performance_state="performed"))
    assert result["final"]["status"] == "compliant"


@pytest.mark.asyncio
async def test_070_still_requires_alt_and_does_not_require_blood_typing():
    names = LAB_NAMES[3:] + ["谷丙转氨酶"]
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (R070,), transfusion_rows(names), llm_client=FrozenTransfusionProtocolClient(performance_state="performed"))
    final = finalize(decision=reduced[0], evidence_snapshot=snapshot, evidence_materials=materials,
                     raw_customer_display_facts=dict(execution.customer_display_facts).get(R070))
    assert final["status"] == "compliant"
    assert len(dict(execution.customer_display_facts)[R070]["checked_items"]) == 9


def test_zero_readable_lab_rows_is_data_gap_even_when_state_available():
    documents = transfusion_rows()
    documents["labtest_item_report"] = [None, "unreadable"]
    # 此处只测项目核对内核，实施前提由测试作者直接提供已确认事件。
    documents["performed_transfusion_events"] = [{"transfusion_start_time": "2026-06-05 14:20:00"}]
    documents["__logical_source_states__"] = {"labtest_item_report": "available"}
    assert transfusion.evaluate_pretransfusion_nine_items(documents) == (
        "data_gap", "pretransfusion_lab_results_absent", None)


@pytest.mark.parametrize("name,expected", [("ABO血型", "abo"), ("ABO血型鉴定", "abo"),
    ("意外抗体筛查", "antibody_screen"), ("不规则抗体筛查", "antibody_screen")])
def test_043_additional_aliases(name, expected):
    assert transfusion.resolve_pretransfusion_required_item(
        {"item_name": name}, required_items=transfusion._PRETRANSFUSION_REGULAR_ITEMS) == expected


@pytest.mark.parametrize("row,expected", [
    # HIV 抗体筛查仍归 HIV，不因“抗体筛查”被判成多重命中而丢弃
    ({"item_name": "HIV抗体筛查"}, "hiv"),
    # 总蛋白缩写同为 TP，不得冒充梅毒检查
    ({"item_name": "*总蛋白测定", "item_abbreviation": "TP"}, None),
    ({"item_name": "梅毒螺旋体特异抗体测定", "item_abbreviation": "TPAb"}, "syphilis"),
])
def test_pretransfusion_aliases_do_not_cross_match(row, expected):
    for items in (transfusion._PRETRANSFUSION_REGULAR_ITEMS, transfusion._PRETRANSFUSION_REQUIRED_ITEMS):
        assert transfusion.resolve_pretransfusion_required_item(row, required_items=items) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["complaint", "diagnosis"])
async def test_018_real_missing_material_remains_data_gap(missing):
    rows = complaint_rows()
    if missing == "complaint":
        rows["admission_record"][0].pop("chief_complaint")
        rows["admission_record"][0]["record_content"] = "仅有现病史。"
    else:
        rows["admission_record_diagnosis"] = []
    client = Client(atomic(["头痛"]))
    _, _, _, final = await _run_chain(R018, rows, client=client)
    assert final["status"] == "data_gap"
    assert not client.prompts


@pytest.mark.asyncio
async def test_070_missing_hepatitis_items_with_other_labs_is_defect():
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (R070,), transfusion_rows(["谷丙转氨酶"]),
        llm_client=FrozenTransfusionProtocolClient(performance_state="performed"))
    final = finalize(decision=reduced[0], evidence_snapshot=snapshot, evidence_materials=materials,
                     raw_customer_display_facts=dict(execution.customer_display_facts).get(R070))
    assert final["status"] == "non_compliant"
    assert "hbsag" in dict(execution.customer_display_facts)[R070]["missing_items"]


@pytest.mark.asyncio
@pytest.mark.parametrize("client,reason", [(None, "model_transport_error"), (Client({}), "model_invalid_output")])
async def test_070_actual_performance_extractor_failure_is_technical(client, reason):
    snapshot, materials, _, reduced = await _evaluate_selected((R070,), {
        "bloodtrans_record": [{"document_id": "synthetic-performance", "record_content": "今日输注红细胞2U。"}]},
        llm_client=client)
    final = finalize(decision=reduced[0], raw_customer_display_facts=None,
                     evidence_snapshot=snapshot, evidence_materials=materials)
    assert final["status"] == "technical_error"
    assert final["reason_code"] == reason


# ---- 合并时补充：实施抽取失败的范围、截断原因码、确定性技术原因码 ----

NINE_LAB_NAMES = ["乙肝表面抗原", "乙肝表面抗体", "乙肝e抗原", "乙肝e抗体", "乙肝核心抗体",
                  "丙肝抗体", "HIV抗体", "梅毒抗体", "谷丙转氨酶"]


class _RaisingClient:
    def __init__(self, error):
        self.error = error

    async def generate(self, prompt, **kwargs):
        raise self.error


@pytest.mark.asyncio
@pytest.mark.parametrize("client,reason", [
    (None, "model_transport_error"),
    (_RaisingClient(RuntimeError("synthetic transport")), "model_transport_error"),
    (_RaisingClient(TimeoutError()), "model_timeout"),
    (Client({"schema_version": "x", "documents": []}), "model_invalid_output"),
])
async def test_performance_extraction_reports_precise_technical_reason(client, reason):
    """实施抽取的模型失败给出细分原因码，并标记为技术失败。"""
    rows = [{"record_content": "今日输注红细胞2U。", "record_time": "2026-06-05 15:00:00"}]
    result = await performance.extract_transfusion_performance(rows, client)
    assert result.reason_code == reason
    assert result.technical_failure


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, "HIV抗体"])
async def test_070_frontpage_cannot_confirm_event_when_performance_extraction_fails(monkeypatch, missing):
    """实施抽取失败时，首页行不能证明事件，也不能据此发布医学缺项。"""
    async def extract(*args, **kwargs):
        return PerformanceExtraction(("unknown",), "model_invalid_output", event_times=(None,))
    monkeypatch.setattr(extended, "extract_transfusion_performance", extract)
    rows = transfusion_rows([name for name in NINE_LAB_NAMES if name != missing])
    rows["mr_bloodtrans"] = [{"document_id": "untrusted-frontpage-event", "transfution_datetime": "2026-06-05 14:20:00"}]
    snapshot, materials, execution, reduced = await _evaluate_selected((R070,), rows)
    final = finalize(decision=reduced[0], evidence_snapshot=snapshot, evidence_materials=materials,
                     raw_customer_display_facts=dict(execution.customer_display_facts).get(R070))
    assert (final["status"], final["reason_code"]) == ("technical_error", "model_invalid_output")


def test_070_confirmed_event_keeps_missing_hiv_as_medical_defect():
    """纯核对内核仍须对已人工确认的实施事件报告缺项，不削弱医学预期。"""
    documents = transfusion_rows([name for name in NINE_LAB_NAMES if name != "HIV抗体"])
    documents["performed_transfusion_events"] = [{"transfusion_start_time": "2026-06-05 14:20:00"}]
    documents["__logical_source_states__"] = {"labtest_item_report": "available"}
    status, reason, facts = transfusion.evaluate_pretransfusion_nine_items(documents)
    assert (status, reason) == ("non_compliant", "pretransfusion_items_incomplete")
    assert facts["missing_items"] == ["hiv"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["model_transport_error", "model_timeout", "privacy_guard_blocked",
                                    "execution_program_error"])
async def test_043_performance_extraction_failure_is_technical_error(monkeypatch, reason):
    """07-01-01 实施抽取模型失败判技术错误，细分原因码原样保留，不改写成可补跑的执行器异常。"""
    async def extract(*args, **kwargs):
        return PerformanceExtraction(("unknown",), reason, event_times=(None,))
    monkeypatch.setattr(performance, "extract_transfusion_performance", extract)
    body = "今日输注红细胞2U。"
    rows = transfusion_rows()
    rows["bloodtrans_record"] = [{"document_id": "synthetic-performance", "record_content": body,
                                  "record_time": "2026-06-05 15:00:00"}]
    final = (await run_transfusion(R043, rows, {body: "record"}))["final"]
    assert final["status"] == "technical_error"
    assert final["reason_code"] == reason


class _TruncatedOrderMaterials:
    """医嘱来源超过读取上限，其余来源为空。"""

    def rows(self, source_key):
        if source_key in transfusion._ORDER_TRIGGER_SOURCES:
            raise EvidenceMaterialTruncated(source_key)
        return ()


@pytest.mark.asyncio
async def test_truncated_order_source_reports_truncation_not_unavailable():
    """医嘱被截断时判资料不足，原因码写明截断，而不是来源未接入。"""
    async def classify(rows):
        raise AssertionError("无候选时不调用模型")

    documents = {key: [] for key in (*transfusion._ORDER_TRIGGER_SOURCES, "daily_course_record", "senior_course_record")}
    state = await transfusion._performed_source_state(
        documents=documents, institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V",
        source_schema=None, classify_course_records=classify, evidence_materials=_TruncatedOrderMaterials(),
        include_course_sources=True,
    )
    assert state == ("data_gap", "transfusion_source_truncated")
