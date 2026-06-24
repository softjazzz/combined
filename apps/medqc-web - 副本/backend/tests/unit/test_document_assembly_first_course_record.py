import json

from app.services.document_assembly.assembler import assemble_document, build_document_select_columns


def test_first_course_record_should_assemble_structured_content_fields() -> None:
    document = assemble_document(
        "first_course_record",
        {
            "document_id": "first-course-structured-1",
            "case_characteristic": "患者老年女性，因反复胸闷入院。",
            "diagnose_based_on": "结合胸闷症状、心电图ST-T改变，考虑冠心病。",
            "differential_diagnosis": "需与肺栓塞、主动脉夹层等鉴别。",
            "treatment_plan": "完善心肌酶、冠脉CTA，给予抗血小板及调脂治疗。",
        },
    )

    assert document.assembly_status in {"assembled", "partial"}
    assert "患者老年女性" in document.assembled_text
    assert "诊断依据" not in document.assembled_text
    assert [section.source_field for section in document.sections] == [
        "case_characteristic",
        "diagnose_based_on",
        "differential_diagnosis",
        "treatment_plan",
    ]
    assert "missing_required_field" not in "|".join(document.data_quality_flags)


def test_first_course_record_should_fallback_to_v2_record_content_when_structured_fields_empty() -> None:
    document = assemble_document(
        "first_course_record",
        {
            "document_id": "first-course-1",
            "record_time": "2026-04-28 09:30:00",
            "v2_schema": json.dumps(
                {
                    "case_characteristic": "",
                    "diagnose_based_on": "",
                    "differential_diagnosis": "",
                    "treatment_plan": "",
                    "record_content": "患者因胸痛1周入院，结合心电图改变考虑冠心病。",
                },
                ensure_ascii=False,
            ),
        },
    )

    assert document.assembly_status == "partial"
    assert document.assembled_text == "患者因胸痛1周入院，结合心电图改变考虑冠心病。"
    assert document.sections[0].source_field == "record_content"
    assert "empty_document" not in document.data_quality_flags


def test_build_document_select_columns_should_include_v2_schema_for_first_course_record() -> None:
    columns = build_document_select_columns(
        "first_course_record",
        {"document_id", "record_time", "v2_schema"},
    )

    assert columns == ["document_id", "record_time", "v2_schema"]


def test_first_course_record_diagnosis_should_assemble_like_record_diagnosis() -> None:
    document = assemble_document(
        "first_course_record_diagnosis",
        {
            "diagnosis_id": "D1",
            "diagnosis_type": "初步诊断",
            "diagnosis_name": "右侧输尿管结石",
            "diagnosis_code": "N20.100",
            "diagnosis_time": "2026-02-01 09:00:00",
        },
    )

    assert document.assembly_status in {"assembled", "partial"}
    assert "诊断名称: 右侧输尿管结石" in document.assembled_text
    assert document.document_title.startswith("首次病程诊断")


def test_transfer_in_record_should_assemble_structured_content_fields() -> None:
    document = assemble_document(
        "transfer_in_record",
        {
            "document_id": "transfer-in-1",
            "transfer_purpose": "因病情复杂转入心内科进一步诊治。",
            "treatment_course": "外科已予抗感染、补液治疗。",
            "transfer_treatment_plan": "转入后完善心电图、心肌酶检查并调整治疗。",
            "current_situation": "患者仍诉胸闷。",
        },
    )

    assert document.assembled_text
    assert "因病情复杂转入心内科" in document.assembled_text
    assert "转入后完善心电图" in document.assembled_text
    assert "transfer_treatment_plan" in [section.source_field for section in document.sections]


def test_transfer_out_record_should_assemble_structured_content_fields() -> None:
    document = assemble_document(
        "transfer_out_record",
        {
            "document_id": "transfer-out-1",
            "transfer_purpose": "需转入骨科继续处理左膝伤口。",
            "treatment_course": "本科已完成清创换药及抗感染治疗。",
            "current_situation": "伤口渗出减少，生命体征平稳。",
            "note": "转科后继续观察伤口及感染指标。",
        },
    )

    assert document.assembled_text
    assert "需转入骨科继续处理左膝伤口" in document.assembled_text
    assert "伤口渗出减少" in document.assembled_text
    assert "current_situation" in [section.source_field for section in document.sections]
