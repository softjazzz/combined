"""06-01-05 完整文书覆盖：截断恢复、长文分窗与冻结完成性。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from finding_selection_test_support import selection_answer

from app.services.luxian_0609 import exam_analysis_freeze as freeze
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_finding_analysis import (
    MAX_COURSE_CHARS,
    RULE_ID,
    SCHEMA_VERSION,
    apply_finding_analysis,
    check_exam_finding_analysis,
)
from app.services.luxian_0609.exam_finding_relevance import apply_relevance_hints
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    build_exam_lab_text_projection,
)


REPORT = "胸部CT提示右肺上叶结节。"
ANALYSIS = "胸部CT提示右肺上叶结节，结合持续咳嗽发热，考虑肺部感染，继续抗感染治疗。"
DISTRIBUTED_REPORT = "胸部CT提示右肺上叶结节。"
DISTRIBUTED_BASIS = "结合持续咳嗽发热，考虑该结节为炎性改变，继续抗感染治疗。"


@pytest.fixture(autouse=True)
def _isolated_freeze(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "freeze"
    monkeypatch.setenv(freeze._ENV_STORE_DIR, str(store))
    return store


def _projection(*course_texts: str):
    rows = tuple(
        {
            "document_id": f"COURSE-{index}",
            "record_time": f"2026-08-18 {14 + index:02d}:00:00",
            "record_content": text,
        }
        for index, text in enumerate(course_texts, 1)
    )
    projection = build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({
            "exam_id": "EXAM-1",
            "exam_name": "胸部CT平扫",
            "exam_time": "2026-08-18 12:00:00",
            "report_time": "2026-08-18 13:00:00",
            "exam_conclusion": REPORT,
        },),
        "daily_course_record": rows,
        "evaluation_context.horizon": ({
            "horizon_datetime": "2026-08-20 13:00:00",
            "horizon_date": "2026-08-20",
        },),
    })
    return apply_relevance_hints(projection, {1: "positive"})


def _prompt_payload(prompt: str) -> dict:
    return json.loads(prompt.split("EVENTS_JSON=", 1)[1])


def _response(payload: dict, *, finish_reason: str = "stop") -> dict:
    return {
        "choices": [{
            "finish_reason": finish_reason,
            "message": {"content": json.dumps(payload, ensure_ascii=False)},
        }],
        "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
        "_api_time": 0.01,
    }


def _negative_answer(prompt: str) -> dict:
    payload = _prompt_payload(prompt)
    docs = [
        {
            "event_position": event["event_position"],
            "course_doc_ref": ref,
            "quote_type": "none",
            "course_fragment_ids": [],
            "report_fragment_id": "",
            "basis_fragment_ids": [],
            "basis_relation": "none",
        }
        for event in payload["events"]
        for ref in event["course_doc_refs"]
    ]
    return _response({"schema_version": SCHEMA_VERSION, "docs": docs})


def _positive_answer(prompt: str) -> dict:
    payload = _prompt_payload(prompt)
    event = payload["events"][0]
    ref = event["course_doc_refs"][0]
    legacy = {
        "schema_version": SCHEMA_VERSION,
        "docs": [{
            "event_position": event["event_position"],
            "course_doc_ref": ref,
            "quote_type": "finding_linked",
            "quote": ANALYSIS,
            "report_span": "右肺上叶结节",
        }],
    }
    return _response(selection_answer(legacy, prompt))


def _visible_text(prompt: str) -> str:
    payload = _prompt_payload(prompt)
    return "".join(
        fragment["text"]
        for document in payload["course_docs"]
        for fragment in document["fragments"]
    )


class _FixedClient:
    """按当前真实提示词即时固定应答，不替换 gather、不访问网络。"""

    def __init__(
        self, *, truncate_multi_once: bool = False, fail_token: str | None = None,
    ) -> None:
        self.truncate_multi_once = truncate_multi_once
        self.fail_token = fail_token
        self.truncated = False
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs) -> dict:
        self.prompts.append(prompt)
        payload = _prompt_payload(prompt)
        pair_count = sum(len(event["course_doc_refs"]) for event in payload["events"])
        if self.truncate_multi_once and pair_count > 1 and not self.truncated:
            self.truncated = True
            return _response({}, finish_reason="length")
        visible = _visible_text(prompt)
        if self.fail_token and self.fail_token in visible:
            raise RuntimeError("fixed transport failure")
        return _positive_answer(prompt) if ANALYSIS in visible else _negative_answer(prompt)


class _DistributedClient:
    """只有同一提示同时含远距离报告描述与分析依据时才返回正证据。"""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs) -> dict:
        self.prompts.append(prompt)
        visible = _visible_text(prompt)
        if DISTRIBUTED_REPORT not in visible or DISTRIBUTED_BASIS not in visible:
            return _negative_answer(prompt)
        payload = _prompt_payload(prompt)
        event = payload["events"][0]
        ref = event["course_doc_refs"][0]
        document = next(doc for doc in payload["course_docs"] if doc["course_doc_ref"] == ref)
        selected = [
            fragment["id"] for fragment in document["fragments"]
            if any(token in fragment["text"] for token in (
                DISTRIBUTED_REPORT,
                "结合持续咳嗽发热",
                "考虑该结节为炎性改变",
                "继续抗感染治疗",
            ))
        ]
        report_id = next(
            fragment["id"] for fragment in event["report_fragments"]
            if "右肺上叶结节" in fragment["text"]
        )
        return _response({
            "schema_version": SCHEMA_VERSION,
            "docs": [{
                "event_position": event["event_position"],
                "course_doc_ref": ref,
                "quote_type": "finding_linked",
                "course_fragment_ids": selected,
                "report_fragment_id": report_id,
                "basis_fragment_ids": selected,
                "basis_relation": "same_finding",
            }],
        })


def _main_fact(projection) -> ExamLabEventFact:
    refs = tuple(sorted(projection.course_candidates or {}))
    return ExamLabEventFact(
        rule_id=RULE_ID,
        applicability="applicable",
        semantic_state="present",
        positive_state="positive",
        course_doc_refs=refs,
        evidence_refs=("synthetic-report", *refs),
        event_position=1,
    )


def _assert_final_and_main_freeze(projection, outcome, *, status: str, frozen: bool) -> None:
    applied = apply_finding_analysis((_main_fact(projection),), outcome)
    final = native._single_text_fact_outcome(
        rule_id=RULE_ID, fact=applied[0], projection=projection,
    )
    assert final.status == status
    incomplete = frozenset() if outcome.state in {"ready", "skipped"} else frozenset({RULE_ID})
    result = native._ExamLabBatchResult(
        facts=applied,
        rule_failures={},
        incomplete_specialty_rule_ids=incomplete,
    )
    native._save_frozen_exam_lab_batch("synthetic-main-key", result)
    assert (freeze.load_payload("main", "synthetic-main-key") is not None) is frozen


@pytest.mark.asyncio
async def test_truncated_parent_is_replaced_by_ready_negative_children(_isolated_freeze: Path):
    projection = _projection("继续当前治疗。", "患者一般情况稳定，观察病情变化。")
    client = _FixedClient(truncate_multi_once=True)

    outcome = await check_exam_finding_analysis(projection, client)

    assert outcome.state == "ready" and outcome.analysed_refs == {1: ()}
    assert outcome.llm_call_count == 4  # 截断父批 + 两个恢复子批 + 完整否定复核
    assert len(list((_isolated_freeze / "analysis").glob("*.json"))) == 1
    _assert_final_and_main_freeze(projection, outcome, status="non_compliant", frozen=True)


@pytest.mark.asyncio
async def test_truncated_parent_with_one_failed_child_stays_partial_and_unfrozen(_isolated_freeze: Path):
    fail_token = "FAIL_CHILD"
    projection = _projection("继续当前治疗。", f"{fail_token}观察病情变化。")

    outcome = await check_exam_finding_analysis(
        projection, _FixedClient(truncate_multi_once=True, fail_token=fail_token),
    )

    assert outcome.state == "partial" and outcome.analysed_refs == {}
    assert not list((_isolated_freeze / "analysis").glob("*.json"))
    # 未完成否定不覆盖主抽取；专项未完成也阻止主事实冻结。
    assert apply_finding_analysis((_main_fact(projection),), outcome)[0].semantic_state == "present"
    _assert_final_and_main_freeze(projection, outcome, status="compliant", frozen=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("analysis_offset", [100, MAX_COURSE_CHARS - 50, MAX_COURSE_CHARS + 400])
async def test_short_boundary_and_post_6400_positive_analysis_are_all_ready(
    analysis_offset: int, _isolated_freeze: Path,
):
    prefix_fail = "FAIL_PREFIX"
    course = prefix_fail + "甲" * (analysis_offset - len(prefix_fail)) + ANALYSIS + "乙" * 200
    projection = _projection(course)
    client = _FixedClient()

    outcome = await check_exam_finding_analysis(projection, client)

    assert outcome.state == "ready"
    assert outcome.analysed_refs == {1: tuple(sorted(projection.course_candidates or {}))}
    # 6000 字边界正例由 512 字重叠窗口完整承载；6400 后正例不会被首窗截断。
    assert any(ANALYSIS in _visible_text(prompt) for prompt in client.prompts)
    _assert_final_and_main_freeze(projection, outcome, status="compliant", frozen=True)


@pytest.mark.asyncio
async def test_ordinary_long_full_context_negative_is_complete_non_compliance(_isolated_freeze: Path):
    # 6900 字的单份全文仍在 MAX_PROMPT 内，应以全局上下文完成否定，而不是机械分窗。
    projection = _projection("甲" * (MAX_COURSE_CHARS + 900))

    outcome = await check_exam_finding_analysis(projection, _FixedClient())

    assert outcome.state == "ready" and outcome.analysed_refs == {1: ()}
    assert len(list((_isolated_freeze / "analysis").glob("*.json"))) == 1
    _assert_final_and_main_freeze(projection, outcome, status="non_compliant", frozen=True)


@pytest.mark.asyncio
async def test_failed_tail_window_cannot_overwrite_or_freeze_main_fact(_isolated_freeze: Path):
    fail_token = "FAIL_TAIL"
    # 超过单次提示容量后才进入窗口模式；尾窗失败时，其余窗口否定不能冒充全文否定。
    projection = _projection("甲" * 70000 + fail_token + "乙" * 300)

    outcome = await check_exam_finding_analysis(projection, _FixedClient(fail_token=fail_token))

    assert outcome.state == "partial" and outcome.analysed_refs == {}
    assert not list((_isolated_freeze / "analysis").glob("*.json"))
    assert apply_finding_analysis((_main_fact(projection),), outcome)[0].semantic_state == "present"
    _assert_final_and_main_freeze(projection, outcome, status="compliant", frozen=False)


@pytest.mark.asyncio
async def test_distant_sections_in_ordinary_long_document_keep_full_context(_isolated_freeze: Path):
    course = DISTRIBUTED_REPORT + "甲" * 6500 + DISTRIBUTED_BASIS
    projection = _projection(course)
    client = _DistributedClient()

    outcome = await check_exam_finding_analysis(projection, client)

    assert outcome.state == "ready"
    assert outcome.analysed_refs == {1: tuple(sorted(projection.course_candidates or {}))}
    assert any(DISTRIBUTED_REPORT in _visible_text(prompt) and DISTRIBUTED_BASIS in _visible_text(prompt)
               for prompt in client.prompts)
    _assert_final_and_main_freeze(projection, outcome, status="compliant", frozen=True)


@pytest.mark.asyncio
async def test_cross_window_relation_over_capacity_is_partial_not_false_negative(_isolated_freeze: Path):
    course = DISTRIBUTED_REPORT + "甲" * 70000 + DISTRIBUTED_BASIS
    projection = _projection(course)
    client = _DistributedClient()

    outcome = await check_exam_finding_analysis(projection, client)

    assert outcome.state == "partial" and outcome.analysed_refs == {}
    assert not any(DISTRIBUTED_REPORT in _visible_text(prompt) and DISTRIBUTED_BASIS in _visible_text(prompt)
                   for prompt in client.prompts)
    assert not list((_isolated_freeze / "analysis").glob("*.json"))
    assert apply_finding_analysis((_main_fact(projection),), outcome)[0].semantic_state == "present"
    _assert_final_and_main_freeze(projection, outcome, status="compliant", frozen=False)


def test_v2_invalidates_old_main_key_without_deleting_old_artifact(_isolated_freeze: Path):
    prompt = "synthetic full-coverage prompt"
    expected = {1: ("course-1",)}

    def key_for(version: str) -> str:
        digest = hashlib.sha256()
        digest.update(version.encode("utf-8"))
        digest.update(b"\x1e")
        digest.update(prompt.encode("utf-8"))
        digest.update(b"\x1e")
        digest.update(json.dumps([(1, ["course-1"])], ensure_ascii=False).encode("utf-8"))
        return digest.hexdigest()

    old_key = key_for("exam-finding-analysis-freeze-v1")
    new_key = freeze.freeze_key(prompt, expected)
    assert freeze.FREEZE_SCHEMA_VERSION == "exam-finding-analysis-freeze-v2"
    assert new_key != old_key
    old_path = _isolated_freeze / "main" / f"{old_key}.json"
    old_path.parent.mkdir(parents=True)
    old_path.write_text(json.dumps({
        "schema_version": "exam-finding-analysis-freeze-v1",
        "key": old_key,
        "payload": {"facts": []},
    }), encoding="utf-8")

    assert freeze.load_payload("main", new_key) is None
    assert old_path.is_file()
    assert json.loads(old_path.read_text(encoding="utf-8"))["schema_version"].endswith("-v1")
