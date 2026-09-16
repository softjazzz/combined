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
    monkeypatch.setattr(bundle_reader, "_load_luxian_0916_patient_facts", lambda **_: {})

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


def test_bundle_reader_reads_age_from_fixed_cdm_query_and_projects_0916_facts(monkeypatch):
    captured: dict[str, object] = {}

    class _Result:
        def mappings(self):
            return self

        def first(self):
            return {"age_year": "13", "age_month": "11", "age": "13岁11月"}

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params):
            captured["statement"] = str(statement)
            captured["params"] = params
            return _Result()

    class _Engine:
        def connect(self):
            return _Connection()

    monkeypatch.setattr(bundle_reader, "engine", _Engine())
    monkeypatch.setattr(
        bundle_reader,
        "load_or_assemble_scene_bundle",
        lambda **_: {"structured_context": {"document_inventory": []}},
    )

    result = bundle_reader.load_luxian_0916_bundle(
        scene="final",
        institute_id="I-1",
        patient_id="P-1",
        visit_id="V-1",
    )

    assert "cdm.admission_record" in str(captured["statement"])
    assert captured["params"] == {
        "institute_id": "I-1",
        "patient_id": "P-1",
        "visit_id": "V-1",
    }
    assert result["structured_context"]["luxian_0916_facts"]["patient"] == {
        "age_year": "13",
        "age_month": "11",
        "age": "13岁11月",
    }


def test_bundle_reader_rejects_unknown_scene_before_database_access(monkeypatch):
    monkeypatch.setattr(bundle_reader, "engine", object())

    with pytest.raises(ValueError, match="unsupported Luxian0916 bundle scene"):
        bundle_reader.load_luxian_0916_bundle(
            scene="all",
            institute_id="I-1",
            patient_id="P-1",
            visit_id="V-1",
        )
