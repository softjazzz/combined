"""012 前置相关性判定（用户口径 2026-10-11）：附带发现不要求分析，结论先固定再判断有无分析。"""

import json

import pytest

from app.services.luxian_0609.exam_finding_relevance import (
    SCHEMA_VERSION,
    apply_relevance_hints,
    classify_exam_finding_relevance,
)
from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_fact_prompt,
    build_exam_lab_text_projection,
    events_for_family,
    parse_exam_lab_fact_response,
)


def _projection():
    return build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {"exam_id": "EX-1", "exam_name": "胸部CT平扫", "exam_time": "2026-08-18 12:00:00",
                 "report_time": "2026-08-18 13:00:00", "exam_conclusion": "主动脉壁钙化。双肺未见明显异常。"},
                {"exam_id": "EX-2", "exam_name": "腰椎MRI平扫", "exam_time": "2026-08-18 12:30:00",
                 "report_time": "2026-08-18 13:30:00", "exam_conclusion": "L4/5椎间盘突出，椎管狭窄。"},
            ),
            "first_course_record": (
                {"record_time": "2026-08-18 10:00:00",
                 "record_content": "主诉：腰痛伴右下肢放射痛2月。初步诊断：腰椎间盘突出症。"},
            ),
            "daily_course_record": (
                {"record_time": "2026-08-18 15:00:00", "record_content": "腰椎MRI示L4/5椎间盘突出，与症状相符，拟手术。"},
            ),
        }
    )


class _Client:
    def __init__(self, outputs):
        self.outputs, self.prompts = list(outputs), []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _answer(**relevance):
    return {"schema_version": SCHEMA_VERSION, "events": [
        {"event_position": int(key[1:]), "relevance": value} for key, value in relevance.items()]}


@pytest.mark.asyncio
async def test_relevance_is_classified_once_with_visit_context_and_fixed_as_hints():
    projection = _projection()
    client = _Client([_answer(e1="incidental_only", e2="related_abnormal")])
    outcome = await classify_exam_finding_relevance(projection, client)
    assert outcome.state == "ready" and outcome.hints == {1: "negative", 2: "positive"}
    assert outcome.llm_call_count == 1 and outcome.total_tokens == 15
    assert "腰椎间盘突出症" in client.prompts[0] and "主动脉壁钙化" in client.prompts[0]
    fixed = apply_relevance_hints(projection, outcome.hints)
    events = events_for_family(fixed, "exam")
    assert [e.positive_hint for e in events] == ["negative", "positive"]
    assert all(e.relevance_fixed for e in events)


@pytest.mark.asyncio
async def test_protocol_violation_retries_once_with_hint_then_fails_closed():
    projection = _projection()
    client = _Client(["不是JSON", _answer(e1="no_abnormal", e2="uncertain")])
    outcome = await classify_exam_finding_relevance(projection, client)
    assert outcome.state == "ready" and outcome.hints == {1: "negative", 2: "unknown"}
    assert outcome.llm_call_count == 2
    assert client.prompts[1].index("上一次输出未通过校验") < client.prompts[1].index("REPORTS_JSON=")

    # 同一份病历换一组应答重跑前清空冻结（2026-10-22 起相关性判定按输入冻结复用）。
    import shutil
    from app.services.luxian_0609.exam_analysis_freeze import default_store_dir
    shutil.rmtree(default_store_dir(), ignore_errors=True)
    client = _Client([_answer(e1="no_abnormal"), _answer(e1="no_abnormal")])  # 漏掉事件2
    outcome = await classify_exam_finding_relevance(projection, client)
    assert outcome.state == "failed" and outcome.hints == {} and outcome.llm_call_count == 2


@pytest.mark.asyncio
async def test_no_candidate_report_skips_model():
    projection = build_exam_lab_text_projection(rows_by_source={"exam_master": ()})
    client = _Client([])
    outcome = await classify_exam_finding_relevance(projection, client)
    assert outcome.state == "skipped" and not client.prompts


@pytest.mark.parametrize("model_positive", ["positive", "negative", "unknown"])
def test_fixed_relevance_overrides_main_extraction_positive_state(model_positive):
    """主抽取不得改判前置结论：附带发现即使模型判阳性也不要求分析；相关异常即使模型判阴性仍须分析。"""
    projection = apply_relevance_hints(_projection(), {1: "negative", 2: "positive"})
    prompt = build_exam_lab_fact_prompt(selected_rule_ids=("LX0609-06-01-05",), projection=projection)
    assert '"positive_state_fixed":"negative"' in prompt and '"positive_state_fixed":"positive"' in prompt
    assert "不得重新判断异常是否为附带发现" in prompt
    payload = json.loads(prompt.rstrip().splitlines()[-1])
    for fact in payload["facts"]:
        fact.update(applicability="applicable", semantic_state="absent", positive_state=model_positive,
                    course_doc_positions=[])
    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)}, selected_rule_ids=("LX0609-06-01-05",), projection=projection,
    )
    by_event = {fact.event_position: fact for fact in facts}
    assert (by_event[1].applicability, by_event[1].positive_state) == ("not_applicable", "negative")
    assert (by_event[2].applicability, by_event[2].positive_state) == ("applicable", "positive")


def test_first_course_prefix_matches_projection_source_order():
    """防止投影来源顺序变化后静默取错首次病程。"""
    projection = build_exam_lab_text_projection(rows_by_source={"first_course_record": (
        {"record_time": "2026-08-18 10:00:00", "record_content": "首次病程。"},)})
    assert list(projection.course_candidates) == ["D05-01"]



@pytest.mark.asyncio
async def test_relevance_is_frozen_and_reused_without_model():
    projection = _projection()
    first = await classify_exam_finding_relevance(projection, _Client([_answer(e1="no_abnormal", e2="uncertain")]))
    flipped = _Client([_answer(e1="uncertain", e2="no_abnormal")])
    reused = await classify_exam_finding_relevance(projection, flipped)
    assert reused.hints == first.hints and reused.llm_call_count == 0 and not flipped.prompts
