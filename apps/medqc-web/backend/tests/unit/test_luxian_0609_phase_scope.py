from app.services.luxian_0609.phase_scope import load_luxian_0609_phase_scope


def test_phase_scope_freezes_all_75_customer_rules() -> None:
    entries = load_luxian_0609_phase_scope()

    assert len(entries) == 75
    assert tuple(entry.rule_id for entry in entries) == tuple(
        f"LX0609-{index:03d}" for index in range(1, 76)
    )
    assert sum(entry.phase_status == "phase_1_target" for entry in entries) == 45
    assert sum(entry.phase_status == "phase_1_partial" for entry in entries) == 2
    assert sum(entry.phase_status == "pending_definition" for entry in entries) == 28
    assert sum(entry.catalog_registered for entry in entries) == 63


def test_phase_scope_splits_rules_009_and_018_without_enabling_pending_semantics() -> None:
    entries = {entry.rule_id: entry for entry in load_luxian_0609_phase_scope()}

    assert entries["LX0609-009"].active_criteria == (
        "critical_daily_course_coverage",
    )
    assert entries["LX0609-009"].pending_criteria == (
        "condition_change_course_timeliness",
    )
    assert entries["LX0609-018"].active_criteria == (
        "chief_complaint_length_lte_20",
    )
    assert entries["LX0609-018"].pending_criteria == (
        "chief_complaint_diagnostic_direction",
    )
