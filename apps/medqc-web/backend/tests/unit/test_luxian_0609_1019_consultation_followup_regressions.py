"""1019 会诊执行二次核实：院外既有用药与条件措施的 023 回归。"""

from dataclasses import replace
from datetime import datetime

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.consultation_measure_check import MeasureCheckOutcome


def _completed(ref: str, kind: str, quote: str, *, declined: bool = False, scope: str = "in_stay"):
    return episode._CompletedRecommendation(
        "consultation_record-1",
        episode._Recommendation(
            ref,
            kind,
            quote,
            quote,
            "consultation_record-1",
            execution_scope=scope,
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
    # 是否院外自备药由第一阶段模型标注 home_medication（2026-10-22），不再按“自备/院外”字样判断。
    for index, text in enumerate(("继续自备药物甲", "继续院外口服药物乙", "服用家中药物丙")):
        assert not episode._is_order_recommendation(
            _completed(f"outside-{index}", "medication", text, scope="home_medication").recommendation
        )
    for index, text in enumerate(("继续原降压药", "继续原有药物甲", "维持既往方案")):
        assert episode._is_order_recommendation(
            _completed(f"ambiguous-{index}", "medication", text).recommendation
        )


def test_023_附条件措施以模型标注为准而非条件词正则() -> None:
    # 用户口径（2026-10-22）：措施是否附条件由措施核对模型标注，程序只按标注剔除。
    completed = (_completed("conditional", "transfer", "建议评估操作甲；病情稳定后；可转科治疗"),)
    outcome = MeasureCheckOutcome(
        "ready",
        {"conditional": ("可转科治疗", "评估操作甲")},
        conditional_measures={"conditional": ("可转科治疗",)},
    )

    filtered = episode._drop_conditional_missing_measures(outcome, completed)

    assert filtered.missing_measures == {"conditional": ("评估操作甲",)}


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
        conditional_measures={"conditional": ("可转科治疗",)},
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


def test_023_手术转科建议逐项核对见患方决定即按已处置剔除() -> None:
    # 用户口径（2026-10-22）：无手术、转科记录时，病程写明患方同意或拒绝由逐项核对模型判断；
    # 模型给出全部措施均有处置证据（无缺项）时，按住院期间已处置不再判缺。
    surgery = _completed("surgery", "procedure", "建议手术治疗")
    plain = _completed("plain", "test", "完善检查甲")
    assert episode._needs_measure_scope_refinement(surgery)
    status, excluded = episode._apply_order_measure_check(
        ("non_compliant", "requirement_violated"),
        MeasureCheckOutcome("ready", {"surgery": ()}),
        completed=(surgery, plain),
        assessments=(_absent("surgery"), _absent("plain")),
        already_excluded=frozenset(),
        source_incomplete_keys=frozenset(),
        checked_refs=frozenset({"surgery"}),
    )
    assert excluded == frozenset({"surgery"})
    assert status == ("non_compliant", "requirement_violated")


def test_023_漏拆时已明确的无证据措施仍维持不合规() -> None:
    # 1022 C10：同批另一建议的标题段落漏拆，不能抹掉已拆出且明确无执行证据的措施。
    plain = _completed("plain", "medication", "阿托伐他汀调脂")
    status, _ = episode._apply_order_measure_check(
        ("non_compliant", "requirement_violated"),
        MeasureCheckOutcome("unresolved", {"plain": ("阿托伐他汀调脂",)}),
        completed=(plain,),
        assessments=(_absent("plain"),),
        already_excluded=frozenset(),
        source_incomplete_keys=frozenset(),
    )
    assert status == ("non_compliant", "requirement_violated")
