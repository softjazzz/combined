"""Caché已同步资料的规则适配：仅虚构数据、正式读入口/会话/执行器。"""

from contextlib import contextmanager
from copy import deepcopy
import json
import re
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import source_evidence_reader as reader
from app.services.luxian_0609.cache_document_source_adapter import (
    document_diagnoses, enrich_discharge_document, explicit_sections, homepage_diagnoses,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session

KEYS = dict(institute_id="fictional-I", patient_id="fictional-P", visit_id="fictional-V")


class Rows:
    def __init__(self, values):
        self.values = values

    def mappings(self):
        return self

    def all(self):
        return self.values


class FakeDB:
    def __init__(self, tables, errors=None):
        self.tables = {key: [{**KEYS, **row} for row in rows] for key, rows in tables.items()}
        self.errors, self.calls = errors or {}, []

    def columns(self, _, table):
        if table not in self.tables:
            return []
        return sorted(set(KEYS) | {k for row in self.tables[table] for k in row}
                      | set(reader._SNAPSHOT_SOURCE_FIELDS.get(table, ())))

    @contextmanager
    def connect(self):
        yield self

    def execute(self, statement, params):
        sql = str(statement)
        table = re.search(r'FROM "cdm"\."([a-z_]+)"', sql)[1]
        self.calls.append((sql, dict(params)))
        if table in self.errors:
            raise self.errors[table]
        rows = [row for row in self.tables.get(table, ())
                if all(row[k] == params[k] for k in KEYS)]
        selected = re.findall(r'"([a-z_]+)"', sql.split("FROM", 1)[0])
        return Rows([{k: r.get(k) for k in selected} for r in rows[:params["limit_rows"]]])


def install(monkeypatch, tables, errors=None):
    db = FakeDB(tables, errors)
    monkeypatch.setattr(reader.bundle_assembly, "engine", db)
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns", db.columns)
    monkeypatch.setattr(reader, "_case_source_schema", lambda **_: "cdm")
    return db


def read(key):
    return reader.read_luxian_0609_snapshot_source_rows(
        source_key=key, **KEYS, source_schema="cdm",
    )


def session(rule):
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), **KEYS, source_schema="cdm",
        created_at="2026-10-29T12:00:00+08:00", evaluation_as_of_date="2026-10-29",
        row_reader=reader.read_luxian_0609_snapshot_source_rows,
    )


def reduce(execution, context, rule):
    decision = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=context.snapshot,
        evidence_materials=context.materials,
    )[0]
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    published = finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=context.snapshot, evidence_materials=context.materials,
    )
    assert published["status"] == decision.final_state.value
    return decision


@pytest.mark.parametrize("source,parent,label", [
    ("admission_record_diagnosis", "admission_record", "入院诊断"),
    ("first_course_record_diagnosis", "first_course_record", "初步诊断"),
    ("discharge_record_diagnosis", "discharge_record", "出院诊断"),
])
def test_missing_child_table_reads_explicit_sections_with_document_and_order(monkeypatch, source, parent, label):
    tables = {parent: [{"document_id": "D01", "record_content": f"{label}：\n1、合成诊断甲\n2、合成诊断乙\n诊疗计划：不要混入诊断"}],
              "diagnosis": []}
    before = deepcopy(tables)
    db = install(monkeypatch, tables)
    result = read(source)
    assert [r["diagnosis_name"] for r in result.rows] == ["合成诊断甲", "合成诊断乙"]
    assert [r["diagnosis_no"] for r in result.rows] == ["1", "2"]
    assert all(r["document_id"] == "D01" and r["source_table"] == parent for r in result.rows)
    assert tables == before
    for sql, params in db.calls:
        assert all(f'"{k}" = :{k}' in sql for k in KEYS)
        assert "fictional" not in sql and all(params[k] == KEYS[k] for k in KEYS)


