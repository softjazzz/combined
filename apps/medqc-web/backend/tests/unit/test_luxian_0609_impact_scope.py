"""规则上线影响范围声明：每个执行器必须声明，待验收规则的分类与逐族核实一致。"""
from app.services.luxian_0609.impact_scope import (
    EXECUTOR_IMPACT,
    IMPACT_INDEPENDENT,
    IMPACT_SHARED_BATCH,
    IMPACT_UNVERIFIED,
    requires_family_regression,
    rule_impacts,
)
from app.services.luxian_0609.native_package import load_luxian_0609_dependency_inventory


def test_every_executor_declares_impact():
    # 新增执行器必须先核实并声明是否共享抽取批次，否则规则验收会按“未核实”从严处理
    executors = {d.executor_key for d in load_luxian_0609_dependency_inventory()}
    assert executors <= set(EXECUTOR_IMPACT), executors - set(EXECUTOR_IMPACT)
    assert all(v[1] for v in EXECUTOR_IMPACT.values())


def test_pending_rules_follow_family_verification():
    impacts = rule_impacts()
    for rule_id in ("LX0609-06-01-01", "LX0609-06-01-03", "LX0609-06-03-02"):
        assert impacts[rule_id]["impact"] == IMPACT_SHARED_BATCH
        assert impacts[rule_id]["executor_key"] == "exam_lab"
        assert "LX0609-06-01-04" in impacts[rule_id]["peer_rule_ids"]
    assert impacts["LX0609-09-01-02"]["impact"] == IMPACT_INDEPENDENT
    assert impacts["LX0609-06-02-01"]["impact"] == IMPACT_INDEPENDENT
    assert "LX0609-09-01-02" not in impacts["LX0609-09-01-02"]["peer_rule_ids"]


def test_unverified_is_treated_as_shared():
    assert requires_family_regression(IMPACT_SHARED_BATCH)
    assert requires_family_regression(IMPACT_UNVERIFIED)
    assert not requires_family_regression(IMPACT_INDEPENDENT)
