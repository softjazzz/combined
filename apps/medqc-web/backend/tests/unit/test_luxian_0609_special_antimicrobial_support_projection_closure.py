"""TP-D04补充：目标药关联同时控制事实、证据、文案和保存；原18oracle不改。"""
from copy import deepcopy
from datetime import datetime
import json

import pytest

from test_luxian_0609_special_antimicrobial_support_closure import CASES, RULE, _run


@pytest.fixture(autouse=True)
def offline_sqlite_only(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("TPD04禁止PG、网络及真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


def case(name):
    return deepcopy(next(c for c in CASES if c["id"] == name))


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("name,present,time", [
    ("expert_other_drug", False, None),
    ("same_drug_before", True, "2026-04-01 07:00:00"),
    ("same_drug_late", True, "2026-04-01 09:00:00"),
    ("same_drug_missing_time", True, None),
])
async def test_unrelated_earlier_support_does_not_supply_target_fact_time_or_evidence(name, present, time, reverse):
    source = case(name)
    source["rows"]["consultation_record"].append({
        "document_id": "SYN-OTHER-EARLY", "record_time": "2026-04-01 06:00:00",
        "record_content": "专家会诊，建议万古霉素抗感染。",
    })
    rows = {key: tuple(reversed(value)) if reverse else tuple(value) for key, value in source["rows"].items()}
    _, _, result = await _run(rows)
    assert result["status"] == source["oracle"]["status"]
    assert result["reason_code"] == source["oracle"]["reason_code"]
    facts = result["customer_display_facts"]
    assert facts["expert_support_present"] is present
    assert facts["expert_support_time"] == time
    assert "06:00:00" not in result["findings"]
    assert "SYN-OTHER-EARLY" not in {e["source_document_id"] for e in result["customer_evidence"]}
    if name == "expert_other_drug":
        assert "可关联" in result["findings"]
        assert "07:00:00" not in result["findings"]
        assert "晚于该时间" not in result["findings"]
        assert {e["source_document_id"] for e in result["customer_evidence"]} == {"synthetic-order"}


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_multiple_named_success_copy_does_not_compare_each_drug_with_global_earliest_times(reverse):
    source = case("multiple_named_each_supported")
    rows = {key: tuple(reversed(value)) if reverse else tuple(value) for key, value in source["rows"].items()}
    _, _, result = await _run(rows)
    assert result["status"] == "compliant"
    assert "逐项" in result["findings"]
    assert "美罗培南" in result["findings"] and "万古霉素" in result["findings"]
    assert "该时间前或同刻找到" not in result["findings"]
    assert {e["source_document_id"] for e in result["customer_evidence"]} == {
        "synthetic-order", "synthetic-order-V", "synthetic-note-M", "synthetic-note-V",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_named_existing_ordinary_antimicrobial_is_not_anonymous_target_support(reverse):
    source = case("expert_other_drug")
    source["rows"]["consultation_record"][0]["record_content"] = "专家会诊，建议头孢曲松抗感染。"
    rows = {key: tuple(reversed(value)) if reverse else tuple(value) for key, value in source["rows"].items()}
    _, _, result = await _run(rows)
    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "required_document_missing"
    assert result["customer_display_facts"]["expert_support_present"] is False
    assert result["customer_display_facts"]["expert_support_time"] is None
    assert {e["source_document_id"] for e in result["customer_evidence"]} == {"synthetic-order"}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["expert_other_drug", "same_drug_late", "multiple_named_each_supported"])
async def test_synthetic_sqlite_new_instance_retains_only_target_related_support_properties(name, tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result, keyed_ref

    source = case(name)
    _, _, result = await _run(source["rows"])
    assert result["status"] == source["oracle"]["status"]
    item = {**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "tpd04.sqlite").as_posix()
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
            saved = CanonicalResultStore(table).load_selected(
                read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )["items"][0]
            for key in ("status", "reason_code", "customer_display_facts", "findings", "suggestion"):
                assert saved.get(key) == item.get(key)
            projected = workspace.project_customer_safe_result_item(saved, hmac_key="test-key")
            expected_refs = {
                (src, keyed_ref("src", row["document_id"], hmac_key="test-key"))
                for src in ("inpat_drug_order", "consultation_record") for row in source["rows"][src]
                if row["document_id"] in source["oracle"]["evidence_document_ids"]
            }
            assert {(e["source_type"], e["source_ref"]) for e in projected["evidence"]} == expected_refs
            assert all("source_document_id" not in e and "document_id" not in e for e in projected["evidence"])
            if name == "expert_other_drug":
                assert projected["customer_display_facts"]["expert_support_present"] is False
                assert projected["customer_display_facts"]["expert_support_time"] is None
                assert all(e["source_type"] != "consultation_record" for e in projected["evidence"])
            else:
                for row in source["rows"]["consultation_record"]:
                    evidence = next(e for e in projected["evidence"] if e["source_ref"] == keyed_ref(
                        "src", row["document_id"], hmac_key="test-key"))
                    assert evidence["source_type"] == "consultation_record"
                    assert evidence["record_time"] == row["record_time"]
                    assert evidence["field_path"] == "record_content"
                    assert evidence["evidence_excerpt"] == row["record_content"]
    finally:
        engine.dispose()
