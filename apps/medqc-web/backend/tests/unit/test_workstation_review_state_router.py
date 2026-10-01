"""运行/终末病历列表 review_state 参数的路由合同：解析、422、带参失败 503、不带参不透传。"""

from __future__ import annotations

import pytest

from app.services.medical_records.query_service import (
    WorkstationDefectRangeTooLarge,
    WorkstationDefectUnavailable,
    WorkstationReviewStateUnavailable,
    WorkstationScoreRangeTooLarge,
    WorkstationScoreUnavailable,
)

URL = "/api/medical-records/workstation"
HEADERS = {"Authorization": "Bearer test-token"}


def _authenticate(monkeypatch, roles=None) -> None:
    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-review"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-review", "roles": roles or ["qc_manager"]},
    )


def _capture(monkeypatch) -> dict:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "app.routers.medical_records_query.get_workstation_data",
        lambda **kwargs: captured.update(kwargs) or {"records": [], "total": 0},
    )
    return captured


def test_review_state_multi_value_is_parsed_and_forwarded(client, monkeypatch):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)

    response = client.get(
        f"{URL}?review_state=pending_review,%20pending_recheck,pending_review", headers=HEADERS,
    )

    assert response.status_code == 200
    assert captured["review_state"] == ("pending_review", "pending_recheck")


def test_without_review_state_service_call_is_unchanged(client, monkeypatch):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)

    response = client.get(URL, headers=HEADERS)

    assert response.status_code == 200
    assert "review_state" not in captured
    assert "defect_workflow" not in captured


def test_workflow_filter_forwards_persistent_subject_and_rejects_record_view(client, monkeypatch):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)
    response = client.get(URL, params={"result_view": "defects", "defect_workflow": "clinical_appeal"}, headers=HEADERS)
    assert response.status_code == 200
    assert captured["defect_workflow"] == "clinical_appeal"
    assert captured["defect_workflow_actor_id"] == "u-review"
    response = client.get(URL, params={"defect_workflow": "pending_rectification"}, headers=HEADERS)
    assert response.status_code == 422


def test_workflow_persistent_permission_error_is_403(client, monkeypatch):
    from app.services.defect_rectification_service import RectificationError
    _authenticate(monkeypatch)
    def broken(**kwargs):
        raise RectificationError("缺陷查询权限不足", 403)
    monkeypatch.setattr("app.routers.medical_records_query.get_workstation_data", broken)
    response = client.get(URL, params={"result_view": "defects", "defect_workflow": "clinical_appeal"}, headers=HEADERS)
    assert response.status_code == 403


@pytest.mark.parametrize("value", ["", "rejected", "pending_review,", "approved,bogus", "APPROVED"])
def test_invalid_review_state_is_422(client, monkeypatch, value):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)

    response = client.get(URL, params={"review_state": value}, headers=HEADERS)

    assert response.status_code == 422
    assert captured == {}


def test_review_state_batch_failure_is_desensitized_503(client, monkeypatch):
    _authenticate(monkeypatch)

    def broken(**_kwargs):
        raise WorkstationReviewStateUnavailable("SELECT secret FROM qc_record_reviews")

    monkeypatch.setattr("app.routers.medical_records_query.get_workstation_data", broken)

    response = client.get(URL, params={"review_state": "pending_review"}, headers=HEADERS)

    assert response.status_code == 503
    assert "secret" not in response.text
    assert "审核状态" in response.text


def test_score_filters_are_validated_and_forwarded(client, monkeypatch):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)
    standard_id = "11111111-1111-4111-8111-111111111111"

    response = client.get(
        URL,
        params={
            "standard_id": standard_id,
            "score_status": "scored",
            "grade": "甲",
            "score_min": 80,
            "score_max": 99.5,
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert captured["standard_id"] == standard_id
    assert captured["score_status"] == "scored"
    assert captured["grade"] == "甲"
    assert captured["score_min"] == 80.0
    assert captured["score_max"] == 99.5


@pytest.mark.parametrize("params", [{"score_status": "unknown"}, {"standard_id": "not-uuid"}])
def test_invalid_score_query_is_422(client, monkeypatch, params):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)
    response = client.get(URL, params=params, headers=HEADERS)
    assert response.status_code == 422 and captured == {}


@pytest.mark.parametrize(
    ("error", "status", "text"),
    [
        (WorkstationScoreUnavailable("secret"), 503, "评分数据暂不可用"),
        (WorkstationScoreRangeTooLarge("secret"), 422, "range_too_large"),
    ],
)
def test_score_filter_errors_are_desensitized(client, monkeypatch, error, status, text):
    _authenticate(monkeypatch)
    monkeypatch.setattr(
        "app.routers.medical_records_query.get_workstation_data",
        lambda **_kwargs: (_ for _ in ()).throw(error),
    )
    response = client.get(URL, params={"score_status": "scored"}, headers=HEADERS)
    assert response.status_code == status
    assert text in response.text and "secret" not in response.text


def test_defect_view_and_source_are_forwarded(client, monkeypatch):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)
    response = client.get(
        URL,
        params={"result_view": "defects", "defect_source": "manual"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert captured["result_view"] == "defects"
    assert captured["defect_source"] == "manual"


def test_defect_view_rejects_record_only_has_defect_before_service(client, monkeypatch):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)
    response = client.get(
        URL,
        params={"result_view": "defects", "has_defect": "true"},
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert "不支持 has_defect" in response.text
    assert captured == {}


def test_record_view_rejects_source_without_has_defect_before_service(client, monkeypatch):
    _authenticate(monkeypatch)
    captured = _capture(monkeypatch)
    response = client.get(URL, params={"defect_source": "manual"}, headers=HEADERS)
    assert response.status_code == 422
    assert "必须与 has_defect" in response.text
    assert captured == {}


@pytest.mark.parametrize("params", [{"result_view": "defects"}, {"has_defect": "true"}])
def test_new_defect_queries_reject_doctor_role(client, monkeypatch, params):
    _authenticate(monkeypatch, ["doctor"])
    captured = _capture(monkeypatch)
    response = client.get(URL, params=params, headers=HEADERS)
    assert response.status_code == 403
    assert "权限不足" in response.text
    assert captured == {}


@pytest.mark.parametrize(
    ("error", "status", "text"),
    [
        (WorkstationDefectUnavailable("secret"), 503, "缺陷数据暂不可用"),
        (WorkstationDefectRangeTooLarge("secret"), 422, "range_too_large"),
    ],
)
def test_defect_query_errors_are_desensitized(client, monkeypatch, error, status, text):
    _authenticate(monkeypatch)
    monkeypatch.setattr(
        "app.routers.medical_records_query.get_workstation_data",
        lambda **_kwargs: (_ for _ in ()).throw(error),
    )
    response = client.get(URL, params={"result_view": "defects"}, headers=HEADERS)
    assert response.status_code == status
    assert text in response.text and "secret" not in response.text
