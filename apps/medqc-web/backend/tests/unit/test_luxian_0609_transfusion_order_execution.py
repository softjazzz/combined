"""新医嘱合同的正式输出链回归；模型替身只验证协议与接线，不证明语义准确率。"""
import json

import pytest

from app.services.luxian_0609 import native_transfusion_execution as native
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session

RULES = ("LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02")


class FrozenOrderClient:
    def __init__(self, classification="transfusion", cancelled=False, record_kind="record"):
        self.record_kind = record_kind
        self.classification = classification
        self.cancelled = cancelled
        self.calls = 0

    async def generate(self, prompt):
        self.calls += 1
        payload = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        if "records" in payload:
            return {"content": json.dumps({
                "schema_version": "lx0609-transfusion-course-presence-v1",
                "records": [{"index": row["index"], "kind": self.record_kind,
                             "quote": row["content"]} for row in payload["records"]],
            }, ensure_ascii=False)}
        rows = payload["orders"]
        return {"content": json.dumps({
            "schema_version": "lx0609-transfusion-order-trigger-v1",
            "orders": [{"index": row["index"], "classification": self.classification,
                        "cancelled": self.cancelled, "quote": row["name"]} for row in rows],
        }, ensure_ascii=False)}


def run_case(rows, *, client=None, truncated=None, failed=None):
    def read(**kwargs):
        key = kwargs["source_key"]
        if key == failed:
            raise SourceEvidenceQueryError("synthetic source failure")
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, []),
                                         truncated=key == truncated, limit_rows=5000)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULES, institute_id="test-I", patient_id="test-P", visit_id="test-V",
        source_schema=None, created_at="2026-10-09T08:00:00+08:00", row_reader=read,
    )
    coroutine = native.execute_luxian_0609_native_transfusion_rules(
        rule_ids=RULES, wrapper_rules=[{"rule_id": rule} for rule in RULES],
        decision_rule_ids=RULES, evidence_payload=None, institute_id="test-I",
        patient_id="test-P", visit_id="test-V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    # 此套协议替身没有I/O await；直接驱动避免Windows测试环境的socketpair依赖。
    try:
        coroutine.send(None)
    except StopIteration as finished:
        execution = finished.value
    else:
        coroutine.close()
        raise AssertionError("unexpected external await")
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=RULES,
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    facts = dict(execution.customer_display_facts)
    final = {item.rule_id: finalize_luxian_0609_reduced_customer_result(
        decision=item, raw_customer_display_facts=facts.get(item.rule_id),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    ) for item in reduced}
    return execution, final


def order_rows(source="inpat_nondrug_order"):
    return {source: [{"order_id": "order-arbitrary-42", "order_name" if source == "inpat_nondrug_order" else "generic_name": "输注去白悬浮红细胞2U", "order_status": "新开"}]}


@pytest.mark.parametrize("source", ["inpat_nondrug_order", "inpat_drug_order"])
def test_open_order_triggers_missing_record_without_performed_claim(source):
    client = FrozenOrderClient()
    execution, final = run_case(order_rows(source), client=client)
    assert client.calls == execution.llm_call_count == 1
    assert final[RULES[1]]["status"] == "non_compliant"
    assert final[RULES[2]]["status"] == "data_gap"
    facts = final[RULES[1]]["customer_display_facts"]
    assert facts["transfusion_order_present"] is True
    assert "performed_transfusion_confirmed" not in facts
    evidence = final[RULES[1]]["customer_evidence"]
    assert any(item["source_type"] == source and item["source_document_id"] == "order-arbitrary-42"
               and item["evidence_excerpt"] == "输注去白悬浮红细胞2U" for item in evidence), evidence
    assert "transfusion_course_record_incomplete" not in json.dumps(final[RULES[2]], ensure_ascii=False)


@pytest.mark.parametrize("classification,cancelled,expected", [
    ("transfusion", True, "not_applicable"),
    ("other", False, "not_applicable"),
    ("unknown", False, "data_gap"),
    ("transfusion", None, "data_gap"),
])
def test_order_classification_controls_trigger(classification, cancelled, expected):
    _, final = run_case(order_rows(), client=FrozenOrderClient(classification, cancelled))
    assert {row["status"] for row in final.values()} == {expected}
    assert "已实施输血" not in json.dumps(final, ensure_ascii=False)


@pytest.mark.parametrize("content", ["拟输注红细胞2U，待家属同意后实施。", "输血记录：" + "正文很长。" * 100])
def test_document_length_cannot_replace_order(content):
    client = FrozenOrderClient()
    _, final = run_case({"bloodtrans_record": [{"document_id": "record", "record_content": content}]}, client=client)
    assert client.calls == 0
    assert {row["status"] for row in final.values()} == {"not_applicable"}


def test_missing_model_is_technical_error_not_no_order():
    _, final = run_case(order_rows())
    assert {row["status"] for row in final.values()} == {"technical_error"}


def test_truncated_order_source_cannot_be_absence():
    _, final = run_case(order_rows(), truncated="inpat_nondrug_order")
    assert {row["status"] for row in final.values()} == {"data_gap"}


def test_failed_order_source_cannot_be_absence():
    _, final = run_case({}, failed="inpat_drug_order")
    assert {row["status"] for row in final.values()} == {"technical_error"}


@pytest.mark.parametrize("text", [
    "拟输注红细胞2U，输血开始14:00，结束16:00，拟观察反应。",
    "患者拒绝输血，暂不实施，拟复查血常规后再决定。",
    "输血计划已取消。本次继续观察，暂无其他处理。",
    "输血记录：指征：；成分：；剂量：；开始：；结束：。签名：张某",
])
def test_invalid_course_is_missing_for_045_and_gap_for_046(text):
    rows = order_rows()
    rows["bloodtrans_record"] = [{"document_id": "course-1", "record_content": text}]
    client = FrozenOrderClient(record_kind="not_record")
    execution, final = run_case(rows, client=client)
    assert final[RULES[1]]["status"] == "non_compliant"
    assert final[RULES[2]]["status"] == "data_gap"
    assert client.calls == execution.llm_call_count == 2
    assert "performed_transfusion_confirmed" not in json.dumps(final[RULES[1:][0]])


def test_short_real_course_is_not_rejected_by_length():
    rows = order_rows()
    rows["bloodtrans_record"] = [{"document_id": "short-course", "record_content": "已输红细胞2U。"}]
    _, final = run_case(rows, client=FrozenOrderClient())
    assert final[RULES[1]]["status"] == "compliant"
    assert final[RULES[2]]["status"] == "non_compliant"


def test_unknown_course_cannot_be_missing_or_compliant():
    rows = order_rows()
    rows["bloodtrans_record"] = [{"document_id": "unclear-course", "record_content": "输血情况详见附件，附件未提供。"}]
    _, final = run_case(rows, client=FrozenOrderClient(record_kind="unknown"))
    assert final[RULES[1]]["status"] == final[RULES[2]]["status"] == "data_gap"


def test_unavailable_course_source_does_not_erase_order_or_become_missing():
    _, final = run_case(order_rows(), client=FrozenOrderClient(), failed="bloodtrans_record")
    assert final[RULES[1]]["status"] == final[RULES[2]]["status"] == "technical_error"


def test_privacy_wrapper_preserves_quote_binding_to_original_document():
    from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
    rows = order_rows()
    rows["bloodtrans_record"] = [{"document_id": "private-course",
        "record_content": "患者姓名：测试甲；已输注红细胞2U。"}]
    delegate = FrozenOrderClient()
    client = wrap_luxian_0609_llm_client(delegate, identity_values=("测试甲",))
    _, final = run_case(rows, client=client)
    assert final[RULES[1]]["status"] == "compliant"
    assert any(item["source_document_id"] == "private-course"
               for item in final[RULES[1]]["customer_evidence"])


@pytest.mark.parametrize("document_id, expected_id", [(" course-with-spaces ", "course-with-spaces"), (0, "0")])
def test_course_identity_keeps_record_and_snapshot_reference(document_id, expected_id):
    rows = order_rows()
    rows["bloodtrans_record"] = [{"document_id": document_id, "record_content": "已输红细胞2U。"}]
    _, final = run_case(rows, client=FrozenOrderClient())
    assert final[RULES[1]]["status"] == "compliant"
    assert final[RULES[1]]["customer_display_facts"]["record_count"] == 1
    assert any(item["source_document_id"] == expected_id
               for item in final[RULES[1]]["customer_evidence"])
