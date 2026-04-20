from app.services.fast_screen_qc import (
    EXECUTION_STRATEGY_FAST_SCREEN,
    EXECUTION_STRATEGY_STANDARD,
    get_fast_screen_full_rule_ids,
    get_fast_screen_pack_definitions,
    get_fast_screen_rule_ids,
    normalize_execution_strategy,
)


def test_fast_screen_pack_definitions_should_match_fixed_grouping():
    packs = get_fast_screen_pack_definitions()

    assert [pack.pack_id for pack in packs] == [
        "first_course_features",
        "first_course_reasoning",
        "daily_course_core",
        "discharge_core",
    ]
    assert [list(pack.rule_ids) for pack in packs] == [
        ["SC-023", "SC-024"],
        ["SC-025", "SC-026", "SC-027"],
        ["SC-032", "SC-033", "SC-036"],
        ["SC-121", "SC-122", "SC-123", "SC-125"],
    ]
    assert max(len(pack.rule_ids) for pack in packs) <= 10
    assert tuple(sorted(get_fast_screen_rule_ids())) == tuple(
        sorted(
            [
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
        )
    )


def test_fast_screen_pack_definitions_should_filter_by_rule_ids():
    packs = get_fast_screen_pack_definitions(["SC-024", "SC-026", "SC-123"])

    assert [pack.pack_id for pack in packs] == [
        "first_course_features",
        "first_course_reasoning",
        "discharge_core",
    ]
    assert [list(pack.rule_ids) for pack in packs] == [
        ["SC-024"],
        ["SC-026"],
        ["SC-123"],
    ]


def test_fast_screen_full_rule_ids_should_cover_all_84_intrinsic_rules():
    rule_ids = get_fast_screen_full_rule_ids()

    assert len(rule_ids) == 84
    assert len(set(rule_ids)) == 84
    assert "SC-004" in rule_ids
    assert "SC-146" in rule_ids


def test_fast_screen_pack_definitions_should_expand_to_full_intrinsic_buckets_when_requested():
    packs = get_fast_screen_pack_definitions(["SC-004", "SC-015", "SC-121", "SC-146"])

    assert [pack.pack_id for pack in packs] == [
        "admission_content_core",
        "admission_consistency_core",
        "discharge_procedure",
        "daily_order_consistency",
    ]
    assert [list(pack.rule_ids) for pack in packs] == [
        ["SC-004"],
        ["SC-015"],
        ["SC-121"],
        ["SC-146"],
    ]


def test_fast_screen_full_buckets_should_cover_all_rules_without_overlap():
    rule_to_pack: dict[str, str] = {}

    for pack in get_fast_screen_pack_definitions(get_fast_screen_full_rule_ids()):
        for rule_id in pack.rule_ids:
            assert rule_id not in rule_to_pack
            rule_to_pack[rule_id] = pack.pack_id

    assert len(rule_to_pack) == 84


def test_normalize_execution_strategy_should_fall_back_to_standard():
    assert normalize_execution_strategy("fast_screen") == EXECUTION_STRATEGY_FAST_SCREEN
    assert normalize_execution_strategy("FAST_SCREEN") == EXECUTION_STRATEGY_FAST_SCREEN
    assert normalize_execution_strategy("unknown") == EXECUTION_STRATEGY_STANDARD
    assert normalize_execution_strategy(None) == EXECUTION_STRATEGY_STANDARD
