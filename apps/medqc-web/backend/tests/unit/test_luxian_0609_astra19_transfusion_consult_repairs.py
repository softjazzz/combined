"""输血逐文书成分补核与会诊模型缺失的合成正式链回归。"""
import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.services.luxian_0609 import consultation_disposition_record as disposition
from app.services.luxian_0609.decision_model import ALLOWED_REASON_CODES_BY_FINAL_STATE
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_transfusion_execution import execute_luxian_0609_native_transfusion_rules
from app.services.luxian_0609.native_consultation_episode_execution import execute_luxian_0609_native_consultation_episode_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.transfusion_result_mapping import (
    safe_transfusion_customer_display_facts, transfusion_customer_fact_status_is_valid,
)
from app.services.llm_token_budget import BudgetError, BudgetVerdict, is_budget_error, note_budget_failure
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER

TRANSFUSION = "LX0609-07-02-02"
CONSULT = "LX0609-03-01-05"


def transfusion_record(ref="A", hour=14, component="红悬", indication=True):
    text = (
        ("输血目的：纠正贫血；" if indication else "")
        + f"2026年07月07日{hour}:00开始输入{component}2U，"
        + f"2026年07月07日{hour + 1}:00输注完毕。输血过程中严密观察，患者生命体征平稳，"
        + "未见寒战、皮疹及输血不良反应。输血后复查血红蛋白提升，治疗有效。"
    )
    return {"document_id": ref, "record_time": f"2026-07-07 {hour + 1}:00:00", "record_content": text}


def transfusion_rows(records):
    return {"inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)], "bloodtrans_record": records}


class TransfusionClient:
    """按真实输入回答已标注的实际输注；成分只读取当前一份正文。"""
    def __init__(self, records, component_failure=None, component_state="explicit"):
        self.known_texts = {row["record_content"] for row in records}
        self.component_failure = component_failure
        self.component_state = component_state
        self.component_calls = 0
        self.fixture_errors = []

    async def generate(self, prompt, **kwargs):
        try:
            if "INPUT_JSON=" in prompt:
                inputs = json.loads(prompt.split("INPUT_JSON=", 1)[1])
                if set(inputs) == {"orders"}:
                    for row in inputs["orders"]:
                        assert row["name"] == OPEN_TRANSFUSION_ORDER["order_name"]
                        assert row["order_status"] == "新开"
                    payload = {"schema_version": "lx0609-transfusion-order-trigger-v1", "orders": [
                        {"index": row["index"], "classification": "transfusion", "cancelled": False, "quote": row["name"]}
                        for row in inputs["orders"]]}
                else:
                    assert set(inputs) == {"records"}
                    for row in inputs["records"]:
                        assert row["content"] in self.known_texts
                    payload = {"schema_version": "lx0609-transfusion-course-presence-v2", "records": [
                        {"index": row["index"], "kind": "record", "quote": row["content"].split("。", 1)[0] + "。"}
                        for row in inputs["records"]]}
            else:
                assert "你只核对下面这一份输血记录单" in prompt
                body = prompt.split("输血记录单正文：\n", 1)[1]
                assert body in self.known_texts
                assert "开始输入红悬2U" in body
                self.component_calls += 1
                if self.component_failure is not None:
                    if self.component_failure == "invalid":
                        return {"content": "{}"}
                    if is_budget_error(self.component_failure):
                        note_budget_failure(self.component_failure)
                    raise self.component_failure
                ref = prompt.split("document_ref: ", 1)[1].split("\n", 1)[0]
                payload = {"assertion": self.component_state,
                    "component_text": "红悬" if self.component_state == "explicit" else "",
                    "quote": "开始输入红悬2U", "document_ref": ref}
            return {"content": json.dumps(payload, ensure_ascii=False)}
        except AssertionError as error:
            self.fixture_errors.append(str(error))
            raise


def consultation_rows():
    return {"consultation_record": [{"document_id": "C", "document_title": "会诊执行记录",
        "record_time": "2026-07-07 12:00:00", "record_content": "会诊建议：给予气压治疗。我科处理：遵照执行。"}]}


async def run(rule, rows, client=None, visit="astra19-synthetic"):
    selected = (rule,) if isinstance(rule, str) else tuple(rule)
    def reader(*, source_key, **kwargs):
        return SnapshotSourceRows.create(source_key=source_key, rows=rows.get(source_key, ()), truncated=False, limit_rows=100)
    session = build_luxian_0609_evidence_read_session(selected_rule_ids=selected, institute_id="I", patient_id="P",
        visit_id=visit, source_schema=None, created_at="2026-07-08T12:00:00+08:00", row_reader=reader)
    args = dict(rule_ids=selected, decision_rule_ids=selected, institute_id="I", patient_id="P", visit_id=visit,
        source_schema=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials, llm_client=client)
    if TRANSFUSION in selected:
        native = await execute_luxian_0609_native_transfusion_rules(**args, wrapper_rules=[{"rule_id": rid} for rid in selected], evidence_payload=None)
    else:
        native = await execute_luxian_0609_native_consultation_episode_rules(**args)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=native.decisions, expected_rule_ids=selected,
        snapshot=session.snapshot, evidence_materials=session.materials)
    finals = {decision.rule_id: finalize_luxian_0609_reduced_customer_result(decision=decision,
        raw_customer_display_facts=dict(native.customer_display_facts).get(decision.rule_id),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials) for decision in reduced}
    if client is not None:
        assert not client.fixture_errors
    return (finals[rule] if isinstance(rule, str) else finals), native


