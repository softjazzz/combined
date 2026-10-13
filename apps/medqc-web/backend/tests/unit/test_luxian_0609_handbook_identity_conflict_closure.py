"""IML-01：同键身份冲突须通过正式执行、归约和发布保持资料缺口。"""

import pytest

from test_luxian_0609_handbook_exam_lab import _session as _report_session
from test_luxian_0609_ct_order_course_consistency import _session as _ct_session, _Client
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.handbook_exam_lab import (
    ORDER_SOURCE, build_handbook_ledger, evaluate_report_completeness,
)

CT_REPORT = "LX0609-06-01-03"
CT_COURSE = "LX0609-06-01-01"
CULTURE_REPORT = "LX0609-06-03-02"


def _rows(culture=False):
    if culture:
        return {
            "labtest_master": [{"test_id": "E1", "labtest_subject": "血培养",
                "specimen_collection_datetime": "2026-09-01 09:00:00"}],
            "labtest_item_report": [{"test_id": "E1", "labtest_subject": "血培养",
                "report_time": "2026-09-01 10:00:00", "result": "大肠埃希菌"}],
        }
    return {
        ORDER_SOURCE: [{"order_id": "O1", "order_name": "胸部CT", "order_status": "新开"}],
        "exam_master": [{"exam_id": "E1", "order_id": "O1", "exam_name": "胸部CT",
            "exam_time": "2026-09-01 09:00:00"}],
        "exam_item_report": [{"exam_id": "E1", "exam_name": "胸部CT",
            "report_time": "2026-09-01 10:00:00", "description": "双肺纹理增多。"}],
        "daily_course_record": [{"document_id": "D1", "record_content": "本次胸部CT已完成，示双肺纹理增多。"}],
    }


def _conflict(case):
    rows = _rows(case == "culture-master-routine-report")
    if case == "ct-master-dr-report":
        rows["exam_item_report"][0]["exam_name"] = "胸部DR"
    elif case == "dr-master-ct-report":
        rows["exam_master"][0]["exam_name"] = "胸部DR"
    elif case == "ct-master-ultrasound-dept":
        rows["exam_item_report"][0].pop("exam_name")
        rows["exam_item_report"][0]["performed_dept"] = "超声科"
    elif case == "culture-master-routine-report":
        rows["labtest_item_report"][0]["labtest_subject"] = "血常规"
    return rows


async def _execute(rows, culture=False, expected_status="data_gap"):
    snapshot, materials = (_report_session(rows=rows) if culture else _ct_session(rows))
    rule_ids = (CULTURE_REPORT,) if culture else (CT_COURSE, CT_REPORT)
    client = _Client()
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rule_ids, decision_rule_ids=rule_ids, wrapper_rules=(), evidence_payload=None,
        llm_client=client, evidence_snapshot=snapshot, evidence_materials=materials,
    )
    facts = dict(result.customer_display_facts)
    published = {}
    for decision in result.decisions:
        reduced = reduce_luxian_0609_rule_decision(decision)
        assert reduced.final_state.value == expected_status
        item = finalize_luxian_0609_reduced_customer_result(
            decision=reduced, raw_customer_display_facts=facts[decision.rule_id],
            evidence_snapshot=snapshot, evidence_materials=materials,
        )
        assert item["status"] == reduced.final_state.value
        assert item["customer_display_facts"] == facts[decision.rule_id]
        published[decision.rule_id] = item
    return result, client, published, snapshot, materials


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "ct-master-dr-report", "dr-master-ct-report", "ct-master-ultrasound-dept",
    "culture-master-routine-report",
])
async def test_frozen_iml01_conflicts_keep_event_refs_and_stop_semantic_call(case):
    # 继承 expected.json 先冻结的四个确认反例，不纳入取消状态争议。
    culture = case == "culture-master-routine-report"
    result, client, published, snapshot, materials = await _execute(_conflict(case), culture)
    report_rule = CULTURE_REPORT if culture else CT_REPORT
    ledger = build_handbook_ledger(rule_ids=(report_rule,), snapshot=snapshot, materials=materials)
    event = ledger.events["culture" if culture else "exam"][0]
    assert evaluate_report_completeness(report_rule, ledger).status == "data_gap"
    assert event.refs and len(event.rows) == len(event.reports) == 1
    assert not event.association_resolved
    for decision in result.decisions:
        assert decision.reason_code == ("required_field_missing" if decision.rule_id == CT_COURSE else "association_failed")
        assert set(event.refs) <= set(decision.fact_refs)
        item = published[decision.rule_id]
        assert item["status"] == "data_gap"
        assert item["customer_display_facts"]["event_results"][0]["issue_kind"] == "association_unresolved"
        assert item["evidence"]
        assert "继续保持" not in str(item)
    assert client.calls == result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("exam_type", "DR"), ("modality", "DR"), ("exam_item_name", "胸部超声"),
])
async def test_structured_non_target_identity_cannot_borrow_target_name(field, value):
    rows = _rows()
    rows["exam_item_report"][0][field] = value
    result, client, published, _, _ = await _execute(rows)
    assert all(item["status"] == "data_gap" for item in published.values())
    assert client.calls == result.llm_call_count == 0


