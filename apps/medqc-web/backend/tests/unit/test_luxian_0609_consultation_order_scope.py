"""023 医嘱核对范围：会诊记录前3天窗口与会诊记录内写明拒绝/暂缓的措施。

用户口径（2026-10-20）：会诊记录写明拒绝或暂缓的措施只免该项。
用户口径（2026-10-22）：哪些措施被拒绝由第一阶段模型抽取，程序只核对拒绝原文与措施原话，
不再用拒绝词正则识别；本文件覆盖原文核对、措施名比对与核对窗口。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.consultation_order_scope import (
    measure_is_declined,
    order_window_start,
)

# 合成文本，结构仿真实会诊记录：会诊意见后接“会诊执行:”段。
_CONSULTATION_TEXT = (
    "既往肺结核病史，请感染性疾病科会诊，指导是否需继续治疗。会诊意见:会诊查房:考虑陈旧性病变?,"
    "建议诱导痰查XPERT,真菌G\\GM试验,若均为阴性,可充分沟通后气管镜进一步排除活动性病变。"
    "会诊执行:患者家属表示不行纤支镜检查。"
)
_RECOMMENDATION = (
    "建议诱导痰查XPERT,真菌G\\GM试验,若均为阴性,可充分沟通后气管镜进一步排除活动性病变"
)


def _scope(**raw):
    return episode._recommendation_scope_fields(
        raw, source_quote=_RECOMMENDATION, document_text=_CONSULTATION_TEXT,
    )


def test_模型给出的部分拒绝须有拒绝原文且被拒措施见于建议原话() -> None:
    scope, continues, conditional, state, measures, quote = _scope(
        decline_state="partial", declined_measures=["气管镜"],
        decline_quote="患者家属表示不行纤支镜检查", has_conditional_measures=True,
    )
    assert (scope, continues, conditional, state) == ("in_stay", False, True, "partial")
    assert measures == ("气管镜",)
    assert quote == "患者家属表示不行纤支镜检查"


def test_拒绝原文用省略号拼接时逐段核对() -> None:
    result = _scope(decline_state="full", declined_measures=[],
                    decline_quote="会诊执行...患者家属表示不行纤支镜检查")
    assert result[3] == "full"


@pytest.mark.parametrize("raw", [
    # 拒绝原文不在会诊文书中
    {"decline_state": "full", "declined_measures": [], "decline_quote": "家属拒绝一切检查"},
    # 被拒措施不是建议原话（如把另一条建议的拒绝安到本条）
    {"decline_state": "partial", "declined_measures": ["胸部CT"], "decline_quote": "患者家属表示不行纤支镜检查"},
    # partial 必须给出被拒措施
    {"decline_state": "partial", "declined_measures": [], "decline_quote": "患者家属表示不行纤支镜检查"},
])
def test_对不上原文的拒绝先列补核问题_补核后仍不实则只作废拒绝(raw) -> None:
    issues = []
    result = episode._recommendation_scope_fields(
        raw, source_quote=_RECOMMENDATION, document_text=_CONSULTATION_TEXT,
        review_issues=issues, position="r1",
    )
    assert result[3:] == ("none", (), "")
    assert [item.reason for item in issues] == ["decline not grounded"]


@pytest.mark.parametrize("raw", [
    # none 不得附带拒绝事实
    {"decline_state": "none", "declined_measures": ["气管镜"], "decline_quote": ""},
    {"execution_scope": "maybe"},
    {"continues_current_treatment": "否"},
])
def test_越界的拒绝与范围取值一律拒收(raw) -> None:
    with pytest.raises(episode._SemanticInvalid):
        _scope(**raw)


def test_缺字段按保守默认值处理() -> None:
    assert _scope() == ("in_stay", False, False, "none", (), "")


def test_措施名比对只免被拒绝的那一项() -> None:
    declined = ("气管镜",)
    assert measure_is_declined("气管镜检查", declined)
    assert measure_is_declined("纤支镜检查", declined)
    assert not measure_is_declined("诱导痰XPERT检测", declined)
    assert not measure_is_declined("真菌G/GM试验", declined)


def test_医嘱核对窗口固定从会诊记录前3天开始() -> None:
    # 系统无可靠会诊日期，不从病程推断（用户口径 2026-10-20）。
    assert order_window_start(date(2026, 10, 7)) == date(2026, 10, 4)
    assert order_window_start(date(2026, 3, 2)) == date(2026, 2, 27)


@pytest.mark.parametrize(("source_quote", "scope_quote", "expected_scope"), [
    ("若家属同意可转我科呼吸机支持治疗", "若家属同意", "conditional"),
    ("可待患者病情稳定后完善病理检查", "待患者病情稳定后", "conditional"),
    # 条件在后半句：整条仍按住院内执行，带条件措施交逐项核对（1022 C02、C25）
    ("建议复查凝血功能,如无明显异常再行气管切开", "如无明显异常", "in_stay"),
    # 模型误标且给不出开头条件原话（1022 C08）
    ("阿托伐他汀钙片 20mg qn稳定斑块", "", "in_stay"),
])
def test_条件式须由建议开头的条件原话证明(source_quote, scope_quote, expected_scope) -> None:
    scope, _, conditional, *_ = episode._recommendation_scope_fields(
        {"execution_scope": "conditional", "scope_quote": scope_quote},
        source_quote=source_quote, document_text=source_quote,
    )
    assert scope == expected_scope
    assert conditional is (expected_scope == "in_stay")
