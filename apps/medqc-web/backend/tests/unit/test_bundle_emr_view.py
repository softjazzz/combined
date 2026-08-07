from app.services.bundles import emr_view as emr_view_module
from app.services.bundles.contracts import BUNDLE_SCHEMA_VERSION_CURRENT
from app.services.bundles.emr_view import (
    _course_bundle_needs_exam_lab_refresh,
    build_documents_from_domain_bundles,
    build_documents_tree,
    build_render_view,
    load_bundle_documents,
    pick_document,
)


def test_old_course_bundle_without_exam_lab_coverage_requires_refresh():
    assert _course_bundle_needs_exam_lab_refresh({"structured_context": {}}) is True


def test_course_bundle_with_complete_exam_lab_coverage_does_not_require_refresh():
    coverage = {
        key: {"row_count": 0, "hit": False}
        for key in (
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item_report",
            "pathology_exam_master",
            "pathology_exam_report",
        )
    }

    assert _course_bundle_needs_exam_lab_refresh(
        {
            "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
            "structured_context": {"source_table_coverage": coverage},
        }
    ) is False


def test_course_bundle_with_previous_schema_requires_report_grouping_refresh():
    coverage = {
        key: {"row_count": 0, "hit": False}
        for key in (
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item_report",
            "pathology_exam_master",
            "pathology_exam_report",
        )
    }

    assert _course_bundle_needs_exam_lab_refresh(
        {
            "bundle_schema_version": "bundle-v4",
            "structured_context": {"source_table_coverage": coverage},
        }
    ) is True


def test_build_documents_should_preserve_grouped_report_payload():
    documents = build_documents_from_domain_bundles(
        {
            "course": {
                "source_documents": [
                    {
                        "document_type": "labtest_item_report",
                        "document_id": "LAB-1",
                        "document_title": "血常规检验报告",
                        "display_time": "2026-02-21 07:45:30",
                        "content": "检验结果",
                        "report_metadata": {"specimen": "外周血"},
                        "report_items": [
                            {"item_name": "白细胞计数", "result": "4.95"},
                            {"item_name": "血小板计数", "result": "254"},
                        ],
                    }
                ]
            }
        }
    )

    assert len(documents) == 1
    assert documents[0]["doc_key"] == "labtest_item_report::LAB-1"
    assert documents[0]["report_metadata"] == {"specimen": "外周血"}
    assert len(documents[0]["report_items"]) == 2


def test_build_documents_should_collapse_unmatched_lab_applications_into_one_summary():
    documents = build_documents_from_domain_bundles(
        {
            "course": {
                "source_documents": [
                    {
                        "document_type": "labtest_master",
                        "document_id": "LAB-M-1",
                        "document_title": "检验申请单",
                        "display_time": "2026-04-03 17:43:59",
                        "content": "检验项目：血常规",
                        "source_fields": [
                            {
                                "source_field": "labtest_subject",
                                "raw_value_preview": "临检实验室",
                                "used": True,
                            }
                        ],
                    },
                    {
                        "document_type": "labtest_master",
                        "document_id": "LAB-M-2",
                        "document_title": "检验申请单",
                        "display_time": "2026-04-03 18:06:47",
                        "content": "检验项目：肝功能",
                        "source_fields": [
                            {
                                "source_field": "labtest_subject",
                                "raw_value_preview": "生化实验室",
                                "used": True,
                            }
                        ],
                    },
                ]
            }
        }
    )

    lab_applications = [doc for doc in documents if doc["doc_type"] == "labtest_master"]
    assert len(lab_applications) == 1
    assert lab_applications[0]["doc_name"] == "检验申请汇总（2）"
    assert lab_applications[0]["content"].startswith(
        "当前仅同步到检验申请，检验结果明细尚未同步。"
    )
    assert "2026-04-03 17:43:59 · 临检实验室 · 血常规" in lab_applications[0]["content"]
    assert "2026-04-03 18:06:47 · 生化实验室 · 肝功能" in lab_applications[0]["content"]


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


