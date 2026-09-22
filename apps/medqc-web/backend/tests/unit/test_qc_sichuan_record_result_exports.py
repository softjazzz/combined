import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import qc_sichuan


class _Workspace:
    def __init__(self, *, record_count: int = 1):
        self.record_count = record_count
        self.latest_calls = []
        self.bulk_calls = []

    def collect_records(self, **kwargs):
        self.collect_kwargs = kwargs
        record_refs = kwargs.get("record_refs")
        if record_refs:
            return [
                {
                    "institute_id": ref["institute_id"],
                    "patient_id": ref["patient_id"],
                    "visit_id": ref["visit_id"],
                    "patient_name": f"患者{index}",
                    "department": "重症医学科（ICU）",
                    "doctor": "李医生",
                    "scope": kwargs.get("scope"),
                }
                for index, ref in enumerate(record_refs)
            ]
        return [
            {
                "institute_id": "H-1",
                "patient_id": f"P-{index}",
                "visit_id": f"V-{index}",
                "patient_name": f"患者{index}",
                "department": "重症医学科（ICU）",
                "doctor": "李医生",
                "scope": "final",
            }
            for index in range(self.record_count)
        ]

    def count_records(self, **kwargs):
        self.count_kwargs = kwargs
        return self.record_count

    def get_latest_luxian_0609_record_result(self, **kwargs):
        self.latest_calls.append(kwargs)
        return {
            "schema_version": "lx0609-single-record-result-v1",
            "state": "ready",
            "record_ref": "rec-safe",
            "job_id": "job-safe",
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "expected_rule_count": 1,
            "result_rule_count": 1,
            "is_complete": True,
            "items": [
                {
                    "rule_id": "LX0609-01-01-01",
                    "rule_name": "入院记录及时完成",
                    "source_document": "入院记录",
                    "qc_point": "入院后24小时内完成",
                    "status": "non_compliant",
                    "conclusion": "未在规定时限内完成。",
                }
            ],
        }

    def build_latest_luxian_0609_record_result_dtos(self, *, record_refs):
        self.bulk_calls.append(record_refs)
        return {
            (ref["institute_id"], ref["patient_id"], ref["visit_id"]): {
                "schema_version": "lx0609-single-record-result-v1",
                "state": "ready",
                "record_ref": f"rec-{ref['visit_id']}",
                "job_id": "job-safe",
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
                "expected_rule_count": 1,
                "result_rule_count": 1,
                "is_complete": True,
                "items": [
                    {
                        "rule_id": "LX0609-01-01-01",
                        "source_document": "入院记录",
                        "qc_point": "入院后24小时内完成",
                        "status": "non_compliant",
                        "conclusion": "未在规定时限内完成。",
                    }
                ],
            }
            for ref in record_refs
        }


def _authorize(client, *, email="qc-admin@hospital.local", roles=None, is_demo_account=None):
    async def _auth_gate():
        return None

    user = {"id": "u-admin", "email": email, "roles": roles or ["admin"]}
    if is_demo_account is not None:
        user["is_demo_account"] = is_demo_account
    client.app.dependency_overrides[enforce_default_auth] = _auth_gate
    client.app.dependency_overrides[get_current_user] = lambda: user


