from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest


RUNNER_PATH = Path(__file__).resolve().parents[3] / "tmp-lx0609-ab-test" / "run_lx0609_fact_gate_ab.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("lx0609_ab_telemetry_runner", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


class FakeClient:
    def __init__(self, responses: list[dict[str, Any] | Exception] | None = None) -> None:
        self.model = "fake-model"
        self.responses = list(responses or [])
        self.call_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_tokens = 0
        self.total_api_time = 0.0

    async def generate(self, _prompt: str) -> dict[str, Any]:
        self.call_count += 1
        await asyncio.sleep(0)
        response = self.responses.pop(0) if self.responses else _response()
        if isinstance(response, Exception):
            self.error_count += 1
            raise response
        breakdown = dict(response.get("_usage_breakdown") or response.get("usage") or {})
        total_tokens = int(
            breakdown.get("total_tokens")
            or breakdown.get("total")
            or (
                int(breakdown.get("input_tokens") or breakdown.get("prompt_tokens") or 0)
                + int(breakdown.get("output_tokens") or breakdown.get("completion_tokens") or 0)
            )
        )
        self.success_count += 1
        self.total_tokens += total_tokens
        return dict(response)


def _response(
    *,
    input_tokens: int = 2,
    output_tokens: int = 3,
    total_tokens: int | None = None,
    content: str = '{"facts": []}',
) -> dict[str, Any]:
    total = input_tokens + output_tokens if total_tokens is None else total_tokens
    return {
        "choices": [{"message": {"content": content}}],
        "_usage_breakdown": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
        },
    }


@pytest.mark.asyncio
async def test_zero_llm_fixture_has_zero_calls_and_tokens() -> None:
    client = FakeClient()
    ledger = runner.LLMCallLedger(model="fake-model", run_id="zero")

    telemetry = ledger.build_telemetry(client=client)

    assert telemetry["llm_call_count"] == 0
    assert telemetry["total_tokens"] == 0
    assert telemetry["unattributed_tokens"] == 0
    assert telemetry["telemetry_invariant_ok"] is True
    assert all(stage["call_count"] == 0 for stage in telemetry["stage_summary"].values())


@pytest.mark.asyncio
async def test_one_shared_call_is_counted_once_for_multiple_rules() -> None:
    client = FakeClient([_response(input_tokens=5, output_tokens=7)])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="shared")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)

    with runner.llm_call_context(
        stage="fact_extraction",
        record_id="record-1",
        family_key="surgery_anesthesia",
        rule_ids=["LX0609-029", "LX0609-030"],
    ):
        await wrapped.generate("shared fact prompt")

    telemetry = ledger.build_telemetry(client=client)
    entry = telemetry["llm_call_ledger"][0]
    assert telemetry["llm_call_count"] == 1
    assert telemetry["total_tokens"] == 12
    assert entry["rule_ids"] == ["LX0609-029", "LX0609-030"]
    assert entry["cache_hit"] is None
    assert entry["cache_observation"] == "unavailable"


@pytest.mark.asyncio
async def test_fact_extraction_internal_calls_keep_family_specific_attribution() -> None:
    client = FakeClient([_response(), _response()])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="families")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)

    with runner.llm_call_context(
        stage="fact_extraction",
        record_id="record-1",
        family_key="multi_family",
        rule_ids=["LX0609-029", "LX0609-030", "LX0609-019"],
        rule_ids_by_family={
            "surgery_anesthesia": ["LX0609-029", "LX0609-030"],
            "tumor_pathology": ["LX0609-019"],
        },
    ):
        await wrapped.generate("抽取与“手术麻醉”相关的事实")
        await wrapped.generate("抽取与“肿瘤病理”相关的事实")

    entries = ledger.entries(stage="fact_extraction", record_id="record-1")
    assert [(entry["family_key"], entry["rule_ids"]) for entry in entries] == [
        ("surgery_anesthesia", ["LX0609-029", "LX0609-030"]),
        ("tumor_pathology", ["LX0609-019"]),
    ]


