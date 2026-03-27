from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.api
def test_openapi_refresh_declares_json_body(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200, resp.text
    spec = resp.json()

    refresh_post = spec["paths"]["/api/v1/auth/refresh"]["post"]
    content = refresh_post["requestBody"]["content"]
    assert "application/json" in content

    schema = content["application/json"]["schema"]
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        schema = spec["components"]["schemas"][name]
    assert "refresh_token" in schema.get("properties", {})


@pytest.mark.unit
@pytest.mark.api
def test_openapi_sync_trigger_declares_security(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200, resp.text
    spec = resp.json()

    sync_trigger = spec["paths"]["/api/v1/sync/trigger"]["post"]
    assert sync_trigger.get("security"), "sync trigger must declare auth security in OpenAPI"
