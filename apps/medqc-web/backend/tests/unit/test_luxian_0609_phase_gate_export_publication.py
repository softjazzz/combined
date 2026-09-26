"""原始 LX0609 暂停规则的公开结果与导出应消费同一发布文案。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
from app.services.luxian_0609.phase_scope import (
    build_luxian_0609_pending_definition_result,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
    safe_customer_display_facts,
)


@pytest.mark.parametrize(
    "rule_id", ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"),
)
def test_phase_gate_published_text_is_preserved_in_canonical_export(rule_id):
    wrapper = get_luxian_0609_rule(rule_id)
    assert wrapper is not None
    published = aggregate_luxian_0609_results(
        wrapper_rules=[wrapper],
        execution_results=[],
        canonical_results=(build_luxian_0609_pending_definition_result(rule_id),),
        delivery_mode=CANONICAL_RESULT_DELIVERY_MODE,
    )[0]
    stored = envelope_item_from_rule_result(published, hmac_key="synthetic-ref-key")
    customer = workspace_module.project_customer_safe_result_item(
        stored, hmac_key="synthetic-ref-key",
    )
    export_items, export_rows, _ = workspace_module._canonical_customer_export_rows(
        {"id": "synthetic-job"},
        hmac_key="synthetic-ref-key",
        canonical_items=[stored],
    )

    assert customer["status"] == export_items[0]["status"] == "not_executed"
    assert customer["reason_code"] == export_items[0]["reason_code"]
    assert customer["conclusion"] == export_items[0]["conclusion"] == export_rows[0][5]
    assert customer["suggestion"] == export_items[0]["suggestion"] == export_rows[0][6]


def test_phase_gate_result_survives_canonical_sqlite_write_and_read():
    rule_id = "LX0609-03-01-01"
    wrapper = get_luxian_0609_rule(rule_id)
    assert wrapper is not None
    published = aggregate_luxian_0609_results(
        wrapper_rules=[wrapper], execution_results=[],
        canonical_results=(build_luxian_0609_pending_definition_result(rule_id),),
        delivery_mode=CANONICAL_RESULT_DELIVERY_MODE,
    )[0]
    table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None,
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as session:
        store.replace_for_job(
            session,
            job_row={
                "id": "synthetic-job", "created_by": "synthetic-tester",
                "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                    "scoped_customer_rule_ids": [rule_id],
                    "record_refs": [{
                        "institute_id": "synthetic-inst",
                        "patient_id": "synthetic-patient",
                        "visit_id": "synthetic-visit",
                    }],
                }),
            },
            items=[{
                **published, "record_id": "synthetic-visit",
                "institute_id": "synthetic-inst", "patient_id": "synthetic-patient",
                "visit_id": "synthetic-visit",
            }],
            now=datetime(2026, 9, 25, 10, 0, 0),
            projector=lambda raw: envelope_item_from_rule_result(
                raw, hmac_key="synthetic-ref-key",
            ),
            projection_key="synthetic-ref-key",
        )
        session.commit()
        loaded = store.load_selected(
            session, root_job_id="synthetic-job",
            institute_id="synthetic-inst", patient_id="synthetic-patient",
            visit_id="synthetic-visit", rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
        )
    engine.dispose()

    assert len(loaded["items"]) == 1
    saved = loaded["items"][0]
    customer = workspace_module.project_customer_safe_result_item(
        saved, hmac_key="synthetic-ref-key",
    )
    export_items, _, _ = workspace_module._canonical_customer_export_rows(
        {"id": "synthetic-job"},
        hmac_key="synthetic-ref-key", canonical_items=[saved],
    )
    assert saved["status"] == customer["status"] == export_items[0]["status"]
    assert saved["reason_code"] == customer["reason_code"] == export_items[0]["reason_code"]
    assert saved["conclusion"] == customer["conclusion"] == export_items[0]["conclusion"]
    assert saved["suggestion"] == customer["suggestion"] == export_items[0]["suggestion"]


def test_phase_gate_public_read_rejects_changed_status_reason_or_rule():
    # 状态、原因码、规则身份由业务合同校验；文案不再做防篡改签章。
    published = build_luxian_0609_pending_definition_result("LX0609-03-01-01")
    for changed in (
        {**published, "status": "compliant", "result_status": "compliant"},
        {**published, "reason_code": "trigger_absent_complete"},
        {**published, "rule_id": "LX0609-03-01-04", "rule_code": "LX0609-03-01-04"},
    ):
        with pytest.raises(ValueError):
            stored = envelope_item_from_rule_result(changed, hmac_key="synthetic-ref-key")
            workspace_module.project_customer_safe_result_item(
                stored, hmac_key="synthetic-ref-key",
            )
    assert safe_customer_display_facts(
        deepcopy(published), rule_id="LX0609-03-01-01",
    ) == {}
