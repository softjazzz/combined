"""1016 引擎修改独立核查发现的缺口：仅合成材料与本地替身，不调用真实模型。"""
import json

import pytest

from app.services.luxian_0609 import anesthesia_visit_fact_extraction as visit
from app.services.luxian_0609 import native_surgery_document_execution as surgery_doc
from app.services.luxian_0609 import native_transfusion_execution as transfusion
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
