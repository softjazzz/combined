import json
from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode


MECHANICAL_SPUTUM_CLEARANCE = "\u673a\u68b0\u8f85\u52a9\u6392\u75f0"
PULMONARY_REHAB_AND_CLEARANCE = "\u80ba\u529f\u80fd\u5eb7\u590d\u5e76\u6392\u75f0"
PULMONARY_REHAB = "\u80ba\u529f\u80fd\u5eb7\u590d"
CONTINUE_ANTI_INFECTIVE = "\u7ee7\u7eed\u6297\u611f\u67d3\u6cbb\u7597"
CONTINUE_EXISTING_REHAB = "\u7ee7\u7eed\u65e2\u6709\u5eb7\u590d\u8bad\u7ec3"


def _completed(ref: str, action_type: str, text: str, when: datetime):
    return episode._CompletedRecommendation(
        "consultation_record-1",
        episode._Recommendation(
            ref,
            action_type,
            text,
            text,
            "consultation_record-1",
            # 是否延续当前治疗由第一阶段模型标注（2026-10-22）；合成样本按“继续”开头给出。
            continues_current_treatment=text.startswith("继续"),
        ),
        episode._ObservedTime(when, True),
        window_start=(when - timedelta(days=3)).date(),
    )


def _payload(prompt: str) -> dict:
    return json.loads(prompt[prompt.rfind('{"recommendations":'):])


def test_visible_window_order_is_shared_with_each_eligible_recommendation():
    target_ref = "inpat_nondrug_order-target"
    completed = (
        _completed(
            "consultation_record-1#r1",
            "procedure",
            PULMONARY_REHAB_AND_CLEARANCE,
            datetime(2026, 8, 12, 9),
        ),
        _completed(
            "consultation_record-1#r2",
            "procedure",
            MECHANICAL_SPUTUM_CLEARANCE,
            datetime(2026, 8, 12, 9),
        ),
    )
    filler = tuple(
        episode._CandidateDocument(
            f"inpat_nondrug_order-{index}",
            "inpat_nondrug_order",
            episode._ObservedTime(datetime(2026, 8, 12, 8, index % 60), True),
            f"synthetic unrelated treatment {index}",
        )
        for index in range(81)
    )
    target = episode._CandidateDocument(
        target_ref,
        "inpat_nondrug_order",
        episode._ObservedTime(datetime(2026, 8, 11, 16, 51), True),
        MECHANICAL_SPUTUM_CLEARANCE,
    )

    candidates = (*filler, target)
    default_prompt, default_allowed = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )
    assert target_ref not in default_allowed["consultation_record-1#r1"]

    prompt, allowed = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
        share_visible_order_refs=True,
    )
    prompt_payload = _payload(prompt)
    assert (
        prompt_payload["candidate_documents"]
        == _payload(default_prompt)["candidate_documents"]
    )
    alias_by_text = {
        item["text"]: item["ref"]
        for item in prompt_payload["candidate_documents"]
    }
    target_alias = alias_by_text[MECHANICAL_SPUTUM_CLEARANCE]
    entries = {
        item["recommendation_ref"]: item
        for item in prompt_payload["recommendations"]
    }

    assert target_ref in allowed["consultation_record-1#r1"]
    assert target_alias in entries["consultation_record-1#r1"]["allowed_candidate_refs"]

    parsed = episode._parse_executions(
        {
            "executions": [
                {
                    "recommendation_ref": item.recommendation.recommendation_ref,
                    "execution_record_state": "no_trace",
                    "trace_refs": [],
                    "execution_state": "linked_specific",
                    "structured_action_refs": [target_alias],
                    "execution_quotes": [],
                    "confidence": "high",
                }
                for item in completed
            ]
        },
        completed=completed,
        allowed_refs=allowed,
        candidates=candidates,
    )

    assert parsed[0].execution_state == "linked_specific"
    assert parsed[0].execution_refs == (target_ref,)


