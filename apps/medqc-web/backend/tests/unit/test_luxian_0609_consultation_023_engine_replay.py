"""现行023固定响应穿过正式会诊聚合链的工程回归。"""

import asyncio
from pathlib import Path

from scripts.verify_consultation_family_acceptance import run_replay


def test_active_023_fixed_model_responses_keep_public_result_and_usage(
    monkeypatch, tmp_path: Path
) -> None:
    fixture = (
        Path(__file__).parents[1]
        / "fixtures"
        / "luxian_0609"
        / "consultation-023-engine-replay.json"
    )

    unused_store = tmp_path / "must-remain-empty"
    monkeypatch.setenv("LUXIAN_0609_OPINION_FREEZE_DIR", str(unused_store))
    replay = asyncio.run(run_replay(fixture))
    repeated = asyncio.run(run_replay(fixture))

    assert not unused_store.exists()
    assert replay["_prompt_bytes"] == repeated["_prompt_bytes"]
    assert replay["results"] == repeated["results"]
    assert replay["network_used"] is False
    # 意见抽取、执行核对，以及原判合规后的会诊措施逐项核对（用户口径 2026-10-12）。
    assert replay["llm_call_count"] == replay["prompt_count"] == 3
    assert (
        replay["prompt_tokens"],
        replay["completion_tokens"],
        replay["total_tokens"],
    ) == (39, 12, 51)
    assert len(replay["results"]) == 1
    result = replay["results"][0]
    assert result["rule_id"] == "LX0609-03-01-04"
    assert (result["status"], result["reason_code"]) == (
        "compliant",
        "requirement_satisfied",
    )
    assert result["fact_ref_count"] == 2
    assert len(result["evidence_coordinates"]) == 2
