"""运行/终末病历列表 review_state 参数的路由合同：解析、422、带参失败 503、不带参不透传。"""

from __future__ import annotations

import pytest

from app.services.medical_records.query_service import WorkstationReviewStateUnavailable

URL = "/api/medical-records/workstation"
HEADERS = {"Authorization": "Bearer test-token"}


def _authenticate(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-review"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-review", "roles": ["qc_manager"]},
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
