from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.domain import INTERFACE_REGISTRY
from medqc_ingest.periop_replay import DISABLED, EXPECTED_COUNTS


def test_catalog_preserves_original_registry_and_has_two_isolated_profiles() -> None:
    original = dict(INTERFACE_REGISTRY)
    with patch("medqc_ingest.config.read_secret", side_effect=AssertionError("no secret read")):
        catalog = ProfileCatalog()
    assert dict(INTERFACE_REGISTRY) == original
    assert set(catalog.get("core13").specs) == set(original)
    assert set(catalog.get("periop13").specs) == set(EXPECTED_COUNTS)
    assert not set(catalog.get("core13").specs) & set(catalog.get("periop13").specs)
    assert catalog.resolve_spec("core13", "web.mr") is INTERFACE_REGISTRY["web.mr"]


def test_readiness_is_enforced_on_every_validation() -> None:
    catalog = ProfileCatalog()
    assert catalog.validate("core13", ["web.mr"], "replay").ready
    with pytest.raises(ControlError) as caught:
        catalog.validate("periop13", ["web.nursing_record"], "replay")
    assert caught.value.code == "profile_disabled"
    unready = ProfileCatalog({"periop13": {"enabled": True}})
    with pytest.raises(ControlError) as caught:
        unready.validate("periop13", ["web.nursing_record"], "replay")
    assert caught.value.code == "profile_not_ready"
    accepted = ProfileCatalog({"periop13": {"enabled": True, "ready": True}})
    assert accepted.validate("periop13", ["web.nursing_record"], "replay").ready


def test_metadata_cannot_expand_interface_or_unverified_strategy() -> None:
    for metadata in (
        {"other": {}},
        {"core13": {"specs": {}}},
        {"core13": {"enabled": "true"}},
        {"core13": {"ready": 1}},
        {"core13": {"incremental_interfaces": ["web.admission_record"]}},
        {"core13": {"scheduled_interfaces": ["web.inpat_drug_order"]}},
        {"periop13": {"incremental_interfaces": ["web.nursing_record"]}},
    ):
        with pytest.raises(ControlError):
            ProfileCatalog(metadata)


def test_disabled_or_other_profile_interfaces_never_resolve() -> None:
    catalog = ProfileCatalog({"periop13": {"enabled": True, "ready": True}})
    for name in (*DISABLED, "web.mr", "web.fake"):
        with pytest.raises(ControlError):
            catalog.validate("periop13", [name], "replay")
    with pytest.raises(ControlError):
        catalog.resolve_spec("core13", "web.nursing_record")
    with pytest.raises(ControlError):
        catalog.get("fictional-private-profile-value")


def test_only_approved_mr_supports_incremental_and_schedule() -> None:
    catalog = ProfileCatalog()
    catalog.validate("core13", ["web.mr"], "incremental")
    catalog.validate("core13", ["web.mr"], "replay", "schedule")
    for name in set(INTERFACE_REGISTRY) - {"web.mr"}:
        with pytest.raises(ControlError):
            catalog.validate("core13", [name], "incremental")
        with pytest.raises(ControlError):
            catalog.validate("core13", [name], "replay", "schedule")
    catalog = ProfileCatalog({"core13": {"incremental_interfaces": [], "scheduled_interfaces": []}})
    with pytest.raises(ControlError):
        catalog.validate("core13", ["web.mr"], "incremental")


def test_profile_specs_are_immutable_and_description_does_not_enable_sources() -> None:
    catalog = ProfileCatalog()
    with pytest.raises(TypeError):
        catalog.get("core13").specs["new"] = INTERFACE_REGISTRY["web.mr"]  # type: ignore[index]
    rows = {row["profile"]: row for row in catalog.describe()}
    assert len(rows["core13"]["interfaces"]) == 13
    assert rows["periop13"]["ready"] is False
    assert all(not row["allowed_modes"] for row in rows["periop13"]["interfaces"])
    assert rows["periop13"]["disabled_interfaces"] == DISABLED


def test_missing_or_tampered_contract_fails_without_private_path_or_content() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / "fictional-private-contract.json"
        for write in (False, True):
            if write:
                file.write_text("fictional-private-body", encoding="utf-8")
            with pytest.raises(ControlError) as caught:
                ProfileCatalog(contract_path=file)
            assert caught.value.status_code == 503
            assert "fictional-private" not in str(caught.value)


def test_source_failure_contract_is_frozen_copy_not_mutable_catalog_state() -> None:
    catalog = ProfileCatalog()
    assert catalog.source_contract("core13", "web.mr") is None
    item = catalog.source_contract("periop13", "web.blood_application")
    assert item is not None and item["source_state"] == "partial_source"
    original = catalog.source_contract("periop13", "web.blood_application")
    item["source_window_status"].clear()
    assert catalog.source_contract("periop13", "web.blood_application") == original
    with pytest.raises(ControlError):
        catalog.source_contract("periop13", "web.surgery_record")


def test_actor_permission_hierarchy_and_error_redaction() -> None:
    assert Actor("reader", frozenset({"read"})).has("read")
    assert Actor("operator", frozenset({"run"})).has("read")
    assert Actor("planner", frozenset({"schedule"})).has("run")
    assert not Actor("reader", frozenset({"read"})).has("schedule")
    with pytest.raises(ControlError) as caught:
        Actor("reader", frozenset({"read"})).require("run")
    assert caught.value.status_code == 403
    error = ControlError("fictional-private body", "fictional-private body", 999)
    assert "fictional-private" not in str(error)
    assert error.status_code == 500
