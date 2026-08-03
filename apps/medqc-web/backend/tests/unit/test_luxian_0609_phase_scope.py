from app.services.luxian_0609.phase_scope import load_luxian_0609_phase_scope


def test_phase_scope_freezes_all_75_customer_rules() -> None:
    entries = load_luxian_0609_phase_scope()

    assert len(entries) == 75
    assert tuple(entry.rule_id for entry in entries) == tuple(
        f"LX0609-{index:03d}" for index in range(1, 76)
    )
    assert sum(entry.phase_status == "phase_1_target" for entry in entries) == 65
    assert sum(entry.phase_status == "phase_1_partial" for entry in entries) == 1
    assert sum(entry.phase_status == "pending_definition" for entry in entries) == 9
    assert sum(entry.catalog_registered for entry in entries) == 75


def test_phase_scope_keeps_confirmed_partial_criteria_and_freezes_pending_rules() -> None:
    entries = {entry.rule_id: entry for entry in load_luxian_0609_phase_scope()}

    assert entries["LX0609-009"].active_criteria == (
        "critical_daily_course_coverage",
    )
    assert entries["LX0609-009"].pending_criteria == (
        "condition_change_course_timeliness",
    )
    assert entries["LX0609-018"].phase_status == "phase_1_target"
    assert entries["LX0609-018"].active_criteria == (
        "chief_complaint_length",
        "diagnostic_direction",
    )
    assert entries["LX0609-018"].pending_criteria == ()
    assert entries["LX0609-018"].pending_reason_code == ""
    assert {
        rule_id
        for rule_id, entry in entries.items()
        if entry.phase_status == "pending_definition"
    } == {
        "LX0609-010",
        "LX0609-017",
        "LX0609-023",
        "LX0609-024",
        "LX0609-028",
        "LX0609-049",
        "LX0609-056",
        "LX0609-059",
        "LX0609-075",
    }
