from app.services.document_assembly.assembler import assemble_document


def test_blood_application_should_use_application_id_and_real_structured_fields() -> None:
    document = assemble_document(
        "blood_application",
        {
            "application_id": "blood-apply-2496813-01",
            "inpat_no": "IP0000174374",
            "dept_name": "重症医学科（ICU）",
            "name": "冯丽平",
            "sex": "女",
            "age_year": "54",
            "patient_bloodtype_abo": "O",
            "patient_bloodtype_rhd": "阳性(+)",
            "transfuse_variety": "红细胞悬液",
            "transfuse_volume": "2",
            "transfuse_volume_unit": "U",
            "request_datetime": "2026-06-16 12:00:00",
            "physician_name": "申请医师",
            "reason_for_blood": "纠正贫血",
            "hemoglobin": "68 g/L",
            "record_content": "",
        },
    )

    assert document.document_id == "blood-apply-2496813-01"
    assert document.document_title == "输血申请单"
    assert document.display_time == "2026-06-16 12:00:00"
    assert [(section.section_label, section.text) for section in document.sections] == [
        ("住院号", "IP0000174374"),
        ("科室", "重症医学科（ICU）"),
        ("患者姓名", "冯丽平"),
        ("性别", "女"),
        ("年龄", "54"),
        ("ABO血型", "O"),
        ("Rh血型", "阳性(+)"),
        ("输血品种", "红细胞悬液"),
        ("输血剂量", "2"),
        ("剂量单位", "U"),
        ("申请时间", "2026-06-16 12:00:00"),
        ("申请医师", "申请医师"),
        ("输血申请理由", "纠正贫血"),
        ("血红蛋白", "68 g/L"),
    ]
