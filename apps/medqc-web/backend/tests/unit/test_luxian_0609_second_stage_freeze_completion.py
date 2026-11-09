"""会诊第二阶段与检查专项核验仅在完整可交付后冻结。"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import consultation_response_freeze
from app.services.luxian_0609 import exam_analysis_freeze
from app.services.luxian_0609 import native_consultation_episode_execution as consultation
from app.services.luxian_0609 import native_exam_lab_execution as exam_lab
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.exam_finding_analysis import FindingAnalysisOutcome
from app.services.luxian_0609.exam_lab_fact_extraction import ExamLabEventFact
from app.services.luxian_0609.exam_reason_check import ExamReasonOutcome
from app.services.luxian_0609.exam_result_record_check import ResultRecordOutcome


_CONSULTATION_RULES = (
    "LX0609-03-01-01",
    "LX0609-03-01-04",
)


class _ResponseClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def generate(self, _prompt, **_kwargs):
        self.calls += 1
        if not self.responses:
            raise AssertionError("冻结命中后不应再次调用底层模型")
        return self.responses.pop(0)


def _typed_decision(rule_id: str, status: str):
    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
        ),
        "evaluation_unknown": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
        ),
    }
    applicability, evidence_state, qc_direction = dimensions[status]
    reason_code = {
        "compliant": "requirement_satisfied",
        "non_compliant": "requirement_violated",
        "not_applicable": "trigger_absent_complete",
        "data_gap": "association_failed",
        "evaluation_unknown": "evidence_conflict",
        "technical_error": "model_invalid_output",
    }[status]
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash="a" * 64,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=(),
        evaluator_version="consultation-freeze-test-v1",
    )


async def _run_consultation(client, *, visit_id: str):
    return await consultation.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=_CONSULTATION_RULES,
        institute_id="synthetic-institute",
        patient_id="synthetic-patient",
        visit_id=visit_id,
        source_schema=None,
        llm_client=client,
    )


def _patch_consultation_result(monkeypatch, result):
    async def _uncached(**kwargs):
        await kwargs["llm_client"].generate("synthetic-second-stage", max_tokens=64)
        return result

    monkeypatch.setattr(
        consultation,
        "_execute_luxian_0609_native_consultation_episode_rules_uncached",
        _uncached,
    )


@pytest.mark.asyncio
async def test_all_typed_consultation_result_freezes_and_second_run_reuses(monkeypatch, tmp_path):
    monkeypatch.setenv(
        consultation_response_freeze._ENV_STORE_DIR,
        str(tmp_path / "consultation-freeze"),
    )
    result = consultation.NativeConsultationEpisodeExecutionResult(
        results=(),
        planned_rule_ids=_CONSULTATION_RULES,
        decisions=tuple(_typed_decision(rule_id, "compliant") for rule_id in _CONSULTATION_RULES),
        llm_call_count=1,
    )
    _patch_consultation_result(monkeypatch, result)

    first_client = _ResponseClient([{"content": "typed-ready"}])
    first = await _run_consultation(first_client, visit_id="typed-ready")
    second_client = _ResponseClient([])
    second = await _run_consultation(second_client, visit_id="typed-ready")

    assert first_client.calls == 1
    assert second_client.calls == 0
    assert first.llm_call_count == 1
    assert second.llm_call_count == 0


@pytest.mark.asyncio
async def test_legacy_consultation_result_still_freezes_normally(monkeypatch, tmp_path):
    monkeypatch.setenv(
        consultation_response_freeze._ENV_STORE_DIR,
        str(tmp_path / "consultation-freeze"),
    )
    result = consultation.NativeConsultationEpisodeExecutionResult(
        results=({"rule_id": _CONSULTATION_RULES[0], "status": "non_compliant"},),
        planned_rule_ids=(_CONSULTATION_RULES[0],),
        llm_call_count=1,
    )
    _patch_consultation_result(monkeypatch, result)

    first_client = _ResponseClient([{"content": "legacy-ready"}])
    await _run_consultation(first_client, visit_id="legacy-ready")
    second_client = _ResponseClient([])
    second = await _run_consultation(second_client, visit_id="legacy-ready")

    assert first_client.calls == 1
    assert second_client.calls == 0
    assert second.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_status", ("technical_error", "evaluation_unknown"))
async def test_mixed_consultation_failure_never_freezes(
    monkeypatch, tmp_path, failed_status,
):
    monkeypatch.setenv(
        consultation_response_freeze._ENV_STORE_DIR,
        str(tmp_path / "consultation-freeze"),
    )
    result = consultation.NativeConsultationEpisodeExecutionResult(
        results=({"rule_id": _CONSULTATION_RULES[0], "status": "compliant"},),
        planned_rule_ids=_CONSULTATION_RULES,
        decisions=(_typed_decision(_CONSULTATION_RULES[1], failed_status),),
        llm_call_count=1,
    )
    _patch_consultation_result(monkeypatch, result)

    first_client = _ResponseClient([{"content": "first-failed"}])
    await _run_consultation(first_client, visit_id=f"mixed-{failed_status}")
    second_client = _ResponseClient([{"content": "second-failed"}])
    await _run_consultation(second_client, visit_id=f"mixed-{failed_status}")

    assert first_client.calls == 1
    assert second_client.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("planned_rule_ids", "results", "decisions"),
    (
        (
            _CONSULTATION_RULES,
            ({"rule_id": _CONSULTATION_RULES[0], "status": "compliant"},),
            (),
        ),
        (
            (_CONSULTATION_RULES[0],),
            (
                {"rule_id": _CONSULTATION_RULES[0], "status": "compliant"},
                {"rule_id": _CONSULTATION_RULES[0], "status": "compliant"},
            ),
            (),
        ),
        (
            (_CONSULTATION_RULES[0], _CONSULTATION_RULES[0]),
            ({"rule_id": _CONSULTATION_RULES[0], "status": "compliant"},),
            (),
        ),
    ),
)
async def test_consultation_missing_or_duplicate_scope_never_freezes(
    monkeypatch, tmp_path, planned_rule_ids, results, decisions,
):
    monkeypatch.setenv(
        consultation_response_freeze._ENV_STORE_DIR,
        str(tmp_path / "consultation-freeze"),
    )
    result = consultation.NativeConsultationEpisodeExecutionResult(
        results=results,
        planned_rule_ids=planned_rule_ids,
        decisions=decisions,
        llm_call_count=1,
    )
    _patch_consultation_result(monkeypatch, result)

    first_client = _ResponseClient([{"content": "first-incomplete"}])
    await _run_consultation(first_client, visit_id="incomplete-scope")
    second_client = _ResponseClient([{"content": "second-incomplete"}])
    await _run_consultation(second_client, visit_id="incomplete-scope")

    assert first_client.calls == 1
    assert second_client.calls == 1


def _specialty_outcomes(rule_id: str):
    if rule_id == "LX0609-06-01-02":
        return (
            ExamReasonOutcome("failed", {}, 2, 7, 3, 10, 0.4),
            ExamReasonOutcome("ready", {1: ("course-1",)}, 1, 5, 2, 7, 0.2),
        )
    if rule_id == "LX0609-06-01-04":
        return (
            ResultRecordOutcome("failed", {}, 2, 7, 3, 10, 0.4),
            ResultRecordOutcome("ready", {1: ("course-1",)}, 1, 5, 2, 7, 0.2),
        )
    return (
        FindingAnalysisOutcome("failed", {}, 2, 7, 3, 10, 0.4),
        FindingAnalysisOutcome("ready", {1: ("course-1",)}, 1, 5, 2, 7, 0.2),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rule_id", "check_name"),
    (
        ("LX0609-06-01-02", "check_exam_reason"),
        ("LX0609-06-01-04", "check_exam_result_record"),
        ("LX0609-06-01-05", "check_exam_finding_analysis"),
    ),
)
async def test_failed_specialty_check_retries_then_successful_batch_reuses(
    monkeypatch, tmp_path, rule_id, check_name,
):
    monkeypatch.setenv(
        exam_analysis_freeze._ENV_STORE_DIR,
        str(tmp_path / "exam-freeze"),
    )
    monkeypatch.setattr(exam_lab, "_main_freeze_key", lambda *_args, **_kwargs: "same-material")
    counters = {"main": 0, "check": 0}
    fact = ExamLabEventFact(
        rule_id=rule_id,
        applicability="applicable",
        semantic_state="absent",
        positive_state="positive",
        course_doc_refs=(),
        evidence_refs=("report-1",),
        event_position=1,
    )

    async def _generate(**_kwargs):
        counters["main"] += 1
        return {"content": "synthetic-main"}

    monkeypatch.setattr(exam_lab, "_generate_exam_lab_fact_response", _generate)
    monkeypatch.setattr(exam_lab, "_usage", lambda _response: (11, 2, 13, 0.25))

    monkeypatch.setattr(
        exam_lab,
        "parse_exam_lab_fact_response_isolated",
        lambda **_kwargs: SimpleNamespace(
            facts=(fact,),
            rule_failures={},
            rule_failure_details={},
        ),
    )
    outcomes = list(_specialty_outcomes(rule_id))

    async def _check(*_args, **_kwargs):
        counters["check"] += 1
        return outcomes.pop(0)

    monkeypatch.setattr(exam_lab, check_name, _check)

    first = await exam_lab._extract_exam_lab_batch(
        projection=SimpleNamespace(imaging_events=(), imaging_event=None),
        eligible_rule_ids=(rule_id,),
        llm_client=object(),
    )
    second = await exam_lab._extract_exam_lab_batch(
        projection=SimpleNamespace(imaging_events=(), imaging_event=None),
        eligible_rule_ids=(rule_id,),
        llm_client=object(),
    )
    third = await exam_lab._extract_exam_lab_batch(
        projection=SimpleNamespace(imaging_events=(), imaging_event=None),
        eligible_rule_ids=(rule_id,),
        llm_client=object(),
    )

    assert first.incomplete_specialty_rule_ids == frozenset({rule_id})
    # 06-01-04 专项失败时主抽取结论改为未决（用户口径 2026-11-08），其余规则沿用原逻辑。
    assert first.facts == (
        (replace(fact, semantic_state="specialty_unverified"),)
        if rule_id == "LX0609-06-01-04" else (fact,)
    )
    assert (first.llm_call_count, first.prompt_tokens, first.completion_tokens, first.total_tokens) == (
        3,
        18,
        5,
        23,
    )
    assert first.api_time == pytest.approx(0.65)
    assert second.incomplete_specialty_rule_ids == frozenset()
    assert (second.llm_call_count, second.prompt_tokens, second.completion_tokens, second.total_tokens) == (
        2,
        16,
        4,
        20,
    )
    assert second.api_time == pytest.approx(0.45)
    assert third.facts == second.facts
    assert third.llm_call_count == 0
    assert counters == {"main": 2, "check": 2}


def test_main_freeze_key_invalidates_v1_without_removing_old_cache(monkeypatch, tmp_path):
    from app.services.luxian_0609.exam_output_batching import OUTPUT_PROTOCOL_VERSION

    monkeypatch.setenv(
        exam_analysis_freeze._ENV_STORE_DIR,
        str(tmp_path / "exam-freeze"),
    )
    rule_ids = ("LX0609-06-01-05",)
    monkeypatch.setattr(
        exam_lab,
        "build_exam_lab_fact_prompt",
        lambda **_kwargs: "same-material-prompt",
    )
    legacy_key = exam_analysis_freeze.freeze_key(
        OUTPUT_PROTOCOL_VERSION + "\x1e" + "same-material-prompt"
    )
    exam_analysis_freeze.save_payload("main", legacy_key, {"incomplete_v1": True})
    legacy_path = exam_analysis_freeze.default_store_dir() / "main" / f"{legacy_key}.json"
    current_key = exam_lab._main_freeze_key(object(), rule_ids)

    assert current_key != legacy_key
    assert legacy_path.is_file()
    assert exam_analysis_freeze.load_payload("main", legacy_key) == {"incomplete_v1": True}
    assert exam_lab._load_frozen_exam_lab_batch(
        current_key,
        requires_specialty_completion=True,
    ) is None


def test_non_specialty_v1_main_cache_remains_readable(monkeypatch, tmp_path):
    monkeypatch.setenv(
        exam_analysis_freeze._ENV_STORE_DIR,
        str(tmp_path / "exam-freeze"),
    )
    fact = ExamLabEventFact(
        rule_id="LX0609-06-03-03",
        applicability="applicable",
        semantic_state="present",
        positive_state="positive",
        course_doc_refs=(),
        evidence_refs=("report-1",),
        event_position=1,
    )
    key = "ordinary-v1-main"
    exam_analysis_freeze.save_payload("main", key, {
        "facts": [{
            "rule_id": fact.rule_id,
            "applicability": fact.applicability,
            "semantic_state": fact.semantic_state,
            "positive_state": fact.positive_state,
            "course_doc_refs": list(fact.course_doc_refs),
            "evidence_refs": list(fact.evidence_refs),
            "event_position": fact.event_position,
        }],
        "result_conflicts": {},
        "analysis_gaps": {},
    })

    loaded = exam_lab._load_frozen_exam_lab_batch(key)

    assert loaded is not None
    assert loaded.facts == (fact,)


def test_main_rule_failure_still_prevents_whole_batch_freeze(monkeypatch, tmp_path):
    monkeypatch.setenv(
        exam_analysis_freeze._ENV_STORE_DIR,
        str(tmp_path / "exam-freeze"),
    )
    fact = ExamLabEventFact(
        rule_id="LX0609-06-01-02",
        applicability="applicable",
        semantic_state="present",
        positive_state="not_relevant",
        course_doc_refs=("course-1",),
        evidence_refs=("report-1", "course-1"),
        event_position=1,
    )
    result = exam_lab._ExamLabBatchResult(
        facts=(fact,),
        rule_failures={"LX0609-06-01-04": "value"},
    )

    exam_lab._save_frozen_exam_lab_batch("mixed-main-result", result)

    assert exam_analysis_freeze.load_payload("main", "mixed-main-result") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ("transport", "parse"))
async def test_main_extraction_failure_paths_do_not_freeze_or_reference_unset_completion(
    monkeypatch, tmp_path, failure_mode,
):
    monkeypatch.setenv(
        exam_analysis_freeze._ENV_STORE_DIR,
        str(tmp_path / "exam-freeze"),
    )
    monkeypatch.setattr(exam_lab, "_main_freeze_key", lambda *_args, **_kwargs: "failed-main")

    async def _generate(**_kwargs):
        if failure_mode == "transport":
            raise RuntimeError("synthetic transport failure")
        return {"content": "invalid synthetic payload"}

    monkeypatch.setattr(exam_lab, "_generate_exam_lab_fact_response", _generate)
    monkeypatch.setattr(exam_lab, "_usage", lambda _response: (3, 1, 4, 0.1))
    if failure_mode == "parse":
        def _parse(**_kwargs):
            raise ValueError("synthetic parse failure")

        monkeypatch.setattr(exam_lab, "parse_exam_lab_fact_response_isolated", _parse)

    result = await exam_lab._extract_exam_lab_batch(
        projection=SimpleNamespace(imaging_events=(), imaging_event=None),
        eligible_rule_ids=("LX0609-06-01-05",),
        llm_client=object(),
    )

    assert result.facts is None
    assert result.incomplete_specialty_rule_ids == frozenset()
    assert exam_analysis_freeze.load_payload("main", "failed-main") is None
