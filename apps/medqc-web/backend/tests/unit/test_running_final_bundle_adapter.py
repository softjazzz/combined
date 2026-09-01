from app.services.qc_input_adapters.running_final_bundle_adapter import (
    adapt_bundle_to_evidence_payload,
    extract_bundle_documents,
)


def test_extract_bundle_documents_should_prefer_document_inventory_full_content():
    bundle = {
        "scene": "final",
        "visit_id": "2248248",
        "source_doc_priority": [
            "discharge_record",
            "daily_course_record",
            "surgery_record",
        ],
        "document_hits": {
            "discharge_record": True,
            "daily_course_record": True,
            "surgery_record": True,
        },
        "structured_context": {
            "documents": {
                "daily_course_record": [
                    {
                        "text_preview": "这是摘要，不应该优先使用",
                    }
                ],
            },
            "document_inventory": [
                {
                    "source_table": "discharge_record",
                    "content": "这是完整出院记录正文",
                },
                {
                    "source_table": "daily_course_record",
                    "content": "这是完整日常病程正文",
                },
                {
                    "source_table": "surgery_record",
                    "content": "这是完整手术记录正文",
                },
            ],
        },
    }

    documents = extract_bundle_documents(bundle)

    assert [item["source_table"] for item in documents] == [
        "discharge_record",
        "daily_course_record",
        "surgery_record",
    ]
    assert documents[1]["document_type"] == "日常病程记录"
    assert documents[1]["content"] == "这是完整日常病程正文"
    assert documents[2]["document_type"] == "手术记录"
    assert documents[2]["content"] == "这是完整手术记录正文"


def test_adapt_bundle_to_evidence_payload_should_fallback_to_structured_timeline_facts():
    bundle = {
        "scene": "final",
        "visit_id": "2248248",
        "source_doc_priority": ["discharge_record"],
        "document_hits": {"discharge_record": True},
        "structured_context": {
            "document_inventory": [
                {
                    "source_table": "discharge_record",
                    "content": "完整出院记录正文",
                }
            ],
            "timeline_facts": [
                {
                    "source_table": "discharge_record",
                    "field": "discharge_datetime",
                    "value": "2026-03-04 09:59:13",
                }
            ],
        },
    }

    payload = adapt_bundle_to_evidence_payload(bundle)

    assert payload["primary_document_text"] == "完整出院记录正文"
    assert payload["timeline_facts"] == [
        {
            "source_table": "discharge_record",
            "field": "discharge_datetime",
            "value": "2026-03-04 09:59:13",
        }
    ]


def test_extract_bundle_documents_should_preserve_inventory_document_id():
    bundle = {
        "scene": "final",
        "visit_id": "VISIT-1",
        "source_doc_priority": ["labtest_item_report", "bloodtrans_record"],
        "document_hits": {"labtest_item_report": True, "bloodtrans_record": True},
        "structured_context": {
            "document_inventory": [
                {
                    "source_table": "labtest_item_report",
                    "document_id": "LAB-009",
                    "content": "检验报告正文",
                },
                {
                    "source_table": "bloodtrans_record",
                    "document_id": "BT-001",
                    "content": "输血记录正文",
                },
            ]
        },
    }

    documents = extract_bundle_documents(bundle)

    assert [item["id"] for item in documents] == ["LAB-009", "BT-001"]
    payload = adapt_bundle_to_evidence_payload(bundle)
    assert payload["supporting_documents"][0]["document_id"] == "BT-001"


def test_extract_bundle_documents_should_include_attention_reports():
    bundle = {
        "scene": "running",
        "visit_id": "2300354",
        "source_doc_priority": [
            "daily_course_record",
            "exam_attention_report",
            "lab_attention_report",
        ],
        "document_hits": {
            "daily_course_record": True,
            "exam_attention_report": True,
            "lab_attention_report": True,
        },
        "structured_context": {
            "document_inventory": [
                {
                    "source_table": "daily_course_record",
                    "content": "今日日常病程记录正文",
                },
                {
                    "source_table": "exam_attention_report",
                    "content": "1. 2026-03-22 血管彩超提示动脉粥样硬化。",
                },
                {
                    "source_table": "lab_attention_report",
                    "content": "1. 2026-03-22 ESR 29，参考范围 0-20，异常标记 H。",
                },
            ],
        },
    }

    documents = extract_bundle_documents(bundle)

    assert [item["source_table"] for item in documents] == [
        "daily_course_record",
        "exam_attention_report",
        "lab_attention_report",
    ]
    assert documents[1]["document_type"] == "检查关注摘要"
    assert documents[2]["document_type"] == "检验关注摘要"
