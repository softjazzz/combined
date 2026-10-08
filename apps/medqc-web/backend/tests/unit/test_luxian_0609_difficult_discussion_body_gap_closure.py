"""CT-03：已定位讨论行但物理正文不可用时，只能保留资料不足。"""
from datetime import datetime
import json

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts as published_facts,
)
from app.services.luxian_0609.difficult_case_result_mapping import (
    difficult_case_customer_fact_status_is_valid as status_valid,
    safe_difficult_case_customer_display_facts as safe_facts,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from test_luxian_0609_native_extended_document_execution import _evaluate_selected

RULE = "LX0609-03-02-01"
ADMISSION = "2026-06-01 08:00:00"
MATURE = "2026-06-08 09:00:00"
KIND = "uncertain_diagnosis_discussion_body_gap"
COUNT = "discussion_body_gap_count"
TIME_COUNT = "candidate_course_time_gap_count"
OLD = {"verification_kind": "uncertain_diagnosis_discussion_check", "admission_time": ADMISSION,
       "uncertain_record_times": [MATURE], "discussion_count": 0}
FACTS = {**OLD, "verification_kind": KIND, "discussion_count": 1, COUNT: 1}
MISSING = object()


@pytest.fixture(autouse=True)
def no_external_access(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("CT-03合成测试禁止PG、网络和真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


class ForbiddenModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("050 program_only/0不得调用模型")


def discussion(body=MISSING, document="SYN-DISCUSSION"):
    row = {"record_time": MATURE, "title": "疑难病例讨论记录", "signature": "合成签名"}
    if document is not None:
        row["document_id"] = document
    if body is not MISSING:
        row["record_content"] = body
    return row


def rows(*discussions, course_time=MATURE, course_text="目前诊断仍不明确。", untimed=False):
    daily = [{"document_id": "SYN-COURSE", "record_content": course_text}]
    if course_time is not None:
        daily[0]["record_time"] = course_time
    if untimed:
        daily.append({"document_id": "SYN-UNTIMED", "record_content": "目前诊断仍不明确。"})
    return {"inpat_registration": [{"admission_datetime": ADMISSION}],
            "daily_course_record": daily, "diffcase_discussion_record": list(discussions)}


async def evaluate(source_rows, *, unavailable=frozenset()):
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (RULE,), source_rows, unavailable_sources=unavailable, llm_client=ForbiddenModel(),
    )
    results = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RULE}], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    assert execution.llm_call_count == execution.total_tokens == 0
    assert len(results) == 1
    assert results[0]["status"] == {"evaluation_unknown": "uncertain"}.get(reduced[0].final_state.value, reduced[0].final_state.value)
    return snapshot, materials, execution, results[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [MISSING, None, 123, False, [], {}, "", " \t\r\n "])
async def test_engineering_supplement_located_rows_without_string_body_are_gap(body):
    _, _, _, result = await evaluate(rows(discussion(body)))
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    assert result["customer_display_facts"] == FACTS
    assert "正文" in result["findings"] and "资料不足" in result["findings"]
    assert "未见" not in result["findings"] and "合规" not in result["findings"]
    assert "源系统" in result["suggestion"]
    assert "补写" not in result["suggestion"] or "不应" in result["suggestion"] or "不得" in result["suggestion"]


