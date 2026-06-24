from __future__ import annotations

from app.services.sc_rule_launch_tier import (
    ALLOWED_LAUNCH_TIERS,
    list_sc_intrinsic_rule_ids_by_launch_tier,
    load_sc_intrinsic_launch_tier_map,
    load_sc_intrinsic_launch_tier_payload,
    resolve_sc_intrinsic_launch_tier,
    validate_sc_intrinsic_launch_tier_map,
)


def test_sc_intrinsic_launch_tier_map_should_cover_sc146_baseline():
    mapping = load_sc_intrinsic_launch_tier_map()
    report = validate_sc_intrinsic_launch_tier_map(mapping)

    assert report["ok"] is True
    assert report["mapped_rule_count"] == 84
    assert report["intrinsic_rule_count"] == 84


def test_sc_intrinsic_launch_tier_summary_should_match_expected_distribution():
    payload = load_sc_intrinsic_launch_tier_payload()
    summary = payload["launch_tier_summary"]

    assert summary["A"]["rule_count"] == 37
    assert summary["B"]["rule_count"] == 38
    assert summary["C"]["rule_count"] == 9


def test_sc_intrinsic_launch_tier_map_should_only_emit_allowed_tiers():
    mapping = load_sc_intrinsic_launch_tier_map()

    assert set(mapping.values()).issubset(set(ALLOWED_LAUNCH_TIERS))


def test_resolve_sc_intrinsic_launch_tier_should_return_expected_tier():
    mapping = load_sc_intrinsic_launch_tier_map()

    assert resolve_sc_intrinsic_launch_tier("SC-004", launch_tier_map=mapping) == "A"
    assert resolve_sc_intrinsic_launch_tier("SC-010", launch_tier_map=mapping) == "B"
    assert resolve_sc_intrinsic_launch_tier("SC-034", launch_tier_map=mapping) == "C"
    assert resolve_sc_intrinsic_launch_tier("LX-001", launch_tier_map=mapping) == "UNKNOWN"


def test_list_sc_intrinsic_rule_ids_by_launch_tier_should_match_expected_counts():
    assert len(list_sc_intrinsic_rule_ids_by_launch_tier("A")) == 37
    assert len(list_sc_intrinsic_rule_ids_by_launch_tier("B")) == 38
    assert len(list_sc_intrinsic_rule_ids_by_launch_tier("C")) == 9
    assert list_sc_intrinsic_rule_ids_by_launch_tier("UNKNOWN") == ()
