"""065/067合成终态经正式Envelope保存后新SQLite实例回读。"""
from datetime import datetime
import json

import pytest

from luxian_0609_course_body_test_facts import FrozenCourseBodyClient
from test_n10_course_body_controlled_facts import RULES, _run


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("scenario", ("present", "absent", "unknown", "capacity"))
async def test_course_body_synthetic_new_sqlite_instance_preserves_public_contract(rule, scenario, tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    body = {"present": "病情稳定。", "absent": "主任医师查房记录", "unknown": "合成待核正文", "capacity": "病情稳定。"}[scenario]
    facts = {} if scenario == "capacity" else {body: (scenario, "病情稳定" if scenario == "present" else None)}
    client = FrozenCourseBodyClient(facts)
    rows = tuple({"document_id": f"synthetic-course-{index}", "record_time": "2026-07-02 09:00:00", "record_content": body} for index in range(9 if scenario == "capacity" else 1))
    final, execution = await _run(rule, rows, client)
    expected = {"present": ("compliant", "requirement_satisfied"), "absent": ("data_gap", "required_field_missing"), "unknown": ("data_gap", "semantic_extraction_unresolved"), "capacity": ("data_gap", "candidate_scope_incomplete")}
    assert (final["status"], final["reason_code"]) == expected[scenario]
    assert execution.llm_call_count == len(client.calls) == (0 if scenario == "capacity" else 1)
    assert client.fixture_error is None
    item = {**final, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    projection = envelope_item_from_rule_result(item, hmac_key="synthetic-r2-key")
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "course-body.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    try:
        with Session(engine) as writing:
            CanonicalResultStore(table).replace_for_job(writing,
                job_row={"id": "J", "created_by": "synthetic-r2-reviewer", "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 10, 8, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="synthetic-r2-key"), projection_key="synthetic-r2-key")
            writing.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as reading:
            saved = CanonicalResultStore(table).load_selected(reading, root_job_id="J", institute_id="I", patient_id="P", visit_id="V", rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
        for field in ("status", "result_status", "is_compliant", "reason_code", "findings", "suggestion", "customer_display_facts", "missing_fields", "missing_sources", "evidence"):
            assert saved.get(field) == projection.get(field), field
        assert all("source_document_id" not in evidence and "document_id" not in evidence for evidence in saved.get("evidence", ()))
        assert all(evidence["source_ref"].startswith("src_") for evidence in saved.get("evidence", ()))
        if scenario in {"unknown", "capacity"}:
            assert saved["missing_fields"] == saved["missing_sources"] == []
            assert "补写" not in saved["suggestion"] or "不要" in saved["suggestion"]
    finally:
        engine.dispose()
