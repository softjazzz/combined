"""023 医嘱核对范围：会诊记录前3天窗口与会诊记录内写明拒绝/暂缓的措施。

用户口径（2026-10-20）：会诊记录写明拒绝或暂缓的措施只免该项。
用户口径（2026-10-22）：哪些措施被拒绝由第一阶段模型抽取，程序只核对拒绝原文与措施原话，
不再用拒绝词正则识别；本文件覆盖原文核对、措施名比对与核对窗口。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.consultation_measure_check import MeasureCheckOutcome
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


@pytest.mark.parametrize(("declined", "pending"), [
    ("右肾穿刺活检", "左肾穿刺活检"),
    ("肝穿刺活检", "肾穿刺活检"),
    ("肾穿刺活检", "左肾穿刺活检"),
    ("左肾穿刺活检", "肾穿刺活检"),
    ("胸部CT", "腹部CT"),
    ("胸部CT", "胸部CT增强"),
    ("支气管镜检查", "支气管镜下活检"),
    ("肝脏检查", "肝脏治疗"),
    ("支气管镜检查", "支气管镜治疗"),
    ("检查", "肾穿刺活检"),
    ("检查", "检查"),
    ("CT", "胸部CT检查"), ("左肾彩超", "右肾彩超检查"),
    ("心电图", "动态心电图检查"), ("骨髓穿刺", "骨髓穿刺活检术"),
    ("胸腔穿刺", "胸腔穿刺引流术"),
])
def test_拒绝匹配不能丢失部位侧别或具体操作(declined, pending) -> None:
    assert not measure_is_declined(pending, (declined,))


@pytest.mark.parametrize(("declined", "pending"), [
    ("右肾穿刺活检", "右肾穿刺活检"),
    ("接受右肾穿刺活检", "行右肾穿刺活检"),
    ("纤维支气管镜检查", "纤支镜"),
    ("核磁共振检查", "MRI"),
])
def test_明确同一措施的拒绝保留别名与通用修饰匹配(declined, pending) -> None:
    assert measure_is_declined(pending, (declined,))


def _measure_refinement(declined: str, pending: str):
    # 固定第一阶段事实须先经过真实原文绑定，再进入逐措施过滤和最终状态聚合。
    quote = f"建议行{declined}及{pending}。"
    rejection = f"患者拒绝{declined}。"
    grounded = episode._recommendation_scope_fields(
        {"decline_state": "partial", "declined_measures": [declined],
         "decline_quote": rejection},
        source_quote=quote, document_text=quote + rejection,
    )
    assert grounded[3:5] == ("partial", (declined,))
    recommendation = episode._Recommendation(
        "r1", "procedure", quote, quote, "consultation_record-1",
        decline_state="partial", declined_measures=grounded[4],
        decline_quote=grounded[5],
    )
    completed = episode._CompletedRecommendation(
        "e1", recommendation, episode._ObservedTime(date(2026, 1, 1), None),
        declined_objects=(declined,), declined_measures=grounded[4],
    )
    assessment = episode._ExecutionAssessment("r1", "absent", (), "high", ())
    outcome = MeasureCheckOutcome("ready", {"r1": (pending,)})
    initial = episode._execution_quality_outcome(
        assessments=(assessment,), completed_recommendations=(completed,),
        source_incomplete_keys=frozenset(),
    )
    filtered = episode._drop_conditional_missing_measures(outcome, (completed,))
    result, excluded = episode._apply_order_measure_check(
        initial, outcome, completed=(completed,), assessments=(assessment,),
        already_excluded=frozenset(), source_incomplete_keys=frozenset(),
    )
    return filtered, result, excluded


@pytest.mark.parametrize(("declined", "pending"), [
    ("右肾穿刺活检", "左肾穿刺活检"),
    ("肝穿刺活检", "肾穿刺活检"),
    ("肾穿刺活检", "左肾穿刺活检"),
])
def test_其他部位的拒绝不能把确定未执行改成不适用(declined, pending) -> None:
    filtered, result, excluded = _measure_refinement(declined, pending)
    assert filtered.missing_measures == {"r1": (pending,)}
    assert result == ("non_compliant", "requirement_violated")
    assert not excluded


def test_确属同项拒绝仍从未执行措施中剔除() -> None:
    filtered, _, _ = _measure_refinement("纤维支气管镜检查", "纤支镜检查")
    assert filtered.missing_measures == {"r1": ()}


@pytest.mark.parametrize(("short", "long"), [
    ("胃镜", "胃镜检查"), ("胸部CT", "胸部CT检查"),
    ("右肾穿刺活检", "右肾穿刺活检术"),
    ("彩超", "彩超检查"), ("B超", "B超检查"),
    ("心电图", "心电图检查"), ("胸部X线", "胸部X线检查"),
    ("CT", "CT检查"), ("超声", "超声检查"),
    ("腰椎穿刺", "腰椎穿刺术"), ("骨髓穿刺", "骨髓穿刺术"),
    ("胸腔穿刺", "胸腔穿刺术"),
])
def test_同项措施摘取边界不同仍可豁免(short, long):
    for declined, pending in ((short, long), (long, short)):
        assert measure_is_declined(pending, (declined,))
        filtered, result, excluded = _measure_refinement(declined, pending)
        assert filtered.missing_measures == {"r1": ()}
        assert result == ("compliant", "requirement_satisfied")
        assert excluded == frozenset({"r1"})


def test_条件句没有实际拒绝事实时不豁免缺失措施() -> None:
    text = "建议右肾穿刺活检。若家属拒绝右肾穿刺活检，再另议方案。"
    # 条件/实际拒绝语义仍由第一阶段判定；确定性匹配不能自行从条件句生成拒绝事实。
    fields = episode._recommendation_scope_fields(
        {"decline_state": "none", "declined_measures": [], "decline_quote": ""},
        source_quote=text, document_text=text,
    )
    assert fields[3:5] == ("none", ())
    assert not measure_is_declined("右肾穿刺活检", fields[4])


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
