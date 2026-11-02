from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.profiles import ProfileCatalog


class CaptureRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str, str, str]] = []

    def submit(
        self, request: dict[str, Any], actor_id: str, idempotency_key: str, source: str = "manual"
    ) -> dict[str, Any]:
        self.calls.append((request, actor_id, idempotency_key, source))
        return {"job_id": "fictional-job", "request": request, "status": "queued"}


def admission() -> tuple[AdmissionService, CaptureRepository]:
    repository = CaptureRepository()
    service = AdmissionService(
        ProfileCatalog(), repository, clock=lambda: datetime(2026, 11, 1, 18, tzinfo=timezone.utc)
    )
    return service, repository


def request(**changes: Any) -> dict[str, Any]:
    return dict(
        {
            "profile": "core13",
            "interfaces": ["web.mr"],
            "start_date": "2026-10-26",
            "end_date": "2026-10-28",
        },
        **changes,
    )


OPERATOR = Actor("operator", frozenset({"run"}))
PLANNER = Actor("planner", frozenset({"schedule"}))


def test_three_day_request_expands_extracts_then_one_publish() -> None:
    service, repository = admission()
    value = service.submit(request(), OPERATOR, "manual-001")
    normalized = value["request"]
    assert normalized["mode"] == "replay"
    assert normalized["publish"] is True
    assert normalized["units"] == [
        {"interface_name": "web.mr", "source_date": "2026-10-26", "phase": "extract"},
        {"interface_name": "web.mr", "source_date": "2026-10-27", "phase": "extract"},
        {"interface_name": "web.mr", "source_date": "2026-10-28", "phase": "extract"},
        {"interface_name": "web.mr", "source_date": None, "phase": "publish"},
    ]
    assert repository.calls[0][1:] == ("operator", "manual-001", "manual")


def test_dry_and_extract_only_do_not_create_publish_unit() -> None:
    service, _repository = admission()
    for payload in (request(mode="dry"), request(publish=False)):
        value = service.prepare(payload, OPERATOR)
        assert value["publish"] is False
        assert len(value["units"]) == 3
        assert all(unit["phase"] == "extract" for unit in value["units"])


def test_publish_only_has_no_date_or_source_unit() -> None:
    service, _repository = admission()
    value = service.prepare(
        {"profile": "core13", "interfaces": ["web.mr"], "mode": "publish_only"}, OPERATOR
    )
    assert "start_date" not in value and "end_date" not in value
    assert value["units"] == [{"interface_name": "web.mr", "source_date": None, "phase": "publish"}]


@pytest.mark.parametrize(
    "payload",
    [
        request(mode="dry", publish=True),
        request(mode="publish_only"),
        request(publish="false"),
        request(mode="anything"),
        request(interfaces=[]),
        request(interfaces=["web.mr", "web.mr"]),
        request(interfaces=[1]),
        request(start_date="2026-10-28", end_date="2026-10-26"),
        request(start_date="2026-10-20", end_date="2026-10-28"),
        request(start_date="2026-11-02", end_date="2026-11-02"),
        request(start_date="2026-1-1"),
        request(start_date="1840-12-31"),
        request(sql="CALL private()"),
        request(dsn="fictional-private-dsn"),
        request(password="fictional-private-password"),
        request(config_path="C:/private"),
        request(units=[{"phase": "publish"}]),
        request(origin="schedule"),
    ],
)
def test_invalid_request_never_reaches_repository(payload: dict[str, Any]) -> None:
    service, repository = admission()
    with pytest.raises(ControlError) as caught:
        service.submit(payload, OPERATOR, "key-001")
    assert not repository.calls
    assert "fictional-private" not in str(caught.value)


def test_hospital_timezone_determines_last_complete_day_not_utc_date() -> None:
    service, _repository = admission()
    # UTC仍11-01，医院已11-02，因此11-01是已完整日期。
    value = service.prepare(request(start_date="2026-11-01", end_date="2026-11-01"), OPERATOR)
    assert value["end_date"] == "2026-11-01"
    service._clock = lambda: datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    with pytest.raises(ControlError):
        service.prepare(request(start_date="2026-11-01", end_date="2026-11-01"), OPERATOR)


def test_entire_interface_set_validated_before_submission() -> None:
    service, repository = admission()
    for names in (["web.mr", "web.surgery_record"], ["web.mr", "web.nursing_record"]):
        with pytest.raises(ControlError):
            service.submit(request(interfaces=names), OPERATOR, "key-001")
    assert not repository.calls


def test_permissions_and_schedule_policy_are_rechecked() -> None:
    service, repository = admission()
    with pytest.raises(ControlError) as caught:
        service.submit(request(), Actor("reader", frozenset({"read"})), "key-001")
    assert caught.value.status_code == 403
    with pytest.raises(ControlError):
        service.prepare(request(), OPERATOR, origin="schedule")
    value = service.submit(request(), PLANNER, "schedule-001", origin="schedule")
    assert value["status"] == "queued"
    assert repository.calls[0][3] == "schedule"
    with pytest.raises(ControlError):
        service.prepare(request(interfaces=["web.admission_record"]), PLANNER, origin="schedule")


def test_idempotency_key_and_clock_are_validated_without_secret_output() -> None:
    service, repository = admission()
    for key in ("", "private secret key", "\n", "x" * 129):
        with pytest.raises(ControlError):
            service.submit(request(), OPERATOR, key)
    assert not repository.calls
    service._clock = lambda: datetime(2026, 11, 1)
    with pytest.raises(ControlError) as caught:
        service.prepare(request(), OPERATOR)
    assert caught.value.code == "invalid_clock"


def test_interface_order_normalizes_for_request_idempotency() -> None:
    service, _repository = admission()
    a = service.prepare(request(interfaces=["web.mr", "web.admission_record"]), OPERATOR)
    b = service.prepare(request(interfaces=["web.admission_record", "web.mr"]), OPERATOR)
    assert a == b
