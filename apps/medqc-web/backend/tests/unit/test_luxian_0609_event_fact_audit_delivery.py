"""事件事实只归属其规则，沿现有私有任务审计持久化。"""
from types import SimpleNamespace
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services.luxian_0609 import execution


RULES = ("LX0609-06-02-02", "LX0609-05-01-01")


def _snapshot(rule):
    return {"schema_version": "synthetic-event-facts-v1", "rule_id": rule, "complete": True,
            "source_refs": [{"material_ref": "synthetic-material-1", "source_field": "record_content"}],
            "actions": [{"quote": "合成事件证据", "start": 0, "end": 6}]}


def test_scoped_facts_do_not_leak_into_sibling_rule_and_legacy_consultation_keeps_scope():
    snapshot = _snapshot(RULES[0])
    raw = SimpleNamespace(diagnostic_semantic_snapshot=snapshot)
    assert execution._rule_scoped_semantic_snapshots(raw, RULES) == ((RULES[0], snapshot),)
    assert execution._rule_scoped_semantic_snapshots(raw, (RULES[1],)) == ()
    legacy = {"schema_version": "consultation-semantic-snapshot-v1", "episodes": []}
    refs = ("LX0609-03-01-01", "LX0609-03-01-04")
    assert execution._rule_scoped_semantic_snapshots(
        SimpleNamespace(diagnostic_semantic_snapshot=legacy), refs
    ) == tuple((rule, legacy) for rule in refs)


@pytest.mark.parametrize("rule", RULES)
def test_realtime_family_publish_carries_same_rule_scoped_audit(monkeypatch, rule):
    seen = []
    envelope = SimpleNamespace(results=[], customer_display_facts=(),
                               diagnostic_semantic_snapshot=_snapshot(rule))
    outcome = SimpleNamespace(selected_rule_ids=RULES, envelope=envelope, executor_key="synthetic")

    def aggregate(**kwargs):
        seen.append(kwargs["context"])
        return {"results": [{"rule_id": rule, "status": "compliant"}]}

    monkeypatch.setattr(execution, "aggregate_luxian_0609_orchestrated_results", aggregate)
    monkeypatch.setattr(execution, "_build_execution_usage_attribution", lambda **_: None)
    execution._published_family_results(outcome=outcome, snapshot=None, materials=None,
        wrapper_rules=[{"rule_id": item} for item in RULES], typed_rule_ids=(), delivery_mode="canonical")
    assert seen[0].diagnostic_semantic_snapshots == ((rule, envelope.diagnostic_semantic_snapshot),)


@pytest.mark.parametrize("rule", RULES)
def test_worker_private_fact_trace_survives_real_progress_json_commit_and_reload(monkeypatch, rule):
    from app.services import custom_qc_workspace_service as workspace_module
    from app.services.sichuan_workspace_batch_worker import _result_diagnostic_trace

    snapshot = _snapshot(rule)
    item = {"rule_id": rule, "status": "compliant", "findings": "合成验证结果"}
    trace = _result_diagnostic_trace(item, {"diagnostic_semantic_snapshot": snapshot})
    assert trace["semantic_fact_snapshot"] == snapshot

    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = sa.Table("synthetic_batch_jobs", metadata,
        sa.Column("id", sa.String, primary_key=True), sa.Column("status", sa.String),
        sa.Column("summary_json", sa.Text), sa.Column("filters_json", sa.Text),
        sa.Column("items_json", sa.Text), sa.Column("failed_records_json", sa.Text),
        sa.Column("updated_at", sa.DateTime),
        *(sa.Column(name, sa.Integer) for name in ("total_records", "success_count", "failed_count",
            "issue_records", "compliant_records", "total_tokens")),
        sa.Column("total_processing_time", sa.Float))
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        session.execute(table.insert().values(id="synthetic-job", status="running", summary_json="{}", filters_json="{}"))
    monkeypatch.setattr(workspace_module, "_session", factory)
    workspace = object.__new__(workspace_module.CustomQCWorkspaceService)
    workspace._batch_job_table = table
    workspace.update_batch_job_progress(job_id="synthetic-job", step_key="run", rule_index=1,
        rule_count=1, processed_records=1, total_records=1,
        items=[{**item, "diagnostic_trace": trace}])
    with factory() as session:
        stored = json.loads(session.execute(sa.select(table.c.items_json)).scalar_one())
    assert stored[0]["diagnostic_trace"]["semantic_fact_snapshot"] == snapshot
    engine.dispose()


def test_sampling_mixed_fact_text_does_not_call_successful_or_unknown_events_missing():
    from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts

    facts = {"failure_kind": "pathology_sampling_not_documented",
             "pathology_trigger_sources": ["pathology_exam_report"],
             "checked_target_sources": [{"source": "surgery_record"}],
             "confirmed_event_count": 1, "absent_event_count": 1, "unknown_event_count": 1}
    text = customer_finding_from_controlled_facts(rule_id=RULES[0], facts=facts)
    assert "其中1次未找到" in text and "1次已核实有对应记录" in text
    assert "1次归属待核，未计入缺失" in text and "均未找到" not in text
    for key in ("confirmed_event_count", "absent_event_count", "unknown_event_count"):
        facts.pop(key)
    assert "均未找到取材情况记录" in customer_finding_from_controlled_facts(rule_id=RULES[0], facts=facts)


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
async def test_event_fact_rules_build_material_session_even_on_legacy_dispatch(monkeypatch, rule):
    from test_luxian_0609_execution_failure_semantics import _all_native_settings

    class MaterialSessionRequested(BaseException):
        pass

    def request_session(**kwargs):
        assert kwargs["selected_rule_ids"] == (rule,)
        assert kwargs["additional_source_keys"]
        raise MaterialSessionRequested()

    async def executor_without_session(**kwargs):
        raise AssertionError("new event contract reached executor without immutable materials")

    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", request_session)
    monkeypatch.setattr(execution, "execute_luxian_0609_native_tumor_pathology_rules", executor_without_session)
    monkeypatch.setattr(execution, "execute_luxian_0609_native_surgery_gate_rules", executor_without_session)
    with pytest.raises(MaterialSessionRequested):
        await execution.prepare_luxian_0609_execution(rule_set_key="luxian_0609_qc_v1", prepared_rules=[],
            visit_id="V", patient_id="P", institute_id="I", medical_text="", evidence_payload=None,
            llm_client=None, selected_customer_rule_ids=(rule,),
            settings=_all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
                LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=False))
