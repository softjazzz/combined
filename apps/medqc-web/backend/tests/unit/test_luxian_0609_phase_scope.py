import json
from itertools import combinations
from pathlib import Path

import pytest

from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609.phase_scope import (
    Luxian0609PhaseScopeEntry,
    build_luxian_0609_pending_definition_result,
    load_luxian_0609_phase_scope,
    partition_luxian_0609_rule_scope,
)
from app.services.sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
    get_luxian_0609_customer_delivery_rule_ids,
    get_luxian_0609_customer_execution_scope,
)


_MASTER_PATH = Path(__file__).resolve().parents[2] / "app/data/luxian_0609_rule_master_v1.json"
_CUSTOMER_EXCLUDED_IDS = frozenset(
    {
        "LX0609-11-01-01",
        "LX0609-11-02-01",
        "LX0609-11-02-02",
        "LX0609-11-03-01",
        "LX0609-11-03-02",
    }
)
_ACCEPTANCE_ONLY_IDS = frozenset(
    {
        "LX0609-04-02-09",
        "LX0609-10-04-01",
        "LX0609-06-03-05", "LX0609-06-03-06",
        "LX0609-06-01-03",
        "LX0609-06-03-02",
        "LX0609-06-02-01",
        "LX0609-09-01-02",
        "LX0609-08-01-05",
    }
)


def _raw_master():
    """预期直接读取权威 JSON，不经加载器或 phase 投影。"""
    return json.loads(_MASTER_PATH.read_text(encoding="utf-8"))


def test_phase_scope_projects_each_raw_master_rule_in_declared_order() -> None:
    payload = _raw_master()
    raw_rules = payload["rules"]
    entries = load_luxian_0609_phase_scope()
    expected_ids = tuple(raw["rule_id"] for raw in raw_rules)

    assert expected_ids
    assert len(set(expected_ids)) == len(expected_ids)
    assert tuple(entry.rule_id for entry in entries) == expected_ids
    registered_ids = tuple(entry.rule_id for entry in entries if entry.catalog_registered)
    assert registered_ids == tuple(
        raw["rule_id"] for raw in raw_rules if raw["implementation_status"] == "active"
    )
    assert registered_ids == tuple(str(item["rule_id"]) for item in load_luxian_0609_rules())
    assert {entry.definition_version for entry in entries} == {payload["definition_version"]}
    assert payload["definition_version"] == "lx0609-defined-scope-2026-09-22-identity-v1"
    for entry, raw in zip(entries, raw_rules, strict=True):
        assert (
            entry.phase_status,
            entry.catalog_registered,
            entry.active_criteria,
            entry.pending_criteria,
            entry.pending_reason_code,
        ) == (
            raw.get("phase_status", "phase_1_target"),
            raw["implementation_status"] == "active",
            tuple(raw.get("active_criteria", ())),
            tuple(raw.get("pending_criteria", ())),
            raw.get("pending_reason_code", ""),
        ), entry.rule_id
    phase_sets = []
    for status in ("phase_1_target", "phase_1_partial", "pending_definition"):
        expected = tuple(
            raw["rule_id"] for raw in raw_rules
            if raw.get("phase_status", "phase_1_target") == status
        )
        actual = tuple(entry.rule_id for entry in entries if entry.phase_status == status)
        assert actual == expected
        phase_sets.append(set(actual))
    assert all(left.isdisjoint(right) for left, right in combinations(phase_sets, 2))
    assert set().union(*phase_sets) == set(expected_ids)


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
        "LX0609-04-04-01",
        # 访视来源缺失，与 04-04-01 同口径暂停（2026-10-10）。
        "LX0609-04-04-02",
        "LX0609-07-04-02",
        # 056 已按院方重点抗菌药物七类清单恢复执行（2026-10-11）。
        "LX0609-05-03-01",
        "LX0609-06-03-01",
        # 2026-11-10 用户决定七条暂未启用，保留旧暂停项及目录身份。
        "LX0609-06-02-02", "LX0609-05-01-01", "LX0609-08-01-04",
        "LX0609-12-02-01", "LX0609-06-01-04", "LX0609-10-03-01", "LX0609-04-02-02",
    }


