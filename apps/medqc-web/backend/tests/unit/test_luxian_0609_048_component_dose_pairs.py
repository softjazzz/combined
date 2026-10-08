"""048成分、数量、单位及事件配对的正式交付边界。"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, SourceEvidenceUnavailable, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_transfusion_execution import execute_luxian_0609_native_transfusion_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results

RID = "LX0609-07-04-01"
SOURCES = ("surgery_record", "anesthesia_record", "postsurg_firstcourse_record")


async def evaluate(texts, *, unavailable=(), overrides=None):
    rows = {
        "mr_bloodtrans": [{"transfution_datetime": datetime(2026, 7, 1, 14, 20)}],
        "bloodtrans_record": [{"document_id": "bt", "record_time": "2026-07-01 17:00:00",
                               "record_content": "本次已输注红细胞2U，输注过程平稳。"}],
        **{source: [{"document_id": f"d-{index}", "record_time": "2026-07-01 18:00:00",
                    "record_content": text}] for index, (source, text) in enumerate(zip(SOURCES, texts))},
    }
    rows.update(overrides or {})
    def read(**kwargs):
        source = kwargs["source_key"]
        if source in unavailable:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(source_key=source, rows=rows.get(source, []),
                                         truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RID,), institute_id="048-i", patient_id="048-p", visit_id="048-v",
        source_schema=None, created_at="2026-07-02T00:00:00", row_reader=read,
    )
    result = await execute_luxian_0609_native_transfusion_rules(
        rule_ids=(RID,), wrapper_rules=[{"rule_id": RID}], evidence_payload=None,
        institute_id="048-i", patient_id="048-p", visit_id="048-v", source_schema=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=(RID,), llm_client=None,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(RID,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RID}], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )[0]
    assert result.llm_call_count == result.total_tokens == 0
    assert canonical["status"] == reduced[0].final_state.value
    return canonical


@pytest.mark.asyncio
async def test_component_dose_swap_is_a_confirmed_difference():
    result = await evaluate(("术中输注红细胞2U，血小板4U。",
                             "术中输注红细胞2U，血小板4U。",
                             "术中输注红细胞4U，血小板2U。"))
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["differing_fields"] == ["doses"]
    matrix = result["customer_display_facts"]["comparison_matrix"]
    assert matrix["surgery_record"]["transfusion_items"][0]["quantity"] == "2"
    assert matrix["postsurg_firstcourse_record"]["transfusion_items"][0]["quantity"] == "4"


@pytest.mark.asyncio
async def test_matching_overall_quantities_cannot_hide_swapped_event_quantities():
    correct = "术中2026-07-01 14:20输注红细胞2U。术中2026-07-01 15:20输注红细胞4U。"
    wrong = "术中2026-07-01 14:20输注红细胞4U。术中2026-07-01 15:20输注红细胞2U。"
    result = await evaluate((correct, correct, wrong))
    assert result["status"] == "non_compliant"
    items = result["customer_display_facts"]["comparison_matrix"]["postsurg_firstcourse_record"]["transfusion_items"]
    assert items[0]["event_time"] == "2026-07-01 14:20:00"
    assert items[0]["quantity"] == "4"


@pytest.mark.asyncio
@pytest.mark.parametrize("texts, expected", [
    (("术中输注红细胞2U，血小板4U。", "术中输注血小板4U，红细胞2U。", "术中输注红细胞2U，血小板4U。"), "compliant"),
    (("术中输注红细胞2U，红细胞2U。", "术中输注红细胞2U。", "术中输注红细胞2U，红细胞2U。"), "non_compliant"),
    (("术中输注红细胞2U，红细胞4U。", "术中输注红细胞4U，红细胞2U。", "术中输注红细胞2U，红细胞4U。"), "compliant"),
    (("术中输注红细胞2U，血浆200ml。", "术中输注红细胞2单位，血浆200毫升。", "术中输注红细胞2.0u，血浆200mL。"), "compliant"),
    (("术中输注红细胞2U。", "术中输注红细胞2ml。", "术中输注红细胞2U。"), "non_compliant"),
    (("术中输注红细胞2U，血小板4U。", "术中输注红细胞2U，血小板4。", "术中输注红细胞2U，血小板4U。"), "data_gap"),
    (("术中输注红细胞2。", "术中输注红细胞2。", "术中输注红细胞2。"), "data_gap"),
    (("术中2026-07-01 14:20输注红细胞2U。术中2026-07-01 15:20输注红细胞4U。",
      "术中2026-07-01 15:20输注红细胞4U。术中2026-07-01 14:20输注红细胞2U。",
      "术中2026-07-01 14:20输注红细胞2U。术中2026-07-01 15:20输注红细胞4U。"), "compliant"),
    (("术中2026-07-01 14:20输注红细胞2U。术中2026-07-01 15:20输注红细胞4U。",
      "术中2026-07-01 14:20输注红细胞2U。术中2026-07-01 15:20输注红细胞4U。",
      "术中输注红细胞2U，红细胞4U。"), "data_gap"),
    (("术中2026-07-01 14:20输注红细胞2U。", "术中2026-07-01 15:20输注红细胞2U。", "术中2026-07-01 14:20输注红细胞2U。"), "data_gap"),
])
async def test_preserves_pairs_counts_units_and_event_identity(texts, expected):
    result = await evaluate(texts)
    assert result["status"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [("anesthesia_record",), ("surgery_record", "anesthesia_record")])
async def test_unavailable_sources_cannot_prove_no_intraoperative_transfusion(unavailable):
    result = await evaluate(("术中输注红细胞2U。",) * 3, unavailable=unavailable)
    assert result["status"] == "data_gap"


@pytest.mark.asyncio
async def test_multiple_document_rows_are_not_sorted_into_event_pairs():
    result = await evaluate(("术中输注红细胞2U。",) * 3, overrides={
        "anesthesia_record": [
            {"document_id": "a1", "record_content": "术中输注红细胞2U。"},
            {"document_id": "a2", "record_content": "术中输注红细胞4U。"},
        ],
    })
    assert result["status"] == "data_gap"
    # typed合同将旧关联失败归约为required_field_missing；只检查保守状态。


@pytest.mark.asyncio
@pytest.mark.parametrize("texts, expected", [
    (("术中输注红细胞2U，血小板4U。", "术中输注红细胞2U，血小板4U。", "术中输注红细胞4U，血小板2U。"), "non_compliant"),
    (("术中输注红细胞2U，血小板4U。", "术中输注血小板4U，红细胞2U。", "术中输注红细胞2U，血小板4U。"), "compliant"),
    (("术中输注红细胞2U，血小板4U。", "术中输注红细胞2U，血小板4。", "术中输注红细胞2U，血小板4U。"), "data_gap"),
])
async def test_sqlite_saved_pairs_are_read_in_a_new_session(tmp_path, texts, expected):
    import json
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    canonical = await evaluate(texts)
    assert canonical["status"] == expected
    metadata = sa.MetaData()
    table = sa.Table("luxian_0609_record_result_envelopes", metadata,
        *[sa.Column(name, sa.String, primary_key=name == "id") for name in (
            "id", "job_id", "root_job_id", "created_by", "record_id", "institute_id",
            "patient_id", "visit_id", "rule_set_key", "rule_set_version",
        )],
        sa.Column("envelope_json", sa.Text), sa.Column("result_count", sa.Integer),
        sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
    )
    database_url = "sqlite:///" + str(tmp_path / "048.sqlite")
    engine = sa.create_engine(database_url)
    reader_engine = None
    metadata.create_all(engine)
    store = CanonicalResultStore(table)
    item = {**canonical, "institute_id": "048-i", "patient_id": "048-p", "visit_id": "048-v"}
    job = {"id": "048-job", "created_by": "048-tester", "filters_json": json.dumps({
        "rule_set_key": "luxian_0609_qc_v1", "rule_ids": [RID],
        "record_refs": [{"institute_id": "048-i", "patient_id": "048-p", "visit_id": "048-v"}],
    })}
    try:
        with Session(engine) as writer:
            store.replace_for_job(writer, job_row=job, items=[item], now=datetime(2026, 7, 2),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="048-test-key"),
                projection_key="048-test-key")
            writer.commit()
        # 关闭写Session和连接池，保证新Session从磁盘读取已提交的Canonical。
        engine.dispose()
        reader_engine = sa.create_engine(database_url)
        with Session(reader_engine) as reader:
            envelope = store.load_selected(reader, root_job_id="048-job", institute_id="048-i",
                patient_id="048-p", visit_id="048-v", rule_set_key="luxian_0609_qc_v1",
                rule_set_version="2026-06-09")
        loaded = envelope["items"][0]
        assert loaded["status"] == canonical["status"]
        assert loaded["reason_code"] == canonical["reason_code"]
        assert loaded["customer_display_facts"] == canonical["customer_display_facts"]
        assert loaded["suggestion"] == canonical["suggestion"]
        assert loaded["evidence"]
    finally:
        engine.dispose()
        if reader_engine is not None:
            reader_engine.dispose()


@pytest.mark.asyncio
async def test_split_same_event_doses_equal_the_recorded_total_without_losing_rows():
    result = await evaluate(("术中输注红细胞2U，红细胞2U。", "术中输注红细胞4U。", "术中输注红细胞4U。"))
    assert result["status"] == "compliant"
    assert len(result["customer_display_facts"]["comparison_matrix"]["surgery_record"]["transfusion_items"]) == 2


@pytest.mark.asyncio
async def test_prior_sentence_time_is_not_borrowed_for_next_unanchored_event():
    text = "术中2026-07-01 14:20输注红细胞2U。术中另一次输注红细胞4U。"
    result = await evaluate((text,) * 3)
    assert result["status"] == "data_gap"


@pytest.mark.parametrize("kind, field", [
    ("transfusion_records_consistent", "checked_fields"),
    ("transfusion_records_inconsistent", "differing_fields"),
])
def test_historical_facts_without_paired_items_remain_readable(kind, field):
    from app.services.luxian_0609.transfusion_result_mapping import safe_transfusion_customer_display_facts

    raw = {
        "verification_kind" if kind.endswith("_consistent") else "failure_kind": kind,
        "performed_intraoperative_transfusion_confirmed": True,
        field: ["components", "doses"],
        "comparison_matrix": {source: {"components": ["红细胞"], "doses": ["2u"]}
                              for source in SOURCES},
    }
    assert safe_transfusion_customer_display_facts(rule_id=RID, raw=raw) == raw


@pytest.mark.asyncio
@pytest.mark.parametrize("text, expected", [
    ("术中输注红细胞2U，另输注4U。", "data_gap"),
    ("术中输注红细胞2U，200ml。", "data_gap"),
    ("术中输注红细胞2U，静滴生理盐水200ml。", "compliant"),
    ("术中输注红细胞2U，另输注生理盐水200ml。", "compliant"),
    ("术中输注红细胞2U，另输注胰岛素4U。", "compliant"),
])
async def test_unpaired_dose_tokens_require_a_transfusion_object(text, expected):
    result = await evaluate((text,) * 3)
    assert result["status"] == expected


def paired_item_facts(item):
    return {
        "verification_kind": "transfusion_records_consistent",
        "performed_intraoperative_transfusion_confirmed": True,
        "checked_fields": ["components", "doses"],
        "comparison_matrix": {source: {
            "components": ["红细胞"], "doses": ["2u"], "transfusion_items": [item],
        } for source in SOURCES},
    }


@pytest.mark.parametrize("field, value", [
    ("quantity", "999"),
    ("unit", "ml"),
    ("component", []),
    ("unit", []),
])
def test_paired_item_rejects_invalid_types_or_inconsistent_dose(field, value):
    from app.services.luxian_0609.transfusion_result_mapping import safe_transfusion_customer_display_facts

    item = {"component": "红细胞", "quantity": "2", "unit": "u",
            "original_dose": "2U", "event_time": ""}
    item[field] = value
    assert safe_transfusion_customer_display_facts(rule_id=RID, raw=paired_item_facts(item)) is None


@pytest.mark.parametrize("quantity, unit, original_dose", [
    ("1.5", "u", "1.50U"),
    ("2", "u", "2单位"),
    ("200", "ml", "200毫升"),
    ("200", "ml", "200mL"),
    ("1", "治疗量", "1个治疗量"),
    ("1", "袋", "1袋"),
])
def test_paired_item_accepts_equivalent_decimal_and_unit_aliases(quantity, unit, original_dose):
    from app.services.luxian_0609.transfusion_result_mapping import safe_transfusion_customer_display_facts

    item = {"component": "红细胞", "quantity": quantity, "unit": unit,
            "original_dose": original_dose, "event_time": ""}
    raw = paired_item_facts(item)
    assert safe_transfusion_customer_display_facts(rule_id=RID, raw=raw) == raw
