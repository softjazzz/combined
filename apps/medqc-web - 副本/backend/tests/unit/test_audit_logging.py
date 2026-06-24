from __future__ import annotations

import logging

from starlette.requests import Request

from app.core.audit import audit_event


def _build_request(path: str = "/unit-test") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    request.state.trace_id = "trace-unit-audit"
    return request


def test_audit_event_masks_sensitive_details(caplog):
    request = _build_request("/api/v1/sync/config/pg")

    with caplog.at_level(logging.INFO, logger="app.audit"):
        audit_event(
            request,
            action="sync.config.pg.update",
            resource="/api/v1/sync/config/pg",
            outcome="success",
            current_user={"email": "admin@medqc.com", "roles": ["admin"]},
            details={
                "remote_host": "127.0.0.1",
                "remote_password": "plain-secret",
                "nested": {"token": "jwt-token"},
            },
        )

    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "action=sync.config.pg.update" in logs
    assert "actor=admin@medqc.com" in logs
    assert "trace_id=trace-unit-audit" in logs
    assert "***" in logs
    assert "plain-secret" not in logs
    assert "jwt-token" not in logs
