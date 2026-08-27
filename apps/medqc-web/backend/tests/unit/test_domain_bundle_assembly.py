from app.services.bundles import assembly as assembly_module


def test_document_inventory_should_group_lab_items_into_one_report(monkeypatch):
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    inventory = assembly_module._build_document_inventory(
        {
            "labtest_master": [
                {
                    "test_id": "LAB-1",
                    "labtest_subject": "血常规",
                    "specimen": "外周血",
                    "request_datetime": "2026-02-20 21:55:46",
                    "report_datetime": "2026-02-21 07:45:30",
                }
            ],
            "labtest_item_report": [
                {
                    "document_id": "item-doc-1",
                    "test_id": "LAB-1",
                    "test_no": "T-001",
                    "item_no": "1",
                    "item_name": "白细胞计数",
                    "result": "4.95",
                    "unit": "*10^9/L",
                    "reference_range": "3.5-9.5",
                    "report_time": "2026-02-21 07:45:30",
                },
                {
                    "document_id": "item-doc-2",
                    "test_id": "LAB-1",
                    "test_no": "T-001",
                    "item_no": "2",
                    "item_name": "血小板计数",
                    "result": "254",
                    "unit": "*10^9/L",
                    "reference_range": "125-350",
                    "report_time": "2026-02-21 07:45:30",
                },
            ],
        },
        "cdm",
    )

    assert len(inventory) == 1
    report = inventory[0]
    assert report["document_type"] == "labtest_item_report"
    assert report["document_id"] == "T-001"
    assert report["document_title"] == "血常规检验报告"
    assert report["display_time"] == "2026-02-21 07:45:30"
    assert [item["item_name"] for item in report["report_items"]] == ["白细胞计数", "血小板计数"]
    assert "白细胞计数：4.95" in report["content"]
    assert "血小板计数：254" in report["content"]


def test_document_inventory_should_group_lab_items_by_report_number_before_item_test_id(monkeypatch):
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    inventory = assembly_module._build_document_inventory(
        {
            "labtest_item_report": [
                {
                    "test_no": "REPORT-001",
                    "test_id": "ITEM-TEST-001",
                    "item_no": "1",
                    "item_name": "白细胞计数",
                    "result": "4.95",
                    "report_time": "2026-02-21 07:45:30",
                },
                {
                    "test_no": "REPORT-001",
                    "test_id": "ITEM-TEST-002",
                    "item_no": "2",
                    "item_name": "血小板计数",
                    "result": "254",
                    "report_time": "2026-02-21 07:45:30",
                },
            ],
        },
        "cdm",
    )

    assert len(inventory) == 1
    assert inventory[0]["document_id"] == "REPORT-001"
    assert [item["item_name"] for item in inventory[0]["report_items"]] == [
        "白细胞计数",
        "血小板计数",
    ]


def test_document_inventory_should_not_merge_different_lab_report_numbers(monkeypatch):
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    inventory = assembly_module._build_document_inventory(
        {
            "labtest_item_report": [
                {
                    "test_no": "REPORT-001",
                    "test_id": "SHARED-TEST-ID",
                    "item_no": "1",
                    "item_name": "白细胞计数",
                    "result": "4.95",
                },
                {
                    "test_no": "REPORT-002",
                    "test_id": "SHARED-TEST-ID",
                    "item_no": "1",
                    "item_name": "尿蛋白",
                    "result": "阴性",
                },
            ],
        },
        "cdm",
    )

    assert len(inventory) == 2
    assert {item["document_id"] for item in inventory} == {"REPORT-001", "REPORT-002"}


