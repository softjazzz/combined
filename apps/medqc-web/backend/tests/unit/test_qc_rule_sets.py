from app.services.qc_rule_sets import get_sichuan_rule_set
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


def test_sc_content_v1_rules_should_exist_in_sichuan_rule_source():
    rule_set = get_sichuan_rule_set("sc_content_v1")
    assert rule_set is not None

    service = SichuanQCService()
    missing = [rule_id for rule_id in rule_set.rule_ids if not service.get_rule_by_id(rule_id)]

    assert missing == []
