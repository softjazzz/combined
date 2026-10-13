"""Structured discussion source -> real executor/Finalizer -> SQLite -> API."""
import asyncio
import json
from copy import deepcopy

import pytest
from tests.integration import test_luxian_0609_all_rules_three_entry_acceptance as H
from tests.integration.test_luxian_0609_all_rules_three_entry_acceptance import _isolated_database  # noqa: F401
from tests.unit.test_luxian_0609_native_preop_content_execution import _session, _Client, _payload
from app.services.luxian_0609.native_preop_content_execution import evaluate_preop_content_rules, RULE_FIELDS
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.document_assembly.assembler import assemble_document

RULE = "LX0609-04-01-05"


def generate_final(mode):
    row = {"document_id": "synthetic-discussion", "record_content": "",
           "document_title": "术前讨论", "host_summary": "手术准备完成，已充分讨论手术方案与风险。",
           "discuss_staff": "医师甲", "record_time": "2026-01-01 08:00:00"}
    items = {field: {"state": "present", "quote": row["host_summary"], "reviewed_all_sections": True}
             for field in RULE_FIELDS[RULE]}
    if mode == "non_compliant":
        items["specific_opinions"] = {"state": "missing", "quote": None, "reviewed_all_sections": True}
    if mode == "data_gap":
        items["preop_preparation"]["quote"] = "不存在的拼接...引文"
    session = _session(discussion=(row,))
    client = _Client(_payload({"document_id": row["document_id"], "source_type": "presurg_discussion", "items": items}))
    result = asyncio.run(evaluate_preop_content_rules(rule_ids=(RULE,), snapshot=session.snapshot,
                                                     materials=session.materials, llm_client=client))
    decisions = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=(RULE,),
                                                         snapshot=session.snapshot, evidence_materials=session.materials)
    final = finalize_luxian_0609_reduced_customer_result(decision=decisions[0],
                raw_customer_display_facts=dict(result.customer_display_facts)[RULE],
                evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final["status"] == mode
    assert final["customer_evidence"][0]["field_path"] == "host_summary"
    assert final["customer_evidence"][0]["evidence_excerpt"] == row["host_summary"]
    assert "不存在的拼接" not in json.dumps(final, ensure_ascii=False)
    return final, row


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["compliant", "non_compliant", "data_gap"])
def test_real_finalizer_evidence_survives_three_entry_store_and_api(monkeypatch, _isolated_database, mode):  # noqa: F811
    final, source_row = generate_final(mode)
    engine, workspace = _isolated_database
    pool_service = H._install_sample_pool_sqlite(monkeypatch, engine)
    H._install_evidence_fixture(monkeypatch, consultation_row=False)
    service = H.sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "stable-semantic",
                    "allow_mock_when_unconfigured": True, "source": "discussion-evidence-regression"})
    H._wire_production_entry(monkeypatch, workspace, pool_service, H._settings(), service)
    original = H.luxian_execution.aggregate_luxian_0609_results
    published = {}
    def inject(**kwargs):
        result = original(**kwargs)
        result[0].update(deepcopy(final))
        result[0]["conclusion"] = final["findings"]
        assert result[0]["customer_evidence"]
        published[kwargs["audit_context"]["visit_id"]] = deepcopy(result[0])
        return result
    monkeypatch.setattr(H.luxian_execution, "aggregate_luxian_0609_results", inject)
    monkeypatch.setattr(H.qc_sichuan, "_sichuan_workspace_service", H.CustomQCWorkspaceService)
    document = assemble_document("presurg_discussion", source_row).to_dict()
    monkeypatch.setattr(H.workspace_module, "load_bundle_documents", lambda **kwargs: {"documents": [document]})
    app = H._api_app(service)
    def verify(job_id, job, _ids):
        assert job["status"] == "completed", job.get("error_message")
        table = workspace._record_result_envelope_table
        with engine.connect() as connection:
            rows = connection.execute(H.sa.select(table).where(table.c.job_id == job_id)).mappings().all()
        for row in rows:
            saved = json.loads(row["envelope_json"])["items"][0]
            assert saved["status"] == final["status"]
            assert saved["customer_display_facts"] == final["customer_display_facts"]
            evidence = saved["evidence"]
            assert evidence and evidence[0]["field_path"] == "host_summary"
            assert evidence[0]["evidence_excerpt"] == final["customer_evidence"][0]["evidence_excerpt"]
            assert "source_document_id" not in evidence[0]
            current = H._read_canonical(app, job_id, dict(row), [RULE])[RULE]
            assert current["status"] == saved["status"]
            assert current["customer_display_facts"] == saved["customer_display_facts"]
            assert current["evidence"] == evidence
        with H.TestClient(app) as client:
            response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}")
        assert response.status_code == 200
        for item in response.json()["data"]["items"]:
            assert item["status"] == final["status"]
            assert item["customer_display_facts"] == final["customer_display_facts"]
            assert item["evidence"][0]["evidence_excerpt"] == final["customer_evidence"][0]["evidence_excerpt"]
            assert item["evidence"][0]["field_path"] == "host_summary"
    pool_id, sample_id = H._create_ready_sample_pool(engine, pool_service)
    jobs = H._entry_job_ids(app=app, workspace=workspace, pool_id=pool_id, sample_item_id=sample_id,
                           workspace_rule_ids=[RULE], on_terminal=verify)
    assert len(jobs) == 3