@pytest.mark.asyncio
async def test_multiple_blank_rows_do_not_prove_completed_discussion():
    _, _, _, result = await evaluate(rows(discussion(None, "SYN-A"), discussion("  ", "SYN-B")))
    assert result["status"] == "data_gap"
    assert result["customer_display_facts"] == {**FACTS, "discussion_count": 2, COUNT: 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_mixed_available_body_preserves_old_facts_and_path(reverse):
    records = [discussion(" ", "SYN-A"), discussion("短有效正文。", "SYN-B")]
    if reverse:
        records.reverse()
    _, _, _, result = await evaluate(rows(*records))
    assert result["status"] == "compliant"
    assert result["reason_code"] == "requirement_satisfied"
    assert result["customer_display_facts"] == {**OLD, "discussion_count": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["短", "疑难病例讨论记录", "  合成有效正文。  "])
async def test_nonempty_string_body_keeps_existing_path_without_semantic_reinterpretation(body):
    _, _, _, result = await evaluate(rows(discussion(body)))
    assert result["status"] == "compliant"
    assert result["customer_display_facts"] == {**OLD, "discussion_count": 1}


@pytest.mark.asyncio
async def test_no_discussion_row_keeps_confirmed_missing_document():
    _, _, _, result = await evaluate(rows())
    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "required_document_missing"
    assert result["customer_display_facts"] == OLD


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["unavailable", "admission", "untimed", "local"])
async def test_existing_source_time_and_scope_priority_is_not_changed_by_blank_body(scenario):
    source_rows = rows(discussion(""))
    unavailable = set()
    expected_kind = None
    if scenario == "unavailable":
        unavailable.add("diffcase_discussion_record")
        status, reason = "data_gap", "source_unavailable"
    elif scenario == "admission":
        source_rows["inpat_registration"] = []
        status, reason = "data_gap", "authoritative_time_missing"
    elif scenario == "untimed":
        source_rows["daily_course_record"][0].pop("record_time")
        status, reason = "data_gap", "authoritative_time_missing"
        expected_kind = "uncertain_diagnosis_course_time_gap"
    else:
        source_rows["daily_course_record"][0]["record_content"] = "发热原因待查。"
        status, reason = "uncertain", "diagnosis_scope_uncertain"
        expected_kind = "uncertain_diagnosis_scope_unverified"
    _, _, _, result = await evaluate(source_rows, unavailable=unavailable)
    assert result["status"] == status
    assert result["reason_code"] == reason
    if expected_kind:
        assert result["customer_display_facts"]["verification_kind"] == expected_kind
    else:
        assert not result.get("customer_display_facts")


@pytest.mark.asyncio
async def test_ct04_candidate_prethreshold_existing_discussion_should_remain_not_applicable():
    # 首轮81fe已复现公开链技术错误；保持工程应NA预期，本轮不修旧合同冲突。
    source_rows = rows(discussion(""), course_time="2026-06-02 09:00:00")
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (RULE,), source_rows, llm_client=ForbiddenModel(),
    )
    assert reduced[0].final_state.value == "not_applicable"
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RULE}], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )[0]
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "trigger_absent_complete"


@pytest.mark.asyncio
async def test_body_gap_with_independent_untimed_candidate_keeps_mature_times_and_both_gaps():
    _, _, _, result = await evaluate(rows(discussion(None), untimed=True))
    assert result["status"] == "data_gap"
    assert result["customer_display_facts"] == {**FACTS, TIME_COUNT: 1}
    assert "正文" in result["findings"] and "时间" in result["findings"]
    assert "正文" in result["suggestion"] and "时间" in result["suggestion"]


@pytest.mark.asyncio
@pytest.mark.parametrize("document", ["SYN-DISCUSSION", None])
async def test_gap_evidence_is_real_selected_document_or_readable_source_anchor(document):
    snapshot, materials, execution, result = await evaluate(rows(discussion(None, document)))
    assert result["status"] == "data_gap"
    refs = execution.decisions[0].fact_refs
    material_rows = materials.document_rows("diffcase_discussion_record", snapshot=snapshot)
    assert len(material_rows) == 1 and material_rows[0][1].get("record_content") is None
    assert any(ob.snapshot_ref.removeprefix("sha256:") in refs for ob in snapshot.observations if ob.source_key == "diffcase_discussion_record")
    evidence = result.get("customer_evidence", [])
    if document:
        assert material_rows[0][0] in refs
        assert any(item.get("source_document_id") == document for item in evidence)
    else:
        assert material_rows[0][0] not in refs
        assert not evidence or all(item.get("source_document_id") == "SYN-COURSE" for item in evidence)
    assert not any(item.get("source_document_id") in {"None", "SYNTHETIC", ""} for item in evidence)


@pytest.mark.parametrize("time_gap", [False, True])
def test_body_gap_contract_accepts_only_data_gap_and_filters_extra_internal_fields(time_gap):
    facts = {**FACTS, **({TIME_COUNT: 1} if time_gap else {})}
    raw = {**facts, "record_content": "内部原文", "debug_payload": {"secret": True}}
    assert safe_facts(rule_id=RULE, raw=raw) == facts
    assert status_valid(rule_id=RULE, status="data_gap", safe_facts=facts)
    assert published_facts(rule_id=RULE, raw=raw, status="data_gap") == facts


@pytest.mark.parametrize("status", ["", "unknown", "compliant", "non_compliant", "not_applicable", "uncertain", "technical_error"])
def test_public_body_gap_kind_rejects_inconsistent_status(status):
    assert not status_valid(rule_id=RULE, status=status, safe_facts=FACTS)
    with pytest.raises(ValueError, match="解释合同不完整"):
        published_facts(rule_id=RULE, raw=FACTS, status=status)