def test_document_inventory_should_group_exam_items_into_one_report(monkeypatch):
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    inventory = assembly_module._build_document_inventory(
        {
            "exam_master": [
                {
                    "exam_id": "EXAM-1",
                    "exam_type": "CT",
                    "exam_time": "2026-02-21 09:00:00",
                    "report_time": "2026-02-21 10:30:00",
                }
            ],
            "exam_item_report": [
                {
                    "document_id": "exam-item-doc-1",
                    "exam_id": "EXAM-1",
                    "exam_no": "E-001",
                    "item_no": "1",
                    "exam_name": "胸部CT平扫",
                    "exam_findings": "双肺纹理增多。",
                    "exam_impression": "双肺炎症可能。",
                    "report_time": "2026-02-21 10:30:00",
                },
                {
                    "document_id": "exam-item-doc-2",
                    "exam_id": "EXAM-1",
                    "exam_no": "E-001",
                    "item_no": "2",
                    "exam_name": "纵隔窗",
                    "exam_findings": "纵隔未见明显肿大淋巴结。",
                    "report_time": "2026-02-21 10:30:00",
                },
            ],
        },
        "cdm",
    )

    assert len(inventory) == 1
    report = inventory[0]
    assert report["document_type"] == "exam_item_report"
    assert report["document_id"] == "E-001"
    assert report["document_title"] == "胸部CT平扫检查报告"
    assert len(report["report_items"]) == 2
    assert "双肺纹理增多" in report["content"]
    assert "双肺炎症可能" in report["content"]