def test_build_documents_should_deduplicate_pathology_document_shared_by_course_and_surgery():
    pathology_report = {
        "document_type": "pathology_exam_report",
        "document_id": "pathology-report-1",
        "document_title": "病理检查报告",
        "display_time": "2026-03-02 10:00:00",
        "content": "病理报告正文。",
        "source_fields": [],
    }
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "daily_course_record",
                    "document_id": "course-1",
                    "document_title": "日常病程记录",
                    "content": "病程正文。",
                    "source_fields": [],
                },
                pathology_report,
            ]
        },
        "surgery": {"source_documents": [pathology_report]},
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    pathology_documents = [doc for doc in documents if doc["doc_type"] == "pathology_exam_report"]
    assert len(pathology_documents) == 1
    assert pathology_documents[0]["doc_key"] == "pathology_exam_report::pathology-report-1"


def test_build_documents_should_keep_distinct_pathology_reports_with_distinct_stable_ids():
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "pathology_exam_report",
                    "document_id": "pathology-report-1",
                    "document_title": "病理检查报告",
                    "content": "报告甲。",
                    "source_fields": [],
                },
                {
                    "document_type": "pathology_exam_report",
                    "document_id": "pathology-report-2",
                    "document_title": "病理检查报告",
                    "content": "报告乙。",
                    "source_fields": [],
                },
            ]
        },
        "surgery": {
            "source_documents": [
                {
                    "document_type": "pathology_exam_report",
                    "document_id": "pathology-report-1",
                    "document_title": "病理检查报告",
                    "content": "报告甲。",
                    "source_fields": [],
                }
            ]
        },
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    pathology_documents = [doc for doc in documents if doc["doc_type"] == "pathology_exam_report"]
    assert [doc["doc_key"] for doc in pathology_documents] == [
        "pathology_exam_report::pathology-report-1",
        "pathology_exam_report::pathology-report-2",
    ]


def test_build_documents_should_restore_order_display_time_from_persisted_source_fields():
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "inpat_drug_order",
                    "document_id": "order-1",
                    "document_title": "长期医嘱",
                    "content": "药品医嘱正文。",
                    "source_fields": [
                        {
                            "source_field": "prescribed_datetime",
                            "raw_value_preview": "2025-10-07 08:53:16",
                        }
                    ],
                }
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)
    tree = build_documents_tree(documents)

    assert documents[0]["sort_time"] == "2025-10-07 08:53:16"
    order_node = next(node for group in tree for node in group["children"] if node["doc_type"] == "inpat_drug_order")
    assert order_node["record_time"] == "2025-10-07 08:53:16"


def test_build_documents_should_merge_only_named_admission_diagnoses():
    domain_bundles = {
        "admission": {
            "source_documents": [
                {
                    "document_type": "admission_record",
                    "document_id": "adm-1",
                    "document_title": "入院记录",
                    "display_time": "2026-03-01 08:00:00",
                    "content": "主诉：腹痛3天",
                    "source_fields": [],
                },
                {
                    "document_type": "admission_record_diagnosis",
                    "document_id": "adm-1::diagnosis::1",
                    "document_title": "入院记录诊断-入院诊断-1",
                    "display_time": "2026-03-01 09:00:00",
                    "content": "诊断类型: 入院诊断",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "入院诊断"},
                        {"source_field": "diagnosis_id", "used": True, "raw_value_preview": "1"},
                    ],
                },
                {
                    "document_type": "admission_record_diagnosis",
                    "document_id": "adm-1::diagnosis::2",
                    "document_title": "入院记录诊断-初步诊断-2",
                    "display_time": "2026-03-01 09:00:00",
                    "content": "诊断类型: 初步诊断\n诊断名称: 1、右侧肩袖损伤；2、疼痛",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "初步诊断"},
                        {"source_field": "diagnosis_name", "used": True, "raw_value_preview": "1、右侧肩袖损伤；2、疼痛"},
                    ],
                },
                {
                    "document_type": "admission_record_diagnosis",
                    "document_id": "adm-1::diagnosis::3",
                    "document_title": "入院记录诊断-出院诊断-3",
                    "display_time": "2026-03-01 09:00:00",
                    "content": "诊断类型: 出院诊断\n诊断名称: 出院诊断污染了入院记录正文",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "出院诊断"},
                        {"source_field": "diagnosis_name", "used": True, "raw_value_preview": "出院诊断污染了入院记录正文"},
                    ],
                },
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    admission_doc = next(doc for doc in documents if doc["doc_type"] == "admission_record")
    assert len(documents) == 1
    assert not any(doc["doc_type"] == "admission_record_diagnosis" for doc in documents)
    assert admission_doc["doc_name"] == "入院记录"
    assert admission_doc["sort_time"] == "2026-03-01 08:00:00"
    assert "主诉：腹痛3天" in admission_doc["content"]
    assert "初步诊断" in admission_doc["content"]
    assert "第一诊断: 右侧肩袖损伤" in admission_doc["content"]
    assert "其他诊断: 疼痛" in admission_doc["content"]
    assert "右侧肩袖损伤" in admission_doc["content"]
    assert "诊断序号" not in admission_doc["content"]
    assert "诊断类型: 入院诊断" not in admission_doc["content"]
    assert "出院诊断污染" not in admission_doc["content"]
    assert admission_doc["sections"][-1]["section_label"] == "入院记录诊断"


