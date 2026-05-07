from app.services.bundles import assembly as assembly_module


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
    assert daily_call["limit"] == 200


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
