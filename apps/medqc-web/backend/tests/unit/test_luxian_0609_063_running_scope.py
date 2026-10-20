"""063 只消费已验证的运行场景，不从空终末表推断场景。"""

import pytest

from test_luxian_0609_native_extended_document_execution import (
    CustomerFinalState,
    _evaluate_selected,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("scene", "terminal_rows", "expected"), [
    ("running", {}, CustomerFinalState.NOT_APPLICABLE),
    (None, {}, CustomerFinalState.DATA_GAP),
    ("final", {}, CustomerFinalState.DATA_GAP),
    ("running", {"discharge_record": ({"document_id": "D"},)}, CustomerFinalState.DATA_GAP),
])
async def test_063_frozen_scene_and_terminal_scope(scene, terminal_rows, expected):
    horizon = {"horizon_date": "2026-10-20", "basis": "evaluation_as_of"}
    if scene:
        horizon["record_scene"] = scene
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-01-03",),
        {"evaluation_context.horizon": (horizon,), **terminal_rows},
    )
    assert reduced[0].final_state is expected
    assert result.llm_call_count == 0
    if expected is CustomerFinalState.NOT_APPLICABLE:
        refs = {ref for ref, _ in materials.document_rows(
            "evaluation_context.horizon", snapshot=snapshot,
        )}
        assert refs
        assert refs.issubset(set(reduced[0].fact_refs))


@pytest.mark.asyncio
async def test_063_explicit_death_retains_priority_over_frozen_running_scene():
    _, _, result, reduced = await _evaluate_selected(("LX0609-08-01-03",), {
        "evaluation_context.horizon": ({
            "horizon_date": "2026-10-20", "basis": "evaluation_as_of",
            "record_scene": "running",
        },),
        "death_record": ({"document_id": "death-document"},),
        "mr_diagnosis": ({"diagnosis_type": "死亡诊断", "diagnosis_name": "合成诊断", "diagnosis_order": 1},),
        "discharge_record_diagnosis": ({"diagnosis_type": "死亡诊断", "diagnosis_name": "合成诊断", "diagnosis_order": 1},),
    })
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert result.llm_call_count == 0
