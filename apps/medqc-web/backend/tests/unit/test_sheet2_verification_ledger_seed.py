import importlib.util
from pathlib import Path


def _load_seed_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_sheet2_verification_ledger_seed.py"
    spec = importlib.util.spec_from_file_location("build_sheet2_verification_ledger_seed", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_canonical_primary_rule_id_should_preserve_tail_issue_families():
    module = _load_seed_script_module()

    cases = [
        ("有创诊疗操作记录缺失/书写不规范", ["SC-045", "SC-046"], "患者行了骨髓穿刺，无有创操作记录", "SC-045"),
        ("有创诊疗操作记录缺失/书写不规范", ["SC-046", "SC-045"], "有创操作记录书写不规范", "SC-046"),
        ("转科记录缺失/书写不规范", ["SC-064"], "转入记录中未书写转入时间", "SC-064"),
        ("疑难病例讨论缺失/缺项", ["SC-056", "SC-057", "SC-058"], "入院超过3天未明确诊断", "SC-056"),
        ("输血记录链缺项", ["SC-074", "LX-018", "SC-073"], "输血后评价时间未书写", "SC-074"),
        ("围手术期术前评估/讨论/小结缺陷", ["SC-081", "SC-082", "SC-097"], "术前评估不充分", "SC-081"),
        ("既往史/用药史记录不全", ["SC-013", "SC-008"], "既往手术史未详细体现", "SC-013"),
        ("术前讨论结论/会诊意见未记入病历", ["SC-084", "SC-083", "SC-082"], "术前讨论无会诊科室意见", "SC-084"),
    ]

    for issue_family, candidate_rule_ids, manual_issue_text, expected_primary in cases:
        primary, secondary = module._canonical_primary_rule_id(
            issue_family=issue_family,
            candidate_rule_ids=candidate_rule_ids,
            manual_issue_text=manual_issue_text,
        )
        assert primary == expected_primary
        assert expected_primary not in secondary
