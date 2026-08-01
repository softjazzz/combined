from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.luxian_0609 import (
    LUXIAN_0609_RULE_SET_KEY,
    build_family_scopes,
    customer_rule_count,
    load_luxian_0609_rules,
    resolve_execution_scope,
)


def _assert_success_shell(body: dict) -> dict:
    assert body["success"] is True
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert "data" in body
    return body["data"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str = "admin@medqc.com", password: str = "admin888") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _load_existing_rule_ids() -> set[str]:
    root = Path(__file__).resolve().parents[2]
    files = [
        root / "app" / "data" / "sichuan_rules_146.json",
        root / "app" / "data" / "custom_rules_33.json",
        root / "app" / "data" / "customer_rules_luxian_v1.json",
    ]
    rule_ids: set[str] = set()
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        for item in payload:
            rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
            if rule_id:
                rule_ids.add(rule_id)
    return rule_ids


@pytest.mark.unit
def test_luxian_0609_catalog_has_63_registered_rules_and_examples():
    rules = load_luxian_0609_rules()

    assert len(rules) == 63
    assert customer_rule_count() == 63
    assert rules[0]["rule_id"] == "LX0609-001"
    assert rules[-1]["rule_id"] == "LX0609-074"

    existing_rule_ids = _load_existing_rule_ids()
    phase_extension_rule_ids = {
        "LX0609-051",
        "LX0609-060",
        "LX0609-061",
        "LX0609-062",
        "LX0609-064",
        "LX0609-065",
        "LX0609-066",
        "LX0609-067",
        "LX0609-068",
        "LX0609-069",
        "LX0609-071",
        "LX0609-072",
        "LX0609-073",
        "LX0609-074",
    }
    for rule in rules:
        assert rule["rule_id"].startswith("LX0609-")
        assert rule.get("positive_example")
        assert rule.get("negative_example")
        assert rule.get("mapped_rule_ids")
        assert rule.get("primary_execution_rule_id") == rule["mapped_rule_ids"][0]
        for mapped_rule_id in rule["mapped_rule_ids"]:
            assert (
                mapped_rule_id.upper() in existing_rule_ids
                or mapped_rule_id.upper() in phase_extension_rule_ids
            )


@pytest.mark.unit
def test_luxian_0609_customer_rule_package_resolves_scope_and_families():
    execution_rule_ids, invalid_rule_ids, gate_only_customer_rule_ids = resolve_execution_scope(
        ["LX0609-020", "LX0609-021", "LX0609-028", "LX0609-999"],
        allowed_rule_ids={"LX0609-020", "LX0609-021", "LX0609-028"},
    )

    assert execution_rule_ids == ["LX0609-020", "LX0609-021", "LX0609-028"]
    assert invalid_rule_ids == ["LX0609-999"]
    assert gate_only_customer_rule_ids == []

    scopes = build_family_scopes(["LX0609-020", "LX0609-021", "LX0609-028"])
    assert scopes == [
        {"key": "consultation_quality", "name": "会诊质量", "rule_ids": ["LX0609-020", "LX0609-021"]},
        {"key": "surgery_anesthesia", "name": "手术麻醉", "rule_ids": ["LX0609-028"]},
    ]


@pytest.mark.unit
@pytest.mark.api
def test_luxian_0609_rules_endpoint_returns_customer_rule_view(client):
    access_token = _login(client)
    resp = client.get(
        f"/api/v1/qc/sichuan/rules?rule_set_key={LUXIAN_0609_RULE_SET_KEY}",
        headers=_headers(access_token),
    )
    assert resp.status_code == 200, resp.text

    payload = _assert_success_shell(resp.json())
    rules = payload["rules"]
    assert payload["rule_set_key"] == LUXIAN_0609_RULE_SET_KEY
    assert payload["total_rules"] == 63
    assert len(rules) == 63
    assert rules[0]["rule_id"] == "LX0609-001"
    assert rules[0]["positive_example"]
    assert rules[0]["negative_example"]
    assert rules[0]["mapped_rule_ids"]
    assert rules[0]["primary_execution_rule_id"] == rules[0]["mapped_rule_ids"][0]
