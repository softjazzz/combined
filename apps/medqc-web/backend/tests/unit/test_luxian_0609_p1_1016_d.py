"""1016 抗菌药与检查族回归；全部使用合成资料。"""

import pytest

from test_luxian_0609_native_extended_document_execution import (
    _056_rows,
    _evaluate,
)
from test_luxian_0609_native_tumor_pathology_execution import (
    _chemo_discharge_material_session,
    _payload,
    _wrapper,
)
from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from test_luxian_0609_native_exam_lab_execution import _run_010_public_native


@pytest.mark.asyncio
async def test_topical_antibiotic_class_does_not_trigger_tumor_chemotherapy():
    rule = "LX0609-05-02-01"
    session = _chemo_discharge_material_session(chemotherapy_orders=({
        "generic_name": "合成外用抗菌乳膏",
        "drug_type": "皮肤病用抗生素和化疗药物",
        "drug_apply_method": "外用",
    },))
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule,), wrapper_rules=[_wrapper(rule)], evidence_payload=_payload(),
        institute_id="safe-institute", patient_id="safe-patient", visit_id="safe-visit",
        source_schema=None, llm_client=None, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, decision_rule_ids=(rule,),
    )
    assert reduce_luxian_0609_rule_decision(result.decisions[0]).final_state.value == "not_applicable"


@pytest.mark.asyncio
async def test_key_drug_specimen_identity_links_detail_to_master_time():
    rows = _056_rows(
        ("注射用美罗培南", "2026-06-02 10:00:00"),
        ("利奈唑胺注射液", "2026-06-03 10:00:00"),
    )
    rows["labtest_master"] = ({
        "test_id": "synthetic-lab", "labtest_subject": "微生物检验",
        "request_datetime": "2026-06-01 09:00:00",
    },)
    rows["labtest_item_report"] = ({
        "test_id": "synthetic-lab", "lab_item_name": "细菌培养及药敏",
    },)
    _, reduced = await _evaluate("LX0609-05-01-04", rows)
    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_infection_department_senior_consultant_can_support_named_drug():
    _, reduced = await _evaluate("LX0609-05-01-06", {
        "inpat_drug_order": ({"generic_name": "美罗培南",
                              "planned_start_datetime": "2026-06-02 10:00:00"},),
        "consultation_record": ({
            "record_time": "2026-06-01 10:00:00",
            "record_content": "感染科合成专家副主任医师会诊意见：感染指标升高，建议予以美罗培南加强抗感染。",
        },),
    })
    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_pre_exam_reason_does_not_publish_missing_report_as_clinical_defect(monkeypatch):
    _, decision, _, _ = await _run_010_public_native(
        monkeypatch,
        exam_rows=({"exam_id": "synthetic-exam", "order_id": "synthetic-order",
                    "exam_name": "头颅CT", "exam_time": "2026-06-02 10:00:00"},),
        order_rows=({"order_id": "synthetic-order", "order_name": "头颅CT",
                     "prescribed_datetime": "2026-06-02 09:00:00"},),
        course_rows=({"record_time": "2026-06-02 08:00:00",
                      "record_content": "因头痛予以头颅CT明确病因。"},),
    )
    assert decision.final_state.value == "data_gap"


def test_ct_department_formal_report_without_order_is_association_gap():
    from app.services.luxian_0609.handbook_exam_lab import build_handbook_ledger
    from app.services.luxian_0609.ct_order_course_consistency import (
        build_ct_review_input, evaluate_ct_review,
    )

    # 使用检查族的完整同会话夹具，专门覆盖名称为空、科室明确的已实施事件。
    from test_luxian_0609_handbook_exam_lab import _session
    snapshot, materials = _session(rows={
        "exam_master": ({"exam_id": "synthetic-exam", "performed_dept": "CT室",
                         "report_time": "2026-06-02 10:00:00"},),
        "exam_item_report": ({"exam_id": "synthetic-exam", "impression": "右肺结节。",
                              "report_time": "2026-06-02 10:00:00"},),
    })
    ledger = build_handbook_ledger(rule_ids=("LX0609-06-01-03",), snapshot=snapshot, materials=materials)
    assert len(ledger.events["exam"]) == 1
    review = build_ct_review_input(ledger=ledger, snapshot=snapshot, materials=materials)
    assert evaluate_ct_review(review).status == "data_gap"


