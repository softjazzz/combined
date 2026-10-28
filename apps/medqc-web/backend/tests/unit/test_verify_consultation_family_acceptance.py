from __future__ import annotations

import asyncio
from copy import deepcopy
import os
from pathlib import Path
import socket

import pytest


@pytest.mark.parametrize("fail", [False, True])
def test_replay_isolates_both_freeze_stores_and_restores_environment(monkeypatch, tmp_path, fail):
    from scripts import verify_consultation_family_acceptance as verify

    keys = ("LUXIAN_0609_OPINION_FREEZE_DIR", "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR")
    originals = {key: str(tmp_path / key) for key in keys}
    for key, value in originals.items():
        monkeypatch.setenv(key, value)
    stores = []
    try:
        with verify._isolated_opinion_freeze():
            stores = [Path(os.environ[key]) for key in keys]
            assert len(set(stores)) == 2
            for key, store in zip(keys, stores):
                assert store != Path(originals[key])
                store.mkdir(parents=True, exist_ok=True)
                (store / "synthetic.json").write_text("{}", encoding="utf-8")
            if fail:
                raise RuntimeError("controlled failure")
    except RuntimeError:
        assert fail
    assert {key: os.environ[key] for key in keys} == originals
    assert all(not store.exists() for store in stores)
    assert all(not Path(value).exists() for value in originals.values())


def test_replay_network_guard_preserves_socket_type_and_blocks_existing_socket():
    from scripts import verify_consultation_family_acceptance as verify

    socket_type = socket.socket
    with socket.socket() as connection:
        with verify._offline_execution_guards() as activity:
            # Windows asyncio 和 ssl 导入依赖 socket.socket 仍是类型。
            assert socket.socket is socket_type
            assert isinstance(connection, socket.socket)
            with pytest.raises(verify.ReplayFixtureError, match="network access"):
                connection.connect(("127.0.0.1", 1))
            assert activity()["network_used"] is True


def test_synthetic_replay_runs_formal_execution_reducer_and_aggregator() -> None:
    from scripts import verify_consultation_family_acceptance as verify

    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-023-engine-replay.json"
    )

    replay = asyncio.run(verify.run_replay(fixture))

    assert replay["historical_b3_response"] is False
    assert replay["network_used"] is False
    # 第一阶段、执行判断与会诊措施逐项核对（2026-10-12）各 1 次。
    assert replay["llm_call_count"] == 3
    assert replay["prompt_count"] == 3
    assert [item["status"] for item in replay["results"]] == ["compliant"]
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
        / "consultation-023-engine-replay.json"
    )

    comparison = verify.compare_replays(
        [asyncio.run(verify.run_replay(fixture)), asyncio.run(verify.run_replay(fixture))]
    )

    assert comparison["prompts_byte_equal"] is True
    assert comparison["prompt_count_by_variant"] == [3, 3]
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
        / "consultation-023-engine-replay.json"
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
            / "consultation-023-engine-replay.json"
        ),
        variant_root=workspace_root,
    )
    execution_result = next(
        item for item in replay["results"] if item["rule_id"] == "LX0609-03-01-04"
    )

    assert execution_result["facts"]["recommendation_count"] == 1


def test_variant_subprocesses_compare_prompt_bytes_with_one_session_key() -> None:
    from scripts import verify_consultation_family_acceptance as verify

    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-023-engine-replay.json"
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
    assert comparison["prompt_count_by_variant"] == [3, 3]
    assert comparison["acceptance_projection_exact_equal"] is True