def test_single_record_html_export_uses_exact_coordinates(client, monkeypatch):
    _authorize(client)
    workspace = _Workspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.get(
        "/api/v1/qc/sichuan/workspace/records/V-0/latest-result/export",
        params={"institute_id": "H-1", "patient_id": "P-0"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "attachment" in response.headers["content-disposition"]
    assert "单病历质控结果" in response.text
    assert workspace.latest_calls == [
        {"institute_id": "H-1", "patient_id": "P-0", "visit_id": "V-0"}
    ]


def test_current_filter_excel_export_freezes_server_records_and_latest_canonical(client, monkeypatch):
    _authorize(client)
    workspace = _Workspace(record_count=2)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.post(
        "/api/v1/qc/sichuan/workspace/records/export",
        json={
            "scope": "final",
            "department": "重症医学科（ICU）",
            "doctor": "李医生",
            "date_field": "discharge",
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "keyword": "患者",
        },
    )

    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    assert workspace.collect_kwargs == {
        "scope": "final",
        "department": "重症医学科（ICU）",
        "doctor": "李医生",
        "date_field": "discharge",
        "start_date": "2026-07-01",
        "end_date": "2026-07-31",
        "keyword": "患者",
    }
    assert workspace.count_kwargs == workspace.collect_kwargs
    assert workspace.latest_calls == []
    assert len(workspace.bulk_calls) == 1
    assert workspace.bulk_calls[0] == [
        {"institute_id": "H-1", "patient_id": "P-0", "visit_id": "V-0"},
        {"institute_id": "H-1", "patient_id": "P-1", "visit_id": "V-1"},
    ]


def test_selected_record_excel_export_uses_exact_coordinates_without_counting_filter_scope(client, monkeypatch):
    _authorize(client)
    workspace = _Workspace(record_count=99)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.post(
        "/api/v1/qc/sichuan/workspace/records/export",
        json={
            "scope": "final",
            "date_field": "discharge",
            "record_refs": [
                {"institute_id": "H-1", "patient_id": "P-7", "visit_id": "V-7"},
                {"institute_id": "H-2", "patient_id": "P-8", "visit_id": "V-8"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    assert not hasattr(workspace, "count_kwargs")
    assert workspace.collect_kwargs == {
        "scope": "final",
        "department": None,
        "doctor": None,
        "date_field": "discharge",
        "start_date": None,
        "end_date": None,
        "keyword": None,
        "record_refs": [
            {"institute_id": "H-1", "patient_id": "P-7", "visit_id": "V-7"},
            {"institute_id": "H-2", "patient_id": "P-8", "visit_id": "V-8"},
        ],
    }
    assert workspace.bulk_calls == [
        [
            {"institute_id": "H-1", "patient_id": "P-7", "visit_id": "V-7"},
            {"institute_id": "H-2", "patient_id": "P-8", "visit_id": "V-8"},
        ]
    ]


@pytest.mark.parametrize(
    "record_refs",
    [
        [{"institute_id": "H-1", "patient_id": "", "visit_id": "V-1"}],
        [
            {"institute_id": "H-1", "patient_id": "P-1", "visit_id": "V-1"},
            {"institute_id": "H-1", "patient_id": "P-1", "visit_id": "V-1"},
        ],
    ],
)
def test_selected_record_excel_rejects_incomplete_or_duplicate_coordinates(
    client, monkeypatch, record_refs
):
    _authorize(client)
    workspace = _Workspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.post(
        "/api/v1/qc/sichuan/workspace/records/export",
        json={"scope": "final", "date_field": "discharge", "record_refs": record_refs},
    )

    assert response.status_code == 422
    assert not hasattr(workspace, "collect_kwargs")
    assert workspace.bulk_calls == []


def test_selected_record_excel_rejects_when_loaded_records_do_not_match_selection(client, monkeypatch):
    _authorize(client)
    workspace = _Workspace()
    workspace.collect_records = lambda **_kwargs: [
        {
            "institute_id": "H-1",
            "patient_id": "P-other",
            "visit_id": "V-other",
        }
    ]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.post(
        "/api/v1/qc/sichuan/workspace/records/export",
        json={
            "scope": "final",
            "date_field": "discharge",
            "record_refs": [
                {"institute_id": "H-1", "patient_id": "P-1", "visit_id": "V-1"}
            ],
        },
    )

    assert response.status_code == 422
    assert workspace.bulk_calls == []


def test_current_filter_excel_rejects_more_than_one_thousand_records(client, monkeypatch):
    _authorize(client)
    workspace = _Workspace(record_count=1001)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.post(
        "/api/v1/qc/sichuan/workspace/records/export",
        json={"scope": "final", "date_field": "discharge"},
    )

    assert response.status_code == 422
    assert not hasattr(workspace, "collect_kwargs")
    assert workspace.latest_calls == []


def test_current_filter_excel_rechecks_loaded_count_after_scope_changes(client, monkeypatch):
    _authorize(client)
    workspace = _Workspace(record_count=1001)
    workspace.count_records = lambda **_kwargs: 1000
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.post(
        "/api/v1/qc/sichuan/workspace/records/export",
        json={"scope": "final", "date_field": "discharge"},
    )

    assert response.status_code == 422
    assert workspace.bulk_calls == []


@pytest.mark.parametrize(
    ("email", "roles"),
    [
        ("admin@medqc.com", ["admin"]),
        ("qc@medqc.com", ["qc_manager"]),
        ("sync_admin@medqc.com", ["sync_admin"]),
    ],
)
def test_builtin_demo_management_account_can_export_record_results(
    client, monkeypatch, email, roles
):
    _authorize(client, email=email, roles=roles, is_demo_account=True)
    workspace = _Workspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.get(
        "/api/v1/qc/sichuan/workspace/records/V-0/latest-result/export",
        params={"institute_id": "H-1", "patient_id": "P-0"},
    )

    assert response.status_code == 200
    assert workspace.latest_calls == [
        {"institute_id": "H-1", "patient_id": "P-0", "visit_id": "V-0"}
    ]


def test_builtin_demo_doctor_still_cannot_export_record_results(client, monkeypatch):
    _authorize(
        client,
        email="doctor@medqc.com",
        roles=["doctor"],
        is_demo_account=True,
    )
    workspace = _Workspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = client.get(
        "/api/v1/qc/sichuan/workspace/records/V-0/latest-result/export",
        params={"institute_id": "H-1", "patient_id": "P-0"},
    )

    assert response.status_code == 403
    assert workspace.latest_calls == []
