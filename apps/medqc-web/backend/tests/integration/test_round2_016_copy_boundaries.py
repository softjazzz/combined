"""016 正式执行及隔离 SQLite 保存边界；全部为合成文书。"""
from datetime import datetime
import json

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_course_quality_execution import execute_luxian_0609_native_course_quality_rules
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result, safe_customer_display_facts
from tests.integration.test_luxian_0609_real_production_rules_076_077 import _session

RULE = 'LX0609-12-01-01'
BASE = '患者腹痛伴发热，发病日期为2025-07-01，血钾为3.5mmol/L，腹膜刺激征（-）。'

async def _execute(right):
    rows = {'admission_record': [{'document_id': 'A', 'history_of_present_illness': BASE}],
            'first_course_record': [{'document_id': 'F', 'case_characteristic': right}]}
    session = _session(RULE, rows)
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), wrapper_rules=[get_luxian_0609_rule(RULE)],
        evidence_payload=None, llm_client=None, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot,
        evidence_materials=session.materials)
    item = aggregate_luxian_0609_results(
        wrapper_rules=[get_luxian_0609_rule(RULE)], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={'evidence_snapshot': session.snapshot, 'evidence_materials': session.materials})[0]
    assert execution.llm_call_count == 0
    return item


def _roundtrip(item):
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine('sqlite://')
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db, job_row={'id': 'J', 'created_by': 'reviewer', 'filters_json': json.dumps({
                    'rule_set_key': 'luxian_0609_qc_v1', 'rule_set_version': '2026-06-09'})},
                items=[{**item, 'record_id': 'V', 'visit_id': 'V', 'institute_id': 'I', 'patient_id': 'P'}],
                now=datetime(2026, 10, 7), projection_key='synthetic-test-key',
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key='synthetic-test-key'))
            db.commit()
        with Session(engine) as db:
            loaded = store.load_selected(db, root_job_id='J', institute_id='I', patient_id='P',
                                         visit_id='V', rule_set_key='luxian_0609_qc_v1',
                                         rule_set_version='2026-06-09')['items'][0]
        assert (loaded['status'], loaded['reason_code']) == (item['status'], item['reason_code'])
        return loaded
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('right', [
    BASE.replace('2025-07-01', '2025-07-10'), BASE.replace('3.5', '35'),
    BASE.replace('（-）', '（+）'), BASE.replace('3.5', '3/5'),
])
async def test_clinical_difference_is_not_complete_copy(right):
    item = await _execute(right)
    assert item['status'] == 'compliant'
    _roundtrip(item)


@pytest.mark.asyncio
@pytest.mark.parametrize('right', [BASE, BASE.replace('，', '；'), '\n  ' + BASE + '\t'])
async def test_equal_and_layout_only_differences_remain_copy(right):
    item = await _execute(right)
    assert item['status'] == 'non_compliant'
    _roundtrip(item)


@pytest.mark.asyncio
@pytest.mark.parametrize('right', ['', ' \n\t', None])
async def test_blank_section_data_gap_survives_real_sqlite_store(right):
    item = await _execute(right)
    assert (item['status'], item['reason_code']) == ('data_gap', 'required_field_missing')
    loaded = _roundtrip(item)
    assert not loaded.get('customer_display_facts')
    assert loaded['missing_fields'] == item['missing_fields']


@pytest.mark.parametrize('status,reason,facts', [
    ('compliant', 'required_field_missing', None),
    ('non_compliant', 'requirement_violated', None),
    ('data_gap', 'invented_reason', None),
    ('data_gap', 'required_field_missing', {'copy_similarity': 1.0}),
])
def test_missing_fact_exception_does_not_accept_corrupted_result(status, reason, facts):
    with pytest.raises(ValueError, match='解释合同不完整'):
        safe_customer_display_facts({'status': status, 'reason_code': reason,
                                     'customer_display_facts': facts}, rule_id=RULE)
