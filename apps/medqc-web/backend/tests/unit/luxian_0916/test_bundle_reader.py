from __future__ import annotations

import pytest

from app.services.luxian_0916 import bundle_reader


def test_bundle_reader_uses_generic_bundle_loader_and_normalizes_json(monkeypatch):
    captured = {}
    monkeypatch.setattr(bundle_reader, "engine", object())

    def load(**kwargs):
        captured.update(kwargs)
        return {
            "structured_context": '{"document_inventory": []}',
            "document_hits": "[]",
            "data_quality_flags": None,
            "source_doc_priority": {"admission_record": 1},
        }

    monkeypatch.setattr(bundle_reader, "load_or_assemble_scene_bundle", load)

    result = bundle_reader.load_luxian_0916_bundle(
        scene="running",
        institute_id="I-1",
        patient_id="P-1",
        visit_id="V-1",
    )

    assert captured == {
        "scene": "running",
        "institute_id": "I-1",
        "patient_id": "P-1",
        "visit_id": "V-1",
        "bundle_schema": "public",
        "force_refresh": False,
        "force_refresh_if_empty": True,
    }
    assert result["structured_context"] == {"document_inventory": []}
    assert result["document_hits"] == []
    assert result["data_quality_flags"] == {}


def test_bundle_reader_rejects_unknown_scene_before_database_access(monkeypatch):
    monkeypatch.setattr(bundle_reader, "engine", object())

    with pytest.raises(ValueError, match="unsupported Luxian0916 bundle scene"):
        bundle_reader.load_luxian_0916_bundle(
            scene="all",
            institute_id="I-1",
            patient_id="P-1",
            visit_id="V-1",
        )
