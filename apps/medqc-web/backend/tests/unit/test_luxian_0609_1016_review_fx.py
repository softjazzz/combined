"""1016 引擎修改独立核查发现的缺口：仅合成材料与本地替身，不调用真实模型。"""
import json

import pytest

from app.services.luxian_0609 import anesthesia_visit_fact_extraction as visit
from app.services.luxian_0609 import native_surgery_document_execution as surgery_doc
from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609 import transfusion_result_mapping as mapping
from app.services.luxian_0609.decision_reducer import CustomerFinalState, reduce_luxian_0609_rule_decision
from app.services.qc_workspace.failed_rule_retry import _automatic_retryable_failure
from tests.unit.test_luxian_0609_native_surgery_document_execution import _typed_session

R0402 = "LX0609-04-04-02"


class _RaisingClient:
    def __init__(self, error):
        self.error = error

    async def generate(self, prompt, **kwargs):
        raise self.error


class _BadOutputClient:
    async def generate(self, prompt, **kwargs):
        return {"choices": [{"message": {"content": json.dumps({"documents": []})}, "finish_reason": "stop"}]}


def _visit_documents():
    return [visit.VisitDocument("synthetic-preane", "preane_surveil_record", "术前访视：患者一般情况可。",
                                ("general_condition",))]


@pytest.mark.asyncio
@pytest.mark.parametrize("client,reason", [
    (None, "model_transport_error"),
    (_RaisingClient(RuntimeError("synthetic transport")), "model_transport_error"),
    (_RaisingClient(TimeoutError()), "model_timeout"),
    (_BadOutputClient(), "model_invalid_output"),
])
async def test_anesthesia_visit_model_failure_is_technical_error(client, reason):
    """麻醉访视抽取的模型失败交付技术错误，不交付为资料不足。"""
    result = await visit.extract_anesthesia_visit_facts(_visit_documents(), client)
    assert (result.state, result.reason_code) == ("technical_error", reason)


@pytest.mark.parametrize("reason", ["model_transport_error", "model_timeout", "model_invalid_output",
                                    "privacy_guard_blocked", "execution_program_error", "source_query_error"])
def test_surgery_document_keeps_technical_reason(reason):
    """手术文书族保留细分技术原因码，不改写为快照异常。"""
    session = _typed_session(selected_rule_ids=(R0402,))
    decision = surgery_doc._typed_decision_from_outcome(
        outcome=surgery_doc._SurgeryDocumentOutcome(R0402, "technical_error", reason, "llm"),
        snapshot=session.snapshot,
    )
    assert decision.reason_code == reason
    assert reduce_luxian_0609_rule_decision(decision).final_state is CustomerFinalState.TECHNICAL_ERROR


def test_surgery_document_unknown_technical_reason_is_snapshot_mismatch():
    """未登记的技术原因仍按快照异常处理。"""
    session = _typed_session(selected_rule_ids=(R0402,))
    decision = surgery_doc._typed_decision_from_outcome(
        outcome=surgery_doc._SurgeryDocumentOutcome(R0402, "technical_error", "something_else", "llm"),
        snapshot=session.snapshot,
    )
    assert decision.reason_code == "snapshot_mismatch"


@pytest.mark.parametrize("items", [transfusion._PRETRANSFUSION_REQUIRED_ITEMS, transfusion._PRETRANSFUSION_REGULAR_ITEMS])
def test_lab_item_name_field_is_matched(items):
    """来源合同认可的 lab_item_name 字段与 item_name 同样参与项目匹配。"""
    assert transfusion.resolve_pretransfusion_required_item(
        {"lab_item_name": "人免疫缺陷病毒抗体测定"}, required_items=items) == "hiv"


def test_pretransfusion_items_complete_with_lab_item_name_only():
    """只提供 lab_item_name 的齐全检验判合规，不误判为全部缺项。"""
    names = ["*ABO血型鉴定", "*Rh血型鉴定", "不规则抗体筛查", "乙肝表面抗原", "乙肝表面抗体", "乙肝e抗原",
             "乙肝e抗体", "乙肝核心抗体", "丙肝抗体", "HIV抗体", "梅毒抗体"]
    documents = {
        "mr_bloodtrans": [{"document_id": "synthetic-event", "transfution_datetime": "2026-06-05 14:20:00"}],
        "labtest_item_report": [{"document_id": f"synthetic-lab-{i}", "lab_item_name": name, "result": "阴性",
                                 "report_datetime": "2026-06-05 10:00:00"} for i, name in enumerate(names)],
        "__logical_source_states__": {"labtest_item_report": "available"},
    }
    status, reason, _facts = transfusion.evaluate_pretransfusion_nine_items(
        documents, required_items=transfusion._PRETRANSFUSION_REGULAR_ITEMS)
    assert (status, reason) == ("compliant", "pretransfusion_items_complete")