@pytest.mark.asyncio
async def test_loaded_reports_with_projection_budget_gap_are_not_missing_sources(monkeypatch):
    from test_luxian_0609_native_exam_lab_execution import _typed_session, _wrapper
    from app.services.luxian_0609.native_exam_lab_execution import execute_luxian_0609_native_exam_lab_rules

    rule = "LX0609-06-01-04"
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({"exam_id": "synthetic-exam", "exam_type": "CT",
                    "report_time": "2026-06-02 10:00:00"},),
        exam_report_rows=({"exam_id": "synthetic-exam", "exam_type": "CT",
                           "report_time": "2026-06-02 10:00:00", "impression": "右肺结节。"},),
        course_rows=tuple({"document_id": f"synthetic-{index}",
                           "record_time": "2026-06-02 11:00:00",
                           "record_content": "合成病程内容。" * 260} for index in range(25)),
    )
    result = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,), wrapper_rules=[_wrapper(rule)], evidence_payload=None,
        evidence_snapshot=snapshot, evidence_materials=materials,
        decision_rule_ids=(rule,), llm_client=object(),
    )
    assert reduce_luxian_0609_rule_decision(result.decisions[0]).reason_code == "source_truncated"


@pytest.mark.asyncio
async def test_report_comparison_with_date_and_exam_header_is_still_listing():
    from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
    from app.services.luxian_0609.exam_finding_relevance import apply_relevance_hints
    from app.services.luxian_0609.exam_finding_analysis import check_exam_finding_analysis
    from test_luxian_0609_exam_finding_analysis import _Client, _answer

    report = "右肺下叶少许炎症，较前病灶减少，建议随诊复查。"
    course = "2026-06-02 胸部螺旋CT平扫：" + report
    projection = apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "synthetic-exam", "exam_name": "胸部CT",
                         "report_time": "2026-06-02 10:00:00", "impression": report},),
        "daily_course_record": ({"record_time": "2026-06-02 11:00:00", "record_content": course},),
    }), {1: "positive"})
    ref = next(iter(projection.course_times))
    outcome = await check_exam_finding_analysis(projection, _Client([
        _answer(ref, "prior_comparison", course, span="右肺下叶少许炎症"),
    ]))
    assert outcome.analysed_refs == {1: ()}


@pytest.mark.asyncio
@pytest.mark.parametrize("detail_name,test_id", [
    ("肿瘤细胞核酸检测", "synthetic-lab"),
    ("细菌培养及药敏", "unrelated-lab"),
])
async def test_non_pathogen_or_unlinked_detail_does_not_prove_specimen(detail_name, test_id):
    rows = _056_rows(("注射用美罗培南", "2026-06-02 10:00:00"),
                     ("利奈唑胺注射液", "2026-06-03 10:00:00"))
    rows["labtest_master"] = ({"test_id": "synthetic-lab",
                               "request_datetime": "2026-06-01 09:00:00"},)
    rows["labtest_item_report"] = ({"test_id": test_id, "lab_item_name": detail_name},)
    _, reduced = await _evaluate("LX0609-05-01-04", rows)
    assert reduced.final_state.value == "non_compliant"


