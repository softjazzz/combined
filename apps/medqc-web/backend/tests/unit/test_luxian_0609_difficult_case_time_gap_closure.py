"""CT-02：候选病程时间缺口不可证明未触发，成熟缺陷不被掩盖。"""

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
from diagnosis_scope_test_support import FrozenDiagnosisScopeClient

RULE = "LX0609-03-02-01"
ADMISSION = "2026-06-01 08:00:00"
MATURE = "2026-06-08 09:00:00"
GAP_KIND = "uncertain_diagnosis_course_time_gap"
GAP_COUNT = "candidate_course_time_gap_count"
GAP_FACTS = {"verification_kind": GAP_KIND, "admission_time": ADMISSION,
             "uncertain_record_times": [], "discussion_count": 0, GAP_COUNT: 1}
OLD_FACTS = {"verification_kind": "uncertain_diagnosis_discussion_check", "admission_time": ADMISSION,
             "uncertain_record_times": [MATURE], "discussion_count": 0}


@pytest.fixture(autouse=True)
def no_external_access(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("CT-02合成测试禁止PG、网络和真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


def course(*, time=MATURE, document="SYN-COURSE", text="目前诊断仍不明确。", field="record_time"):
    row = {"record_content": text}
    if document is not None:
        row["document_id"] = document
    if time is not None:
        row[field] = time
    return row


def rows(*records, discussion=False):
    return {"inpat_registration": [{"admission_datetime": ADMISSION}],
            "daily_course_record": list(records),
            "diffcase_discussion_record": ([{"document_id": "SYN-DISCUSSION", "record_time": MATURE,
                                             "record_content": "合成疑难病例讨论记录。"}] if discussion else [])}


async def evaluate(source_rows, *, unavailable=frozenset()):
    client = FrozenDiagnosisScopeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (RULE,), source_rows, unavailable_sources=unavailable, llm_client=client,
    )
    results = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RULE}], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    assert client.fixture_error is None, client.fixture_error
    # 本文件来源未就绪或完全无入院资料的冻结用例均须在抽取前返回。
    # 两个精确早期时间是本文件原人工边界oracle；不调用生产时间解析反推计量。
    early_times = {"2026-06-02 09:00:00", "2026-06-08 07:59:59"}
    eligible_rows = [row for row in source_rows.get("daily_course_record", ())
        if next((row[key] for key in ("record_time", "record_datetime", "submit_time", "submit_datetime")
                 if key in row), None) not in early_times]
    expected_calls = int(not unavailable and bool(eligible_rows) and bool(
        source_rows.get("inpat_registration") or source_rows.get("admission_record")))
    assert execution.llm_call_count == len(client.calls) == expected_calls
    assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (
        expected_calls * 10, expected_calls * 5, expected_calls * 15)
    assert len(results) == 1
    assert results[0]["status"] == reduced[0].final_state.value
    return snapshot, materials, execution, results[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, "", "  ", "not-a-time"])
@pytest.mark.parametrize("discussion", [False, True])
async def test_frozen_missing_course_time_is_gap_with_or_without_discussion(missing, discussion):
    _, _, _, result = await evaluate(rows(course(time=missing), discussion=discussion))
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"
    assert result["customer_display_facts"] == {**GAP_FACTS, "discussion_count": int(discussion)}
    assert "病程" in result["findings"] and "时间" in result["findings"]
    assert "未触发" not in result["findings"]
    assert "未发现" not in result["findings"]
    assert "诊断仍不明确" not in result["findings"]
    assert "源系统" in result["suggestion"]
    assert "补写" not in result["suggestion"] or "不应" in result["suggestion"] or "不得" in result["suggestion"]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["record_time", "record_datetime", "submit_time", "submit_datetime"])
async def test_existing_authoritative_time_aliases_preserve_mature_missing_discussion(field):
    _, _, _, result = await evaluate(rows(course(field=field)))
    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "required_document_missing"
    assert result["customer_display_facts"] == OLD_FACTS


@pytest.mark.asyncio
@pytest.mark.parametrize("time,status", [
    ("2026-06-08 07:59:59", "not_applicable"),
    ("2026-06-08 08:00:00", "non_compliant"),
    ("2026-06-08T00:00:00Z", "non_compliant"),
    ("2026-06-08T09:00:00+09:00", "non_compliant"),
])
async def test_seven_day_boundary_and_same_instant_timezone_expressions_are_unchanged(time, status):
    _, _, _, result = await evaluate(rows(course(time=time)))
    assert result["status"] == status
    assert GAP_COUNT not in result["customer_display_facts"]