def test_build_documents_should_merge_first_course_diagnoses_into_first_course_record():
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "first_course_record",
                    "document_id": "first-course-1",
                    "document_title": "首次病程记录",
                    "display_time": "2026-03-01 10:00:00",
                    "content": "病例特点：患者因颈背部包块入院。",
                    "source_fields": [],
                },
                {
                    "document_type": "first_course_record_diagnosis",
                    "document_id": "diagnosis-row-1",
                    "document_title": "首次病程诊断-初步诊断-1",
                    "content": "诊断类型: 初步诊断\n诊断名称: 颈背部脂肪瘤",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "初步诊断"},
                        {"source_field": "diagnosis_no", "used": True, "raw_value_preview": "1"},
                        {"source_field": "diagnosis_name", "used": True, "raw_value_preview": "颈背部脂肪瘤"},
                    ],
                },
                {
                    "document_type": "first_course_record_diagnosis",
                    "document_id": "diagnosis-row-2",
                    "document_title": "首次病程诊断-初步诊断-2",
                    "content": "诊断类型: 初步诊断\n诊断名称: 肺结节",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "初步诊断"},
                        {"source_field": "diagnosis_no", "used": True, "raw_value_preview": "2"},
                        {"source_field": "diagnosis_name", "used": True, "raw_value_preview": "肺结节"},
                    ],
                },
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    assert len(documents) == 1
    assert not any(doc["doc_type"] == "first_course_record_diagnosis" for doc in documents)
    first_course_doc = documents[0]
    assert first_course_doc["doc_type"] == "first_course_record"
    assert first_course_doc["doc_name"] == "首次病程记录"
    assert "病例特点：患者因颈背部包块入院。" in first_course_doc["content"]
    assert "首次病程诊断" in first_course_doc["content"]
    assert "第一诊断: 颈背部脂肪瘤" in first_course_doc["content"]
    assert "其他诊断: 肺结节" in first_course_doc["content"]
    assert first_course_doc["sections"][-1]["section_label"] == "首次病程诊断"