@pytest.mark.parametrize("culture,named,body", [
    (False, True, "未见异常，建议必要时超声复查。"),
    (False, False, "建议胸部DR、超声复查。"),
    (True, True, "未见细菌生长，建议复查血常规。"),
    (True, False, "大肠埃希菌；建议结合血常规。"),
])
def test_report_recommendation_body_is_not_event_identity(culture, named, body):
    rows = _rows(culture)
    report_key = "labtest_item_report" if culture else "exam_item_report"
    report = rows[report_key][0]
    if not named:
        report.pop("labtest_subject" if culture else "exam_name")
    report["result" if culture else "description"] = body
    snapshot, materials = _report_session(rows=rows)
    rule = CULTURE_REPORT if culture else CT_REPORT
    ledger = build_handbook_ledger(rule_ids=(rule,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(rule, ledger).status == "compliant"


@pytest.mark.parametrize("name", ["胸部CT", "头颅MRI", "磁共振", "计算机断层"])
def test_legal_target_and_unnamed_detail_remain_compliant(name):
    rows = _rows()
    rows[ORDER_SOURCE][0]["order_name"] = name
    rows["exam_master"][0]["exam_name"] = name
    rows["exam_item_report"][0].pop("exam_name")
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CT_REPORT,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(CT_REPORT, ledger).status == "compliant"


def test_culture_organism_and_sensitivity_details_are_one_legal_event():
    rows = _rows(True)
    rows["labtest_item_report"] = [
        {"test_id": "E1", "item_name": "大肠埃希菌", "result": "检出",
            "report_time": "2026-09-01 10:00:00"},
        {"test_id": "E1", "lab_item_name": "头孢曲松药敏", "result": "敏感",
            "report_time": "2026-09-01 10:00:00"},
    ]
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CULTURE_REPORT,), snapshot=snapshot, materials=materials)
    evaluation = evaluate_report_completeness(CULTURE_REPORT, ledger)
    assert evaluation.status == "compliant"
    assert evaluation.display_facts["event_count"] == 1
    assert len(ledger.events["culture"][0].reports) == 2


def test_one_valid_report_cannot_hide_conflicting_sibling_detail():
    rows = _rows()
    rows["exam_item_report"].append({**rows["exam_item_report"][0], "exam_name": "胸部DR"})
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CT_REPORT,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(CT_REPORT, ledger).status == "data_gap"
    assert len(ledger.events["exam"][0].reports) == 2


def test_non_target_report_with_ct_recommendation_remains_not_applicable():
    rows = {"exam_master": [{"exam_id": "E1", "exam_name": "胸部DR"}],
        "exam_item_report": [{"exam_id": "E1", "exam_name": "胸部DR",
            "description": "建议CT复查", "report_time": "2026-09-01 10:00:00"}]}
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CT_REPORT,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(CT_REPORT, ledger).status == "not_applicable"


@pytest.mark.asyncio
@pytest.mark.parametrize("culture", [False, True])
async def test_normal_target_through_native_and_finalizer_keeps_usage(culture):
    result, client, published, _, _ = await _execute(_rows(culture), culture, "compliant")
    assert all(item["status"] == "compliant" for item in published.values())
    assert client.calls == result.llm_call_count == (0 if culture else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["ct-master-dr-report", "culture-master-routine-report"])
