"""Astra19 六项手术反例：真实取材、执行、绑定及内存保存链。"""
import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
from app.services.luxian_0609.native_surgery_gate_execution import execute_luxian_0609_native_surgery_gate_rules
from test_luxian_0609_death_record_timeliness import saved_roundtrip

DISCUSSION = "LX0609-04-01-02"
LYMPH = "LX0609-04-02-03"
CONSENT = "LX0609-11-02-01"
SIGNATURE = "LX0609-11-02-02"


async def run(rule, rows):
    def reader(**kw):
        source = kw["source_key"]
        return SnapshotSourceRows.create(source_key=source, rows=tuple(rows.get(source, ())),
                                         truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-20T12:00:00+08:00", row_reader=reader,
        additional_source_keys=tuple(rows))
    kwargs = dict(rule_ids=(rule,), wrapper_rules=[], evidence_payload=None, llm_client=None,
                  evidence_snapshot=session.snapshot, evidence_materials=session.materials,
                  decision_rule_ids=(rule,))
    if rule == LYMPH:
        execution = await execute_luxian_0609_native_surgery_gate_rules(
            institute_id="I", patient_id="P", visit_id="V", source_schema=None, **kwargs)
    else:
        execution = await execute_luxian_0609_native_surgery_document_rules(**kwargs)
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
        evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    loaded = saved_roundtrip(final)
    assert loaded["status"] == final["status"]
    assert loaded.get("customer_display_facts") == final.get("customer_display_facts")
    return loaded


def surgery(day=2, **kw):
    return {"document_id":f"S{day}", "surgery_id":f"S{day}", "surgeon":"张三",
        "surgery_name":"腹腔镜胆囊切除术", "surgery_code":"51.2300",
        "surgery_begin_time":f"2026-06-{day:02} 09:00:00+08:00",
        "surgery_end_time":f"2026-06-{day:02} 11:00:00+08:00",
        "record_time":f"2026-06-{day:02} 12:00:00", "record_content":"已实施手术，过程顺利。", **kw}


def discussion(day=1, **kw):
    return {"document_id":f"D{day}", "surgery_id":f"S{day+1}",
        "record_time":f"2026-06-{day:02} 10:00:00", "surgery_name":"腹腔镜胆囊切除术",
        "discuss_staff":"张三、李四", "record_content":"讨论手术指征、方案、风险，张三、李四参加。", **kw}


@pytest.mark.parametrize("reverse", [False, True])
async def test_discussion_does_not_cover_another_surgery(reverse):
    records = [surgery(), surgery(8, surgery_name="腹腔镜阑尾切除术", surgery_code="47.0100")]
    result = await run(DISCUSSION, {"surgery_record":records[::-1] if reverse else records,
        "presurg_discussion":[discussion()]})
    assert result["status"] != "compliant"


@pytest.mark.parametrize("submitter", ["", "张三"])
async def test_submitter_does_not_prove_participation(submitter):
    result = await run(DISCUSSION, {"surgery_record":[surgery()], "presurg_discussion":[discussion(
        discuss_staff="李四、王五", submitter=submitter,
        record_content="李四、王五参加讨论，术者张三未参加；张三仅补录上传。") ]})
    assert result["status"] == "non_compliant"


@pytest.mark.parametrize("mixed,reverse", [(False, False), (True, False), (True, True)])
async def test_emergency_exception_does_not_cover_elective_surgery(mixed, reverse):
    records = [surgery(surgery_name="急诊冠脉介入治疗", surgery_code="00.6600",
                       record_content="6月2日已实施急诊冠脉介入治疗。")]
    if mixed:
        records.append(surgery(8, record_content="6月8日择期实施腹腔镜胆囊切除术。"))
    result = await run(DISCUSSION, {"surgery_record":records[::-1] if reverse else records,
        "daily_course_record":[{"document_id":"C2", "record_time":"2026-06-02 08:00:00",
                                "record_content":"本日因急性心梗行急诊冠脉介入治疗。"}]})
    assert result["status"] == ("non_compliant" if mixed else "not_applicable")


