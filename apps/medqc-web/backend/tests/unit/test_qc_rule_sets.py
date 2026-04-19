from app.services.qc_rule_sets import get_sichuan_rule_set, list_sichuan_rule_sets
from app.services.sichuan_qc_service import SichuanQCService


def test_sc_content_v1_rule_set_should_be_fixed_first_batch():
    rule_set = get_sichuan_rule_set("sc_content_v1")

    assert rule_set is not None
    assert rule_set.name == "内涵质控首批 v1"
    assert rule_set.scope == "final"
    assert rule_set.quality_profile == "effect_priority_v1"
    assert rule_set.bucket_strategy == "domain_family"
    assert rule_set.enable_selective_refine is True
    assert rule_set.refine_confidence_threshold == 0.75
    assert list(rule_set.rule_ids) == [
        "SC-023",
        "SC-024",
        "SC-025",
        "SC-026",
        "SC-027",
        "SC-032",
        "SC-033",
        "SC-036",
        "SC-121",
        "SC-122",
        "SC-123",
        "SC-125",
    ]


def test_split_launch_rule_sets_should_match_latest_p1a_decision():
    hard_rule_set = get_sichuan_rule_set("sc_content_hard_v1")
    review_rule_set = get_sichuan_rule_set("sc_content_review_v1")
    full_rule_set = get_sichuan_rule_set("sc_content_v1")

    assert hard_rule_set is not None
    assert review_rule_set is not None
    assert full_rule_set is not None

    assert hard_rule_set.name == "内涵质控硬判定首发 v1"
    assert list(hard_rule_set.rule_ids) == [
        "SC-033",
        "SC-121",
        "SC-123",
    ]

    assert review_rule_set.name == "内涵质控待复核首发 v1"
    assert list(review_rule_set.rule_ids) == [
        "SC-023",
        "SC-024",
        "SC-025",
        "SC-026",
        "SC-027",
        "SC-032",
        "SC-036",
        "SC-122",
        "SC-125",
    ]

    assert set(hard_rule_set.rule_ids).isdisjoint(set(review_rule_set.rule_ids))
    assert set(hard_rule_set.rule_ids) | set(review_rule_set.rule_ids) == set(full_rule_set.rule_ids)


def test_sc_content_v1_rules_should_exist_in_sichuan_rule_source():
    rule_set = get_sichuan_rule_set("sc_content_v1")
    assert rule_set is not None

    service = SichuanQCService()
    missing = [rule_id for rule_id in rule_set.rule_ids if not service.get_rule_by_id(rule_id)]

    assert missing == []


def test_rule_set_list_should_expose_new_launch_rule_sets():
    items = list_sichuan_rule_sets()
    keys = {item["rule_set_key"] for item in items}

    assert "sc_content_hard_v1" in keys
    assert "sc_content_review_v1" in keys
    assert "sc_content_v1" in keys
