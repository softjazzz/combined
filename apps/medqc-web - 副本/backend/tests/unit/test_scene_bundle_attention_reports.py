from app.services.bundles import assembly as assembly_module


def test_build_scene_attention_artifacts_should_generate_exam_and_lab_attention_docs(monkeypatch):
    rows_by_table = {
        "exam_master": [
            {
                "exam_no": "EX-1",
                "exam_name": "下肢血管彩超",
                "report_time": "2026-03-22 08:00:00",
                "record_content": "双下肢动脉粥样硬化伴局部斑块形成。",
            }
        ],
        "labtest_master": [
            {
                "test_id": "TEST-1",
                "labtest_subject": "血沉",
                "report_time": "2026-03-22 06:00:00",
            }
        ],
        "labtest_item_report": [
            {
                "test_id": "TEST-1",
                "item_id": "ITEM-1",
                "item_name": "红细胞沉降率测定（ESR）",
                "result": "29",
                "unit": "mm/h",
                "reference_range": "0-20",
                "abnormal_indicator": "H",
                "report_time": "2026-03-22 06:00:00",
            },
            {
                "test_id": "TEST-2",
                "item_id": "ITEM-2",
                "item_name": "Rh血型鉴定",
                "result": "阳性(+)",
                "report_time": "2026-03-22 06:10:00",
            },
            {
                "test_id": "TEST-3",
                "item_id": "ITEM-3",
                "item_name": "备注",
                "result": "正常",
                "report_time": "2026-03-22 06:20:00",
            },
        ],
    }

    def _fake_select_records(**kwargs):
        return list(rows_by_table.get(kwargs["table"], []))

    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)

    docs, timeline_facts = assembly_module._build_scene_attention_artifacts(
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
    )

    assert docs["exam_attention_report"][0]["document_title"] == "检查关注摘要"
    assert "动脉粥样硬化" in docs["exam_attention_report"][0]["record_content"]
    assert docs["lab_attention_report"][0]["document_title"] == "检验关注摘要"
    assert "红细胞沉降率测定（ESR）" in docs["lab_attention_report"][0]["record_content"]
    assert "Rh血型鉴定" not in docs["lab_attention_report"][0]["record_content"]
    assert len(docs["labtest_item_report"]) == 1
    assert docs["labtest_item_report"][0]["document_title"] == "检验明细：红细胞沉降率测定（ESR）"
    assert any(item["source_table"] == "exam_master" for item in timeline_facts)
    assert any(item["source_table"] == "labtest_item_report" for item in timeline_facts)