def test_build_documents_should_merge_only_discharge_diagnoses():
    domain_bundles = {
        "terminal": {
            "source_documents": [
                {
                    "document_type": "discharge_record",
                    "document_id": "dis-1",
                    "document_title": "出院记录",
                    "display_time": "2026-03-08 10:00:00",
                    "content": "出院情况：好转",
                    "source_fields": [],
                },
                {
                    "document_type": "discharge_record_diagnosis",
                    "document_id": "dis-2::diagnosis::1",
                    "document_title": "出院记录诊断-出院诊断-1",
                    "display_time": "2026-03-08 11:00:00",
                    "content": "诊断类型: 出院诊断\n诊断名称: 急性阑尾炎\n是否主诊断: 是",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "出院诊断"},
                        {"source_field": "diagnosis_name", "used": True, "raw_value_preview": "急性阑尾炎"},
                        {"source_field": "diagnosis_main", "used": True, "raw_value_preview": "是"},
                    ],
                },
                {
                    "document_type": "discharge_record_diagnosis",
                    "document_id": "dis-2::diagnosis::2",
                    "document_title": "出院记录诊断-出院诊断-2",
                    "display_time": "2026-03-08 11:00:00",
                    "content": "诊断类型: 出院诊断\n诊断名称: 腹腔感染\n是否主诊断: 否",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "出院诊断"},
                        {"source_field": "diagnosis_name", "used": True, "raw_value_preview": "腹腔感染"},
                        {"source_field": "diagnosis_main", "used": True, "raw_value_preview": "否"},
                    ],
                },
                {
                    "document_type": "discharge_record_diagnosis",
                    "document_id": "dis-2::diagnosis::3",
                    "document_title": "出院记录诊断-初步诊断-3",
                    "display_time": "2026-03-08 11:00:00",
                    "content": "诊断类型: 初步诊断\n诊断名称: 初步诊断不应进入出院记录",
                    "source_fields": [
                        {"source_field": "diagnosis_type", "used": True, "raw_value_preview": "初步诊断"},
                        {"source_field": "diagnosis_name", "used": True, "raw_value_preview": "初步诊断不应进入出院记录"},
                    ],
                },
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    discharge_doc = next(doc for doc in documents if doc["doc_type"] == "discharge_record")
    assert len(documents) == 1
    assert not any(doc["doc_type"] == "discharge_record_diagnosis" for doc in documents)
    assert discharge_doc["doc_name"] == "出院记录"
    assert discharge_doc["sort_time"] == "2026-03-08 10:00:00"
    assert "出院情况：好转" in discharge_doc["content"]
    assert "出院诊断" in discharge_doc["content"]
    assert "主诊断: 急性阑尾炎" in discharge_doc["content"]
    assert "其他诊断: 腹腔感染" in discharge_doc["content"]
    assert discharge_doc["content"].count("诊断类型: 出院诊断") == 1
    assert "初步诊断不应进入出院记录" not in discharge_doc["content"]
    assert discharge_doc["sections"][-1]["section_label"] == "出院记录诊断"


def test_build_documents_should_expose_display_time_when_record_time_missing():
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "first_course_record",
                    "document_id": "first-1",
                    "document_title": "首次病程记录",
                    "record_time": "",
                    "display_time": "2026-06-10 08:26:37",
                    "content": "患者为70岁男性，起病缓，病程长。",
                    "source_fields": [],
                }
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    first_course_doc = next(doc for doc in documents if doc["doc_type"] == "first_course_record")
    assert first_course_doc["sort_time"] == "2026-06-10 08:26:37"
    assert first_course_doc["record_time"] == "2026-06-10 08:26:37"
    assert first_course_doc["record_time_source"] == "fallback_display_time"
    assert "源库未返回记录时间" in first_course_doc["record_time_note"]


def test_build_documents_should_expose_senior_round_display_time_when_record_time_missing():
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "senior_course_record",
                    "document_id": "round-1",
                    "document_title": "彭中主任医师查房记录",
                    "record_time": "",
                    "display_time": "2026-06-21 17:05:00",
                    "content": "今日随彭中主任医师查房，患者病情变化记录。",
                    "source_fields": [],
                }
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    round_doc = next(doc for doc in documents if doc["doc_type"] == "senior_course_record")
    assert round_doc["sort_time"] == "2026-06-21 17:05:00"
    assert round_doc["record_time"] == "2026-06-21 17:05:00"
    assert round_doc["record_time_source"] == "fallback_display_time"
    assert "源库未返回记录时间" in round_doc["record_time_note"]