@pytest.mark.asyncio
async def test_invalid_high_priority_time_does_not_use_lower_priority_alias_to_claim_trigger():
    candidate = course(time="invalid")
    candidate["submit_time"] = MATURE
    _, _, _, result = await evaluate(rows(candidate))
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("discussion", [False, True])
async def test_independently_mature_decision_survives_another_untimed_candidate(reverse, discussion):
    records = [course(document="SYN-MATURE"), course(time=None, document="SYN-UNTIMED")]
    if reverse:
        records.reverse()
    _, _, _, result = await evaluate(rows(*records, discussion=discussion))
    assert result["status"] == ("compliant" if discussion else "non_compliant")
    assert result["reason_code"] == ("requirement_satisfied" if discussion else "required_document_missing")
    assert result["customer_display_facts"] == {**OLD_FACTS, "discussion_count": int(discussion), GAP_COUNT: 1}
    assert "病程" in result["findings"] and "时间" in result["findings"]
    if not discussion:
        assert "未见疑难病例讨论" in result["findings"]
    assert "另" in result["findings"]


@pytest.mark.asyncio
async def test_known_prethreshold_candidate_does_not_hide_another_untimed_candidate():
    _, _, _, result = await evaluate(rows(course(time="2026-06-02 09:00:00"),
                                          course(time=None, document="SYN-UNTIMED")))
    assert result["status"] == "data_gap"


@pytest.mark.asyncio
async def test_local_scope_candidate_with_missing_time_remains_a_timing_gap_not_confirmed_missing_discussion():
    _, _, _, result = await evaluate(rows(course(time=None, text="发热原因待查。")))
    assert result["status"] == "data_gap"
    assert result["customer_display_facts"][GAP_COUNT] == 1
    assert "诊断仍不明确" not in result["findings"]


