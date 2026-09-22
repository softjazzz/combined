from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_luxian_0609_fast5_readonly as fast5


def _case_map() -> dict[str, object]:
    return {
        "cases": [
            {
                "case_label": f"case-{index:02d}",
                "scene": "running",
                "institute_id": f"inst-private-{index}",
                "patient_id": f"patient-private-{index}",
                "visit_id": f"visit-private-{index}",
            }
            for index in range(1, 6)
        ]
    }


def _response(selected: tuple[str, ...], *, private_marker: str = "") -> dict[str, object]:
    return {
        "schema_version": "lx0609-preproduction-runner-v1",
        "results": [
            {
                "rule_id": rule_id,
                "status": "compliant",
                "metadata": {
                    "reason_code": "qualified_document_present",
                    "execution_source": "lx0609_native",
                    "executor_type": "program",
                    "record_content": private_marker,
                },
                "evidence_payload": {"primary_document_text": private_marker},
            }
            for rule_id in selected
        ],
        "metrics": {
            "wall_time_ms": 12.5,
            "llm_call_count": 1,
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
        },
    }


@pytest.mark.asyncio
async def test_fast5_runs_five_cases_once_in_catalog_order_and_projects_safe_output():
    loaded: list[tuple[str, str, str, str]] = []
    calls: list[tuple[str, ...]] = []
    marker = "FAST5_PRIVATE_BODY_MARKER"

    def loader(**kwargs):
        loaded.append(
            (
                kwargs["scene"],
                kwargs["institute_id"],
                kwargs["patient_id"],
                kwargs["visit_id"],
            )
        )
        return {"scene": kwargs["scene"], "medical_text": marker}

    async def runner(**kwargs):
        selected = tuple(kwargs["selected_customer_rule_ids"])
        calls.append(selected)
        return _response(selected, private_marker=marker)

    result = await fast5.build_fast5_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-20",
        sample_kind="real",
        bundle_loader=loader,
        runner=runner,
        llm_client=SimpleNamespace(model="test-model"),
        base_settings=SimpleNamespace(),
    )

    assert len(loaded) == 5
    assert calls == [fast5.FAST5_RULE_IDS] * 5
    assert result["selected_rule_ids"] == list(fast5.FAST5_RULE_IDS)
    assert result["summary"]["case_count"] == 5
    assert result["summary"]["judgment_count"] == 60
    assert result["summary"]["llm_call_count"] == 5
    assert len(result["cases"]) == 5
    assert all(len(case["results"]) == 12 for case in result["cases"])
    output = repr(result)
    assert marker not in output
    assert "inst-private" not in output
    assert "patient-private" not in output
    assert "visit-private" not in output
    assert "2026-07-20" not in output


@pytest.mark.asyncio
async def test_fast5_supports_family_and_catalog_ordered_subsets():
    calls: list[tuple[str, ...]] = []

    def loader(**kwargs):
        return {"scene": kwargs["scene"]}

    async def runner(**kwargs):
        selected = tuple(kwargs["selected_customer_rule_ids"])
        calls.append(selected)
        return _response(selected)

    result = await fast5.build_fast5_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-20",
        sample_kind="synthetic",
        family="surgery",
        selected_rule_ids=("LX0609-04-02-04", "LX0609-11-01-01"),
        bundle_loader=loader,
        runner=runner,
        llm_client=SimpleNamespace(model="test-model"),
        base_settings=SimpleNamespace(),
    )

    assert calls == [("LX0609-04-02-04", "LX0609-11-01-01")] * 5
    assert result["selected_rule_ids"] == ["LX0609-04-02-04", "LX0609-11-01-01"]
    assert result["summary"]["judgment_count"] == 10


@pytest.mark.asyncio
async def test_fast5_wraps_case_failures_as_safe_technical_results_without_echo():
    marker = "FAST5_RAW_EXCEPTION_MARKER_13800138000"

    def loader(**kwargs):
        if kwargs["visit_id"].endswith("3"):
            raise RuntimeError(marker)
        return {"scene": kwargs["scene"]}

    async def runner(**kwargs):
        return _response(tuple(kwargs["selected_customer_rule_ids"]))

    result = await fast5.build_fast5_batch(
        case_map=_case_map(),
        evaluation_as_of_date="2026-07-20",
        sample_kind="real",
        family="course",
        bundle_loader=loader,
        runner=runner,
        llm_client=SimpleNamespace(model="test-model"),
        base_settings=SimpleNamespace(),
    )

    failed = result["cases"][2]
    assert [item["status"] for item in failed["results"]] == ["technical_error"] * 3
    assert all(
        item["metadata"] == {"reason_code": "fast5_case_execution_failed"}
        for item in failed["results"]
    )
    assert marker not in repr(result)


def test_fast5_rejects_invalid_or_noncanonical_scope_before_loading():
    with pytest.raises(fast5.Fast5ContractError, match="scope"):
        fast5._resolve_selected_rule_ids(
            family="course",
            selected_rule_ids=("LX0609-12-01-02", "LX0609-02-01-04"),
        )


def test_fast5_has_no_output_file_or_persistence_path():
    source = Path(fast5.__file__).read_text(encoding="utf-8").lower()
    assert "open(" not in source
    assert ".write(" not in source
    assert "from app.routers" not in source
    assert "customer_result" not in source
