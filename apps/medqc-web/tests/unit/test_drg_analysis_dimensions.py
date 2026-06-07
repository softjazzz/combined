from backend.app.services.drg.analysis_service import build_analysis_payload


class _EmptyBatchStore:
    def get_all_records(self, session_id=None, batch_id=None):
        return []


class _DemoStore:
    def list_cases(self, limit=500):
        return [
            {
                "admission_id": "A001",
                "department_name": "心内科",
                "ward_name": "心内一病区",
                "attending_group": "张医生组",
                "doctor": "张医生",
                "diagnosis_group": "缺血性心脏病",
                "drg": "DRG-001",
                "drg_weight": 1.2,
                "total_cost": 10000,
                "insurance_payment": 12000,
                "los": 7,
                "age": 45,
                "leaving_type": 1,
                "admission_date": "2026-03-01",
            },
            {
                "admission_id": "A002",
                "department_name": "普外科",
                "ward_name": "普外二病区",
                "attending_group": "李医生组",
                "doctor": "李医生",
                "diagnosis_group": "胆道疾病",
                "drg": "DRG-002",
                "drg_weight": 0.9,
                "total_cost": 9000,
                "insurance_payment": 7000,
                "los": 9,
                "age": 70,
                "leaving_type": 5,
                "admission_date": "2026-03-02",
            },
        ][:limit]


def _payload(dimension: str):
    return build_analysis_payload(
        dimension=dimension,
        start_date=None,
        end_date=None,
        filter_id=None,
        session_id=None,
        batch_id=None,
        department=None,
        doctor=None,
        batch_store=_EmptyBatchStore(),
        demo_store=_DemoStore(),
    )


def test_drg_analysis_required_dimensions_have_table_data():
    for dimension in [
        "hospital",
        "department",
        "ward",
        "attending_group",
        "person",
        "diagnosis_group",
        "drg",
    ]:
        payload = _payload(dimension)

        assert payload["tableData"], dimension
        assert "drg_dip_group_count" in payload["kpis"]
        assert set(["hospital", "department", "ward", "attending_group", "person"]).issubset(
            payload["levels"].keys()
        )


def test_drg_analysis_keeps_doctor_alias_for_person_dimension():
    doctor_payload = _payload("doctor")
    person_payload = _payload("person")

    assert doctor_payload["tableData"] == person_payload["tableData"]
