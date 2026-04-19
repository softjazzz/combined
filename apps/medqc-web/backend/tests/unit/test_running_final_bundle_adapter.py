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