async def test_identity_gap_survives_isolated_sqlite_publication(case):
    import json
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore, envelope_item_from_rule_result,
    )
    from app.services.custom_qc_workspace_service import project_customer_safe_result_item

    culture = case == "culture-master-routine-report"
    _, _, published, _, _ = await _execute(_conflict(case), culture)
    rule = CULTURE_REPORT if culture else CT_REPORT
    item = published[rule]
    item.update(record_id="visit", visit_id="visit", institute_id="test", patient_id="patient")
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as session:
        store.replace_for_job(session, job_row={"id": "identity-job", "created_by": "tester",
            "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09"})}, items=[item], now=datetime(2026, 10, 8),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
            projection_key="test-key")
        session.commit()
        loaded = store.load_selected(session, root_job_id="identity-job", institute_id="test",
            patient_id="patient", visit_id="visit", rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09")
    engine.dispose()
    safe = project_customer_safe_result_item(loaded["items"][0], hmac_key="test-key")
    assert safe["status"] == "data_gap"
    assert safe["reason_code"] == item["reason_code"] == "association_failed"
    assert safe["customer_display_facts"] == item["customer_display_facts"]
    assert safe["evidence"]
    assert "继续保持" not in str(safe)


@pytest.mark.parametrize("name", ["CT引导下操作", "CT", "胸部MRI"])
def test_existing_legal_imaging_identity_is_not_denied_by_operation_body(name):
    # CT引导下操作仅继承 imaging_report_scope 的既有精确身份合同。
    rows = _rows()
    rows[ORDER_SOURCE][0]["order_name"] = name
    rows["exam_master"][0]["exam_name"] = name
    rows["exam_item_report"][0].update(exam_name=name, description="CT引导下操作。")
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CT_REPORT,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(CT_REPORT, ledger).status == "compliant"


@pytest.mark.parametrize("culture,field,value", [
    (False, "exam_item_name", "未命名项目"), (False, "modality", "未知"),
    (True, "item_name", "金黄色葡萄球菌"), (True, "lab_item_name", "万古霉素药敏"),
    (True, "lab_type", "未知"),
])
def test_unknown_detail_adds_no_identity_proof_and_cannot_clear_conflict(culture, field, value):
    rows = _rows(culture)
    report_key = "labtest_item_report" if culture else "exam_item_report"
    report = rows[report_key][0]
    report.pop("labtest_subject" if culture else "exam_name")
    report[field] = value
    rule = CULTURE_REPORT if culture else CT_REPORT
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(rule,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(rule, ledger).status == "compliant"
    # 未识别行只能继承同键已确认的目标身份，不能清除另一条明确反证。
    rows[report_key].append({**report, "labtest_subject" if culture else "exam_name":
        "血常规" if culture else "胸部DR"})
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(rule,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(rule, ledger).status == "data_gap"


@pytest.mark.parametrize("culture,name", [
    (False, "CT与超声联合检查"), (True, "血常规，建议培养"),
])
def test_ambiguous_composite_identity_remains_unresolved(culture, name):
    rows = _rows(culture)
    rows["labtest_item_report" if culture else "exam_item_report"][0][
        "labtest_subject" if culture else "exam_name"] = name
    rule = CULTURE_REPORT if culture else CT_REPORT
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(rule,), snapshot=snapshot, materials=materials)
    evaluation = evaluate_report_completeness(rule, ledger)
    assert evaluation.status == "data_gap"
    assert evaluation.display_facts["event_results"][0]["issue_kind"] == "association_unresolved"


def test_explicit_merged_ct_mri_orders_and_duplicate_import_remain_one_legal_event():
    rows = _rows()
    rows[ORDER_SOURCE].append({"order_id": "O2", "order_name": "头颅MRI", "order_status": "新开"})
    rows["exam_master"][0].update(exam_id="O1^O2", order_id="O1+O1")
    rows["exam_item_report"][0].update(exam_id="O1^O2")
    rows["exam_master"].append(dict(rows["exam_master"][0]))
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CT_REPORT,), snapshot=snapshot, materials=materials)
    evaluation = evaluate_report_completeness(CT_REPORT, ledger)
    assert evaluation.status == "compliant"
    assert evaluation.display_facts["event_count"] == 1
    assert len(ledger.events["exam"][0].orders) == 2