@pytest.mark.asyncio
async def test_usage_breakdown_preserves_unattributed_tokens() -> None:
    client = FakeClient([_response(input_tokens=4, output_tokens=5, total_tokens=12)])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="usage")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)

    with runner.llm_call_context(
        stage="semantic_evaluation",
        record_id="record-1",
        family_key="single_rule_b2",
        rule_ids=["LX0609-029"],
    ):
        await wrapped.generate("usage prompt")

    telemetry = ledger.build_telemetry(client=client)
    entry = telemetry["llm_call_ledger"][0]
    assert (entry["input_tokens"], entry["output_tokens"], entry["unattributed_tokens"]) == (4, 5, 3)
    assert entry["total_tokens"] == 12
    assert telemetry["total_tokens"] == telemetry["input_tokens"] + telemetry["output_tokens"] + telemetry["unattributed_tokens"]


@pytest.mark.asyncio
async def test_failed_call_has_sanitized_ledger_entry_and_zero_unknown_tokens() -> None:
    credential_error = " ".join(
        ["API", "key=secret-value", "Author" + "ization:", "Bear" + "er", "hidden"]
    )
    client = FakeClient([RuntimeError(credential_error)])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="error")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)

    with pytest.raises(RuntimeError), runner.llm_call_context(
        stage="semantic_evaluation",
        record_id="record-1",
        family_key="single_rule_b2",
        rule_ids=["LX0609-029"],
    ):
        await wrapped.generate("prompt with private content")

    telemetry = ledger.build_telemetry(client=client)
    entry = telemetry["llm_call_ledger"][0]
    serialized = json.dumps(telemetry, ensure_ascii=False)
    assert entry["success"] is False
    assert entry["error_type"] == "RuntimeError"
    assert entry["total_tokens"] == 0
    assert "secret-value" not in serialized
    assert "private content" not in serialized
    assert telemetry["telemetry_invariant_ok"] is True


@pytest.mark.asyncio
async def test_fallback_stage_is_independently_attributed() -> None:
    client = FakeClient([_response(input_tokens=1, output_tokens=2)])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="fallback")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)

    with runner.llm_call_context(
        stage="fallback",
        record_id="record-1",
        family_key="surgery_anesthesia",
        rule_ids=["LX0609-032"],
    ):
        await wrapped.generate("fallback prompt")

    telemetry = ledger.build_telemetry(client=client)
    assert telemetry["stage_summary"]["fallback"]["call_count"] == 1
    assert telemetry["stage_summary"]["fact_extraction"]["call_count"] == 0
    assert telemetry["stage_summary"]["semantic_evaluation"]["call_count"] == 0


@pytest.mark.asyncio
async def test_concurrent_calls_have_unique_ids_and_exact_totals() -> None:
    call_count = 24
    client = FakeClient([_response(input_tokens=2, output_tokens=1) for _ in range(call_count)])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="concurrent")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)

    async def invoke(index: int) -> None:
        with runner.llm_call_context(
            stage="semantic_evaluation",
            record_id=f"record-{index}",
            family_key="single_rule_b2",
            rule_ids=["LX0609-029"],
        ):
            await wrapped.generate(f"prompt-{index}")

    await asyncio.gather(*(invoke(index) for index in range(call_count)))

    telemetry = ledger.build_telemetry(client=client)
    ids = [entry["call_id"] for entry in telemetry["llm_call_ledger"]]
    assert len(ids) == len(set(ids)) == call_count
    assert telemetry["total_tokens"] == call_count * 3
    assert telemetry["llm_call_count"] == sum(
        stage["call_count"] for stage in telemetry["stage_summary"].values()
    )
    assert telemetry["telemetry_invariant_ok"] is True


