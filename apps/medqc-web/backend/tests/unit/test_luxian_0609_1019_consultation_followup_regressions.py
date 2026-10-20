"""1019 会诊执行二次核实：院外既有用药与条件措施的 023 回归。"""

from dataclasses import replace
from datetime import datetime

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.consultation_measure_check import MeasureCheckOutcome


def _completed(ref: str, kind: str, quote: str, *, declined: bool = False):
    return episode._CompletedRecommendation(
        "consultation_record-1",
        episode._Recommendation(
            ref,
            kind,
            quote,
            quote,
            "consultation_record-1",
        ),
        episode._ObservedTime(datetime(2026, 10, 1, 11, 30), True),
        fully_declined=declined,
    )


def _absent(ref: str):
    return episode._ExecutionAssessment(ref, "absent", (), "high", ())


def test_023_仅原有表述不推定院外_拒绝只豁免对应检查() -> None:
    medication = _completed("med", "medication", "继续服用原有药物甲")
    declined_test = _completed("test", "test", "完善检查乙", declined=True)

    kept, view = episode._order_execution_view(
        (medication, declined_test),
        (_absent("med"), _absent("test")),
    )

    assert [item.recommendation.recommendation_ref for item in kept] == ["med"]
    assert [item.recommendation_ref for item in view] == ["med"]
    assert episode._execution_quality_outcome(
        assessments=view,
        completed_recommendations=kept,
        source_incomplete_keys=frozenset(),
    ) == ("non_compliant", "requirement_violated")


def test_023_仅明确院外来源用药豁免住院医嘱核对() -> None:
    for index, text in enumerate(("继续自备药物甲", "继续院外口服药物乙", "服用家中药物丙")):
        assert not episode._is_order_recommendation(
            _completed(f"outside-{index}", "medication", text).recommendation
        )
    for index, text in enumerate(("继续原降压药", "继续原有药物甲", "维持既往方案")):
        assert episode._is_order_recommendation(
            _completed(f"ambiguous-{index}", "medication", text).recommendation
        )


def test_023_条件说明可位于措施前一分句() -> None:
    recommendation = _completed(
        "conditional",
        "transfer",
        "建议评估操作甲；病情稳定后；可转科治疗",
    ).recommendation

    assert episode._measure_in_conditional_clause(recommendation, "可转科治疗")
    assert not episode._measure_in_conditional_clause(recommendation, "评估操作甲")
    anomaly_condition = _completed(
        "anomaly-condition",
        "transfer",
        "建议评估操作乙；无明显异常后；可转科治疗",
    ).recommendation
    assert episode._measure_in_conditional_clause(anomaly_condition, "可转科治疗")


def test_023_完整条件措施不向下一项传播() -> None:
    recommendation = _completed(
        "conditional-action",
        "medication",
        "必要时复查血气；给予药物甲",
    ).recommendation

    assert episode._measure_in_conditional_clause(recommendation, "复查血气")
    assert not episode._measure_in_conditional_clause(recommendation, "给予药物甲")


def test_023_初判缺失的建议仍进入逐措施核验() -> None:
    conditional = _completed(
        "conditional",
        "transfer",
        "建议评估操作甲；病情稳定后；可转科治疗",
    )

    scope = episode._measure_check_scope((conditional,), (_absent("conditional"),))

    assert [item.recommendation.recommendation_ref for item in scope] == ["conditional"]


def test_023_初判不合规只补核条件或部分拒绝项() -> None:
    plain = _completed("plain", "test", "完善检查甲")
    conditional = _completed("conditional", "transfer", "病情稳定后可转科治疗")
    partial_decline = replace(
        _completed("declined", "test", "完善检查乙和检查丙"),
        declined_objects=("检查乙",),
        declined_measures=("检查乙",),
    )

    assert not episode._needs_measure_scope_refinement(plain)
    assert episode._needs_measure_scope_refinement(conditional)
    assert episode._needs_measure_scope_refinement(partial_decline)


def test_023_初判不合规可由全条件缺项收敛为不适用() -> None:
    conditional = _completed(
        "conditional",
        "transfer",
        "病情评估；病情稳定后；可转科治疗",
    )
    assessments = (_absent("conditional"),)
    outcome = MeasureCheckOutcome(
        "ready",
        {"conditional": ("可转科治疗",)},
    )

    status, excluded = episode._apply_order_measure_check(
        ("non_compliant", "requirement_violated"),
        outcome,
        completed=(conditional,),
        assessments=assessments,
        already_excluded=frozenset(),
        source_incomplete_keys=frozenset(),
    )

    assert status == ("not_applicable", "trigger_absent_complete")
    assert excluded == frozenset({"conditional"})


def test_023_逐措施漏拆或协议失败覆盖初判不合规为资料不足() -> None:
    recommendation = _completed("plain", "test", "完善检查甲")
    for state in ("failed", "unresolved"):
        status, excluded = episode._apply_order_measure_check(
            ("non_compliant", "requirement_violated"),
            MeasureCheckOutcome(state, {}),
            completed=(recommendation,),
            assessments=(_absent("plain"),),
            already_excluded=frozenset(),
            source_incomplete_keys=frozenset(),
        )
        assert status == ("data_gap", "semantic_extraction_unresolved")
        assert not excluded


def test_023_补核失败不覆盖其他普通建议的已证实缺项() -> None:
    plain = _completed("plain", "test", "完善检查甲")
    conditional = _completed("conditional", "transfer", "病情稳定后可转科治疗")

    status, excluded = episode._apply_order_measure_check(
        ("non_compliant", "requirement_violated"),
        MeasureCheckOutcome("failed", {}),
        completed=(plain, conditional),
        assessments=(_absent("plain"), _absent("conditional")),
        already_excluded=frozenset(),
        source_incomplete_keys=frozenset(),
        checked_refs=frozenset({"conditional"}),
    )

    assert status == ("non_compliant", "requirement_violated")
    assert not excluded


def test_023_非条件缺项仍维持不合规() -> None:
    recommendation = _completed("plain", "test", "完善检查甲")
    status, excluded = episode._apply_order_measure_check(
        ("non_compliant", "requirement_violated"),
        MeasureCheckOutcome("ready", {"plain": ("完善检查甲",)}),
        completed=(recommendation,),
        assessments=(_absent("plain"),),
        already_excluded=frozenset(),
        source_incomplete_keys=frozenset(),
    )

    assert status == ("non_compliant", "requirement_violated")
    assert not excluded
