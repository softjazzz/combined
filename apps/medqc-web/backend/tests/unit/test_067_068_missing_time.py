import asyncio
import json

import pytest
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient

from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    SCHEMA_VERSION as DISCHARGE_APPROVAL_SCHEMA_VERSION,
)


class _ApprovalClient:
    """068 上级同意出院以模型抽取为准（用户口径 2026-10-22）：受控 Fake 逐份判为上级同意。"""

    # approved 引文须为整句（2026-11-18 合同变更）；本组只验证时间/窗口语义，替身改给整句合法回答。
    _QUOTES = ("上级医师查看患者，同意明日出院。", "上级医师查看患者，同意今日出院。")

    def __init__(self):
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        payload = json.loads(prompt[prompt.index("[{"):prompt.rindex("}]") + 2])
        items = [
            {
                "local_doc_id": doc["local_doc_id"],
                "opinion": "approved",
                "quote": next(quote for quote in self._QUOTES if quote in doc["text"]),
            }
            for doc in payload
        ]
        return {
            "choices": [{
                "message": {"content": json.dumps({
                    "schema_version": DISCHARGE_APPROVAL_SCHEMA_VERSION, "items": items,
                })},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
            "_api_time": 0.1,
        }


def _run(rule, *, valid=False, approval=True, llm_client=None):
    rows = {
        "inpat_registration": [{"patient_status": "出院"}],
        "discharge_record": [{"document_id": "discharge", "discharge_time": "2026-02-09 08:00:00"}],
        "senior_course_record": [{
            "document_id": "undated", "record_time": None,
            "record_content": "上级医师查看患者，同意明日出院。" if approval else "一般病程。",
        }],
        "daily_course_record": [{"document_id": "outside", "record_time": "2026-02-13 08:00:00", "record_content": "一般病程。"}],
    }
    if valid:
        rows["senior_course_record"].append({
            "document_id": "valid", "record_time": "2026-02-09 07:00:00",
            "record_content": "上级医师查看患者，同意今日出院。",
        })

    def reader(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=source, rows=rows.get(source, []), truncated=False, limit_rows=50)

    # 067有已定时窗口正文时使用逐字人工事实；068的上级同意由模型抽取（受控 Fake）。
    if rule == "LX0609-08-02-01" and valid:
        assert llm_client is None
        llm_client = FrozenCourseBodyClient({
            "上级医师查看患者，同意明日出院。": ("present", "同意明日出院"),
            "上级医师查看患者，同意今日出院。": ("present", "同意今日出院"),
        })
    if rule == "LX0609-08-02-02" and approval and llm_client is None:
        llm_client = _ApprovalClient()

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-02-10T09:00:00+08:00", row_reader=reader,
    )
    result = asyncio.run(execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        llm_client=llm_client,
    ))
    return session, result


@pytest.mark.parametrize("rule,kind", [
    ("LX0609-08-02-01", "predischarge_course_time_missing"),
    ("LX0609-08-02-02", "senior_discharge_approval_time_missing"),
])
def test_missing_time_preserves_window_and_selected_document(rule, kind):
    session, result = _run(rule)
    facts = dict(result.customer_display_facts)[rule]
    assert facts["failure_kind"] == kind
    assert facts["discharge_date"] == "2026-02-09"
    assert list(facts["checked_dates"]) == ["2026-02-08", "2026-02-09"]
    assert facts["missing_time_count"] == 1
    assert "approval_present" not in facts
    assert result.decisions[0].reason_code == "authoritative_time_missing"
    assert result.llm_call_count == (1 if rule == "LX0609-08-02-02" else 0)
    assert len(result.decisions[0].fact_refs) == 1
    selected = [row["document_id"] for ref, row in session.materials.document_rows(
        "senior_course_record", snapshot=session.snapshot,
    ) if ref in result.decisions[0].fact_refs]
    assert selected == ["undated"]
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    canonical = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=facts,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert canonical["status"] == "data_gap"
    assert canonical["customer_display_facts"]["failure_kind"] == kind
    assert canonical["missing_fields"]
    assert "2026-02-08" in canonical["customer_message"]
    assert "2026-02-09" in canonical["customer_message"]
    assert canonical["data_gap_details"]["customer_message"] == canonical["customer_message"]
    assert [item["source_document_id"] for item in canonical["customer_evidence"]] == ["undated"]


@pytest.mark.parametrize("rule", ["LX0609-08-02-01", "LX0609-08-02-02"])
def test_valid_window_evidence_is_not_blocked_by_undated_document(rule):
    _, result = _run(rule, valid=True)
    assert result.decisions[0].reason_code == "requirement_satisfied"
    assert "missing_time_count" not in dict(result.customer_display_facts)[rule]
    assert len(result.decisions[0].fact_refs) == 1
    assert result.llm_call_count == 1


def test_068_without_approval_keeps_original_missing_semantics():
    _, result = _run("LX0609-08-02-02", approval=False)
    assert result.decisions[0].reason_code == "source_empty"
    assert result.llm_call_count == 0
    assert dict(result.customer_display_facts)["LX0609-08-02-02"]["approval_present"] is False


def test_068_model_confirmed_undated_approval_is_time_missing():
    """模型确认上级同意但文书无时间：说明无法确认窗口，不能说未读到意见。"""
    client = _ApprovalClient()
    _, result = _run("LX0609-08-02-02", llm_client=client)

    assert result.decisions[0].reason_code == "authoritative_time_missing"
    assert result.llm_call_count == len(client.calls) == 1
