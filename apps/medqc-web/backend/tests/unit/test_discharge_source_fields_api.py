"""只读现场核查：权限、范围、失败脱敏和字段/时间混淆回归。"""

from unittest.mock import Mock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import qc_diagnostics
from app.services.qc_diagnostics import discharge_source_fields as service


BASE = "/api/v1/qc/diagnostics/source-fields/discharge/00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    app.include_router(qc_diagnostics.router)
    user = {"id": "synthetic-admin", "roles": ["admin"]}
    app.dependency_overrides[get_current_user] = lambda: user
    check = Mock(return_value={"read_only": True, "passed": True})
    monkeypatch.setattr(service, "check_discharge_source_fields", check)
    return TestClient(app), user, check


def test_admin_scope_uses_service_and_no_cache(api):
    client, _, check = api
    response = client.get(BASE, params=[("row_no", 3), ("row_no", 18)])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    check.assert_called_once_with(pool_id=BASE.rsplit("/", 1)[1], row_numbers=[3, 18])


def test_doctor_cannot_read_and_no_service_access(api):
    client, user, check = api
    user["roles"] = ["doctor"]
    assert client.get(BASE, params={"row_no": 3}).status_code == 403
    check.assert_not_called()


def test_unauthenticated_cannot_read(monkeypatch):
    app = FastAPI(dependencies=[Depends(enforce_default_auth)])
    app.include_router(qc_diagnostics.router)
    check = Mock()
    monkeypatch.setattr(service, "check_discharge_source_fields", check)
    assert TestClient(app).get(BASE, params={"row_no": 3}).status_code == 401
    check.assert_not_called()


@pytest.mark.parametrize("rows", [[], [1] * 2, [0], [-1], list(range(1, 8))])
def test_invalid_scope_never_reads(api, rows):
    client, _, check = api
    assert client.get(BASE, params=[("row_no", row) for row in rows]).status_code == 422
    check.assert_not_called()


@pytest.mark.parametrize("error,status", [(LookupError("private-identifier"), 404), (RuntimeError("private-text"), 503)])
def test_error_does_not_expose_source(api, error, status):
    client, _, check = api
    check.side_effect = error
    response = client.get(BASE, params={"row_no": 1})
    assert response.status_code == status
    assert "private" not in response.text


def _raw():
    return {"document_id": "synthetic-doc", "chief_physician_sign_datetime": "2026-01-03T00:00:00+08:00",
            "v2_schema": '{"private_body":"synthetic-secret-content"}', "record_time": None, "submit_time": None}


def test_exact_fields_preserved_and_signing_is_not_clock():
    raw = _raw()
    result = service._layer_check([raw], raw)
    assert result["passed"]
    assert not result["document_time_present"]
    assert not result["completion_time_present"]
    assert "synthetic-secret-content" not in str(result)
    assert "2026-01-03" not in str(result)


@pytest.mark.parametrize("mutation", ["missing_json", "changed_json", "promoted_record", "promoted_submit", "duplicate", "missing_row"])
def test_projection_or_time_loss_does_not_pass(mutation):
    raw = _raw()
    changed = dict(raw)
    if mutation == "missing_json":
        del changed["v2_schema"]
    if mutation == "changed_json":
        changed["v2_schema"] = "{}"
    if mutation == "promoted_record":
        changed["record_time"] = raw["chief_physician_sign_datetime"]
    if mutation == "promoted_submit":
        changed["submit_time"] = raw["chief_physician_sign_datetime"]
    rows = [] if mutation == "missing_row" else [changed] * (2 if mutation == "duplicate" else 1)
    assert not service._layer_check(rows, raw)["passed"]


def test_source_null_json_readable_without_fabrication():
    raw = {**_raw(), "v2_schema": None}
    assert service._layer_check([raw], raw)["passed"]
    assert not service._layer_check([{k: v for k, v in raw.items() if k != "v2_schema"}], raw)["passed"]


@pytest.mark.parametrize("clock", ["document", "completion"])
def test_both_layers_misusing_signature_clock_cannot_pass(monkeypatch, clock):
    def wrong_clock(row):
        return row.get("chief_physician_sign_datetime")

    if clock == "document":
        monkeypatch.setattr(service.reader, "authoritative_document_time_value", wrong_clock)
    else:
        monkeypatch.setattr(service, "_discharge_record_completion_time", wrong_clock)
    raw = _raw()
    assert not service._layer_check([raw], raw)["passed"]
