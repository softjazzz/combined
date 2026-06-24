from app.services.bundles import assembly as assembly_module


def test_load_or_assemble_scene_bundle_should_fallback_to_latest_usable_cached_bundle(monkeypatch):
    calls: list[dict[str, object]] = []

    empty_bundle = {
        "bundle_schema_version": assembly_module.BUNDLE_SCHEMA_VERSION_CURRENT,
        "medical_text": "",
        "text_available": False,
        "document_hits": {},
        "structured_context": {"documents": {}},
    }
    usable_bundle = {
        "bundle_schema_version": assembly_module.BUNDLE_SCHEMA_VERSION_CURRENT,
        "medical_text": "有效正文",
        "text_available": True,
        "document_hits": {"daily_course_record": True},
        "structured_context": {"documents": {"daily_course_record": [{"document_id": "D1"}]}},
    }

    def fake_load_scene_bundle(**kwargs):
        calls.append(dict(kwargs))
        if kwargs.get("prefer_usable_content"):
            return dict(usable_bundle)
        return dict(empty_bundle)

    monkeypatch.setattr(assembly_module, "ensure_scene_bundle_tables", lambda schema: None)
    monkeypatch.setattr(assembly_module, "_load_scene_bundle", fake_load_scene_bundle)
    monkeypatch.setattr(
        assembly_module,
        "_assemble_scene_bundle",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("不应触发重组装")),
    )

    result = assembly_module.load_or_assemble_scene_bundle(
        scene="final",
        institute_id="I1",
        patient_id="P1",
        visit_id="V1",
        bundle_schema="public",
        force_refresh=False,
        force_refresh_if_empty=True,
    )

    assert result["medical_text"] == "有效正文"
    assert len(calls) == 2
    assert calls[1]["prefer_usable_content"] is True
    assert calls[1]["limit"] == 5
