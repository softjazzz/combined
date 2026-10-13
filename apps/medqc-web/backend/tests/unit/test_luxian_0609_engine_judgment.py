"""质控规则页的引擎判定说明：每条规则都有说明，且与执行范围、规则合同一致。"""

from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609_rule_catalog import (
    attach_luxian_0609_customer_policy,
    load_luxian_0609_engine_judgment,
    load_luxian_0609_rules,
)
from app.services.sample_validation_rule_sets import get_luxian_0609_customer_execution_scope


def test_every_catalog_rule_has_engine_judgment_matching_execution_scope():
    entries = load_luxian_0609_engine_judgment()["rules"]
    catalog_ids = {contract.rule_id for contract in load_luxian_0609_rule_contracts()}
    executable, withheld = get_luxian_0609_customer_execution_scope()

    assert catalog_ids <= set(entries), sorted(catalog_ids - set(entries))
    assert set(entries) <= catalog_ids, sorted(set(entries) - catalog_ids)
    for rule_id in executable:
        entry = entries[rule_id]
        assert not entry.get("withheld") and not entry.get("excluded"), rule_id
        assert entry["trigger"].strip() and entry["steps"], rule_id
        assert {"compliant", "non_compliant"} <= set(entry["outcomes"]), rule_id
        assert set(entry["outcomes"]) <= {"compliant", "non_compliant", "data_gap", "not_applicable"}, rule_id
    for rule_id in withheld:
        assert entries[rule_id].get("withheld") is True, rule_id


def test_rule_detail_projection_attaches_method_from_contract_and_withheld_reason():
    rules = {rule["rule_id"]: rule for rule in attach_luxian_0609_customer_policy(load_luxian_0609_rules())}

    judged = rules["LX0609-06-01-04"]["engine_judgment"]
    assert judged["withheld"] is False and judged["method"].startswith("程序为主、模型辅助")
    assert judged["outcomes"]["non_compliant"] and judged["extra_notes"]
    assert judged["data_gap_note"].startswith("资料不足表示")
    assert rules["LX0609-01-01-01"]["engine_judgment"]["method"].startswith("程序判定")

    paused = rules["LX0609-03-01-01"]["engine_judgment"]
    assert paused == {"withheld": True, "withheld_reason": paused["withheld_reason"]}
    assert paused["withheld_reason"]
    assert rules["LX0609-11-01-01"]["engine_judgment"]["withheld_reason"].startswith("本质控点不在本次客户交付范围")
