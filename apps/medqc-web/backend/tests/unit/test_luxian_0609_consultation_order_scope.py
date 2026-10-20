"""023 医嘱核对范围：会诊记录前3天窗口与会诊记录内写明拒绝/暂缓的措施（用户口径 2026-10-20）。"""

from __future__ import annotations

from datetime import date
import re

from app.services.luxian_0609.consultation_order_scope import (
    declined_measure_objects,
    measure_is_declined,
    order_window_start,
    recommendation_decline,
)

_CONDITIONAL = re.compile(r"若|如果|假如|倘若|如[^，,。；;]{1,16}(?:则|时|者)|必要时|酌情|视情况")


def _is_conditional(text: str) -> bool:
    return bool(_CONDITIONAL.search(text or ""))


# 合成文本，结构仿真实会诊记录：会诊意见后接“会诊执行:”段。
_CONSULTATION_TEXT = (
    "既往肺结核病史，请感染性疾病科会诊，指导是否需继续治疗。会诊意见:会诊查房:考虑陈旧性病变?,"
    "建议诱导痰查XPERT,真菌G\\GM试验,若均为阴性,可充分沟通后气管镜进一步排除活动性病变。"
    "会诊执行:患者家属表示不行纤支镜检查。"
)
_RECOMMENDATION = (
    "建议诱导痰查XPERT,真菌G\\GM试验,若均为阴性,可充分沟通后气管镜进一步排除活动性病变"
)


def test_家属表示不行纤支镜检查_识别为拒绝对象() -> None:
    assert declined_measure_objects(_CONSULTATION_TEXT, is_conditional=_is_conditional) == (
        "纤支镜检查",
    )


def test_只免被拒绝的气管镜_其余措施仍须核对() -> None:
    objects = declined_measure_objects(_CONSULTATION_TEXT, is_conditional=_is_conditional)
    declined, fully = recommendation_decline(
        _RECOMMENDATION, objects, is_conditional=_is_conditional,
    )
    assert declined == ("纤支镜检查",)
    assert fully is False
    assert measure_is_declined("气管镜检查", objects)
    assert not measure_is_declined("诱导痰XPERT检测", objects)
    assert not measure_is_declined("真菌G/GM试验", objects)


def test_建议只有被拒绝的一项时整条不纳入核对() -> None:
    objects = declined_measure_objects(
        "会诊意见:建议行支气管镜检查。会诊执行:已与家属沟通，家属拒绝支气管镜检查。",
        is_conditional=_is_conditional,
    )
    declined, fully = recommendation_decline(
        "建议行支气管镜检查", objects, is_conditional=_is_conditional,
    )
    assert declined
    assert fully is True


def test_条件句中的拒绝不是事实() -> None:
    assert declined_measure_objects(
        "会诊意见:建议手术治疗，若家属拒绝手术则保守治疗。会诊执行:遵医嘱用药。",
        is_conditional=_is_conditional,
    ) == ()


def test_会诊意见里的建议暂缓不当作本科室暂缓决定() -> None:
    assert declined_measure_objects(
        "会诊意见:建议暂缓抗凝治疗，复查凝血。会诊执行:遵医嘱复查凝血。",
        is_conditional=_is_conditional,
    ) == ()


def test_会诊执行段写明暂不考虑的措施逐项识别() -> None:
    objects = declined_measure_objects(
        "会诊意见:建议血气分析、肺功能检查、痰培养。会诊执行:现无气紧，暂不考虑血气分析、肺功能检查。",
        is_conditional=_is_conditional,
    )
    assert objects == ("血气分析", "肺功能检查")
    declined, fully = recommendation_decline(
        "建议血气分析、肺功能检查、痰培养", objects, is_conditional=_is_conditional,
    )
    assert declined == ("血气分析", "肺功能检查")
    assert fully is False


def test_泛称对象不免任何措施() -> None:
    objects = declined_measure_objects(
        "会诊执行:家属拒绝进一步检查。", is_conditional=_is_conditional,
    )
    assert objects == ()


def test_医嘱核对窗口固定从会诊记录前3天开始() -> None:
    # 系统无可靠会诊日期，不从病程推断（用户口径 2026-10-20）。
    assert order_window_start(date(2026, 10, 7)) == date(2026, 10, 4)
    assert order_window_start(date(2026, 3, 2)) == date(2026, 2, 27)
