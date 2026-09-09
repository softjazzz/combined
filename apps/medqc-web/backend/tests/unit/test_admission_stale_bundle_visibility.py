"""固定本地资料，验证旧 Bundle 对页面展示的影响；不连接数据库。"""
from copy import deepcopy
from unittest.mock import Mock

from app.services.bundles import assembly, emr_view

IDENTITY = {"institute_id": "TEST", "patient_id": "P-TEST", "visit_id": "V-TEST"}
TIME = "2025-08-12 17:24:13"


def _setup(monkeypatch, with_diagnosis=False):
    local_rows = {
        "admission_record": [{**IDENTITY, "document_id": "ADM-TEST",
            "admission_datetime": TIME, "record_time": "2025-08-12 17:42:11",
            "chief_complaint": "腰背痛一天"}],
        "admission_record_diagnosis": [{**IDENTITY, "document_id": "DX-TEST",
            "diagnosis_name": "腰椎骨折", "diagnosis_type": "初步诊断"}],
    }
    if not with_diagnosis:
        local_rows["admission_record_diagnosis"] = []
    read_rows = Mock(side_effect=lambda **kw: deepcopy(local_rows.get(kw["table"], [])))
    monkeypatch.setattr(assembly, "engine", object())
    monkeypatch.setattr(assembly, "_material_rows", read_rows)
    monkeypatch.setattr(assembly, "_get_table_columns", lambda schema, table: set().union(
        *(r.keys() for r in local_rows.get(table, []))))
    # 模拟旧版投影未携带入院时间；版本仍与当前相同。
    admission_time = local_rows["admission_record"][0].pop("admission_datetime")
    old = assembly.assemble_domain_bundle(execution_domain="admission", source_schema="public", **IDENTITY)
    local_rows["admission_record"][0]["admission_datetime"] = admission_time
    fresh = assembly.assemble_domain_bundle(execution_domain="admission", source_schema="public", **IDENTITY)
    read_rows.reset_mock()
    saved = {"admission": old}
    monkeypatch.setattr(emr_view, "load_domain_bundle", lambda **kw: deepcopy(saved.get(kw["execution_domain"])))
    rebuild = Mock(return_value=None)
    monkeypatch.setattr(emr_view, "load_or_assemble_domain_bundle", rebuild)
    # 其他文书补全入口可读当前资料，但不能假定一定替换入院 Bundle。
    overlay = Mock(side_effect=lambda **kw: deepcopy(fresh) if kw["execution_domain"] == "admission" else None)
    monkeypatch.setattr(emr_view, "assemble_domain_bundle", overlay)
    return local_rows, saved, fresh, read_rows, rebuild, overlay


def _admission_sections(result):
    return [s for d in result["documents"] if d["doc_type"] == "admission_record"
            for s in d.get("sections", []) if (s.get("section_label") or s.get("label")) == "入院时间"]


def test_local_time_present_but_old_bundle_hides_it_until_rebuilt(monkeypatch):
    local_rows, saved, fresh, reads, rebuild, overlay = _setup(monkeypatch)
    assert local_rows["admission_record"][0]["admission_datetime"] == TIME
    assert not emr_view._domain_bundle_needs_projection_refresh(saved["admission"])
    before = emr_view.load_bundle_documents(**IDENTITY)
    assert _admission_sections(before) == []
    assert not any(c.kwargs.get("execution_domain") == "admission" for c in rebuild.call_args_list)
    assert not before["domain_bundle_hits"].get("admission_runtime_overlay")
    reads.assert_not_called()
    # 仅替换保存 Bundle，不修改本地入院记录。
    saved["admission"] = fresh
    after = emr_view.load_bundle_documents(**IDENTITY)
    sections = _admission_sections(after)
    assert len(sections) == 1
    assert sections[0]["text"] == TIME
    assert local_rows["admission_record"][0]["admission_datetime"] == TIME


def test_missing_diagnosis_can_incidentally_refresh_admission_overlay(monkeypatch):
    _, saved, _, _, _, overlay = _setup(monkeypatch, with_diagnosis=True)
    saved["admission"]["source_documents"] = [
        d for d in saved["admission"]["source_documents"]
        if d.get("document_type") != "admission_record_diagnosis"
    ]
    result = emr_view.load_bundle_documents(**IDENTITY)
    assert any(c.kwargs.get("execution_domain") == "admission" for c in overlay.call_args_list)
    assert _admission_sections(result)[0]["text"] == TIME