def test_primary_child_rows_keep_original_priority(monkeypatch):
    install(monkeypatch, {
        "first_course_record_diagnosis": [{"document_id": "D", "diagnosis_name": "原结构化诊断"}],
        "first_course_record": [{"document_id": "D", "record_content": "初步诊断：另一诊断"}],
    })
    assert read("first_course_record_diagnosis").rows[0]["diagnosis_name"] == "原结构化诊断"


def test_generic_diagnosis_only_binds_exact_document_and_correct_type():
    docs = [{"document_id": "D1", "record_content": "初步诊断：正文诊断"},
            {"document_id": "D2", "record_content": "初步诊断：第二文书诊断"}]
    diagnoses = [
        {"document_id": "D1", "diagnosis_type": "初步诊断", "diagnosis_name": "已绑定", "diagnosis_no": "3"},
        {"document_id": "D2", "diagnosis_type": "出院诊断", "diagnosis_name": "不能挪用"},
        {"document_id": "D3", "diagnosis_type": "初步诊断", "diagnosis_name": "别份文书"},
    ]
    rows = document_diagnoses("first_course_record_diagnosis", docs, diagnoses)
    assert [r["diagnosis_name"] for r in rows] == ["已绑定", "第二文书诊断"]
    assert rows[0]["diagnosis_no"] == "3" and "diagnosis_no" not in rows[1]


def test_html_headers_and_nonclinical_style_are_handled_without_mutating_body():
    body = "<style>初步诊断：假内容</style><p>初步诊断</p><p>1、合成诊断</p><p>鉴别诊断：另一疾病</p>"
    rows = document_diagnoses("first_course_record_diagnosis", [{"document_id": "D", "record_content": body}])
    assert len(rows) == 1 and rows[0]["diagnosis_name"] == "合成诊断"
    assert "假内容" not in str(explicit_sections(body))


def test_unlabelled_text_and_missing_document_id_do_not_invent_diagnoses():
    assert document_diagnoses("admission_record_diagnosis", [{"document_id": "D", "record_content": "考虑某疾病，尚待检查"}]) == ()
    with pytest.raises(ValueError):
        document_diagnoses("admission_record_diagnosis", [{"record_content": "入院诊断：疾病"}])


def test_generic_discharge_diagnosis_is_not_mislabeled_as_homepage():
    ordinary = {"diagnosis_type": "出院诊断", "diagnosis_name": "诊断", "diagnosis_source": "其他来源"}
    assert homepage_diagnoses([ordinary]) == ()
    assert homepage_diagnoses([{**ordinary, "diagnosis_source": "病案首页"}])[0]["source_table"] == "diagnosis"


def test_unavailable_homepage_source_does_not_claim_clinically_empty(monkeypatch):
    install(monkeypatch, {"mr_diagnosis": [], "diagnosis": [{
        "diagnosis_name": "诊断", "diagnosis_type": "出院诊断", "diagnosis_source": "其他来源",
    }]})
    with pytest.raises(reader.SourceEvidenceUnavailable):
        read("mr_diagnosis")


def test_missing_diagnosis_heading_is_unavailable_not_complete_empty(monkeypatch):
    install(monkeypatch, {"admission_record": [{"document_id": "D", "record_content": "等待明确病情"}]})
    with pytest.raises(reader.SourceEvidenceUnavailable):
        read("admission_record_diagnosis")


def test_discharge_section_preserves_text_and_structured_priority():
    raw = {"record_content": "出院医嘱：按时复诊\n出院带药：药品名称：合成药；用药剂量：1片；给药途径：口服；用药时间：7天\n随访计划：门诊随访"}
    result = enrich_discharge_document(raw)
    assert result["record_content"] == raw["record_content"]
    assert result["discharge_order"].startswith("药品名称") and "门诊随访" not in result["discharge_order"]
    assert enrich_discharge_document({**raw, "discharge_order": "原栏目"})["discharge_order"] == "原栏目"
    assert "discharge_order" not in enrich_discharge_document({"record_content": "请遵医嘱用药"})


