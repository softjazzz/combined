"""来源登记保护：不连业务库、不使用HTTP角色或机构猜测材料来源。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"backend"))
from app.services import validation_material_source as source  # noqa: E402


def test_real_case_has_no_registry_lookup(monkeypatch):
    monkeypatch.setattr(source,"_registered_schema",lambda *args:pytest.fail("real case must not query registry"))
    assert source.material_source_schema(default_schema="cdm",institute_id="SYN-A",patient_id="P",visit_id="V") == "cdm"


def test_copy_schema_must_come_from_full_identity_registration(monkeypatch):
    calls = []
    def registry(*args):
        calls.append(args)
        return "pdfmat_123456abcdef"
    monkeypatch.setattr(source,"_registered_schema",registry)
    assert source.material_source_schema(default_schema="cdm",institute_id="SYN-A",patient_id="pdfp_p",visit_id="pdfv_v",requested_schema="cdm",strict=True) == "pdfmat_123456abcdef"
    assert calls == [("SYN-A","pdfp_p","pdfv_v")]
    with pytest.raises(ValueError,match="schema_mismatch"):
        source.material_source_schema(default_schema="cdm",institute_id="SYN-A",patient_id="pdfp_p",visit_id="pdfv_v",requested_schema="pdfmat_000000000000")


def test_incomplete_or_unregistered_copy_cannot_fall_back_to_real_data(monkeypatch):
    def missing(*args):
        raise ValueError("not_registered")
    monkeypatch.setattr(source,"_registered_schema",missing)
    with pytest.raises(ValueError,match="identity_incomplete"):
        source.material_source_schema(default_schema="cdm",institute_id="SYN-A",patient_id="P",visit_id="pdfv_v")
    with pytest.raises(ValueError,match="not_registered"):
        source.material_source_schema(default_schema="cdm",institute_id="SYN-A",patient_id="pdfp_p",visit_id="pdfv_v")


def test_native_reader_keeps_original_schema_validation():
    with pytest.raises(ValueError,match="untrusted"):
        source.material_source_schema(default_schema="cdm",requested_schema="other",strict=True,institute_id="SYN-A",patient_id="P",visit_id="V")


def test_copy_display_uses_discharge_department_and_real_stay_timestamps():
    display = source.project_copy_display({"mr":{"name":"合成甲","admission_dept_name":"入院科"},
        "discharge_record":{"dept_name":"出院科","discharge_time":"2026-10-09T08:00:00","record_time":"2026-10-10T09:00:00"},
        "inpat_registration":{"admission_datetime":"2026-10-01T08:00:00"}})
    assert display["department"] == "出院科"
    assert display["discharge_time"] == "2026-10-09T08:00:00"
    assert display["hospitalization_status"] == "discharged"


def test_copy_display_does_not_guess_stay_dates_from_signature_or_document_time():
    display = source.project_copy_display({"discharge_record":{"record_time":"2026-10-10T09:00:00","chief_physician_sign_datetime":"2026-10-10T10:00:00"}})
    assert display["admission_time"] == ""
    assert display["discharge_time"] == ""
    assert display["hospitalization_status"] == ""