@pytest.mark.asyncio
async def test_client_counter_mismatch_is_exposed() -> None:
    client = FakeClient([_response(input_tokens=2, output_tokens=3)])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="mismatch")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)
    with runner.llm_call_context(
        stage="fact_extraction",
        record_id="record-1",
        family_key="surgery_anesthesia",
        rule_ids=["LX0609-029"],
    ):
        await wrapped.generate("mismatch prompt")
    client.total_tokens += 9

    telemetry = ledger.build_telemetry(client=client)

    assert telemetry["telemetry_invariant_ok"] is False
    assert any("client_total_tokens_mismatch" in error for error in telemetry["telemetry_invariant_error"])


@pytest.mark.asyncio
async def test_prompt_hash_is_present_without_prompt_or_credentials() -> None:
    client = FakeClient([_response()])
    ledger = runner.LLMCallLedger(model="fake-model", run_id="privacy")
    wrapped = runner.LedgeredLLMClient(client, ledger=ledger)
    secret_prompt = " ".join(
        ["Author" + "ization:", "Bear" + "er", "top-secret", "API", "key=another-secret"]
    )
    with runner.llm_call_context(
        stage="fact_extraction",
        record_id="record-1",
        family_key="surgery_anesthesia",
        rule_ids=["LX0609-029"],
    ):
        await wrapped.generate(secret_prompt)

    telemetry = ledger.build_telemetry(client=client)
    entry = telemetry["llm_call_ledger"][0]
    serialized = json.dumps(telemetry, ensure_ascii=False)
    assert len(entry["prompt_hash"]) == 64
    assert secret_prompt not in serialized
    assert "top-secret" not in serialized
    assert "another-secret" not in serialized
    assert "prompt" not in entry
    assert "response" not in entry


@pytest.mark.asyncio
async def test_runner_compatibility_aliases_match_stage_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(
        [
            _response(input_tokens=2, output_tokens=3, content='{"facts": []}'),
            _response(
                input_tokens=4,
                output_tokens=6,
                content='{"status":"compliant","conclusion":"ok","evidence":"fact","suggestion":"","missing_fields":[],"confidence":0.9}',
            ),
        ]
    )

    async def fake_extract(_documents, *, llm_client, **_kwargs):
        await llm_client.generate("事实抽取“手术麻醉”")
        return SimpleNamespace(facts=(), stats={"stage_counts": {"llm": 0}})

    decision = SimpleNamespace(
        status=runner.TRIGGER_PRESENT,
        reason="triggered",
        data_gap_fields=(),
        matched_keywords=(),
    )
    monkeypatch.setattr(runner, "_llm_client", lambda _model: client)
    monkeypatch.setattr(runner, "_documents_for_visit", lambda _record_id: [{"has_content": True}])
    monkeypatch.setattr(runner, "extract_luxian_0609_unified_fact_table", fake_extract)
    monkeypatch.setattr(
        runner,
        "evaluate_luxian_0609_gates_from_facts",
        lambda **_kwargs: SimpleNamespace(decisions={"LX0609-029": decision}),
    )
    monkeypatch.setattr(
        runner,
        "_rule_catalog",
        lambda _rule_ids: {"LX0609-029": {"rule_id": "LX0609-029", "name": "test"}},
    )

    result = await runner.run_fact_gate_plus_trimmed_qc(
        record_ids=["record-1"],
        selected_rule_ids=["LX0609-029"],
        families=["surgery_anesthesia"],
        model="fake-model",
    )

    telemetry = result["telemetry"]
    fact_stage = telemetry["stage_summary"]["fact_extraction"]
    semantic_stage = telemetry["stage_summary"]["semantic_evaluation"]
    assert result["llm_call_count"] == telemetry["llm_call_count"] == 2
    assert result["llm_total_tokens"] == telemetry["total_tokens"] == 15
    assert result["fact_extraction_llm_call_count"] == result["gate_llm_call_count"] == fact_stage["call_count"] == 1
    assert result["fact_extraction_llm_total_tokens"] == result["gate_llm_total_tokens"] == fact_stage["total_tokens"] == 5
    assert result["b2_llm_call_count"] == semantic_stage["call_count"] == 1
    assert result["b2_llm_total_tokens"] == semantic_stage["total_tokens"] == 10
    assert result["rows"][("record-1", "LX0609-029")]["tokens_additive"] is False
    assert telemetry["telemetry_invariant_ok"] is True


