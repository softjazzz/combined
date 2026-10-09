"""074 连续引文工程合同；合成响应不代表真实模型准确率。"""
from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import MetaData, create_engine, select, func
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.extended_document.diagnosis_change_extraction import (
    SCHEMA_VERSION,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)
from tests.integration.test_luxian_0609_real_production_rules_076_077 import _session

RULE = "LX0609-12-02-01"
REASON = "结合症状及检查，修正诊断：甲病"
BASIS = "诊断依据：1.症状反复出现；2.检查提示甲病"
TEXT = REASON + "。" + BASIS + "。"


class ResponseClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {
            "choices": [{"message": {"content": json.dumps({
                "schema_version": SCHEMA_VERSION, "items": self.items,
            }, ensure_ascii=False)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 70, "completion_tokens": 30, "total_tokens": 100},
        }


def item(*, reason_state="present", reason_quote=REASON,
         basis_state="present", basis_quote=BASIS, local_doc_id="doc_01"):
    return dict(local_doc_id=local_doc_id, reason_state=reason_state,
                reason_quote=reason_quote, basis_state=basis_state, basis_quote=basis_quote)


async def run(items, texts=(TEXT,)):
    session = _session(RULE, {"senior_course_record": tuple({
        "document_id": f"synthetic-{i}", "record_time": f"2026-07-0{i} 10:00:00",
        "record_content": text,
    } for i, text in enumerate(texts, 1))})
    client = ResponseClient(items)
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert len(client.calls) == execution.llm_call_count == 1
    assert client.calls[0][1]["allow_length_retry"] is False
    return final, client


def roundtrip(final, tmp_path, *, accepted):
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite:///" + str(tmp_path / "quote-contract.sqlite"))
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    raw = dict(final, record_id="v", visit_id="v", patient_id="p", institute_id="i")
    key = "synthetic-quote-contract-key"
    def save():
        with Session(engine) as session:
            store.replace_for_job(
                session, job_row={"id": "quote-job", "created_by": "test",
                    "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09", "scoped_customer_rule_ids": [RULE]})},
                items=[raw], now=datetime.now(timezone.utc),
                projector=lambda x: envelope_item_from_rule_result(x, hmac_key=key),
                projection_key=key,
            )
            session.commit()
    try:
        if accepted:
            save()
            with Session(engine) as session:
                loaded = store.load_selected(
                    session, root_job_id="quote-job", institute_id="i", patient_id="p",
                    visit_id="v", rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
                )
            expected = envelope_item_from_rule_result(raw, hmac_key=key)
            assert {k: loaded["items"][0][k] for k in expected if k != "record_ref"} == {
                k: v for k, v in expected.items() if k != "record_ref"
            }
        else:
            with pytest.raises(ValueError):
                save()
            with Session(engine) as session:
                assert session.execute(select(func.count()).select_from(table)).scalar_one() == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_prompt_requires_verbatim_span_and_distinguishes_unverified_from_missing():
    _, client = await run([item()])
    prompt = client.calls[0][0]
    assert "逐字复制，保留编号、空白和标点" in prompt
    assert "不得删改、拼接或省略" in prompt
    assert "missing表示未记录" in prompt
    assert "unknown表示无法可靠判断" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", [BASIS, "检查提示甲病"])
async def test_contiguous_basis_survives_finalizer_and_new_session_readback(quote, tmp_path):
    final, _ = await run([item(basis_quote=quote)])
    assert final["status"] == "compliant"
    roundtrip(final, tmp_path, accepted=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", [
    "诊断依据：症状反复出现；检查提示甲病",  # 省略两个列表编号。
    "诊断依据：1.症状反复出现2.检查提示甲病",  # 删除中间标点。
    "诊断依据：1.症状反复出现……2.检查提示甲病",  # 新增省略号。
    "诊断依据：1.症状反复出现...2.检查提示甲病",
    "诊断依据：1.症状反复出现；2.检查提示乙病",  # 改写事实。
])
async def test_noncontiguous_or_rewritten_basis_is_not_public_or_saved(quote, tmp_path):
    final, _ = await run([item(basis_quote=quote)])
    assert (final["status"], final["reason_code"]) == ("technical_error", "model_invalid_output")
    assert not final.get("customer_display_facts")
    roundtrip(final, tmp_path, accepted=False)


@pytest.mark.asyncio
async def test_quote_cannot_be_borrowed_from_another_document(tmp_path):
    other = "结合检查，补充诊断：乙病。诊断依据：CT提示乙病。"
    final, _ = await run([
        item(basis_quote="CT提示乙病"),
        item(local_doc_id="doc_02", reason_quote="结合检查，补充诊断：乙病", basis_quote="CT提示乙病"),
    ], (TEXT, other))
    assert final["status"] == "technical_error"
    assert not final.get("customer_display_facts")
    roundtrip(final, tmp_path, accepted=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(("state", "expected", "saved"), [
    ("missing", "non_compliant", True), ("unknown", "uncertain", False),
])
async def test_empty_missing_and_unknown_keep_distinct_outcomes(state, expected, saved, tmp_path):
    final, _ = await run([item(basis_state=state, basis_quote="")])
    assert final["status"] == expected
    roundtrip(final, tmp_path, accepted=saved)


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["missing", "unknown"])
async def test_absent_state_with_nonempty_quote_is_rejected(state, tmp_path):
    final, _ = await run([item(basis_state=state)])
    assert final["status"] == "technical_error"
    roundtrip(final, tmp_path, accepted=False)
