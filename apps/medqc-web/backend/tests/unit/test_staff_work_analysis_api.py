"""质控员工作分析 HTTP 合同；服务替换为内存桩。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import staff_work_analysis as routes
from app.services import staff_work_analysis_service as service


BASE = "/api/v1/quality-reports/staff-work"


def _client(roles=("qc_manager",)) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "qc-1", "roles": list(roles)}
    return TestClient(app)


def test_authorized_request_passes_period_and_scene(monkeypatch):
    captured = {}
    expected = {
        "period": "last_week", "scene": "all", "summary": {"record_review_count": 3},
        "staff": [{"user_id": "qc-1", "record_review_count": 3}], "unavailable_reason": None,
        "unavailable_metrics": {},
    }

    def get_analysis(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(service, "get_staff_work_analysis", get_analysis)
    response = _client().get(BASE, params={"period": "last_week", "scene": "all"})
    assert response.status_code == 200
    assert response.json()["data"] == expected
    assert captured == {"period": "last_week", "scene": "all"}


@pytest.mark.parametrize("suffix, method", [("", "get_staff_work_analysis"), ("/export", "export_staff_work_csv")])
def test_rank_metric_is_forwarded_to_both_report_and_export(monkeypatch, suffix, method):
    captured = {}

    def read(**kwargs):
        captured.update(kwargs)
        return (b"rank,user\n1,a\n", 1) if suffix else {"staff": []}

    monkeypatch.setattr(service, method, read)
    response = _client().get(BASE + suffix, params={"rank_metric": "urged_defect_count", "scene": "final"})
    assert response.status_code == 200
    assert captured == {"period": "this_week", "scene": "final", "rank_metric": "urged_defect_count"}


def test_scene_unavailable_contract_preserves_nulls(monkeypatch):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: {
        "period": "this_week", "scene": "final", "summary": None, "staff": None,
        "unavailable_reason": "scene_not_attributable",
    })
    response = _client().get(BASE, params={"scene": "final"})
    assert response.status_code == 200
    assert response.json()["data"]["staff"] is None
    assert response.json()["data"]["unavailable_reason"] == "scene_not_attributable"


def test_scene_field_level_unknown_contract_preserves_real_rows(monkeypatch):
    expected = {
        "period": "this_week", "scene": "running",
        "summary": {"record_review_count": 2, "appeal_approved_count": None,
                    "appeal_rejected_count": None},
        "staff": [{"user_id": "qc-1", "record_review_count": 2,
                  "appeal_approved_count": None, "appeal_rejected_count": None}],
        "unavailable_reason": None,
        "unavailable_metrics": {
            "appeal_approved_count": "scene_not_attributable",
            "appeal_rejected_count": "scene_not_attributable",
        },
    }
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: expected)
    response = _client().get(BASE, params={"scene": "running"})
    assert response.status_code == 200
    assert response.json()["data"] == expected


@pytest.mark.parametrize("roles", [("doctor",), ("qc_staff",), ()])
def test_non_manager_roles_are_forbidden_before_read(monkeypatch, roles):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: pytest.fail("不应读取分析"))
    assert _client(roles).get(BASE).status_code == 403


@pytest.mark.parametrize("params", [{"period": "next_week"}, {"scene": "outpatient_emergency"}])
def test_invalid_query_is_422(params):
    assert _client().get(BASE, params=params).status_code == 422


def test_service_invalid_is_422(monkeypatch):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: (_ for _ in ()).throw(
        service.StaffWorkAnalysisInvalid("时间范围无效")
    ))
    assert _client().get(BASE).status_code == 422


def test_read_failure_is_redacted(monkeypatch):
    monkeypatch.setattr(service, "get_staff_work_analysis", lambda **_kwargs: (_ for _ in ()).throw(
        RuntimeError("patient P001 SQL secret")
    ))
    response = _client().get(BASE)
    assert response.status_code == 503
    assert response.json()["detail"] == "质控员工作分析暂不可用，请稍后重试"
    assert "P001" not in response.text and "secret" not in response.text


def test_report_forwards_compound_department_custom_dates_and_as_of(monkeypatch):
    captured = {}

    def get_analysis(**kwargs):
        captured.update(kwargs)
        return {"staff": [], "summary": {}}

    monkeypatch.setattr(service, "get_staff_work_analysis", get_analysis)
    response = _client().get(BASE, params={
        "institute_id": "H1", "department": "内科", "task_id": "task-1",
        "start_date": "2026-09-01", "end_date": "2026-09-02",
        "as_of": "2026-09-02T12:00:00+08:00",
    })
    assert response.status_code == 200
    assert captured == {
        "period": "this_week", "scene": "all", "institute_id": "H1",
        "department": "内科", "task_id": "task-1", "start_date": "2026-09-01",
        "end_date": "2026-09-02", "as_of": "2026-09-02T12:00:00+08:00",
    }


def test_details_forwards_metric_paging_and_same_filters(monkeypatch):
    captured = {}

    def get_details(**kwargs):
        captured.update(kwargs)
        return {"items": [], "total": 0}

    monkeypatch.setattr(service, "get_staff_work_details", get_details)
    response = _client().get(f"{BASE}/qc-2/details", params={
        "metric": "record_review_count", "page": 2, "page_size": 10,
        "scene": "running", "task_id": "task-1",
    })
    assert response.status_code == 200
    assert captured == {
        "user_id": "qc-2", "metric": "record_review_count", "page": 2,
        "page_size": 10, "period": "this_week", "scene": "running",
        "task_id": "task-1",
    }


def test_export_returns_hardened_csv_and_audits_only_filter_metadata(monkeypatch):
    captured = {}
    audits = []

    def export(**kwargs):
        captured.update(kwargs)
        return b"\xef\xbb\xbfheader\r\n", 2

    monkeypatch.setattr(service, "export_staff_work_csv", export)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))
    response = _client().get(f"{BASE}/export", params={"task_id": "task-1"})
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].endswith("staff-work.csv")
    assert captured == {"period": "this_week", "scene": "all", "task_id": "task-1"}
    assert audits[0]["details"]["task_filter_applied"] is True
    assert audits[0]["details"]["row_count"] == 2
    assert "institute_id" not in audits[0]["details"]


def test_export_too_large_is_413(monkeypatch):
    monkeypatch.setattr(service, "export_staff_work_csv", lambda **_kwargs: (_ for _ in ()).throw(
        service.StaffWorkAnalysisTooLarge(5001)
    ))
    response = _client().get(f"{BASE}/export")
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "staff_work_export_too_large"


@pytest.mark.parametrize("path", [
    f"{BASE}/export",
    f"{BASE}/qc-2/details?metric=record_review_count",
])
def test_non_manager_cannot_export_or_read_details(monkeypatch, path):
    monkeypatch.setattr(
        service, "export_staff_work_csv",
        lambda **_kwargs: pytest.fail("无权用户不应导出"),
    )
    monkeypatch.setattr(
        service, "get_staff_work_details",
        lambda **_kwargs: pytest.fail("无权用户不应读取明细"),
    )
    assert _client(("qc_staff",)).get(path).status_code == 403