def test_compare_and_markdown_do_not_sum_shared_rule_tokens(tmp_path: Path) -> None:
    full = {
        "job_id": "job",
        "wall_elapsed_sec": 1,
        "processing_time_sec": 1,
        "total_tokens": 20,
        "item_count": 2,
        "status_counter": {"compliant": 2},
        "rows": {
            ("record-1", "LX0609-029"): {"status": "compliant", "duration_sec": 1, "tokens": 10},
            ("record-2", "LX0609-029"): {"status": "compliant", "duration_sec": 1, "tokens": 10},
        },
    }
    telemetry = {
        "telemetry_schema_version": runner.TELEMETRY_SCHEMA_VERSION,
        "llm_call_count": 1,
        "total_tokens": 9,
        "input_tokens": 4,
        "output_tokens": 5,
        "unattributed_tokens": 0,
        "telemetry_invariant_ok": True,
        "stage_summary": {
            "fact_extraction": {"call_count": 1, "total_tokens": 9},
            "semantic_evaluation": {"call_count": 0, "total_tokens": 0},
        },
    }
    trimmed_rows = {
        ("record-1", "LX0609-029"): {
            "status": "compliant",
            "duration_sec": 2,
            "duration_additive": False,
            "tokens": 9,
            "tokens_additive": False,
            "token_attribution": "shared_fact_extraction_non_additive",
            "shared_call_ids": ["call-1"],
        },
        ("record-2", "LX0609-029"): {
            "status": "compliant",
            "duration_sec": 2,
            "duration_additive": False,
            "tokens": 9,
            "tokens_additive": False,
            "token_attribution": "shared_fact_extraction_non_additive",
            "shared_call_ids": ["call-1"],
        },
    }
    trimmed = {
        "wall_elapsed_sec": 2,
        "llm_total_elapsed_sec": 1,
        "llm_total_tokens": 9,
        "item_count": 2,
        "status_counter": {"compliant": 2},
        "rows": trimmed_rows,
        "telemetry": telemetry,
    }
    comparison = runner.compare(full, trimmed)
    stat = comparison["rule_stats"]["LX0609-029"]
    assert stat["fact_gate_record_tokens_sum"] is None
    assert stat["fact_gate_shared_duration_sum_sec"] is None
    assert stat["fact_gate_unique_call_ids"] == ["call-1"]

    output = tmp_path / "summary.md"
    runner.write_markdown(
        {
            "full_text": full,
            "fact_gate_trimmed": trimmed,
            "comparison": comparison,
            "model": "fake-model",
            "parallel_records": 1,
            "record_ids": ["record-1", "record-2"],
            "selected_rule_ids": ["LX0609-029"],
        },
        output,
    )
    markdown = output.read_text(encoding="utf-8")
    assert "shared/non-additive (1 unique calls)" in markdown
    assert "| 18 |" not in markdown
    assert "ledger tokens: `9`" in markdown


def test_full_text_rows_do_not_emit_patient_name(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeWorkspaceService:
        def get_batch_job_for_processing(self, *, job_id: str):
            assert job_id == "job"
            return {
                "items": [
                    {
                        "record_id": "record-1",
                        "rule_id": "LX0609-029",
                        "status": "compliant",
                        "patient_name": "person-name",
                        "evidence": "person-name has a short evidence fragment",
                        "conclusion": "person-name result",
                    }
                ],
                "summary": {},
            }

    monkeypatch.setattr(runner, "CustomQCWorkspaceService", FakeWorkspaceService)

    result = runner.load_full_text_job("job")
    row = result["rows"][("record-1", "LX0609-029")]
    serialized = json.dumps(
        {**result, "rows": runner._stringify_row_keys(result["rows"])},
        ensure_ascii=False,
    )
    assert "patient_name" not in row
    assert "person-name" not in serialized
    assert "[REDACTED]" in row["evidence"]
