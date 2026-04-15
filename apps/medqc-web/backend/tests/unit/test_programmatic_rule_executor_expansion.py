import pytest

from app.services.programmatic_rule_executor import (
    PROGRAMMATIC_RULE_SPECS,
    ProgrammaticRuleExecutor,
)


def test_programmatic_rule_specs_should_expand_to_20_plus():
    # P1 目标：程序化规则从 10 条扩展到 20~30 条高价值规则
    assert len(PROGRAMMATIC_RULE_SPECS) >= 20
    assert "SC-022" in PROGRAMMATIC_RULE_SPECS
    assert "SC-096" in PROGRAMMATIC_RULE_SPECS
    assert "LX-026" in PROGRAMMATIC_RULE_SPECS


def test_sc104_exists_all_should_fail_when_missing_any_required_record():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-104", "name": "术后首次病程与麻醉术后访视记录完整性"},
        medical_record={"content": "已见术后首次病程记录，未见麻醉访视内容"},
    )

    assert result["status"] == "non_compliant"
    assert "缺失关键词" in str(result.get("evidence") or "")


def test_sc022_8h_time_window_should_detect_timeout():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-022", "name": "首次病程记录8小时完成"},
        medical_record={
            "content": (
                "入院时间：2026-04-01 08:00\n"
                "记录时间：2026-04-01 18:30\n"
                "首次病程记录内容完整"
            )
        },
    )

    assert result["status"] == "non_compliant"
    assert "间隔=10.5h" in str(result.get("evidence") or "")


@pytest.mark.parametrize("rule_id", ["SC-096", "LX-026"])
def test_surgery_24h_time_window_should_pass_when_in_time(rule_id: str):
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": rule_id, "name": "术后24小时完成"},
        medical_record={
            "content": (
                "手术结束时间：2026-04-01 10:00\n"
                "记录时间：2026-04-02 08:00\n"
                "手术记录内容"
            )
        },
    )

    assert result["status"] == "compliant"
