import pytest

from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
from tests.luxian_0609_identity_test_support import published_rule_ids
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609.phase_scope import (
    Luxian0609PhaseScopeEntry,
    build_luxian_0609_pending_definition_result,
    load_luxian_0609_phase_scope,
    partition_luxian_0609_rule_scope,
)
from app.services.sample_validation_rule_sets import (
    get_luxian_0609_customer_delivery_rule_ids,
    get_luxian_0609_customer_execution_scope,
)


def test_phase_scope_freezes_all_77_customer_rules() -> None:
    entries = load_luxian_0609_phase_scope()

    assert len(entries) == 77
    assert tuple(entry.rule_id for entry in entries) == tuple(
        published_rule_ids(1, 77)
    )
    assert {entry.definition_version for entry in entries} == {
        "lx0609-defined-scope-2026-09-22-identity-v1"
    }
    assert sum(entry.phase_status == "phase_1_target" for entry in entries) == 67
    assert sum(entry.phase_status == "phase_1_partial" for entry in entries) == 0
    assert sum(entry.phase_status == "pending_definition" for entry in entries) == 10
    assert sum(entry.catalog_registered for entry in entries) == 77


def test_phase_scope_uses_latest_confirmed_contract_and_freezes_only_unresolved_rules() -> None:
    entries = {entry.rule_id: entry for entry in load_luxian_0609_phase_scope()}

    for rule_id in ("LX0609-02-01-05", "LX0609-06-01-02", "LX0609-12-01-02", "LX0609-03-01-04"):
        assert entries[rule_id].phase_status == "phase_1_target"
        assert entries[rule_id].pending_reason_code == ""

    assert entries["LX0609-04-02-04"].phase_status == "pending_definition"
    assert (
        entries["LX0609-04-02-04"].pending_reason_code
        == "implant_five_field_real_gold_pending"
    )
    assert entries["LX0609-05-03-01"].phase_status == "pending_definition"
    assert (
        entries["LX0609-05-03-01"].pending_reason_code
        == "treatment_event_order_course_real_gold_pending"
    )
    assert entries["LX0609-01-01-02"].phase_status == "phase_1_target"
    assert entries["LX0609-01-01-02"].active_criteria == (
        "chief_complaint_length",
        "diagnostic_direction",
    )
    assert entries["LX0609-01-01-02"].pending_criteria == ()
    assert entries["LX0609-01-01-02"].pending_reason_code == ""
    assert {
        rule_id
        for rule_id, entry in entries.items()
        if entry.phase_status == "pending_definition"
    } == {
        "LX0609-03-01-01",
        "LX0609-03-01-02",
        "LX0609-03-01-03",
        "LX0609-04-02-04",
        "LX0609-05-01-01",
        "LX0609-04-04-01",
        "LX0609-07-04-02",
        "LX0609-05-01-04",
        "LX0609-05-03-01",
        "LX0609-10-03-01",
    }


@pytest.mark.parametrize(
    ("rule_id", "pending_reason_code"),
    (
        ("LX0609-07-04-02", "charging_source_unavailable_customer_scope"),
        ("LX0609-05-01-04", "key_antimicrobial_catalog_missing"),
        ("LX0609-05-03-01", "treatment_event_order_course_real_gold_pending"),
        ("LX0609-10-03-01", "invasive_procedure_catalog_missing"),
    ),
)
def test_pending_definition_result_has_one_empty_evidence_contract(
    rule_id: str,
    pending_reason_code: str,
) -> None:
    result = build_luxian_0609_pending_definition_result(rule_id)

    assert result["rule_id"] == rule_id
    assert result["status"] == "not_executed"
    assert result["is_compliant"] is None
    assert result["facts"] == {}
    assert result["evidence"] == []
    assert result["metadata"] == {
        "execution_source": "lx0609_phase_gate",
        "executor_type": "programmatic",
        "reason_code": "policy_definition_pending",
        "pending_reason_code": pending_reason_code,
    }


def test_phase_scope_is_a_read_only_master_projection() -> None:
    master_entries = load_luxian_0609_rule_master()
    phase_entries = load_luxian_0609_phase_scope()

    assert tuple(entry.rule_id for entry in phase_entries) == tuple(
        entry.rule_id for entry in master_entries
    )
    assert [
        (
            entry.phase_status,
            entry.catalog_registered,
            entry.active_criteria,
            entry.pending_criteria,
            entry.pending_reason_code,
        )
        for entry in phase_entries
    ] == [
        (
            entry.phase_status,
            entry.implementation_status == "active",
            entry.active_criteria,
            entry.pending_criteria,
            entry.pending_reason_code,
        )
        for entry in master_entries
    ]