def test_visible_orders_still_reject_wrong_source_and_outside_window():
    completed = (
        _completed(
            "consultation_record-1#r1",
            "procedure",
            PULMONARY_REHAB,
            datetime(2026, 8, 12, 9),
        ),
        _completed(
            "consultation_record-1#r2",
            "medication",
            CONTINUE_ANTI_INFECTIVE,
            datetime(2026, 8, 12, 9),
        ),
        _completed(
            "consultation_record-1#r3",
            "procedure",
            CONTINUE_EXISTING_REHAB,
            datetime(2026, 8, 12, 9),
        ),
    )
    candidates = (
        episode._CandidateDocument(
            "inpat_drug_order-wrong-source",
            "inpat_drug_order",
            episode._ObservedTime(datetime(2026, 8, 11, 10), True),
            "synthetic antimicrobial",
        ),
        episode._CandidateDocument(
            "inpat_nondrug_order-outside-window",
            "inpat_nondrug_order",
            episode._ObservedTime(datetime(2026, 8, 1, 10), True),
            "existing rehabilitation training",
        ),
    )

    prompt, allowed = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
        share_visible_order_refs=True,
    )
    prompt_payload = _payload(prompt)
    aliases = {
        item["source"]: item["ref"]
        for item in prompt_payload["candidate_documents"]
    }
    target_allowed = allowed["consultation_record-1#r1"]
    assert "inpat_drug_order-wrong-source" not in target_allowed
    assert "inpat_nondrug_order-outside-window" not in target_allowed

    parsed = episode._parse_executions(
        {
            "executions": [
                {
                    "recommendation_ref": "consultation_record-1#r1",
                    "execution_record_state": "no_trace",
                    "trace_refs": [],
                    "execution_state": "linked_specific",
                    "structured_action_refs": list(aliases.values()),
                    "execution_quotes": [],
                    "confidence": "high",
                },
                {
                    "recommendation_ref": "consultation_record-1#r2",
                    "execution_record_state": "no_trace",
                    "trace_refs": [],
                    "execution_state": "linked_specific",
                    "structured_action_refs": [aliases["inpat_drug_order"]],
                    "execution_quotes": [],
                    "confidence": "high",
                },
                {
                    "recommendation_ref": "consultation_record-1#r3",
                    "execution_record_state": "no_trace",
                    "trace_refs": [],
                    "execution_state": "linked_specific",
                    "structured_action_refs": [aliases["inpat_nondrug_order"]],
                    "execution_quotes": [],
                    "confidence": "high",
                },
            ]
        },
        completed=completed,
        allowed_refs=allowed,
        candidates=candidates,
    )

    assert parsed[0].execution_state == "absent"
    assert parsed[0].execution_refs == ()


def test_visible_order_ref_sharing_keeps_existing_prompt_budget_fail_closed(monkeypatch):
    target_ref = "inpat_nondrug_order-target"
    completed = (
        _completed(
            "consultation_record-1#r1",
            "procedure",
            PULMONARY_REHAB_AND_CLEARANCE,
            datetime(2026, 8, 12, 9),
        ),
        _completed(
            "consultation_record-1#r2",
            "procedure",
            MECHANICAL_SPUTUM_CLEARANCE,
            datetime(2026, 8, 12, 9),
        ),
    )
    filler = tuple(
        episode._CandidateDocument(
            f"inpat_nondrug_order-{index}",
            "inpat_nondrug_order",
            episode._ObservedTime(datetime(2026, 8, 12, 8, index % 60), True),
            f"synthetic unrelated treatment {index}",
        )
        for index in range(81)
    )
    candidates = (
        *filler,
        episode._CandidateDocument(
            target_ref,
            "inpat_nondrug_order",
            episode._ObservedTime(datetime(2026, 8, 11, 16, 51), True),
            MECHANICAL_SPUTUM_CLEARANCE,
        ),
    )
    default_prompt, _ = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )
    default_payload_length = len(
        default_prompt[default_prompt.rfind('{"recommendations":'):]
    )
    monkeypatch.setattr(
        episode,
        "_MAX_EXECUTION_PROMPT_CHARS",
        default_payload_length,
    )

    episode._execution_prompt(completed=completed, candidates=candidates)
    with pytest.raises(episode._SourceGap):
        episode._execution_prompt(
            completed=completed,
            candidates=candidates,
            share_visible_order_refs=True,
        )