def persist(final):
    metadata = sa.MetaData()
    table = sa.Table("luxian_0609_record_result_envelopes", metadata,
        *[sa.Column(name, sa.String, primary_key=name == "id") for name in (
            "id", "job_id", "root_job_id", "created_by", "record_id", "institute_id", "patient_id", "visit_id", "rule_set_key", "rule_set_version")],
        sa.Column("envelope_json", sa.Text), sa.Column("result_count", sa.Integer),
        sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime))
    engine = sa.create_engine("sqlite://", poolclass=StaticPool)
    metadata.create_all(engine)
    store = CanonicalResultStore(table)
    item = dict(final, institute_id="I", patient_id="P", visit_id="V")
    job = {"id": "astra19", "created_by": "synthetic", "filters_json": json.dumps({
        "rule_set_key": "luxian_0609_qc_v1", "rule_ids": [final["rule_id"]]})}
    try:
        with Session(engine) as writer:
            store.replace_for_job(writer, job_row=job, items=[item], now=datetime(2026, 7, 8),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="astra19"), projection_key="astra19")
            writer.commit()
        with Session(engine) as reader:
            saved = store.load_selected(reader, root_job_id="astra19", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
        assert saved["status"] == final["status"]
        assert saved["reason_code"] == final["reason_code"]
        assert saved.get("customer_display_facts") == final.get("customer_display_facts")
        return saved
    finally:
        engine.dispose()


def assert_technical_failure(final):
    assert final["status"] == "technical_error", final
    assert final["reason_code"] in ALLOWED_REASON_CODES_BY_FINAL_STATE["technical_error"]
    assert not final.get("customer_display_facts")
    with pytest.raises(ValueError, match="Canonical Envelope"):
        persist(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
async def test_single_component_success_preserves_other_record_defect(reverse):
    records = [transfusion_record(), transfusion_record("B", 18, "红细胞", indication=False)]
    if reverse:
        records.reverse()
    client = TransfusionClient(records)
    final, _ = await run(TRANSFUSION, transfusion_rows(records), client)
    assert final["status"] == "non_compliant", final
    facts = persist(final)["customer_display_facts"]
    assert facts["missing_fields"] == ["reason_or_indication"]
    assert facts["missing_field_record_counts"] == {"reason_or_indication": 1}
    assert facts["incomplete_record_count"] == 1
    assert client.component_calls <= 2


@pytest.mark.asyncio
async def test_multiple_pending_components_are_not_confirmed_missing():
    records = [transfusion_record(), transfusion_record("B", 18)]
    client = TransfusionClient(records)
    final, _ = await run(TRANSFUSION, transfusion_rows(records), client)
    # 原有单文书补核限额内未核完，走技术失败而不是医学缺失或临床资料不足。
    assert_technical_failure(final)
    assert client.component_calls <= 2


@pytest.mark.asyncio
async def test_missing_consultation_model_is_not_clinical_data_gap():
    final, native = await run(CONSULT, consultation_rows())
    assert_technical_failure(final)
    assert native.llm_call_count == 0


@pytest.mark.asyncio
async def test_unresolved_component_does_not_enter_confirmed_defect_list():
    records = [transfusion_record(indication=False), transfusion_record("B", 18)]
    client = TransfusionClient(records)
    final, _ = await run(TRANSFUSION, transfusion_rows(records), client)
    assert final["status"] == "non_compliant"
    saved = persist(final)
    facts = saved["customer_display_facts"]
    assert facts["record_count"] == 2
    assert facts["incomplete_record_count"] == 1
    assert facts["unresolved_component_record_count"] == 2
    assert facts["missing_fields"] == ["reason_or_indication"]
    assert "component" not in facts["checked_fields"]
    assert "另有2份输血记录的成分尚待核验" in saved["findings"]
    assert "血液成分" not in saved["suggestion"]
    assert client.component_calls == 0


@pytest.mark.asyncio
async def test_component_success_keeps_all_complete_records():
    records = [transfusion_record(), transfusion_record("B", 18, "红细胞")]
    client = TransfusionClient(records)
    final, _ = await run(TRANSFUSION, transfusion_rows(records), client)
    assert final["status"] == "compliant"
    assert persist(final)["customer_display_facts"]["record_count"] == 2
    assert client.component_calls == 1


@pytest.mark.asyncio
async def test_explicit_incomplete_record_keeps_unverified_component_separate():
    record = transfusion_record(indication=False)
    record["record_content"] += "过程记录不完整。"
    client = TransfusionClient([record])
    final, _ = await run(TRANSFUSION, transfusion_rows([record]), client)
    assert final["status"] == "non_compliant"
    facts = persist(final)["customer_display_facts"]
    assert facts["missing_fields"] == ["reason_or_indication"]
    assert facts["unresolved_component_record_count"] == 1
    assert client.component_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid", "transport", "budget"])
async def test_component_failure_remains_technical(failure):
    records = [transfusion_record()]
    error = (
        BudgetError(BudgetVerdict(status="OVER_BUDGET", reason="synthetic", profile="test", model="fixed"))
        if failure == "budget" else RuntimeError("synthetic transport failure") if failure == "transport" else "invalid"
    )
    client = TransfusionClient(records, component_failure=error)
    final, _ = await run(TRANSFUSION, transfusion_rows(records), client)
    assert_technical_failure(final)
    assert final["reason_code"] == {
        "budget": "llm_context_over_budget", "transport": "model_transport_error", "invalid": "model_invalid_output",
    }[failure]
    assert client.component_calls == 1


@pytest.mark.asyncio
async def test_component_budget_failure_preserves_independent_defect():
    records = [transfusion_record(), transfusion_record("B", 18, "红细胞", indication=False)]
    error = BudgetError(BudgetVerdict(status="OVER_BUDGET", reason="synthetic", profile="test", model="fixed"))
    client = TransfusionClient(records, component_failure=error)
    final, _ = await run(TRANSFUSION, transfusion_rows(records), client)
    assert final["status"] == "non_compliant"
    facts = persist(final)["customer_display_facts"]
    assert facts["missing_fields"] == ["reason_or_indication"]
    assert facts["unresolved_component_record_count"] == 1


@pytest.mark.asyncio
async def test_component_limit_failure_does_not_remove_family_success():
    records = [transfusion_record(), transfusion_record("B", 18)]
    rows = transfusion_rows(records)
    consent_rule = "LX0609-11-03-01"
    rows["consent_form"] = [{"document_id": "consent", "document_title": "输血治疗知情同意书", "record_content": "输血治疗知情同意书，合成患者已同意。"}]
    finals, native = await run((TRANSFUSION, consent_rule), rows, TransfusionClient(records))
    assert set(finals) == {TRANSFUSION, consent_rule}
    assert len(native.decisions) == 2
    assert_technical_failure(finals[TRANSFUSION])
    assert finals[consent_rule]["status"] == "compliant"
    assert persist(finals[consent_rule])["status"] == "compliant"


@pytest.mark.asyncio
async def test_component_unclear_has_controlled_semantic_state():
    records = [transfusion_record()]
    _, native = await run(TRANSFUSION, transfusion_rows(records), TransfusionClient(records, component_state="unclear"))
    decision = reduce_luxian_0609_rule_decision(native.decisions[0])
    assert decision.final_state.value == "data_gap"
    assert decision.reason_code == "semantic_extraction_unresolved"
    facts = safe_transfusion_customer_display_facts(rule_id=TRANSFUSION, raw=dict(native.customer_display_facts)[TRANSFUSION])
    assert facts == {"failure_kind": "transfusion_component_unresolved", "transfusion_order_present": True,
                     "record_count": 1, "unresolved_component_record_count": 1}
    assert transfusion_customer_fact_status_is_valid(rule_id=TRANSFUSION, status="data_gap", reason_code=decision.reason_code, safe_facts=facts)
    assert not transfusion_customer_fact_status_is_valid(rule_id=TRANSFUSION, status="data_gap", reason_code="source_unavailable", safe_facts=facts)
    assert not transfusion_customer_fact_status_is_valid(rule_id=TRANSFUSION, status="non_compliant", reason_code="requirement_violated", safe_facts=facts)
    # Finalizer原因透传及Canonical新形状严格配对由父整合；本节点只承诺Native与validator边界。


def test_unresolved_counter_rejects_invalid_values_and_preserves_history():
    old = {"failure_kind": "transfusion_course_record_incomplete", "transfusion_order_present": True,
           "record_count": 1, "checked_fields": ["reason_or_indication"], "missing_fields": ["reason_or_indication"],
           "incomplete_record_count": 1, "missing_field_record_counts": {"reason_or_indication": 1}}
    assert safe_transfusion_customer_display_facts(rule_id=TRANSFUSION, raw=old) == old
    zero = {**old, "unresolved_component_record_count": 0}
    assert safe_transfusion_customer_display_facts(rule_id=TRANSFUSION, raw=zero) == zero
    for count in (True, -1, 2, 0.5):
        assert safe_transfusion_customer_display_facts(rule_id=TRANSFUSION, raw={**old, "unresolved_component_record_count": count}) is None
    unknown = {"failure_kind": "transfusion_component_unresolved", "transfusion_order_present": True,
               "record_count": 1, "unresolved_component_record_count": 2}
    assert safe_transfusion_customer_display_facts(rule_id=TRANSFUSION, raw=unknown) is None


class ConsultClient:
    """两阶段协议仅响应同一份人工标注原文；未知请求不伪造成功。"""

    def __init__(self, failure=None):
        self.failure = failure
        self.calls = 0
        self.fixture_errors = []

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        stage = "opinion" if "\nDOCUMENTS_JSON=" in prompt else "action"
        if self.failure == stage:
            raise RuntimeError("synthetic transport failure")
        try:
            marker = "\nDOCUMENTS_JSON=" if stage == "opinion" else "\nROLE_FACTS_JSON="
            items, _ = json.JSONDecoder().raw_decode(prompt.split(marker, 1)[1])
            result = []
            for row in items:
                if stage == "opinion":
                    body = "会诊建议：给予气压治疗。我科处理：遵照执行。"
                    assert row["text"].endswith(body)
                    assert row["text"][:-len(body)] in {"", "会诊执行记录；"}
                    result.append({"ref": row["ref"], "scope": "ordinary", "suggestion_state": "present",
                                   "opinion_quotes": ["给予气压治疗"], "feedback_quotes": ["遵照执行"]})
                else:
                    assert row["opinion_quotes"] == ["给予气压治疗"]
                    assert row["feedback_quotes"] == ["遵照执行"]
                    result.append({"ref": row["ref"], "medications": [], "examinations": [], "other_actions": [],
                        "therapies": [{"action_quote": "给予气压治疗", "feedback_quote": "遵照执行", "referent_quote": "", "feedback_kind": "generic"}]})
            return {"content": json.dumps({"schema_version": disposition.SCHEMA_VERSION + ("-opinions" if stage == "opinion" else ""), "documents": result}, ensure_ascii=False)}
        except (AssertionError, ValueError, KeyError, IndexError) as error:
            self.fixture_errors.append(str(error))
            raise


@pytest.mark.asyncio
async def test_consultation_no_trigger_does_not_require_model():
    final, native = await run(CONSULT, {})
    assert final["status"] == "not_applicable"
    assert persist(final)["status"] == "not_applicable"
    assert native.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["opinion", "action"])
async def test_consultation_failure_keeps_existing_semantics(stage):
    final, _ = await run(CONSULT, consultation_rows(), ConsultClient(failure=stage), visit="failure-" + stage)
    if stage == "opinion":
        assert_technical_failure(final)
    else:
        assert final["status"] == "non_compliant"
        assert persist(final)["customer_display_facts"]["unspecific_document_count"] == 1


@pytest.mark.asyncio
async def test_consultation_missing_model_cannot_reuse_response_but_verified_freeze_survives(tmp_path, monkeypatch):
    monkeypatch.setenv("LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR", str(tmp_path))
    initial = ConsultClient()
    final, _ = await run(CONSULT, consultation_rows(), initial, visit="same-visit")
    assert final["status"] == "non_compliant"
    assert initial.calls == 2
    frozen = {str(path): path.read_bytes() for path in tmp_path.rglob("*.json")}
    assert frozen
    missing, _ = await run(CONSULT, consultation_rows(), None, visit="same-visit")
    assert_technical_failure(missing)
    cached_client = ConsultClient(failure="opinion")
    cached, native = await run(CONSULT, consultation_rows(), cached_client, visit="same-visit")
    assert cached["status"] == final["status"]
    assert persist(cached)["customer_display_facts"] == final["customer_display_facts"]
    assert native.llm_call_count == cached_client.calls == 0
    assert {str(path): path.read_bytes() for path in tmp_path.rglob("*.json")} == frozen