@pytest.mark.asyncio
@pytest.mark.parametrize("route,expected", [("口服", "compliant"), ("", "non_compliant")])
async def test_discharge_body_drives_formal_medication_rule_without_inventing_prescription(monkeypatch, route, expected):
    from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
    install(monkeypatch, {"discharge_record": [{"document_id": "D", "record_content":
        "出院带药：药品名称：合成注射药；用药剂量：1mg；给药途径：" + route + "；用药时间：7天"}]})
    rule = "LX0609-08-01-02"
    context = session(rule)
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=context.snapshot,
        evidence_materials=context.materials, llm_client=None,
    )
    decision = reduce(execution, context, rule)
    assert decision.final_state.value == expected
    facts = dict(execution.customer_display_facts)[rule]
    assert "prescription_medication_count" not in facts
    assert "missing_drug_names" not in facts
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_report_completeness_runs_with_no_exam_master_and_preserves_repeated_exams(monkeypatch):
    from app.services.luxian_0609.native_exam_lab_execution import execute_luxian_0609_native_exam_lab_rules
    install(monkeypatch, {"exam_item_report": [
        {"document_id": "R1", "exam_id": "E1", "item_name": "胸部CT", "description": "明确所见甲", "report_time": "2026-10-28 09:00:00"},
        {"document_id": "R2", "exam_id": "E2", "item_name": "胸部CT", "description": "明确所见乙", "report_time": "2026-10-28 15:00:00"},
    ]})
    rule = "LX0609-06-01-03"
    context = session(rule)
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,), wrapper_rules=[{"rule_id": rule}],
        decision_rule_ids=(rule,), evidence_payload=None,
        evidence_snapshot=context.snapshot, evidence_materials=context.materials, llm_client=None,
    )
    assert reduce(execution, context, rule).final_state.value == "compliant"
    assert dict(execution.customer_display_facts)[rule]["event_count"] == 2
    assert execution.llm_call_count == 0
    assert all("exam_time" not in row for row in context.materials.rows("exam_item_report"))


def test_inline_sections_stop_at_next_heading_and_do_not_split_decimal_codes():
    rows = document_diagnoses("first_course_record_diagnosis", [{
        "document_id": "D", "record_content":
        "初步诊断：1、合成疾病 ICD 12.3。鉴别诊断：不能混为初步诊断。治疗计划：观察。",
    }])
    assert len(rows) == 1 and rows[0]["diagnosis_name"] == "合成疾病 ICD 12.3。"
    assert rows[0]["diagnosis_no"] == "1"


def test_empty_initial_diagnosis_does_not_consume_the_next_section():
    assert document_diagnoses("first_course_record_diagnosis", [{
        "document_id": "D", "record_content": "初步诊断：\n鉴别诊断：不能挪为初步诊断\n诊疗计划：检查",
    }]) == ()


@pytest.mark.parametrize("code,expected", [
    ("42P01", None), ("42501", None), ("57014", reader.SourceEvidenceQueryError),
])
def test_child_table_access_failure_only_falls_back_for_missing_or_unauthorized(monkeypatch, code, expected):
    error = RuntimeError("PRIVATE_SQL_DIAGNOSTIC")
    error.pgcode = code
    install(monkeypatch, {
        "first_course_record_diagnosis": [],
        "first_course_record": [{"document_id": "D", "record_content": "初步诊断：合成诊断"}],
    }, {"first_course_record_diagnosis": error})
    if expected:
        with pytest.raises(expected) as caught:
            read("first_course_record_diagnosis")
        assert "PRIVATE_SQL_DIAGNOSTIC" not in str(caught.value)
    else:
        assert read("first_course_record_diagnosis").rows[0]["source_table"] == "first_course_record"


def test_truncated_parent_is_not_promoted_to_complete_diagnosis_source(monkeypatch):
    install(monkeypatch, {"first_course_record": [
        {"document_id": str(i), "record_content": "初步诊断：合成诊断"} for i in range(3)
    ]})
    monkeypatch.setattr(reader, "_source_limit", lambda _: 2)
    with pytest.raises(reader.SourceEvidenceUnavailable):
        read("first_course_record_diagnosis")