def test_family_order_mismatch_is_not_auto_retried():
    """族输出顺序错误属确定性结构问题，不自动补跑（历史失败数据）。"""
    assert not _automatic_retryable_failure(
        {"rule_id": "LX0609-07-01-01", "reason_code": "family_result_order_mismatch"})
    assert _automatic_retryable_failure({"rule_id": "LX0609-07-01-01", "reason_code": "model_timeout"})


@pytest.mark.parametrize("rule_id", sorted(mapping._SYSTEM_GAP_REASONS))
def test_stripped_system_gap_facts_pass_published_validation(rule_id):
    """Finalizer 剥离文案后的系统缺口公开形状，对每条登记规则都能通过发布校验。"""
    expected = mapping._SYSTEM_GAP_REASONS[rule_id]
    reason = sorted(expected)[0] if isinstance(expected, frozenset) else expected
    raw = {"failure_kind": "system_data_contract_gap", "system_gap_reason": reason, "gap_owner": "system_integration"}
    assert mapping._safe_system_gap(rule_id=rule_id, raw=raw) == raw
    # 原因与本规则不符时仍拒绝
    assert mapping._safe_system_gap(rule_id=rule_id, raw={**raw, "system_gap_reason": "other_reason"}) is None


@pytest.mark.asyncio
async def test_043_empty_lab_source_holds_customer_contract():
    """07-01-01 检验来源为空判资料不足，经收口后仍满足交付合同，不被改判技术错误。"""
    from app.services.luxian_0609.canonical_result_finalizer import luxian_0609_customer_result_contract_holds
    from test_luxian_0609_transfusion_performance_043_047 import BLOOD_APPLICATION, STRUCTURED_EVENT, _run

    final = (await _run("LX0609-07-01-01", {"mr_bloodtrans": STRUCTURED_EVENT, "blood_application": BLOOD_APPLICATION,
                                             "labtest_item_report": []}, {}))["final"]
    assert (final["status"], final["reason_code"]) == ("data_gap", "source_unavailable")
    assert luxian_0609_customer_result_contract_holds(final)


@pytest.mark.parametrize("reason", ["model_invalid_output", "model_parse_error"])
def test_output_format_failure_is_not_auto_retried(reason):
    """模型输出格式错误在温度 0 下重跑无效，不自动补跑。"""
    assert not _automatic_retryable_failure({"rule_id": "LX0609-08-01-04", "reason_code": reason})


@pytest.mark.parametrize("reason", ["model_timeout", "model_transport_error", "model_rate_limited", "model_upstream_error"])
def test_transient_model_failure_is_still_auto_retried(reason):
    """超时、网络、限流等偶发错误仍自动补跑。"""
    assert _automatic_retryable_failure({"rule_id": "LX0609-08-01-04", "reason_code": reason})


def test_candidate_scope_incomplete_is_not_auto_retried():
    """候选范围超限由输入规模决定（03-01-04 存疑项），不自动补跑。"""
    assert not _automatic_retryable_failure({"rule_id": "LX0609-03-01-04", "reason_code": "candidate_scope_incomplete"})


@pytest.mark.parametrize("example", ["急性意识障碍对脑出血", "呼吸困难对心力衰竭", "头昏、乏力伴心累、气促对缺铁性贫血",
                                     "头痛、头晕对脑梗死"])
def test_018_prompt_states_symptom_grading_examples(example):
    """01-01-02 提示词写明器官系统方向与全身性非特异症状的划分示例。"""
    from app.services.luxian_0609.course_quality.rule_018 import _lx018_prompt
    assert example in _lx018_prompt(context="")


def test_parse_failure_description_never_echoes_model_content():
    """解析失败日志描述只含受控类别与计数，不带出模型输出片段。"""
    from app.services.luxian_0609.llm_prompt_privacy import describe_luxian_0609_llm_parse_failure

    response = {"choices": [{"finish_reason": "length", "message": {"content": "患者张三"}}],
                "usage": {"completion_tokens": 2048}}
    text = describe_luxian_0609_llm_parse_failure(ValueError("malignancy result count invalid"), response)
    assert text == ("error_kind=ValueError detail=malignancy result count invalid "
                    "finish_reason=length completion_tokens=2048")
    for error in (KeyError("患者张三"), ValueError("引文不在原文：患者张三"), ValueError("ref D07 invalid")):
        described = describe_luxian_0609_llm_parse_failure(error, response)
        assert "张三" not in described and "D07" not in described
    assert "finish_reason=-" in describe_luxian_0609_llm_parse_failure(ValueError("x"), None)


