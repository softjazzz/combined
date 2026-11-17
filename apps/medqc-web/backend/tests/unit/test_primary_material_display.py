"""四类材料目录/全文的合成透传验证，不接数据库或规则。"""
from copy import deepcopy

from app.services.bundles.emr_view import (
    _normalize_source_document,
    build_render_view,
    summarize_frozen_documents,
)


def test_primary_material_metadata_survives_summary_and_render_without_reselection():
    fields = {
        "source_version_key": "surgery_record::R::held-v1",
        "version_id": "held-v1",
        "source_record_identity": "R",
        "source_namespace": "clinical",
        "source_object": "clinical.public.surgery_record",
        "material_selected": False,
        "material_rule_usable": False,
        "material_state": "HELD",
        "material_source_label": "clinical",
        "material_notice": "状态待核；替代版本；内容冲突",
        "material_scope_notice": "来源未覆盖；尚未发布",
        "primary_material": {"selected": False, "raw_fields": {"synthetic": "retained"}},
        "primary_material_scope": {"can_judge_clinical_absence": False},
    }
    raw = {"document_type": "surgery_record", "document_id": "D", "content": "合成手术正文", "surgery_process": "合成手术正文", **fields}
    original = deepcopy(raw)
    document = _normalize_source_document(raw_doc=raw, index=0, execution_domain="surgery")
    for key, value in fields.items():
        assert document[key] == value
    scope = {"contract": "clinical-primary-four-v1", "notice": "状态待核", "kinds": {"surgery_record": {"status": "HELD"}}}
    summary = summarize_frozen_documents(documents=[document], primary_material_status=scope)
    assert summary["primary_material_status"] == scope
    for key in fields.keys() - {"primary_material", "primary_material_scope"}:
        assert summary["documents"][0][key] == fields[key]
        assert build_render_view(document=document)["document_meta"][key] == fields[key]
    assert "primary_material" not in summary["documents"][0]
    assert "primary_material" not in build_render_view(document=document)["document_meta"]
    assert raw == original


def test_old_summary_without_primary_status_keeps_daily_compatibility():
    daily = {"notice": "旧材料提示"}
    result = summarize_frozen_documents(documents=[], daily_material_status=daily)
    assert result["daily_material_status"] == daily
    assert result.get("primary_material_status") is None


def test_router_summary_transports_frozen_or_current_status_without_reading_cdm(monkeypatch):
    from app.routers import emr_render

    scope = {"contract": "clinical-primary-four-v1", "notice": "来源未发布", "kinds": {"surgery_record": {"status": "NOT_DEPLOYED"}}}
    documents = {"documents": [], "primary_material_status": scope}
    monkeypatch.setattr(emr_render.case_material, "identity_check", lambda *args: None)
    monkeypatch.setattr(emr_render.case_material, "current", lambda: {"documents": documents})
    monkeypatch.setattr(emr_render, "_load_live_cdm_documents", lambda *args: (_ for _ in ()).throw(AssertionError("frozen read current CDM")))
    params = dict(record_id="V", institute_id="I", patient_id="P", visit_id="V")
    assert emr_render._load_document_summaries_from_bundle(**params)["primary_material_status"] == scope
    monkeypatch.setattr(emr_render.case_material, "current", lambda: None)
    monkeypatch.setattr(emr_render, "_load_live_cdm_documents", lambda *args: deepcopy(documents))
    assert emr_render._load_document_summaries_from_bundle(**params)["primary_material_status"] == scope