def test_derived_diagnosis_overflow_is_reported_as_truncated(monkeypatch):
    install(monkeypatch, {"first_course_record": [{
        "document_id": "D", "record_content": "初步诊断：\n1、甲\n2、乙\n3、丙",
    }]})
    monkeypatch.setattr(reader, "_source_limit", lambda _: 2)
    result = read("first_course_record_diagnosis")
    assert result.truncated is True and len(result.rows) == 2


def test_unordered_multiple_diagnoses_do_not_gain_an_invented_first_diagnosis(monkeypatch):
    from app.services.luxian_0609.course_quality.rule_018 import _lx018_primary_diagnosis_resolution
    install(monkeypatch, {"admission_record": [{
        "document_id": "D", "record_content": "入院诊断：\n甲\n乙",
    }]})
    rows = read("admission_record_diagnosis").rows
    assert all("diagnosis_no" not in row for row in rows)
    assert len(rows) == 2
    assert _lx018_primary_diagnosis_resolution({"admission_record_diagnosis": list(rows)}) == ("unknown", "")


def test_explicit_admission_order_reaches_formal_first_diagnosis_resolution(monkeypatch):
    from app.services.luxian_0609.course_quality.rule_018 import _lx018_primary_diagnosis_resolution
    install(monkeypatch, {"admission_record": [{
        "document_id": "D", "record_content": "入院诊断：\n2、乙\n1、甲",
    }]})
    assert _lx018_primary_diagnosis_resolution({
        "admission_record_diagnosis": list(read("admission_record_diagnosis").rows),
    }) == ("available", "甲")


@pytest.mark.asyncio
async def test_first_course_formal_rule_reads_parent_diagnosis_and_uses_fake_semantic_client(monkeypatch):
    from app.services.luxian_0609.course_quality.rule_077 import evaluate_rule_077
    install(monkeypatch, {"first_course_record": [{
        "document_id": "D", "record_content":
        "初步诊断：1、急性胆囊炎\n鉴别诊断：消化性溃疡穿孔；急性胰腺炎。\n治疗计划：完善检查。",
    }]})
    calls = []

    class Client:
        async def generate(self, prompt, **kwargs):
            calls.append(prompt)
            assert "急性胆囊炎" in prompt and "消化性溃疡穿孔" in prompt
            return {"content": json.dumps({
                "relation_state": "related", "rationale_code": "same_clinical_problem",
                "medical_analysis": "所列鉴别用于解释同一腹痛临床问题。",
                "evidence_id": "p01",
            }, ensure_ascii=False)}

    context = session("LX0609-01-02-02")
    execution = await evaluate_rule_077(snapshot=context.snapshot, materials=context.materials, llm_client=Client())
    from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
    assert reduce_luxian_0609_rule_decision(execution.decision).final_state.value == "compliant"
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("source_label", ["病案首页", "未证实来源"])
async def test_homepage_comparison_stays_pending_without_reading_or_model(monkeypatch, source_label):
    from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
    from app.services.luxian_0609.execution import (
        aggregate_luxian_0609_orchestrated_results, prepare_luxian_0609_execution,
    )

    db = install(monkeypatch, {
        "discharge_record": [{"document_id": "D", "record_content": "出院诊断：1、合成诊断"}],
        "diagnosis": [{"diagnosis_type": "出院诊断", "diagnosis_no": "1",
                       "diagnosis_name": "合成诊断", "diagnosis_source": source_label}],
        "mr": [{"admission_datetime": "2026-10-26 09:00:00", "discharge_datetime": "2026-10-28 12:00:00"}],
        "death_record": [],
    })
    rule = "LX0609-08-01-03"

    class ForbiddenClient:
        async def generate(self, *_args, **_kwargs):
            pytest.fail("暂停的首页比较规则不能调用模型")

    executable, context = await prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY, prepared_rules=[{"rule_id": rule}],
        medical_text="", evidence_payload=None, llm_client=ForbiddenClient(),
        settings=SimpleNamespace(
            LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
            LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
            LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
        ),
        selected_customer_rule_ids=(rule,), source_schema="cdm", **KEYS,
    )
    assert executable == []
    published = aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []}, context=context, visit_id=KEYS["visit_id"],
        model_name="unused", evidence_payload=None,
    )
    assert len(published["results"]) == 1
    result = published["results"][0]
    assert (result["status"], result["reason_code"]) == ("not_executed", "policy_definition_pending")
    assert result["evidence"] == [] and result["is_compliant"] is None
    assert context.native_llm_call_count == 0
    assert db.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rule,name", [
    ("LX0609-06-01-03", "PCT检验"),
    ("LX0609-06-01-01", "胸部CT"),
])
async def test_reports_do_not_invent_ct_trigger_or_his_order_association(monkeypatch, rule, name):
    from app.services.luxian_0609.native_exam_lab_execution import execute_luxian_0609_native_exam_lab_rules
    install(monkeypatch, {"exam_item_report": [{
        "document_id": "R", "exam_id": "E", "item_name": name,
        "description": "合成所见", "report_time": "2026-10-28 09:00:00",
    }]})
    context = session(rule)
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,), wrapper_rules=[{"rule_id": rule}], decision_rule_ids=(rule,),
        evidence_payload=None, evidence_snapshot=context.snapshot,
        evidence_materials=context.materials, llm_client=None,
    )
    assert reduce(execution, context, rule).final_state.value == "data_gap"
    assert execution.llm_call_count == 0