def test_phase_scope_partitions_customer_selection_in_catalog_order() -> None:
    executable, pending = partition_luxian_0609_rule_scope(
        ("LX0609-05-03-01", "LX0609-12-01-02", "LX0609-07-04-02", "LX0609-01-01-01")
    )

    assert executable == ("LX0609-01-01-01", "LX0609-12-01-02")
    assert pending == ("LX0609-07-04-02", "LX0609-05-03-01")


def test_consultation_family_keeps_only_023_executable() -> None:
    """会诊申请单/会诊记录单来源缺失，020/021/022 暂停，只保留 023。"""

    entries = {entry.rule_id: entry for entry in load_luxian_0609_phase_scope()}

    assert entries["LX0609-03-01-04"].phase_status == "phase_1_target"
    for rule_id in ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"):
        assert entries[rule_id].phase_status == "pending_definition"
        assert (
            entries[rule_id].pending_reason_code
            == "consultation_source_document_unavailable_customer_scope"
        )
        result = build_luxian_0609_pending_definition_result(rule_id)
        assert result["status"] == "not_executed"
        assert result["is_compliant"] is None
        assert "请会诊执行记录" in result["findings"]
        assert "LX0609-03-01-04" in result["suggestion"]

    executable, withheld = partition_luxian_0609_rule_scope(
        ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04")
    )
    assert executable == ("LX0609-03-01-04",)
    assert withheld == ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03")


def test_customer_delivery_scope_is_72_with_62_executable_and_10_withheld() -> None:
    delivery = get_luxian_0609_customer_delivery_rule_ids()
    executable, withheld = get_luxian_0609_customer_execution_scope()

    assert len(delivery) == 72
    assert len(executable) == 62
    assert len(withheld) == 10
    assert "LX0609-04-04-01" in withheld
    assert {"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"}.issubset(withheld)
    assert "LX0609-03-01-04" in executable
    result = build_luxian_0609_pending_definition_result("LX0609-04-04-01")
    assert result["status"] == "not_executed"
    assert result["is_compliant"] is None
    assert "数据源暂不可用" in result["findings"]
    assert "不要求据此补写" in result["suggestion"]
    assert set(executable).isdisjoint(withheld)
    assert set(executable) | set(withheld) == set(delivery)
    catalog_ids = {
        str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        for item in load_luxian_0609_rules()
    }
    assert set(delivery) == catalog_ids - {
        "LX0609-11-01-01",
        "LX0609-11-02-01",
        "LX0609-11-02-02",
        "LX0609-11-03-01",
        "LX0609-11-03-02",
    }
    assert delivery == tuple(
        entry.rule_id
        for entry in load_luxian_0609_phase_scope()
        if entry.rule_id not in {
            "LX0609-11-01-01",
            "LX0609-11-02-01",
            "LX0609-11-02-02",
            "LX0609-11-03-01",
            "LX0609-11-03-02",
        }
    )


def test_phase_scope_fails_closed_for_partial_rule_until_criterion_projection_exists(
    monkeypatch,
) -> None:
    entries = (
        Luxian0609PhaseScopeEntry(
            rule_id="LX0609-01-01-01",
            phase_status="phase_1_target",
            catalog_registered=True,
            definition_version="v-test",
        ),
        Luxian0609PhaseScopeEntry(
            rule_id="LX0609-01-02-01",
            phase_status="phase_1_partial",
            catalog_registered=True,
            definition_version="v-test",
            active_criteria=("criterion_ready",),
            pending_criteria=("criterion_pending",),
        ),
        Luxian0609PhaseScopeEntry(
            rule_id="LX0609-04-02-01",
            phase_status="pending_definition",
            catalog_registered=True,
            definition_version="v-test",
            pending_reason_code="pending_contract",
        ),
    )
    monkeypatch.setattr(
        "app.services.luxian_0609.phase_scope.load_luxian_0609_phase_scope",
        lambda: entries,
    )

    executable, withheld = partition_luxian_0609_rule_scope(
        ("LX0609-04-02-01", "LX0609-01-02-01", "LX0609-01-01-01")
    )

    assert executable == ("LX0609-01-01-01",)
    assert withheld == ("LX0609-01-02-01", "LX0609-04-02-01")