async def test_mixed_emergency_and_complete_elective_discussion_keeps_selected_evidence():
    result = await run(DISCUSSION, {
        "surgery_record":[surgery(record_content="本次为紧急抢救生命手术。"), surgery(8)],
        "presurg_discussion":[discussion(7, record_content="择期胆囊手术讨论：张三、李四参加。")],
    })
    assert result["status"] == "compliant"
    excerpts = [item.get("evidence_excerpt", "") for item in result["evidence"]]
    assert "择期胆囊手术讨论：张三、李四参加。" in excerpts
    assert not any("紧急抢救" in text for text in excerpts)


@pytest.mark.parametrize("case", ["single", "each", "ambiguous", "identity_conflict", "crossed"])
async def test_discussion_event_controls(case):
    rows = {"surgery_record":[surgery()], "presurg_discussion":[discussion()]}
    if case != "single":
        rows["surgery_record"].append(surgery(8, surgeon="王五"))
        rows["presurg_discussion"].append(discussion(7, discuss_staff="王五、李四"))
    if case == "ambiguous":
        rows["presurg_discussion"] = [{"discuss_staff":"张三、王五"}]
    if case == "crossed":
        rows["presurg_discussion"][0]["discuss_staff"] = "王五、李四"
        rows["presurg_discussion"][1]["discuss_staff"] = "张三、李四"
    if case == "identity_conflict":
        rows["presurg_discussion"][0]["surgery_id"] = "unmatched-surgery"
    result = await run(DISCUSSION, rows)
    assert result["status"] == ("data_gap" if case in {"ambiguous", "identity_conflict"} else
                                "non_compliant" if case == "crossed" else "compliant")


@pytest.mark.parametrize("stage,expected", [
    ("pTNM：未填写", "non_compliant"), ("未记录pTNM分期", "non_compliant"),
    ("未记录pT3N0", "non_compliant"),
    ("pT3N0", "compliant"), ("ypT2N0", "compliant"),
    ("未见淋巴结转移 pT3N0", "compliant"),
])
async def test_pathology_requires_stage_value(stage, expected):
    result = await run(LYMPH, {
        "surgery_record":[surgery(surgery_code="45.7601", surgery_name="乙状结肠癌根治术",
            surgery_process="完成乙状结肠癌根治及区域淋巴结清扫。")],
        "diagnosis":[{"diagnosis_code":"C18.700", "diagnosis_name":"乙状结肠腺癌"}],
        "discharge_record":[{"document_id":"DIS", "record_content":"本次术后分期T3N0M0。"}],
        "pathology_exam_report":[{"document_id":"PATH", "diagnosis":f"乙状结肠腺癌，淋巴结0/14；{stage}。"}],
    })
    assert result["status"] == expected
    if expected == "non_compliant":
        assert result["customer_display_facts"]["missing_items"] == ["pathologic_stage"]


def anesthesia():
    return {"document_id":"A2", "surgery_id":"S2", "anesthesia_method":"全身麻醉"}


@pytest.mark.parametrize("case,form,expected", [
    ("mention", {"document_title":"手术知情同意书", "consent_type":"手术知情同意书",
                 "record_content":"本表为手术知情同意书。麻醉知情同意书尚未签署，须另行补签。"}, "non_compliant"),
    ("title", {"document_title":"麻醉知情同意书", "record_content":"已告知风险。"}, "compliant"),
    ("body", {"record_content":"麻醉知情同意书：已告知麻醉风险、方式及替代方案，患者同意麻醉并签名。"}, "compliant"),
    ("negative_body", {"record_content":"尚无麻醉知情同意书，待补签。"}, "non_compliant"),
])
async def test_consent_identity_is_not_an_incidental_mention(case, form, expected):
    result = await run(CONSENT, {"anesthesia_record":[anesthesia()], "consent_form":[{"document_id":"C1", **form}]})
    assert result["status"] == expected


@pytest.mark.parametrize("clock,expected", [
    ("2026-06-01T09:30:00+0800", "compliant"),
    ("2026-06-01T09:30:00+08:00", "compliant"),
    ("2026-06-01", "non_compliant"),
])
async def test_equivalent_minute_signature_offsets(clock, expected):
    result = await run(SIGNATURE, {"anesthesia_record":[anesthesia()], "consent_form":[{
        "document_id":"C1", "document_title":"麻醉知情同意书", "patient_sign":"王患者", "physician_sign":"李四",
        "patient_sign_datetime":clock, "physician_sign_datetime":"2026-06-01 09:35"}]})
    assert result["status"] == expected
    if expected == "non_compliant":
        assert result["customer_display_facts"]["missing_fields"] == ["patient_signature_time"]