def test_ambiguous_medication_sections_do_not_get_silently_merged():
    result = enrich_discharge_document({"record_content": "出院带药：合成药甲\n出院用药：合成药乙"})
    assert "discharge_order" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["query_error", "truncated", "partial_prescription"])
async def test_body_medication_path_does_not_mask_prescription_failure(monkeypatch, failure):
    from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
    prescriptions = [] if failure == "query_error" else [
        {"prescription_id": str(i), "order_type": "出院带药", "order_status": "执行"}
        for i in range(3 if failure == "truncated" else 1)
    ]
    install(monkeypatch, {
        "discharge_record": [{"document_id": "D", "record_content":
            "出院带药：药品名称：合成药；用药剂量：1mg；给药途径：口服；用药时间：7天"}],
        "inpat_prescription": prescriptions,
    }, {"inpat_prescription": RuntimeError("PRIVATE_ERROR")} if failure == "query_error" else {})
    if failure == "truncated":
        monkeypatch.setattr(reader, "_source_limit", lambda _: 2)
    rule = "LX0609-08-01-02"
    context = session(rule)
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=context.snapshot,
        evidence_materials=context.materials, llm_client=None,
    )
    assert reduce(execution, context, rule).final_state.value == "data_gap"
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_admission_body_diagnosis_reaches_formal_chief_complaint_rule(monkeypatch):
    from app.services.luxian_0609.native_course_quality_execution import execute_luxian_0609_native_course_quality_rules
    from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
    from test_luxian_0609_native_course_quality_execution import _Client
    install(monkeypatch, {"admission_record": [{
        "document_id": "D", "record_content": "主诉：反复胸痛2个月。\n入院诊断：1、稳定型心绞痛",
    }], "diagnosis": []})
    rule = "LX0609-01-01-02"
    context = session(rule)
    client = _Client([{
        "diagnostic_relation_state": "supported",
        "diagnostic_reason_dimensions": ["symptom_pattern"],
        "diagnostic_rationale_code": "supported",
    }])
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=(rule,), wrapper_rules=[get_luxian_0609_rule(rule)], decision_rule_ids=(rule,),
        evidence_payload=None, evidence_snapshot=context.snapshot,
        evidence_materials=context.materials, llm_client=client,
    )
    assert reduce(execution, context, rule).final_state.value == "compliant"
    assert len(client.prompts) == 1 and "稳定型心绞痛" in client.prompts[0]
