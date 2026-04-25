from app.services.bundles.emr_view import (
    build_documents_from_domain_bundles,
    build_documents_tree,
    build_render_view,
    pick_document,
)


def test_build_documents_tree_from_domain_bundles():
    domain_bundles = {
        "admission": {
            "source_documents": [
                {
                    "document_type": "admission_record",
                    "document_id": "adm-1",
                    "document_title": "入院记录",
                    "display_time": "2026-03-01 09:00:00",
                    "content": "主诉：腹痛3天",
                    "sections": [
                        {
                            "section_key": "chief_complaint",
                            "section_label": "主诉",
                            "text": "腹痛3天",
                            "source_field": "chief_complaint",
                            "order_index": 0,
                        }
                    ],
                    "source_fields": [
                        {
                            "source_field": "chief_complaint",
                            "used": True,
                            "raw_value_preview": "腹痛3天",
                        }
                    ],
                }
            ]
        },
        "surgery": {
            "source_documents": [
                {
                    "document_type": "surgery_record",
                    "document_id": "surg-1",
                    "document_title": "手术记录",
                    "display_time": "2026-03-02 10:00:00",
                    "content": "手术经过：顺利",
                    "sections": [
                        {
                            "section_key": "record_content",
                            "section_label": "正文",
                            "text": "手术经过：顺利",
                            "source_field": "record_content",
                            "order_index": 0,
                        }
                    ],
                    "source_fields": [],
                }
            ]
        },
    }

    documents = build_documents_from_domain_bundles(domain_bundles)
    assert len(documents) == 2
    assert documents[0]["doc_type"] == "admission_record"
    assert documents[1]["group_key"] == "surgery"

    tree = build_documents_tree(documents)
    by_key = {item["key"]: item for item in tree}
    assert by_key["all"]["count"] == 2
    assert by_key["admission"]["count"] == 1
    assert by_key["surgery"]["count"] == 1


def test_pick_document_priority():
    docs = [
        {
            "id": "a1",
            "doc_id": "a1",
            "doc_key": "admission_record::a1",
            "doc_type": "admission_record",
            "has_content": False,
        },
        {
            "id": "d1",
            "doc_id": "d1",
            "doc_key": "discharge_record::d1",
            "doc_type": "discharge_record",
            "has_content": True,
        },
    ]

    picked_by_type = pick_document(documents=docs, doc_type="admission_record", doc_id="")
    assert picked_by_type is not None
    assert picked_by_type["doc_type"] == "admission_record"

    picked_by_id = pick_document(documents=docs, doc_type="", doc_id="d1")
    assert picked_by_id is not None
    assert picked_by_id["doc_type"] == "discharge_record"

    default_picked = pick_document(documents=docs, doc_type="", doc_id="")
    assert default_picked is not None
    assert default_picked["doc_type"] == "discharge_record"


def test_build_render_view_with_sections_and_kv():
    document = {
        "id": "adm-1",
        "doc_key": "admission_record::adm-1",
        "doc_type": "admission_record",
        "doc_name": "入院记录",
        "group_key": "admission",
        "content": "主诉：腹痛3天\n现病史：间断疼痛",
        "sections": [
            {
                "section_key": "chief_complaint",
                "section_label": "主诉",
                "text": "腹痛3天",
                "source_field": "chief_complaint",
                "order_index": 0,
            },
            {
                "section_key": "history_of_present_illness",
                "section_label": "现病史",
                "text": "间断疼痛",
                "source_field": "history_of_present_illness",
                "order_index": 1,
            },
        ],
        "source_fields": [
            {
                "source_field": "chief_complaint",
                "used": True,
                "raw_value_preview": "腹痛3天",
            },
            {
                "source_field": "history_of_present_illness",
                "used": True,
                "raw_value_preview": "间断疼痛",
            },
        ],
    }

    payload = build_render_view(document)
    assert payload["layout_version"] == "bundle_struct_v1"
    assert payload["document_meta"]["doc_type"] == "admission_record"
    assert len(payload["render_blocks"]) >= 2
    assert payload["render_blocks"][0]["block_type"] == "kv_section"
    assert payload["render_blocks"][1]["block_type"] == "paragraph"
    assert len(payload["highlight_anchors"]) >= 1


def test_build_render_view_order_table_empty_state():
    order_doc = {
        "id": "order-1",
        "doc_key": "inpat_drug_order::order-1",
        "doc_type": "inpat_drug_order",
        "doc_name": "长期医嘱",
        "group_key": "orders",
        "content": "",
        "sections": [],
        "source_fields": [],
    }

    payload = build_render_view(order_doc)
    assert payload["layout_version"] == "bundle_struct_v1"
    assert payload["render_blocks"][0]["block_type"] == "order_table"
    assert payload["render_blocks"][0]["empty"] is True


def test_build_documents_tree_should_group_exam_and_lab_documents():
    documents = [
        {
            "id": "exam-attn-1",
            "doc_id": "exam-attn-1",
            "doc_key": "exam_attention_report::exam-attn-1",
            "doc_type": "exam_attention_report",
            "doc_name": "检查关注摘要",
            "group_key": "exam_attention",
            "has_content": True,
            "length": 120,
            "sort_time": "2026-03-25 10:00:00",
        },
        {
            "id": "lab-1",
            "doc_id": "lab-1",
            "doc_key": "labtest_item_report::lab-1",
            "doc_type": "labtest_item_report",
            "doc_name": "检验明细：ESR",
            "group_key": "lab_results",
            "has_content": True,
            "length": 88,
            "sort_time": "2026-03-25 10:01:00",
        },
        {
            "id": "exam-1",
            "doc_id": "exam-1",
            "doc_key": "exam_master::exam-1",
            "doc_type": "exam_master",
            "doc_name": "检查结果：血管彩超",
            "group_key": "exam_results",
            "has_content": True,
            "length": 140,
            "sort_time": "2026-03-25 10:02:00",
        },
    ]

    tree = build_documents_tree(documents)
    by_key = {item["key"]: item for item in tree}

    assert by_key["exam_attention"]["count"] == 1
    assert by_key["lab_results"]["count"] == 1
    assert by_key["exam_results"]["count"] == 1