@pytest.mark.parametrize("changes", [
    {COUNT: None}, {COUNT: True}, {COUNT: 0}, {COUNT: -1}, {COUNT: 2},
    {"discussion_count": 0}, {"discussion_count": True}, {"discussion_count": 2},
    {"uncertain_record_times": []}, {"uncertain_record_times": ["bad"]},
    {"admission_time": "bad"}, {TIME_COUNT: False},
    {"verification_kind": "unknown_kind"},
    {"verification_kind": "uncertain_diagnosis_discussion_check"},
    {"verification_kind": "uncertain_diagnosis_scope_unverified"},
    {"verification_kind": "uncertain_diagnosis_course_time_gap"},
])
def test_body_gap_count_and_mature_time_contract_is_strict(changes):
    raw = {**FACTS, **changes}
    assert safe_facts(rule_id=RULE, raw=raw) is None
    with pytest.raises(ValueError, match="解释合同不完整"):
        published_facts(rule_id=RULE, raw=raw, status="data_gap")


def test_body_gap_kind_requires_the_count_field():
    raw = {key: value for key, value in FACTS.items() if key != COUNT}
    assert safe_facts(rule_id=RULE, raw=raw) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["gap", "body_and_time", "mixed_c"])
async def test_synthetic_sqlite_new_instance_preserves_body_gap_or_old_compliance(scenario, tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result, keyed_ref

    records = [discussion(None)]
    if scenario == "mixed_c":
        records.append(discussion("有效正文。", "SYN-VALID"))
    snapshot, materials, execution, result = await evaluate(rows(*records, untimed=scenario == "body_and_time"))
    assert result["status"] == ("compliant" if scenario == "mixed_c" else "data_gap")
    item = {**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "ct03.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    try:
        with Session(engine) as write_db:
            CanonicalResultStore(table).replace_for_job(
                write_db, job_row={"id": "J", "created_by": "synthetic-reviewer",
                    "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 10, 8, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"), projection_key="test-key",
            )
            write_db.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as read_db:
            loaded = CanonicalResultStore(table).load_selected(
                read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )
            saved = loaded["items"][0]
            for key in ("status", "reason_code", "customer_display_facts", "findings", "suggestion"):
                assert saved.get(key) == item.get(key)
            projected = workspace.project_customer_safe_result_item(saved, hmac_key="test-key")
            assert projected["customer_display_facts"] == saved["customer_display_facts"]
            assert projected["evidence"] == saved["evidence"]
            source_evidence = projected["evidence"]
            if scenario != "mixed_c":
                discussion_evidence = next(e for e in source_evidence if e.get("source_ref") == keyed_ref(
                    "src", "SYN-DISCUSSION", hmac_key="test-key"))
                assert discussion_evidence["source_type"] == "diffcase_discussion_record"
                assert discussion_evidence["record_time"] == MATURE
                assert not discussion_evidence.get("field_path")
                assert not discussion_evidence.get("evidence_excerpt")
            else:
                # 旧来源级投影不能从两讨论行猜选ID；保持可核快照和病程精确卡。
                assert not any(e.get("source_type") == "diffcase_discussion_record" for e in source_evidence)
                discussion_rows = materials.document_rows("diffcase_discussion_record", snapshot=snapshot)
                assert len(discussion_rows) == 2
                assert any(row.get("record_content") == "有效正文。" for _, row in discussion_rows)
                assert any(ob.snapshot_ref.removeprefix("sha256:") in execution.decisions[0].fact_refs
                           for ob in snapshot.observations if ob.source_key == "diffcase_discussion_record")
            course_evidence = next(e for e in source_evidence if e.get("source_ref") == keyed_ref(
                "src", "SYN-COURSE", hmac_key="test-key"))
            assert course_evidence["source_type"] == "daily_course_record"
            assert course_evidence["record_time"] == MATURE
            assert course_evidence["field_path"] == "record_content"
            assert course_evidence["evidence_excerpt"] == "目前诊断仍不明确。"
            assert all(e.get("source_ref", "").startswith("src_") and len(e["source_ref"]) == 28 for e in source_evidence)
            assert all("source_document_id" not in e and "document_id" not in e for e in projected["evidence"])
            assert "record_content" not in projected["customer_display_facts"]
            assert "debug_payload" not in projected
    finally:
        engine.dispose()
