from app.services.document_assembly.assembler import assemble_document


def test_surgery_record_uses_surgery_process_and_structured_fields() -> None:
    document = assemble_document(
        "surgery_record",
        {
            "document_id": "4563221||1",
            "document_title": "手术记录",
            "record_time": "2026-03-16 15:10:37",
            "dept_name": "骨科烧伤科",
            "surgery_name": "全髋关节置换术(陶瓷对陶瓷)",
            "surgeon": "马晨曦",
            "anesthesia_method": "静吸复合全麻",
            "preoperative_diagnosis": "西医诊断：股骨头缺血性坏死",
            "surgery_process": "1、全麻麻醉后平稳后患者左侧卧位。\n2、采用右髋后外侧切口约15cm。",
            "record_content": "术中C臂透视2次,手术过程详见手术记录。",
        },
    )

    fields = {field.source_field: field.raw_value_preview for field in document.source_fields}

    assert document.document_title == "手术记录"
    assert document.assembly_status == "assembled"
    assert document.sections == []
    assert "手术经过: 1、全麻麻醉后平稳后患者左侧卧位。" in document.assembled_text
    assert fields["dept_name"] == "骨科烧伤科"
    assert fields["surgery_name"] == "全髋关节置换术(陶瓷对陶瓷)"
    assert fields["surgeon"] == "马晨曦"
    assert fields["anesthesia_method"] == "静吸复合全麻"
    assert fields["preoperative_diagnosis"] == "西医诊断：股骨头缺血性坏死"
    assert fields["surgery_process"].startswith("1、全麻麻醉后平稳后患者左侧卧位。")
    assert fields["record_content"] == "术中C臂透视2次,手术过程详见手术记录。"