def test_build_documents_should_expose_transfer_display_time_when_record_time_missing():
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "transfer_in_record",
                    "document_id": "transfer-in-1",
                    "document_title": "转入记录",
                    "record_time": "",
                    "display_time": "2026-06-21 17:05:00",
                    "content": "患者由外科转入本科继续治疗。",
                    "source_fields": [],
                },
                {
                    "document_type": "transfer_out_record",
                    "document_id": "transfer-out-1",
                    "document_title": "转出记录",
                    "record_time": "",
                    "display_time": "2026-06-22 11:27:47",
                    "content": "患者转出至重症医学科进一步治疗。",
                    "source_fields": [],
                },
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    transfer_in_doc = next(doc for doc in documents if doc["doc_type"] == "transfer_in_record")
    transfer_out_doc = next(doc for doc in documents if doc["doc_type"] == "transfer_out_record")
    assert transfer_in_doc["record_time"] == "2026-06-21 17:05:00"
    assert transfer_out_doc["record_time"] == "2026-06-22 11:27:47"
    assert transfer_in_doc["record_time_source"] == "fallback_display_time"
    assert transfer_out_doc["record_time_source"] == "fallback_display_time"
    assert "源库未返回记录时间" in transfer_in_doc["record_time_note"]
    assert "源库未返回记录时间" in transfer_out_doc["record_time_note"]