@pytest.mark.asyncio
async def test_untimed_non_candidate_does_not_create_a_time_gap():
    _, _, _, result = await evaluate(rows(course(time=None, text="当前诊断已明确。")))
    assert result["status"] == "not_applicable"
    assert result["customer_display_facts"] == {**OLD_FACTS, "uncertain_record_times": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_source", ["daily_course_record", "diffcase_discussion_record"])
async def test_source_gap_still_has_priority_and_does_not_manufacture_course_time_facts(missing_source):
    _, _, _, result = await evaluate(rows(course(time=None)), unavailable={missing_source})
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "source_unavailable"
    assert not result.get("customer_display_facts")


@pytest.mark.asyncio
async def test_missing_admission_time_keeps_existing_gap_without_a_fabricated_admission_value():
    source_rows = rows(course(time=None))
    source_rows["inpat_registration"] = []
    _, _, _, result = await evaluate(source_rows)
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"
    assert not result.get("customer_display_facts")


@pytest.mark.asyncio
@pytest.mark.parametrize("document", ["SYN-UNTIMED", None])
async def test_time_gap_evidence_uses_real_document_or_source_anchor_without_unrelated_documents(document):
    candidate = course(time=None, document=document)
    snapshot, materials, execution, result = await evaluate(rows(
        candidate, course(text="当前诊断已明确。", document="SYN-UNRELATED"),
    ))
    assert result["status"] == "data_gap"
    refs = execution.decisions[0].fact_refs
    material_rows = materials.document_rows("daily_course_record", snapshot=snapshot)
    unrelated_ref = next(ref for ref, row in material_rows if row.get("document_id") == "SYN-UNRELATED")
    assert unrelated_ref not in refs
    evidence = result.get("customer_evidence", [])
    assert "SYN-UNRELATED" not in json.dumps(evidence, ensure_ascii=False)
    if document:
        candidate_ref = next(ref for ref, row in material_rows if row.get("document_id") == document)
        assert candidate_ref in refs
        assert any(item.get("source_document_id") == document for item in evidence)
    else:
        source_ref = next(ob.snapshot_ref.removeprefix("sha256:") for ob in snapshot.observations
                          if ob.source_key == "daily_course_record")
        assert source_ref in refs
        assert evidence == []
        assert "customer_evidence" not in result or result["customer_evidence"] == []
        assert any(row == candidate for _, row in material_rows)
        assert all(ref != unrelated_ref for ref in refs)
    serialized = json.dumps(result["customer_display_facts"], ensure_ascii=False)
    assert "document_id" not in serialized and "目前诊断仍不明确" not in serialized


@pytest.mark.parametrize("count", [None, 0, -1, True, "1", 1.0])
def test_invalid_gap_counts_are_rejected_by_family_and_public_boundary(count):
    raw = {**GAP_FACTS, GAP_COUNT: count}
    assert safe_facts(rule_id=RULE, raw=raw) is None
    assert not status_valid(rule_id=RULE, status="data_gap", safe_facts=raw)
    with pytest.raises(ValueError, match="解释合同不完整"):
        published_facts(rule_id=RULE, raw=raw, status="data_gap")


@pytest.mark.parametrize("status", ["", "unknown", "uncertain", "technical_error", "not_executed",
                                        "not_applicable", "compliant", "non_compliant"])
def test_time_gap_cannot_be_published_under_any_other_status(status):
    assert not status_valid(rule_id=RULE, status=status, safe_facts=GAP_FACTS)
    with pytest.raises(ValueError, match="解释合同不完整"):
        published_facts(rule_id=RULE, raw=GAP_FACTS, status=status)


def test_legal_gap_is_preserved_by_family_and_public_boundary():
    assert safe_facts(rule_id=RULE, raw=GAP_FACTS) == GAP_FACTS
    assert status_valid(rule_id=RULE, status="data_gap", safe_facts=GAP_FACTS)
    assert published_facts(rule_id=RULE, raw=GAP_FACTS, status="data_gap") == GAP_FACTS


@pytest.mark.parametrize("status,discussion", [("non_compliant", 0), ("compliant", 1)])
def test_mixed_mature_facts_keep_old_status_and_reject_other_statuses(status, discussion):
    raw = {**OLD_FACTS, "discussion_count": discussion, GAP_COUNT: 1}
    assert safe_facts(rule_id=RULE, raw=raw) == raw
    assert status_valid(rule_id=RULE, status=status, safe_facts=raw)
    assert published_facts(rule_id=RULE, raw=raw, status=status) == raw
    for invalid in ("", "unknown", "data_gap", "not_applicable", "compliant" if status == "non_compliant" else "non_compliant"):
        assert not status_valid(rule_id=RULE, status=invalid, safe_facts=raw)
        with pytest.raises(ValueError, match="解释合同不完整"):
            published_facts(rule_id=RULE, raw=raw, status=invalid)


@pytest.mark.parametrize("changes", [
    {"verification_kind": "unknown_kind"}, {"uncertain_record_times": [MATURE]},
    {"discussion_count": True}, {"discussion_count": -1}, {"admission_time": ""},
])
def test_malformed_time_gap_facts_are_rejected(changes):
    assert safe_facts(rule_id=RULE, raw={**GAP_FACTS, **changes}) is None


@pytest.mark.parametrize("kind", ["uncertain_diagnosis_discussion_check", "uncertain_diagnosis_scope_unverified"])
def test_time_gap_summary_cannot_make_an_unmatured_or_local_only_fact_determined(kind):
    raw = {**GAP_FACTS, "verification_kind": kind}
    assert safe_facts(rule_id=RULE, raw=raw) is None


@pytest.mark.parametrize("scenario", ["gap", "mixed_nc", "mixed_c"])
@pytest.mark.asyncio
async def test_pure_synthetic_sqlite_new_instance_read_preserves_time_gap_and_mature_decision(scenario, tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    records = [course(time=None, document="SYN-UNTIMED")]
    if scenario != "gap":
        records.append(course(document="SYN-MATURE"))
    _, _, _, result = await evaluate(rows(*records, discussion=scenario == "mixed_c"))
    assert result["status"] == {"gap": "data_gap", "mixed_nc": "non_compliant", "mixed_c": "compliant"}[scenario]
    assert result["customer_display_facts"][GAP_COUNT] == 1
    item = {**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "ct02.sqlite").as_posix()
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
            assert "目前诊断仍不明确" not in json.dumps(projected["customer_display_facts"], ensure_ascii=False)
            assert "record_content" not in projected
            assert "record_content" not in projected["customer_display_facts"]
    finally:
        engine.dispose()