class _MalignancyClient:
    """按提示里实际送出的条目逐条应答；可指定某诊断名为 uncertain。"""

    def __init__(self, uncertain_name=None, drop_one=False):
        self.uncertain_name, self.drop_one, self.sent = uncertain_name, drop_one, []

    async def generate(self, prompt, **kwargs):
        from app.services.luxian_0609.malignancy_fact import SCHEMA_VERSION
        items = json.loads(prompt.rsplit("输入：", 1)[1])
        self.sent.append(items)
        results = [{"ref": i["ref"], "state": "uncertain" if i["diagnosis_name"] == self.uncertain_name
                    else "explicit_nonmalignant"} for i in items]
        if self.drop_one:
            results = results[:-1]
        content = json.dumps({"schema_version": SCHEMA_VERSION, "results": results}, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}


def _dup_sources():
    from app.services.luxian_0609.malignancy_fact import build_malignancy_sources
    rows = [{"diagnosis_name": name} for name in ("肺部肿物", "高血压", "肺部肿物", "高血压", "糖尿病")]
    return build_malignancy_sources(diagnosis_state="available", diagnosis_rows=rows,
                                    pathology_state="available", pathology_rows=[])


@pytest.mark.asyncio
async def test_malignancy_sends_duplicate_diagnoses_once_and_maps_back():
    """重复诊断只送一次，不确定结果映射回全部重复行。"""
    from app.services.luxian_0609.malignancy_fact import MalignancyFactResolver
    client = _MalignancyClient(uncertain_name="肺部肿物")
    resolution = await MalignancyFactResolver(client).resolve(_dup_sources())
    assert [i["diagnosis_name"] for i in client.sent[0]] == ["肺部肿物", "高血压", "糖尿病"]
    assert (resolution.state, resolution.reason_code) == ("unknown", "malignancy_semantics_uncertain")
    assert [row["diagnosis_name"] for _, row in resolution.uncertain_rows] == ["肺部肿物", "肺部肿物"]


@pytest.mark.asyncio
async def test_malignancy_result_count_check_stays_strict():
    """去重后仍严格校验条数：模型少返回一条仍判输出无效。"""
    from app.services.luxian_0609.malignancy_fact import MalignancyFactResolver
    resolution = await MalignancyFactResolver(_MalignancyClient(drop_one=True)).resolve(_dup_sources())
    assert (resolution.state, resolution.reason_code) == ("technical_error", "malignancy_llm_invalid")


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["diagnosis", "discharge_record_diagnosis"])
async def test_027_unknown_malignancy_without_uncertain_rows_is_plain_data_gap(source):
    """诊断内容缺失导致恶性性质未知、且无可疑诊断行时，按普通资料不足交付，不携带未决事实。

    此前仍携带计数为 0 的“恶性性质未决”事实，被事实合同拒绝后改判技术错误（第四轮 C06/C09/C24）。
    """
    from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys

    rule = "LX0609-08-01-04"
    rows = [{"document_id": "normal", "diagnosis_name": "合成普通诊断"}, {"document_id": "blank"}]

    def reader(**kwargs):
        key = kwargs["source_key"]
        material = rows if key == source else (
            [{"document_id": "discharge", "treatment_course": "合成出院记录。"}] if key == "discharge_record" else [])
        return SnapshotSourceRows.create(source_key=key, rows=material, truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=(rule,)),
    )

    class NoModel:
        async def generate(self, prompt, **kwargs):
            raise AssertionError("诊断内容缺失时不调用模型")

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule,), wrapper_rules=[{"rule_id": rule, "custom_prompt": "{medical_text}"}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=NoModel(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=(rule,),
    )
    assert dict(result.customer_display_facts).get(rule) is None
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=(rule,),
                                                         snapshot=session.snapshot, evidence_materials=session.materials)
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced[0], raw_customer_display_facts=None,
                                                         evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final["status"] == "data_gap"


@pytest.mark.parametrize("rule_id", ["LX0609-06-01-02", "LX0609-06-03-03"])
def test_exam_lab_default_facts_cap_source_document_ids_to_public_limit(rule_id):
    """文书 ID 超过公开事实上限时只保留前 8 个，事实仍能通过合同校验（第四轮 C15 有 24 个）。"""
    from app.services.luxian_0609.exam_lab_result_mapping import (
        build_default_display_facts, safe_exam_lab_customer_display_facts)

    ids = [f"doc-{index:02d}" for index in range(24)]
    facts = build_default_display_facts(rule_id=rule_id, status="non_compliant",
                                        reason_code="exam_lab_text_fact", source_document_ids=ids)
    assert facts["source_document_ids"] == ids[:8]
    assert safe_exam_lab_customer_display_facts(rule_id=rule_id, raw=facts) is not None