@pytest.mark.asyncio
async def test_later_ambiguous_expert_support_cannot_hide_unsupported_first_use():
    _, reduced = await _evaluate("LX0609-05-01-06", {
        "inpat_drug_order": (
            {"generic_name": "美罗培南", "planned_start_datetime": "2026-06-01 10:00:00"},
            {"generic_name": "美罗培南", "planned_start_datetime": "2026-06-03 10:00:00"},
        ),
        "consultation_record": ({"record_time": "2026-06-02 11:00:00",
                                  "record_content": "感染科合成专家副主任医师会诊意见：建议予以美罗培南抗感染。"},),
    })
    assert reduced.final_state.value == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("support_time,status", [
    ("2026-06-01 10:50:00", "compliant"),  # 第六轮 C08：启用后 50 分钟专家会诊同意（紧急越级补办）
    ("2026-06-02 10:00:00", "compliant"),  # 恰好 24 小时
    ("2026-06-02 10:00:01", "non_compliant"),  # 超过 24 小时
])
async def test_058_expert_support_within_24h_after_emergency_use_is_compliant(support_time, status):
    # 用户口径（2026-10-17）：启用后 24 小时内补办专家支持即合规，紧急指征不单独核对。
    _, reduced = await _evaluate("LX0609-05-01-06", {
        "inpat_drug_order": (
            {"generic_name": "亚胺培南西司他丁", "planned_start_datetime": "2026-06-01 10:00:00"},
        ),
        "consultation_record": ({"record_time": support_time,
                                  "record_content": "感染科合成专家副主任医师会诊意见：患者脓毒性休克，同意使用亚胺培南西司他丁。"},),
    })
    assert reduced.final_state.value == status


@pytest.mark.asyncio
async def test_058_same_drug_renewal_reuses_first_use_expert_support():
    # 用户口径（2026-10-17）：同药续开/调整剂量医嘱沿用首次启用时的专家支持（第六轮 C08）。
    _, reduced = await _evaluate("LX0609-05-01-06", {
        "inpat_drug_order": (
            {"order_id": "I-1", "generic_name": "亚胺培南西司他丁", "planned_start_datetime": "2026-06-01 19:00:00"},
            {"order_id": "I-2", "generic_name": "亚胺培南西司他丁", "planned_start_datetime": "2026-06-03 11:00:00"},
        ),
        "consultation_record": ({"record_time": "2026-06-01 20:00:00",
                                  "record_content": "感染科合成专家副主任医师会诊意见：同意使用亚胺培南西司他丁。"},),
    })
    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_058_same_drug_untimed_renewal_keeps_time_gap():
    _, reduced = await _evaluate("LX0609-05-01-06", {
        "inpat_drug_order": (
            {"order_id": "I-1", "generic_name": "亚胺培南西司他丁", "planned_start_datetime": "2026-06-01 19:00:00"},
            {"order_id": "I-2", "generic_name": "亚胺培南西司他丁"},
        ),
        "consultation_record": ({"record_time": "2026-06-01 20:00:00",
                                  "record_content": "感染科合成专家副主任医师会诊意见：同意使用亚胺培南西司他丁。"},),
    })
    assert (reduced.final_state.value, reduced.reason_code) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_058_bracketed_infection_expert_signature_is_recognized():
    _, reduced = await _evaluate("LX0609-05-01-06", {
        "inpat_drug_order": (
            {"order_id": "V-1", "generic_name": "万古霉素", "planned_start_datetime": "2026-06-05 09:30:00"},
        ),
        "consultation_record": ({"record_time": "2026-06-05 12:51:00",
                                  "record_content": "[感染科合成专家副主任医师]会诊意见:感染重,同意使用万古霉素加强抗感染治疗。"},),
    })
    assert reduced.final_state.value == "compliant"


@pytest.mark.parametrize("signature,expected", [
    ("[感染科合成专家副主任医师]会诊意见:", True),
    ("感染性疾病科合成专家副主任医师会诊查房:", True),
    ("感染科会诊协助诊治!合成专家副主任医师会诊:", True),
    ("感染科合成专家主任医师:病史尽知,", True),
    ("感染科合成专家副主任医师,患者发热,", True),
    ("感染科合成专家主治医师会诊意见:", False),  # 用户口径（2026-10-17）：主治医师不算授权专家
    ("临床药学科合成专家主管药师会诊意见:", False),  # 临床药师不算授权专家
    ("请感染科会诊,呼吸科合成专家主任医师会诊意见:", False),  # 他科医师不能算作感染科
    ("感染科合成专家医师会诊后建议:", False),  # 无职称
])
def test_058_infection_expert_signature_variants(signature, expected):
    from app.services.luxian_0609 import native_extended_document_execution as ned

    row = {"record_content": signature + "患者感染重,同意使用美罗培南加强抗感染治疗。"}
    assert bool(ned._is_special_antimicrobial_expert_support(row)) is expected
