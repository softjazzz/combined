"""RR-PUB01：未知规则 sentinel 与已拥有合同的公开/保存边界。"""

from copy import deepcopy
from datetime import datetime
import json

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts as validate,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
    safe_customer_display_facts,
    validated_customer_explanation,
)

UNKNOWN = "LX0609-99-99-99"
PRIVATE_RAW = {"verification_kind": "unowned_contract", "private_payload": "synthetic-secret"}
KNOWN = [
    ("LX0609-01-01-01", "compliant", {
        "failure_kind": "timeliness_requirement_satisfied", "target_document": "admission_record",
        "timeliness_state": "within", "threshold_hours": 24, "source_label": "入院记录",
    }),
    ("LX0609-05-01-02", "non_compliant", {
        "verification_kind": "antimicrobial_reason_documentation_check", "antimicrobials": ["合成药品甲"],
        "reason_documented": False, "unmatched_antimicrobials": ["合成药品甲"], "association_ambiguous": False,
    }),
    ("LX0609-08-01-03", "data_gap", {
        "verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": "scope_conflict", "written_gap": None,
    }),
]


@pytest.fixture(autouse=True)
def offline_sqlite_only(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("RR-PUB01仅合成SQLite，禁止PG、网络和真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


@pytest.mark.parametrize("rule_id", [UNKNOWN, " lx0609-99-99-99 "])
@pytest.mark.parametrize("raw", [{}, PRIVATE_RAW])
def test_unknown_dictionary_returns_identity_sentinel_without_mutation(rule_id, raw):
    frozen = deepcopy(raw)
    assert validate(rule_id=rule_id, raw=raw) is NotImplemented
    assert raw == frozen


@pytest.mark.parametrize("raw", [None, [], "synthetic", 1])
def test_unknown_absent_or_non_dictionary_preserves_none(raw):
    assert validate(rule_id=UNKNOWN, raw=raw) is None


@pytest.mark.parametrize("raw", [{}, PRIVATE_RAW])
def test_store_unknown_dictionary_is_empty_and_cannot_leak_raw(raw):
    item = {"rule_id": UNKNOWN, "status": "compliant", "customer_display_facts": deepcopy(raw)}
    assert safe_customer_display_facts(item, rule_id=UNKNOWN) == {}
    assert item["customer_display_facts"] == raw
    assert validated_customer_explanation(item, rule_id=UNKNOWN, status="compliant") == ({}, [])


@pytest.mark.parametrize("raw", [{}, PRIVATE_RAW])
def test_store_unknown_non_compliant_without_auditable_explanation_is_rejected(raw):
    with pytest.raises(ValueError, match="解释合同不完整"):
        validated_customer_explanation(
            {"rule_id": UNKNOWN, "status": "non_compliant", "customer_display_facts": deepcopy(raw)},
            rule_id=UNKNOWN, status="non_compliant",
        )


def test_unknown_does_not_hide_inconsistent_rule_identity():
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"rule_id": UNKNOWN, "customer_rule_id": "LX0609-01-01-01", "customer_display_facts": {}},
            rule_id=UNKNOWN,
        )


@pytest.mark.parametrize("rule_id,status,raw", KNOWN)
def test_known_valid_published_facts_preserve_exact_dictionary(rule_id, status, raw):
    assert validate(rule_id=rule_id, raw=deepcopy(raw), status=status) == raw
    assert safe_customer_display_facts(
        {"rule_id": rule_id, "status": status, "customer_display_facts": deepcopy(raw)}, rule_id=rule_id,
    ) == raw


@pytest.mark.parametrize("rule_id,status,raw", KNOWN)
def test_known_invalid_facts_still_raise_value_error(rule_id, status, raw):
    invalid = {**deepcopy(raw), "private_payload": "synthetic-secret"}
    if rule_id == "LX0609-05-01-02":
        invalid["reason_documented"] = "invalid"
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate(rule_id=rule_id, raw=invalid, status=status)


@pytest.mark.parametrize("rule_id,status,raw", KNOWN)
def test_known_contradictory_status_still_raises_value_error(rule_id, status, raw):
    invalid_status = "non_compliant" if status == "compliant" else "compliant"
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate(rule_id=rule_id, raw=deepcopy(raw), status=invalid_status)


@pytest.mark.parametrize("raw", [None, {}])
def test_pending_definition_preserves_existing_absent_facts_policy(raw):
    assert validate(rule_id="LX0609-03-01-01", raw=raw, status="not_executed",
                    reason_code="policy_definition_pending") is None


@pytest.mark.parametrize("rule_id,status,raw", [("HISTORIC-LX-UNKNOWN", "compliant", PRIVATE_RAW), (UNKNOWN, "compliant", PRIVATE_RAW), *KNOWN])
def test_isolated_sqlite_new_instance_read_never_reintroduces_unknown_raw(rule_id, status, raw, tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace

    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "rr-pub01.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    item_rule = KNOWN[0][0] if rule_id == "HISTORIC-LX-UNKNOWN" else rule_id
    item_raw = KNOWN[0][2] if rule_id == "HISTORIC-LX-UNKNOWN" else raw
    item = {"rule_id": item_rule, "status": status, "reason_code": "synthetic_contract_probe",
            "result_status": status, "display_status": status,
            "is_compliant": True if status == "compliant" else False if status == "non_compliant" else None,
            "findings": "合成公开边界探针", "suggestion": "", "customer_display_facts": deepcopy(item_raw),
            "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    try:
        if rule_id == UNKNOWN:
            with Session(engine) as write_db, pytest.raises(ValueError, match="状态字段不一致"):
                CanonicalResultStore(table).replace_for_job(
                    write_db, job_row={"id": "J"}, items=[item], now=datetime(2026, 10, 8, 12),
                    projector=lambda source: envelope_item_from_rule_result(source, hmac_key="test-key"),
                    projection_key="test-key",
                )
            return
        with Session(engine) as write_db:
            CanonicalResultStore(table).replace_for_job(
                write_db, job_row={"id": "J", "created_by": "synthetic-reviewer",
                    "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 10, 8, 12),
                projector=lambda source: envelope_item_from_rule_result(source, hmac_key="test-key"), projection_key="test-key",
            )
            write_db.commit()
            if rule_id == "HISTORIC-LX-UNKNOWN":
                # 仅SQLite合成历史行；正式保存仍拒绝未登记LX身份。
                stored_json = write_db.execute(table.select()).mappings().one()["envelope_json"]
                historical = json.loads(stored_json)
                historical["items"][0]["rule_id"] = UNKNOWN
                historical["items"][0]["customer_display_facts"] = deepcopy(raw)
                historical["items"][0]["decision_facts"] = deepcopy(raw)
                write_db.execute(table.update().values(envelope_json=json.dumps(historical, ensure_ascii=False)))
                write_db.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as read_db:
            loaded = CanonicalResultStore(table).load_selected(
                read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )
            saved = loaded["items"][0]
            expected = {} if rule_id == "HISTORIC-LX-UNKNOWN" else raw
            if rule_id == "HISTORIC-LX-UNKNOWN":
                assert safe_customer_display_facts(saved, rule_id=UNKNOWN) == {}
            else:
                assert saved["customer_display_facts"] == expected
            assert saved["status"] == status
            api = workspace.project_customer_safe_result_item(saved, hmac_key="test-key")
            assert api.get("customer_display_facts", {}) == expected
            assert "synthetic-secret" not in json.dumps(api, ensure_ascii=False)
            assert "private_payload" not in json.dumps(api, ensure_ascii=False)
    finally:
        engine.dispose()
