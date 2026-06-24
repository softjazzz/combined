from types import SimpleNamespace

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService


def test_serialize_record_row_should_include_programmatic_execution_keys():
    service = CustomQCWorkspaceService()
    row = SimpleNamespace(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        name="张三",
        mr_no="MR1",
        inpat_no="IP1",
        discharge_dept_name="普外科",
        admission_dept_name="普外科",
        attending_physician_sign="李医生",
        admission_datetime="2026-04-01 08:00:00",
        discharge_datetime="2026-04-05 09:00:00",
        record_content="病历正文",
        update_time=None,
    )

    item = service._serialize_record_row(row)

    assert item["institute_id"] == "H1"
    assert item["patient_id"] == "P1"
    assert item["medical_text"] == "病历正文"
    assert item["admission_datetime"] == "2026-04-01 08:00:00"
    assert item["discharge_datetime"] == "2026-04-05 09:00:00"


def test_hydrate_records_with_medical_text_should_preserve_scope_and_dates(monkeypatch):
    service = CustomQCWorkspaceService()

    class _Row:
        institute_id = "H1"
        patient_id = "P1"
        visit_id = "V1"
        name = "张三"
        department = "普外科"
        attending_physician_sign = "李医生"
        record_content = "补齐病历正文"

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [_Row()]

    class _Session:
        def query(self, *_args, **_kwargs):
            return _Query()

        def close(self):
            return None

    monkeypatch.setattr("app.services.custom_qc_workspace_service._session", lambda: _Session())

    hydrated = service.hydrate_records_with_medical_text(
        [
            {
                "record_id": "V1",
                "visit_id": "V1",
                "scope": "final",
                "discharge_datetime": "2026-04-05 09:00:00",
                "medical_text": "",
            }
        ]
    )

    assert hydrated[0]["scope"] == "final"
    assert hydrated[0]["discharge_datetime"] == "2026-04-05 09:00:00"
    assert hydrated[0]["medical_text"] == "补齐病历正文"