@pytest.mark.asyncio
async def test_standalone_order_with_ambiguous_identity_stops_before_semantic_call():
    rows = {ORDER_SOURCE: [{"order_id": "O1", "order_name": "CT与超声联合检查",
        "order_status": "已执行"}], "daily_course_record": [{"document_id": "D1",
        "record_content": "本次CT与超声联合检查已完成。"}]}
    result, client, published, _, _ = await _execute(rows)
    assert all(item["status"] == "data_gap" for item in published.values())
    assert client.calls == result.llm_call_count == 0


def test_unknown_identity_and_body_recommendation_do_not_create_target_execution():
    rows = {"exam_master": [{"exam_id": "E1", "exam_name": "未知项目"}],
        "exam_item_report": [{"exam_id": "E1", "description": "建议CT复查。",
            "report_time": "2026-09-01 10:00:00"}]}
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CT_REPORT,), snapshot=snapshot, materials=materials)
    assert not ledger.events["exam"]
    assert evaluate_report_completeness(CT_REPORT, ledger).status == "not_applicable"


@pytest.mark.asyncio
async def test_independent_us_modality_conflict_stops_formal_execution():
    # 继承独立冻结 ct-us-modality-conflict，不改 expected.json 或原复核产物。
    rows = _rows()
    rows["exam_master"][0]["modality"] = "CT"
    rows["exam_item_report"][0].pop("exam_name")
    rows["exam_item_report"][0]["modality"] = "US"
    result, client, published, _, _ = await _execute(rows)
    assert all(item["status"] == "data_gap" for item in published.values())
    assert client.calls == result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("detail_field", ["item_name", "lab_item_name"])
async def test_independent_culture_biochemical_identification_is_detail_not_event_type(detail_field):
    # 独立冻结 culture-empty-name-biochemical-identification 的合法下游角色。
    rows = _rows(True)
    rows["labtest_master"][0]["lab_type"] = "微生物培养"
    report = rows["labtest_item_report"][0]
    report.pop("labtest_subject")
    report[detail_field] = "生化鉴定"
    result, client, published, _, _ = await _execute(rows, True, "compliant")
    assert published[CULTURE_REPORT]["status"] == "compliant"
    assert client.calls == result.llm_call_count == 0


@pytest.mark.parametrize("master_modality,report_modality", [("MR", "MRI"), ("MRI", "mr"), ("CT", "ct")])
def test_structured_modality_aliases_do_not_create_identity_conflict(master_modality, report_modality):
    rows = _rows()
    name = "头颅MRI" if master_modality in {"MR", "MRI"} else "胸部CT"
    rows[ORDER_SOURCE][0]["order_name"] = name
    rows["exam_master"][0].update(exam_name=name, modality=master_modality)
    rows["exam_item_report"][0].update(exam_name=name, modality=report_modality)
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CT_REPORT,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(CT_REPORT, ledger).status == "compliant"


def test_culture_master_item_name_remains_an_existing_identity_source():
    rows = _rows(True)
    master = rows["labtest_master"][0]
    master.pop("labtest_subject")
    master["item_name"] = "血培养"
    rows["labtest_item_report"][0].pop("labtest_subject")
    rows["labtest_item_report"][0]["item_name"] = "生化鉴定"
    snapshot, materials = _report_session(rows=rows)
    ledger = build_handbook_ledger(rule_ids=(CULTURE_REPORT,), snapshot=snapshot, materials=materials)
    assert evaluate_report_completeness(CULTURE_REPORT, ledger).status == "compliant"


