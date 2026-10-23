"""用户确认的成对判定例子（2026-10-22）必须实际进入对应提示词。"""

from app.services.luxian_0609 import consultation_measure_check as measure_check
from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609 import posttransfusion_effect_extraction as effect
from app.services.luxian_0609.exam_finding_analysis import _prompt as analysis_prompt, _targets
from app.services.luxian_0609.judgement_examples import (
    CONSULTATION_MEASURE_EXAMPLES,
    CONSULTATION_SCOPE_EXAMPLES,
    EXAM_FINDING_ANALYSIS_EXAMPLES,
    POSTTRANSFUSION_EFFECT_EXAMPLES,
)
from test_luxian_0609_exam_finding_analysis import LINKED, _projection


def test_examples_reach_each_prompt_before_input_material():
    projection = _projection(LINKED)
    prompt = analysis_prompt(projection, _targets(projection))
    assert EXAM_FINDING_ANALYSIS_EXAMPLES in prompt
    assert prompt.index(EXAM_FINDING_ANALYSIS_EXAMPLES) < prompt.index("EVENTS_JSON=")

    prompt = effect._prompt([{"index": 0, "content": "输注完毕。"}])
    assert prompt.index(POSTTRANSFUSION_EFFECT_EXAMPLES) < prompt.index("INPUT_JSON=")

    assert CONSULTATION_SCOPE_EXAMPLES in episode._RECOMMENDATION_SCOPE_PROMPT
    assert CONSULTATION_MEASURE_EXAMPLES in measure_check._prompt([], {}, {}, {})


def test_consultation_freeze_version_invalidates_frozen_stage_one_without_examples():
    from app.services.luxian_0609.consultation_opinion_freeze import FREEZE_SCHEMA_VERSION

    assert FREEZE_SCHEMA_VERSION == "consultation-opinion-freeze-v6"