def test_course_bundle_should_keep_raw_lab_rows_but_publish_one_report(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "labtest_master":
            return [{"test_id": "LAB-1", "labtest_subject": "血常规"}]
        if kwargs["table"] == "labtest_item_report":
            return [
                {
                    "test_id": "LAB-1",
                    "item_no": "1",
                    "item_name": "白细胞计数",
                    "result": "4.95",
                    "report_time": "2026-02-21 07:45:30",
                },
                {
                    "test_id": "LAB-1",
                    "item_no": "2",
                    "item_name": "血小板计数",
                    "result": "254",
                    "report_time": "2026-02-21 07:45:30",
                },
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda _docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="course",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    assert len(bundle["structured_context"]["documents"]["labtest_item_report"]) == 2
    published_reports = [
        item
        for item in bundle["source_documents"]
        if item["document_type"] == "labtest_item_report"
    ]
    assert len(published_reports) == 1
    assert len(published_reports[0]["report_items"]) == 2


def test_course_domain_bundle_should_assemble_first_course_structured_fields(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "first_course_record":
            return [
                {
                    "document_id": "first-course-1",
                    "case_characteristic": "患者因胸痛入院。",
                    "diagnose_based_on": "心电图提示ST-T改变。",
                    "differential_diagnosis": "需鉴别肺栓塞。",
                    "treatment_plan": "完善心肌酶并予抗血小板治疗。",
                }
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="course",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    context = bundle["structured_context"]
    assert context["source_table_coverage"]["first_course_record"]["row_count"] == 1
    assert context["assembly_coverage"]["first_course_record"]["assembled_count"] == 1
    assert "diagnose_based_on" in context["assembly_coverage"]["first_course_record"]["used_source_fields"]


def test_course_domain_bundle_should_assemble_transfer_structured_fields(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "transfer_in_record":
            return [
                {
                    "document_id": "transfer-in-1",
                    "transfer_purpose": "转入心内科进一步诊治。",
                    "treatment_course": "已予抗感染治疗。",
                    "transfer_treatment_plan": "完善心电图并调整治疗。",
                }
            ]
        if kwargs["table"] == "transfer_out_record":
            return [
                {
                    "document_id": "transfer-out-1",
                    "transfer_purpose": "转出至骨科继续处理。",
                    "treatment_course": "已完成清创换药。",
                    "current_situation": "生命体征平稳。",
                }
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="course",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    context = bundle["structured_context"]
    assert context["assembly_coverage"]["transfer_in_record"]["assembled_count"] == 1
    assert context["assembly_coverage"]["transfer_out_record"]["assembled_count"] == 1
    assert "transfer_treatment_plan" in context["assembly_coverage"]["transfer_in_record"]["used_source_fields"]
    assert "current_situation" in context["assembly_coverage"]["transfer_out_record"]["used_source_fields"]


def test_course_domain_bundle_should_keep_contentful_bloodtrans_record(monkeypatch):
    select_calls: list[dict[str, object]] = []

    def _fake_select_records(**kwargs):
        select_calls.append(kwargs)
        if kwargs["table"] == "bloodtrans_record":
            return [
                {
                    "document_id": "bloodtrans-1",
                    "document_title": "输血记录",
                    "submit_datetime": "2026-07-10 20:19:03",
                    "record_content": "输入A型Rh(D)阳性红细胞悬液1u，输血过程顺利。",
                }
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="course",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    context = bundle["structured_context"]
    assert context["source_table_coverage"]["bloodtrans_record"]["row_count"] == 1
    assert context["documents"]["bloodtrans_record"][0]["record_content"].startswith("输入A型")
    assert any(
        item["document_type"] == "bloodtrans_record"
        and item["content"].startswith("输入A型")
        and item["display_time"] == "2026-07-10 20:19:03"
        for item in bundle["source_documents"]
    )
    bloodtrans_call = next(item for item in select_calls if item["table"] == "bloodtrans_record")
    assert bloodtrans_call["limit"] == 51


def test_assemble_domain_bundle_should_keep_more_than_three_course_documents(monkeypatch):
    course_rows = [
        {
            "document_id": f"doc-{index}",
            "record_time": f"2026-03-{index + 10:02d} 08:00:00",
            "record_content": f"病程记录-{index}",
        }
        for index in range(5)
    ]
    select_calls: list[dict[str, object]] = []

    def _fake_select_records(**kwargs):
        select_calls.append(kwargs)
        if kwargs["table"] == "daily_course_record":
            return list(course_rows)
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="course",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    docs = bundle["structured_context"]["documents"]
    assert len(docs["daily_course_record"]) == 5

    daily_call = next(item for item in select_calls if item["table"] == "daily_course_record")
    assert daily_call["limit"] == 201


def test_assemble_domain_bundle_should_emit_source_and_assembly_coverage(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "inpat_bill_item":
            return [
                {
                    "bill_item_id": "B1",
                    "visit_id": "V1",
                    "medical_catalog_name": "康复训练",
                    "billing_datetime": "2026-02-03 09:00:00",
                }
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="consult_discussion",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    context = bundle["structured_context"]
    assert context["source_table_coverage"]["inpat_bill_item"]["row_count"] == 1
    assert context["assembly_coverage"]["inpat_bill_item"]["assembled_count"] == 1
    assert "blood_application" in context["source_table_coverage"]


def test_surgery_domain_bundle_should_cover_postane_and_docpat_records(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "docpat_commu_record":
            return [{"document_id": "D1", "record_content": "已沟通手术风险"}]
        if kwargs["table"] == "postane_surveil_record":
            return [{"document_id": "P1", "record_content": "麻醉术后访视无特殊"}]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="surgery",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    context = bundle["structured_context"]
    assert context["source_table_coverage"]["docpat_commu_record"]["row_count"] == 1
    assert context["assembly_coverage"]["docpat_commu_record"]["assembled_count"] == 1
    assert context["source_table_coverage"]["postane_surveil_record"]["row_count"] == 1
    assert context["assembly_coverage"]["postane_surveil_record"]["assembled_count"] == 1


def test_surgery_domain_bundle_should_cover_pathology_sources(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "pathology_exam_master":
            return [
                {
                    "pathology_exam_id": "PEM1",
                    "specimen_name": "结肠肿物标本",
                    "surgery_name": "结肠肿物切除术",
                    "request_datetime": "2026-02-03 10:00:00",
                }
            ]
        if kwargs["table"] == "pathology_exam_report":
            return [
                {
                    "pathology_exam_id": "PER1",
                    "specimen_name": "结肠肿物标本",
                    "diagnosis": "腺瘤性息肉。",
                    "report_datetime": "2026-02-05 09:00:00",
                }
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="surgery",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    context = bundle["structured_context"]
    assert context["source_table_coverage"]["pathology_exam_master"]["row_count"] == 1
    assert context["source_table_coverage"]["pathology_exam_report"]["row_count"] == 1
    assert context["assembly_coverage"]["pathology_exam_master"]["assembled_count"] == 1
    assert context["assembly_coverage"]["pathology_exam_report"]["assembled_count"] == 1


def test_assemble_final_record_bundle_should_fallback_to_mr_admission_datetime(monkeypatch):
    select_calls: list[dict[str, object]] = []

    def _fake_select_records(**kwargs):
        select_calls.append(kwargs)
        table = kwargs["table"]
        if table == "discharge_record":
            return [{"document_id": "discharge-1", "discharge_datetime": "2026-02-05 10:00:00"}]
        if table == "admission_record":
            return [{"document_id": "admission-1", "admission_datetime": None}]
        if table == "mr":
            return [{"document_id": "mr-1", "admission_datetime": "2026-01-30 10:00:00"}]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_scene_attention_artifacts", lambda **kwargs: ({}, []))
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda schema, table: ())
    monkeypatch.setattr(
        assembly_module,
        "_fetch_patient_profile",
        lambda **kwargs: {"patient_name": "", "mobile": "", "id_card": ""},
    )

    bundle = assembly_module.assemble_final_record_bundle(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    assert bundle["structured_context"]["admission_datetime"] == "2026-01-30 10:00:00"

    mr_call = next(item for item in select_calls if item["table"] == "mr")
    assert mr_call["limit"] == 1


def test_assemble_final_record_bundle_should_cover_pathology_sources(monkeypatch):
    def _fake_select_records(**kwargs):
        table = kwargs["table"]
        if table == "pathology_exam_master":
            return [{"pathology_exam_id": "PEM1", "specimen_name": "阑尾标本"}]
        if table == "pathology_exam_report":
            return [{"pathology_exam_id": "PER1", "specimen_name": "阑尾标本", "diagnosis": "急性阑尾炎。"}]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_scene_attention_artifacts", lambda **kwargs: ({}, []))
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda schema, table: ())
    monkeypatch.setattr(
        assembly_module,
        "_fetch_patient_profile",
        lambda **kwargs: {"patient_name": "", "mobile": "", "id_card": ""},
    )

    bundle = assembly_module.assemble_final_record_bundle(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    context = bundle["structured_context"]
    assert context["source_table_coverage"]["pathology_exam_master"]["row_count"] == 1
    assert context["source_table_coverage"]["pathology_exam_report"]["row_count"] == 1
    assert context["assembly_coverage"]["pathology_exam_master"]["assembled_count"] == 1
    assert context["assembly_coverage"]["pathology_exam_report"]["assembled_count"] == 1


def test_assemble_final_record_bundle_should_fallback_to_admission_record_time(monkeypatch):
    def _fake_select_records(**kwargs):
        table = kwargs["table"]
        if table == "discharge_record":
            return [{"document_id": "discharge-1", "discharge_datetime": "2026-02-05 10:00:00"}]
        if table == "admission_record":
            return [{"document_id": "admission-1", "admission_datetime": None, "record_time": "2026-01-24 20:42:25"}]
        if table == "mr":
            return [{"document_id": "mr-1", "admission_datetime": None}]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_scene_attention_artifacts", lambda **kwargs: ({}, []))
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda schema, table: ())
    monkeypatch.setattr(
        assembly_module,
        "_fetch_patient_profile",
        lambda **kwargs: {"patient_name": "", "mobile": "", "id_card": ""},
    )

    bundle = assembly_module.assemble_final_record_bundle(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    assert bundle["structured_context"]["admission_datetime"] == "2026-01-24 20:42:25"


def test_running_bundle_projects_discharge_record_without_expanding_medical_text(monkeypatch):
    def _fake_select_records(**kwargs):
        table = kwargs["table"]
        if table == "admission_record":
            return [{"document_id": "admission-1", "record_content": "入院主文书"}]
        if table == "discharge_record":
            return [{"document_id": "discharge-1", "record_content": "出院补充文书"}]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_scene_attention_artifacts", lambda **kwargs: ({}, []))
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda schema, table: ())
    monkeypatch.setattr(
        assembly_module,
        "_fetch_patient_profile",
        lambda **kwargs: {"patient_name": "", "mobile": "", "id_card": ""},
    )

    bundle = assembly_module.assemble_running_record_bundle(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    assert bundle["document_hits"]["discharge_record"] is True
    assert "discharge_record" in bundle["source_doc_priority"]
    assert "出院补充文书" not in bundle["medical_text"]
    assert any(
        item["document_type"] == "discharge_record"
        for item in bundle["source_documents"]
    )


def test_assemble_frontpage_bundle_should_share_admission_resolution_with_frontpage_coding(monkeypatch):
    def _fake_select_records(**kwargs):
        table = kwargs["table"]
        if table == "mr":
            return [{"document_id": "mr-1", "patient_name": "张三", "admission_datetime": None}]
        if table == "admission_record":
            return [{"document_id": "admission-1", "admission_datetime": None, "record_time": "2026-01-24 20:42:25"}]
        if table == "discharge_record":
            return [{"document_id": "discharge-1", "discharge_datetime": "2026-02-05 10:00:00"}]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_build_scene_attention_artifacts", lambda **kwargs: ({}, []))
    monkeypatch.setattr(assembly_module, "_build_document_inventory", lambda docs, schema: [])
    monkeypatch.setattr(assembly_module, "_build_timeline_facts_from_docs", lambda docs: [])
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda schema, table: ())
    monkeypatch.setattr(
        assembly_module,
        "_fetch_patient_profile",
        lambda **kwargs: {"patient_name": "张三", "mobile": "", "id_card": ""},
    )

    bundle = assembly_module.assemble_frontpage_bundle(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    assert bundle["structured_context"]["admission_datetime"] == "2026-01-24 20:42:25"
    assert (
        bundle["structured_context"]["frontpage_coding"]["coding_payload"]["admission_datetime"]
        == "2026-01-24 20:42:25"
    )
    assert (
        bundle["structured_context"]["frontpage_coding"]["frontpage_formal_payload"]["admission_datetime"]
        == "2026-01-24 20:42:25"
    )


def test_unified_refresh_should_read_each_material_once_and_keep_variant_limits(monkeypatch):
    select_calls: list[dict[str, object]] = []
    scene_bundles: dict[tuple[str, str], dict] = {}
    domain_bundles: dict[tuple[str, str], dict] = {}
    progress_events: list[dict[str, int]] = []

    def _fake_select_records(**kwargs):
        select_calls.append(kwargs)
        row_count = 5 if kwargs["table"] == "daily_course_record" else 1
        return [
            {
                "document_id": f"{kwargs['visit_id']}-{kwargs['table']}-{index}",
                "record_content": f"{kwargs['visit_id']}:{kwargs['table']}:{index}",
            }
            for index in range(row_count)
        ]

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(assembly_module, "ensure_scene_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly_module, "ensure_domain_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly_module, "mark_bundle_refresh_success", lambda **_kwargs: None)
    monkeypatch.setattr(
        assembly_module,
        "_upsert_scene_bundle",
        lambda **kwargs: scene_bundles.__setitem__(
            (kwargs["bundle"]["visit_id"], kwargs["scene"]),
            kwargs["bundle"],
        ),
    )
    monkeypatch.setattr(
        assembly_module,
        "_upsert_domain_bundle",
        lambda **kwargs: domain_bundles.__setitem__(
            (kwargs["bundle"]["visit_id"], kwargs["execution_domain"]),
            kwargs["bundle"],
        ),
    )

    result = assembly_module.refresh_all_bundle_variants_for_rows(
        rows=[
            {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
            {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
        ],
        source_schema="cdm",
        scenes=("running", "final"),
        domains=("course",),
        progress_callback=progress_events.append,
    )

    calls_by_visit_table: dict[tuple[str, str], list[dict[str, object]]] = {}
    for call in select_calls:
        calls_by_visit_table.setdefault(
            (str(call["visit_id"]), str(call["table"])),
            [],
        ).append(call)
    assert all(len(calls) == 1 for calls in calls_by_visit_table.values())
    for visit_id in ("V1", "V2"):
        assert calls_by_visit_table[(visit_id, "daily_course_record")][0]["limit"] == 201
        assert calls_by_visit_table[(visit_id, "exam_master")][0]["limit"] == 501
        assert calls_by_visit_table[(visit_id, "labtest_item_report")][0]["limit"] == 5001
        assert len(
            domain_bundles[(visit_id, "course")]["structured_context"]["documents"][
                "daily_course_record"
            ]
        ) == 5
        assert (
            scene_bundles[(visit_id, "running")]["structured_context"][
                "source_table_coverage"
            ]["daily_course_record"]["row_count"]
            == 3
        )
    assert result["processed"] == 2
    assert result["material_reads"] == len(select_calls)
    assert progress_events == [
        {"completed": 1, "total": 2, "remaining": 1},
        {"completed": 2, "total": 2, "remaining": 0},
    ]


def test_material_snapshot_should_match_legacy_assembly_key_fields(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "admission_record":
            return [
                {
                    "document_id": "A1",
                    "admission_datetime": "2026-07-30 08:00:00",
                    "record_content": "患者因发热入院。",
                }
            ]
        if kwargs["table"] == "patient_information":
            return [{"patient_name": "测试患者"}]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())

    legacy_scene = assembly_module._assemble_scene_bundle(
        scene="running",
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
    )
    legacy_domain = assembly_module.assemble_domain_bundle(
        execution_domain="admission",
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
    )
    limits = assembly_module._material_limits_for_variants(
        scenes=("running",),
        domains=("admission",),
    )
    snapshot = assembly_module._build_material_snapshot(
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        table_limits=limits,
    )
    snapshot_scene = assembly_module._assemble_scene_bundle(
        scene="running",
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        material_snapshot=snapshot,
    )
    snapshot_domain = assembly_module.assemble_domain_bundle(
        execution_domain="admission",
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        material_snapshot=snapshot,
    )

    assert snapshot_scene["document_hits"] == legacy_scene["document_hits"]
    assert snapshot_scene["medical_text"] == legacy_scene["medical_text"]
    assert snapshot_scene["structured_context"]["admission_datetime"] == (
        legacy_scene["structured_context"]["admission_datetime"]
    )
    assert snapshot_domain["document_hits"] == legacy_domain["document_hits"]
    assert snapshot_domain["source_documents"] == legacy_domain["source_documents"]


def test_scene_bundle_should_mark_normal_source_summary_projection_truncation(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "daily_course_record":
            return [
                {
                    "document_id": f"course-{index}",
                    "record_time": f"2026-08-0{index} 08:00:00",
                    "record_content": f"第{index}份病程记录",
                }
                for index in range(1, 5)
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(
        assembly_module,
        "_build_scene_attention_artifacts",
        lambda **_kwargs: ({}, []),
    )

    bundle = assembly_module._assemble_scene_bundle(
        scene="running",
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
    )

    projection = bundle["structured_context"]["scene_projection"]
    daily_projection = projection["per_source"]["daily_course_record"]
    assert projection["projection_kind"] == "scene_summary"
    assert projection["is_evidence_source"] is False
    assert daily_projection == {
        "projected_count": 3,
        "projection_limit": 3,
        "has_more": True,
    }
    assert len(bundle["structured_context"]["documents"]["daily_course_record"]) == 3
    assert len(
        [
            item
            for item in bundle["source_documents"]
            if item["document_type"] == "daily_course_record"
        ]
    ) == 3


def test_scene_bundle_should_mark_complete_normal_source_summary_projection(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "daily_course_record":
            return [
                {
                    "document_id": f"course-{index}",
                    "record_time": f"2026-08-0{index} 08:00:00",
                    "record_content": f"第{index}份病程记录",
                }
                for index in range(1, 4)
            ]
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(
        assembly_module,
        "_build_scene_attention_artifacts",
        lambda **_kwargs: ({}, []),
    )

    bundle = assembly_module._assemble_scene_bundle(
        scene="running",
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
    )

    assert bundle["structured_context"]["scene_projection"]["per_source"][
        "daily_course_record"
    ] == {
        "projected_count": 3,
        "projection_limit": 3,
        "has_more": False,
    }


def test_scene_bundle_should_mark_attention_projection_has_more_as_unknown(monkeypatch):
    attention_row = {
        "document_id": "exam-attention-1",
        "document_title": "检查关注摘要",
        "record_time": "2026-08-01 08:00:00",
        "record_content": "检查关注摘要正文",
    }

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", lambda **_kwargs: [])
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(
        assembly_module,
        "_build_scene_attention_artifacts",
        lambda **_kwargs: ({"exam_attention_report": [attention_row]}, []),
    )

    bundle = assembly_module._assemble_scene_bundle(
        scene="running",
        source_schema="cdm",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
    )

    assert bundle["structured_context"]["scene_projection"]["per_source"][
        "exam_attention_report"
    ] == {
        "projected_count": 1,
        "projection_limit": None,
        "has_more": None,
    }


def test_unified_refresh_should_isolate_variant_failures(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "presurg_summary":
            raise RuntimeError("surgery source unavailable")
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(assembly_module, "ensure_domain_bundle_tables", lambda **_kwargs: None)
    monkeypatch.setattr(assembly_module, "_upsert_domain_bundle", lambda **_kwargs: None)

    result = assembly_module.refresh_all_bundle_variants_for_rows(
        rows=[{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
        source_schema="cdm",
        scenes=(),
        domains=("surgery", "terminal"),
        continue_on_error=True,
    )

    assert result["domains"]["surgery"]["failed"] == 1
    assert result["domains"]["terminal"]["updated"] == 1


def test_unified_refresh_should_raise_on_variant_failure_when_requested(monkeypatch):
    def _fake_select_records(**kwargs):
        if kwargs["table"] == "presurg_summary":
            raise RuntimeError("surgery source unavailable")
        return []

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_select_records", _fake_select_records)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setattr(assembly_module, "ensure_domain_bundle_tables", lambda **_kwargs: None)

    import pytest

    with pytest.raises(RuntimeError, match="surgery source unavailable"):
        assembly_module.refresh_all_bundle_variants_for_rows(
            rows=[{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
            source_schema="cdm",
            scenes=(),
            domains=("surgery", "terminal"),
            continue_on_error=False,
        )


def test_domain_bundle_should_mark_projection_when_rows_exceed_existing_limit(monkeypatch):
    calls: list[tuple[str, int]] = []

    def _fake_material_rows(**kwargs):
        table_name = kwargs["table"]
        calls.append((table_name, kwargs["limit"]))
        if table_name != "admission_record":
            return []
        return [
            {
                "document_id": f"admission-{index}",
                "record_time": f"2026-08-{index + 1:02d} 08:00:00",
                "record_content": f"入院记录 {index}",
            }
            for index in range(21)
        ]

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_material_rows", _fake_material_rows)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="admission",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    assert ("admission_record", 21) in calls
    assert len(bundle["structured_context"]["documents"]["admission_record"]) == 20
    assert bundle["structured_context"]["domain_projection"] == {
        "projection_kind": "domain_documents",
        "is_evidence_source": False,
        "per_source": {
            "admission_record": {
                "projected_count": 20,
                "projection_limit": 20,
                "has_more": True,
            },
            "admission_record_diagnosis": {
                "projected_count": 0,
                "projection_limit": 50,
                "has_more": False,
            },
        },
    }
    admission_documents = bundle["source_documents"]
    assert len(admission_documents) == 20
    assert all(item["projection_incomplete"] is True for item in admission_documents)
    assert all("已展示20条，仍有更多" in item["projection_notice"] for item in admission_documents)


def test_domain_bundle_should_not_present_partial_lab_report_as_complete(monkeypatch):
    calls: list[tuple[str, int]] = []

    def _fake_material_rows(**kwargs):
        table_name = kwargs["table"]
        calls.append((table_name, kwargs["limit"]))
        if table_name != "labtest_item_report":
            return []
        return [
            {
                "test_no": "LAB-001",
                "item_no": str(index + 1),
                "item_name": f"项目{index + 1}",
                "result": str(index + 1),
                "report_time": "2026-08-01 09:00:00",
            }
            for index in range(4)
        ]

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_material_rows", _fake_material_rows)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())
    monkeypatch.setitem(assembly_module._DOMAIN_FETCH_LIMITS, "labtest_item_report", 3)

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="course",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    assert ("labtest_item_report", 4) in calls
    report = next(
        item
        for item in bundle["source_documents"]
        if item["document_type"] == "labtest_item_report"
    )
    assert [item["item_name"] for item in report["report_items"]] == ["项目1", "项目2", "项目3"]
    assert report["projection_incomplete"] is True
    assert "已展示3条，仍有更多" in report["projection_notice"]
    assert bundle["structured_context"]["domain_projection"]["per_source"][
        "labtest_item_report"
    ] == {
        "projected_count": 3,
        "projection_limit": 3,
        "has_more": True,
    }


def test_domain_bundle_projection_should_mark_within_limit_as_complete_projection(monkeypatch):
    def _fake_material_rows(**kwargs):
        if kwargs["table"] != "admission_record":
            return []
        return [
            {
                "document_id": "admission-1",
                "record_time": "2026-08-01 08:00:00",
                "record_content": "入院记录",
            }
        ]

    monkeypatch.setattr(assembly_module, "engine", object())
    monkeypatch.setattr(assembly_module, "_material_rows", _fake_material_rows)
    monkeypatch.setattr(assembly_module, "_get_table_columns", lambda *_args: set())

    bundle = assembly_module.assemble_domain_bundle(
        execution_domain="admission",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        source_schema="cdm",
    )

    projection = bundle["structured_context"]["domain_projection"]["per_source"][
        "admission_record"
    ]
    assert projection == {
        "projected_count": 1,
        "projection_limit": 20,
        "has_more": False,
    }
    assert bundle["source_documents"][0]["projection_incomplete"] is False