def test_build_documents_should_expose_discharge_display_time_when_record_time_missing():
    domain_bundles = {
        "terminal": {
            "source_documents": [
                {
                    "document_type": "discharge_record",
                    "document_id": "discharge-1",
                    "document_title": "出院记录",
                    "record_time": "",
                    "display_time": "2026-07-10 20:19:03",
                    "content": "出院情况：好转。",
                    "source_fields": [],
                }
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)

    assert len(documents) == 1
    discharge_doc = documents[0]
    assert discharge_doc["record_time"] == "2026-07-10 20:19:03"
    assert discharge_doc["record_time_source"] == "fallback_display_time"
    assert "源库未返回记录时间" in discharge_doc["record_time_note"]


def test_build_documents_should_expose_surgery_form_display_time_when_record_time_missing():
    domain_bundles = {
        "surgery": {
            "source_documents": [
                {
                    "document_type": "presurg_summary",
                    "document_id": "summary-1",
                    "document_title": "术前小结记录",
                    "record_time": "",
                    "display_time": "2026-07-07 19:42:23",
                    "content": "手术适应症：明确。",
                },
                {
                    "document_type": "surgery_safecheck_record",
                    "document_id": "safecheck-1",
                    "document_title": "手术安全核查记录",
                    "record_time": "",
                    "display_time": "2026-07-07 16:14:26",
                    "content": "手术时间：2026-07-07 16:30:00",
                },
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)
    documents_by_type = {item["doc_type"]: item for item in documents}

    summary = documents_by_type["presurg_summary"]
    safecheck = documents_by_type["surgery_safecheck_record"]
    assert summary["record_time"] == "2026-07-07 19:42:23"
    assert safecheck["record_time"] == "2026-07-07 16:14:26"
    assert summary["record_time_source"] == "fallback_display_time"
    assert safecheck["record_time_source"] == "fallback_display_time"
    assert "源库未返回记录时间" in summary["record_time_note"]
    assert "源库未返回记录时间" in safecheck["record_time_note"]


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


def test_pick_document_prefers_type_when_document_id_is_reused():
    docs = [
        {
            "id": "4632166||28",
            "doc_id": "4632166||28",
            "document_id": "4632166||28",
            "doc_key": "daily_course_record::4632166||28",
            "doc_type": "daily_course_record",
            "doc_name": "今日王春萌主治医师查房",
            "has_content": True,
        },
        {
            "id": "4632166||28",
            "doc_id": "4632166||28",
            "document_id": "4632166||28",
            "doc_key": "senior_course_record::4632166||28",
            "doc_type": "senior_course_record",
            "doc_name": "王春萌主治医师查房记录",
            "has_content": True,
        },
    ]

    picked = pick_document(
        documents=docs,
        doc_type="senior_course_record",
        doc_id="4632166||28",
    )

    assert picked is not None
    assert picked["doc_key"] == "senior_course_record::4632166||28"


def test_build_documents_should_keep_senior_round_display_time_when_id_is_reused():
    domain_bundles = {
        "course": {
            "source_documents": [
                {
                    "document_type": "daily_course_record",
                    "document_id": "4632166||28",
                    "document_title": "今日王春萌主治医师查房",
                    "record_time": "2026-04-15 08:35:46",
                    "display_time": "2026-04-15 08:35:46",
                    "content": "今日王春萌主治医师查房后指出: 术后第10天。",
                    "source_fields": [],
                },
                {
                    "document_type": "senior_course_record",
                    "document_id": "4632166||28",
                    "document_title": "王春萌主治医师查房记录",
                    "record_time": "",
                    "display_time": "2026-04-19 09:39:42",
                    "content": "查房内容：今日王春萌主治医师查房后指出：术后第10天。",
                    "source_fields": [],
                },
            ]
        }
    }

    documents = build_documents_from_domain_bundles(domain_bundles)
    senior_doc = next(doc for doc in documents if doc["doc_type"] == "senior_course_record")

    assert senior_doc["record_time"] == "2026-04-19 09:39:42"
    assert senior_doc["record_time_source"] == "fallback_display_time"
    assert senior_doc["sort_time"] == "2026-04-19 09:39:42"

    tree = build_documents_tree(documents)
    senior_node = next(
        node
        for group in tree
        for node in group["children"]
        if node["doc_key"] == "senior_course_record::4632166||28"
    )
    assert senior_node["record_time"] == "2026-04-19 09:39:42"


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
        "document_id": "ADM-001",
        "authors": [{"role": "submitter", "name": "张医生", "code": "D001"}],
        "signatures": [
            {
                "role": "physician",
                "name": "李医生",
                "signed_at": "2026-08-01 08:30:00",
                "source_field": "physician_sign",
            }
        ],
        "projection_incomplete": True,
        "projection_notice": "已展示20条，仍有更多。",
    }

    payload = build_render_view(document)
    assert payload["layout_version"] == "bundle_struct_v1"
    assert payload["document_meta"]["doc_type"] == "admission_record"
    assert payload["document_meta"]["document_id"] == "ADM-001"
    assert payload["document_meta"]["authors"] == [{"role": "submitter", "name": "张医生", "code": "D001"}]
    assert payload["document_meta"]["signatures"][0]["name"] == "李医生"
    assert payload["document_meta"]["projection_incomplete"] is True
    assert payload["document_meta"]["projection_notice"] == "已展示20条，仍有更多。"
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
    assert by_key["lab_results"]["label"] == "检验报告"
    assert by_key["exam_results"]["count"] == 1


def test_bundle_documents_response_should_expose_domain_projection_and_tree_marker(monkeypatch):
    bundle = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
        "source_documents": [
            {
                "document_type": "labtest_item_report",
                "document_id": "LAB-001",
                "document_title": "血常规检验报告",
                "display_time": "2026-08-01 09:00:00",
                "record_time": "2026-08-01 09:00:00",
                "content": "白细胞计数：4.5",
                "authors": [{"role": "reporter", "name": "检验师"}],
                "signatures": [{"role": "verifier", "name": "审核医师"}],
                "projection_incomplete": True,
                "projection_notice": "已展示3条，仍有更多。",
            }
        ],
        "structured_context": {
            "domain_projection": {
                "projection_kind": "domain_documents",
                "is_evidence_source": False,
                "per_source": {
                    "labtest_item_report": {
                        "projected_count": 3,
                        "projection_limit": 3,
                        "has_more": True,
                    }
                },
            }
        },
    }

    monkeypatch.setattr(emr_view_module, "load_domain_bundle", lambda **_kwargs: bundle)
    monkeypatch.setattr(
        emr_view_module,
        "load_or_assemble_domain_bundle",
        lambda **_kwargs: bundle,
    )

    payload = load_bundle_documents(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        bundle_schema="public",
    )

    assert payload["domain_projection"]["projection_kind"] == "domain_documents"
    assert payload["domain_projection"]["is_evidence_source"] is False
    assert payload["domain_projection"]["domains"]["course"]["per_source"][
        "labtest_item_report"
    ]["has_more"] is True
    document = payload["documents"][0]
    assert document["document_id"] == "LAB-001"
    assert document["record_time"] == "2026-08-01 09:00:00"
    assert document["signatures"][0]["name"] == "审核医师"
    tree_node = payload["documents_tree"][0]["children"][0]
    assert tree_node["document_id"] == "LAB-001"
    assert tree_node["projection_incomplete"] is True
    assert tree_node["projection_notice"] == "已展示3条，仍有更多。"
