from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path


def test_synthetic_replay_runs_formal_execution_reducer_and_aggregator() -> None:
    from scripts import verify_consultation_family_acceptance as verify

    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )

    replay = asyncio.run(verify.run_replay(fixture))

    assert replay["historical_b3_response"] is False
    assert replay["network_used"] is False
    assert replay["llm_call_count"] == 2
    assert replay["prompt_count"] == 2
    assert [item["status"] for item in replay["results"]] == [
        "compliant",
        "compliant",
        "compliant",
        "compliant",
    ]
    assert all(item["reason_code"] == "requirement_satisfied" for item in replay["results"])
    assert replay["results"][0]["fact_ref_count"] > 0
    assert replay["results"][0]["evidence_coordinates"]
    assert all(
        coordinate[field]
        for result in replay["results"]
        for coordinate in result["evidence_coordinates"]
        for field in (
            "source_type",
            "source_document_id",
            "field_path",
            "record_time",
        )
    )
    assert "_prompt_bytes" in replay
    assert "source_quote" not in str(verify._public_replay(replay))


def test_variant_comparison_reports_byte_equal_prompts_without_serializing_them() -> None:
    from scripts import verify_consultation_family_acceptance as verify

    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )

    comparison = verify.compare_replays(
        [asyncio.run(verify.run_replay(fixture)), asyncio.run(verify.run_replay(fixture))]
    )

    assert comparison["prompts_byte_equal"] is True
    assert comparison["prompt_count_by_variant"] == [2, 2]
    assert comparison["acceptance_projection_exact_equal"] is True
    assert all(
        result["status_equal"]
        and result["reason_code_equal"]
        and result["facts_equal"]
        and result["evidence_coordinates_set_equal"]
        and result["fact_ref_count_equal"]
        and result["exact_equal"]
        for result in comparison["rule_comparisons"]
    )
    assert "prompt_text" not in comparison


def test_variant_comparison_normalizes_coordinate_order_but_reports_fact_ref_count_change() -> None:
    from scripts import verify_consultation_family_acceptance as verify

    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )
    baseline = asyncio.run(verify.run_replay(fixture))
    candidate = deepcopy(baseline)
    candidate["results"][0]["evidence_coordinates"].reverse()
    candidate["results"][0]["fact_ref_count"] += 11

    comparison = verify.compare_replays([baseline, candidate])
    first_rule = comparison["rule_comparisons"][0]

    assert first_rule["status_equal"] is True
    assert first_rule["reason_code_equal"] is True
    assert first_rule["facts_equal"] is True
    assert first_rule["evidence_coordinates_set_equal"] is True
    assert first_rule["fact_ref_count_by_variant"] == [2, 13]
    assert first_rule["fact_ref_count_equal"] is False
    assert first_rule["exact_equal"] is False
    assert comparison["acceptance_projection_exact_equal"] is False


def test_variant_subprocess_decodes_utf8_json_output() -> None:
    from scripts import verify_consultation_family_acceptance as verify

    workspace_root = Path(__file__).parents[3]
    replay = verify._run_variant_subprocess(
        fixture_path=(
            Path(__file__).parents[1]
            / "fixtures"
            / "luxian_0609"
            / "consultation-family-replay.json"
        ),
        variant_root=workspace_root,
    )
    application_result = next(
        item for item in replay["results"] if item["rule_id"] == "LX0609-021"
    )

    assert application_result["facts"]["checked_requirement"] == (
        "说明具体临床问题、会诊理由或明确会诊目的"
    )


def test_variant_subprocesses_compare_prompt_bytes_with_one_session_key() -> None:
    from scripts import verify_consultation_family_acceptance as verify

    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-family-replay.json"
    )
    workspace_root = Path(__file__).parents[3]
    session_key = b"consultation-replay-test-session"

    replays = [
        verify._run_variant_subprocess(
            fixture_path=fixture,
            variant_root=workspace_root,
            session_hmac_key=session_key,
        )
        for _ in range(2)
    ]

    comparison = verify.compare_replays(replays)
    assert comparison["prompts_byte_equal"] is True
    assert comparison["prompt_count_by_variant"] == [2, 2]
    assert comparison["acceptance_projection_exact_equal"] is True
