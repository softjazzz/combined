from app.services.bundles import assembly as assembly_module


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