@pytest.mark.parametrize(
    ("rule_id", "pending_reason_code"),
    (
        ("LX0609-07-04-02", "charging_source_unavailable_customer_scope"),
        ("LX0609-05-03-01", "treatment_event_order_course_real_gold_pending"),
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


def test_customer_delivery_excludes_registration_only_handbook_rules() -> None:
    delivery = get_luxian_0609_customer_delivery_rule_ids()
    executable, withheld = get_luxian_0609_customer_execution_scope()

    raw_rules = _raw_master()["rules"]
    assert LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS == _CUSTOMER_EXCLUDED_IDS
    expected_delivery = tuple(
        raw["rule_id"] for raw in raw_rules
        if raw["implementation_status"] == "active"
        and raw["rule_id"] not in _CUSTOMER_EXCLUDED_IDS
    )
    assert delivery == expected_delivery
    assert executable == tuple(
        raw["rule_id"] for raw in raw_rules
        if raw["rule_id"] in expected_delivery
        and raw.get("phase_status", "phase_1_target") == "phase_1_target"
    )
    assert withheld == tuple(
        raw["rule_id"] for raw in raw_rules
        if raw["rule_id"] in expected_delivery
        and raw.get("phase_status", "phase_1_target") != "phase_1_target"
    )
    assert delivery and executable and withheld
    assert len(set(delivery)) == len(delivery)
    assert "LX0609-04-04-01" in withheld
    assert {"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"}.issubset(withheld)
    assert "LX0609-03-01-04" in executable
    assert "LX0609-06-03-01" not in delivery
    assert "LX0609-06-01-01" in executable
    with pytest.raises(ValueError, match="invalid LX0609 customer rule id"):
        partition_luxian_0609_rule_scope(("LX0609-06-03-01",))
    with pytest.raises(ValueError, match="not an LX0609 pending definition"):
        build_luxian_0609_pending_definition_result("LX0609-06-01-01")
    result = build_luxian_0609_pending_definition_result("LX0609-04-04-01")
    assert result["status"] == "not_executed"
    assert result["is_compliant"] is None
    assert "数据源暂不可用" in result["findings"]
    assert "不要求据此补写" in result["suggestion"]
    assert set(executable).isdisjoint(withheld)
    assert set(executable) | set(withheld) == set(delivery)
    catalog_ids = {str(item["rule_id"]) for item in load_luxian_0609_rules()}
    assert _CUSTOMER_EXCLUDED_IDS.issubset(catalog_ids)
    assert set(delivery) == catalog_ids - _CUSTOMER_EXCLUDED_IDS


def test_acceptance_only_registration_is_separate_from_phase_and_customer_selection() -> None:
    """验收元数据出现在选项中，不表示普通业务复检已获发布。"""
    raw_rules = _raw_master()["rules"]
    acceptance_ids = {
        raw["rule_id"] for raw in raw_rules if raw.get("release_scope") == "acceptance_only"
    }
    assert acceptance_ids == _ACCEPTANCE_ONLY_IDS
    entries = {entry.rule_id: entry for entry in load_luxian_0609_rule_master()}
    assert {rule_id for rule_id, entry in entries.items() if entry.release_scope == "acceptance_only"} == acceptance_ids
    assert all(entries[rule_id].implementation_status == "active" for rule_id in acceptance_ids)
    assert all(entries[rule_id].phase_status == "phase_1_target" for rule_id in acceptance_ids)
    assert acceptance_ids.isdisjoint(_CUSTOMER_EXCLUDED_IDS)
    assert acceptance_ids.issubset(get_luxian_0609_customer_delivery_rule_ids())


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
