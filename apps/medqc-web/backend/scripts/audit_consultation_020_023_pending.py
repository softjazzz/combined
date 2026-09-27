"""离线反例：020/023已确认事实、资料缺口与低置信复核；无病例正文/网络/数据库。"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.luxian_0609.native_consultation_episode_execution import (
    _ExecutionAssessment,
    _execution_outcome,
    _merge_rechecked_execution_assessment,
)


def assessment(ref, trace, confidence="high"):
    return _ExecutionAssessment(
        recommendation_ref=ref, execution_state="absent", execution_refs=(),
        confidence=confidence, execution_quotes=(), execution_record_state=trace,
        trace_refs=(f"candidate-{ref}",) if trace in {"specific_trace", "generic_trace"} else (),
    )


def main():
    specific = assessment("specific", "specific_trace")
    unknown = assessment("unknown", "unknown", "low")
    missing = assessment("missing", "no_trace")
    vague = assessment("vague", "generic_trace")
    cases = (
        ("020-specific-plus-unknown", "LX0609-03-01-01", (specific, unknown), (), "evaluation_unknown"),
        ("020-specific-with-course-gap", "LX0609-03-01-01", (specific,), ("senior_course_record",), "compliant"),
        ("020-missing-plus-unknown", "LX0609-03-01-01", (missing, unknown), (), "non_compliant"),
        ("020-missing-with-course-gap", "LX0609-03-01-01", (missing,), ("senior_course_record",), "data_gap"),
        ("020-missing-with-auxiliary-gap", "LX0609-03-01-01", (missing,), ("exam_master",), "non_compliant"),
        ("023-high-vague-plus-unknown", "LX0609-03-01-04", (vague, unknown), (), "non_compliant"),
        ("023-medium-vague-plus-specific", "LX0609-03-01-04", (replace(vague, confidence="medium"), specific), (), "evaluation_unknown"),
    )
    for label, rule, items, gaps, expected in cases:
        actual = _execution_outcome(
            rule, episodes=(SimpleNamespace(confidence="high", opinion_state="clear"),),
            completed_recommendations=tuple(object() for _ in items), assessments=items,
            source_incomplete_keys=frozenset(gaps),
        )
        assert actual[0] == expected, (label, actual)
        print(label, *actual)

    low_missing = replace(missing, confidence="low")
    assert _merge_rechecked_execution_assessment(low_missing, low_missing).confidence == "high"
    assert _merge_rechecked_execution_assessment(low_missing, replace(low_missing, execution_state="unknown")).confidence == "low"
    medium_vague = replace(vague, confidence="medium")
    assert _merge_rechecked_execution_assessment(medium_vague, medium_vague).confidence == "medium"
    # 当前调用方仅将非high建议纳入复核；按ref归并保留没有投递的specific原对象。
    originals = (specific, low_missing)
    rechecks = {low_missing.recommendation_ref: low_missing}
    merged = tuple(_merge_rechecked_execution_assessment(item, rechecks[item.recommendation_ref])
                   if item.recommendation_ref in rechecks else item for item in originals)
    assert merged[0] is specific
    assert merged[1].confidence == "high"
    print("recheck-consensus-and-preserved-specific", "passed")


if __name__ == "__main__":
    main()
