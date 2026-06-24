from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException, status

from app.core.rate_limit import reset_rate_limit_store_for_testing


def _login(client, email: str = "admin@medqc.com", password: str = "admin888") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    return payload["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _force_rate_limited(*_args, **_kwargs):
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests, please retry later.",
    )


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limit_store_for_testing()


def test_tools_upload_endpoint_enforces_rate_limit(client, monkeypatch):
    monkeypatch.setattr("app.routers.tools.enforce_rate_limit", _force_rate_limited)
    token = _login(client)

    resp = client.post(
        "/api/v1/parse-medical-file-public",
        headers=_headers(token),
        files={"file": ("sample.txt", b"hello", "text/plain")},
        data={"options": "{}"},
    )
    assert resp.status_code == 429


def test_drg_batch_upload_endpoint_enforces_rate_limit(client, monkeypatch):
    monkeypatch.setattr("app.routers.drg.enforce_rate_limit", _force_rate_limited)
    token = _login(client)

    csv_payload = "病案号,性别,年龄,住院天数,诊断列表,总费用\nA001,1,32,3,I10,1000\n".encode("utf-8")
    resp = client.post(
        "/api/v1/drg/batch-upload",
        headers=_headers(token),
        files={"file": ("sample.csv", csv_payload, "text/csv")},
    )
    assert resp.status_code == 429


def test_records_upload_endpoint_enforces_rate_limit(client, monkeypatch):
    monkeypatch.setattr("app.routers.records.enforce_rate_limit", _force_rate_limited)
    token = _login(client)

    resp = client.post(
        "/api/v1/records/upload",
        headers=_headers(token),
        files={"file": ("record.txt", b"content", "text/plain")},
    )
    assert resp.status_code == 429


def test_smart_upload_rate_limit_writes_audit_log(client, caplog):
    caplog.set_level(logging.WARNING, logger="app.core.rate_limit")
    token = _login(client)
    headers = _headers(token)

    for _ in range(10):
        allowed_resp = client.post(
            "/api/v1/drg/smart-upload",
            headers=headers,
            files={"file": ("unsupported.txt", b"dummy", "text/plain")},
        )
        assert allowed_resp.status_code == 400

    blocked_resp = client.post(
        "/api/v1/drg/smart-upload",
        headers=headers,
        files={"file": ("unsupported.txt", b"dummy", "text/plain")},
    )
    assert blocked_resp.status_code == 429
    assert any(
        "audit.rate_limit.exceeded" in rec.getMessage() and "drg_smart_upload" in rec.getMessage()
        for rec in caplog.records
    )