def _default_reader_session(monkeypatch, rows, rule, *, missing_fields=()):
    """模拟列目录/SELECT结果，实际调用默认reader与正式snapshot构建器。"""
    import re
    from app.services.luxian_0609 import source_evidence_reader as source_reader
    from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session

    table_rows = {"inpat_nondrug_order" if key == ORDER_SOURCE else key: value
        for key, value in rows.items()}
    sql_queries = []

    def columns(_schema, table):
        available = {"institute_id", "patient_id", "visit_id"}
        if table == "inpat_nondrug_order":
            available |= {"order_id", "order_name", "order_status"}
        for row in table_rows.get(table, ()):
            available.update(row)
        return available - {field for missing_table, field in missing_fields if missing_table == table}

    class FakeRows:
        def __init__(self, selected_rows):
            self.selected_rows = selected_rows

        def mappings(self):
            return self

        def all(self):
            return self.selected_rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            sql = str(statement)
            sql_queries.append(sql)
            table = re.search(r'FROM\s+"[^"]+"\."([^"]+)"', sql).group(1)
            fields = [part.strip().strip('"') for part in sql.split(" FROM ", 1)[0][7:].split(",")]
            assert set(fields) <= columns("synthetic", table)
            assert params["institute_id"] == "test"
            return FakeRows([{field: row.get(field) for field in fields}
                for row in table_rows.get(table, ())])

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr(source_reader.bundle_assembly, "engine", FakeEngine())
    monkeypatch.setattr(source_reader.bundle_assembly, "_get_table_columns", columns)
    monkeypatch.setattr(source_reader.bundle_assembly, "_default_source_schema", lambda: "synthetic")
    # 不传row_reader，确保使用正式默认函数而非绕过SQL投影的typed字典。
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="test", patient_id="patient", visit_id="visit",
        source_schema="synthetic", created_at="2026-10-08T09:00:00+08:00",
    )
    return session, sql_queries


@pytest.mark.parametrize("culture,available", [(False, True), (False, False), (True, True), (True, False)])
def test_default_sql_reader_preserves_available_identity_fields_without_guessing_missing_columns(monkeypatch, culture, available):
    rows = _rows(culture)
    if culture:
        rows["labtest_item_report"][0]["labtest_subject"] = "血常规"
        field, report_key, rule = "labtest_subject", "labtest_item_report", CULTURE_REPORT
    else:
        rows["exam_master"][0]["modality"] = "CT"
        rows["exam_item_report"][0].pop("exam_name")
        rows["exam_item_report"][0]["modality"] = "US"
        field, report_key, rule = "modality", "exam_item_report", CT_REPORT
    session, queries = _default_reader_session(monkeypatch, rows, rule,
        missing_fields=() if available else ((report_key, field),))
    report = session.materials.document_rows(report_key, snapshot=session.snapshot)[0][1]
    report_query = next(sql for sql in queries if f'."{report_key}"' in sql)
    selected = report_query.split(" FROM ", 1)[0]
    assert (f'"{field}"' in selected) is available
    assert (field in report) is available
    ledger = build_handbook_ledger(rule_ids=(rule,), snapshot=session.snapshot, materials=session.materials)
    evaluation = evaluate_report_completeness(rule, ledger)
    if available:
        assert evaluation.status == "data_gap"
        assert evaluation.reason_code == "association_failed"
    else:
        # 缺列时仍是未命名明细合同，没有取得该字段反证，不冒认已核查模态。
        assert evaluation.status == "compliant"
        assert field not in report
    assert len(queries) == 4


def test_default_sql_reader_keeps_culture_biochemical_identification_detail(monkeypatch):
    rows = _rows(True)
    rows["labtest_master"][0]["lab_type"] = "微生物培养"
    rows["labtest_item_report"][0].pop("labtest_subject")
    rows["labtest_item_report"][0]["item_name"] = "生化鉴定"
    session, _ = _default_reader_session(monkeypatch, rows, CULTURE_REPORT)
    ledger = build_handbook_ledger(rule_ids=(CULTURE_REPORT,), snapshot=session.snapshot, materials=session.materials)
    assert evaluate_report_completeness(CULTURE_REPORT, ledger).status == "compliant"


def test_default_sql_reader_retains_four_existing_source_queries(monkeypatch):
    import re
    from collections import Counter

    for culture, rule in ((False, CT_REPORT), (True, CULTURE_REPORT)):
        _, queries = _default_reader_session(monkeypatch, _rows(culture), rule)
        tables = Counter(re.search(r'FROM\s+"[^"]+"\."([^"]+)"', sql).group(1) for sql in queries)
        # 既有通用医嘱和检查检验过滤医嘱各读取一次同一物理表；字段投影不增加查询。
        assert tables == {"inpat_nondrug_order": 2,
            "labtest_master" if culture else "exam_master": 1,
            "labtest_item_report" if culture else "exam_item_report": 1}
