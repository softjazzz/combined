"""Codex Round-3 回归测试：06-01-02 多事件锚点冲突隔离 & 运行时合同 max_llm_calls_per_rule 对齐。

覆盖两项根因修复与全部离线反例：
1. LX0609-06-01-02 多事件锚点冲突隔离：
   - 单一冲突早期 CT -> data_gap（保留 Codex R1）
   - 冲突 CT + 明确违规 CT（48h 窗内 0 份病程，含空病程/仅窗外病程/正反序/缺锚点时间）-> non_compliant（0 LLM）
   - 冲突 CT + 含窗内病程的合规 CT -> data_gap（未决冲突不得被误判合规；冲突事件不进 LLM）
   - 冲突 CT + 含无关窗内病程的违规 CT -> non_compliant（冲突事件不进 LLM）
   - 冲突 CT + 入院 24h 豁免 CT -> data_gap（0 LLM）
   - 病程来源截断/不完整时不得误判 non_compliant -> data_gap
   - 无冲突入院 24h 内 CT -> not_applicable（admission_window_exempt 保留）
2. 运行时合同三方对齐：
   - rule_contracts.py / luxian_0609_rule_contracts_v1.json / luxian_0609_acceptance_matrix.json
     及 runtime manifest 对 LX0609-06-02-02、LX0609-06-02-03、LX0609-01-01-02 一致为 2，
     且编译器拒绝退回为 1。
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.customer_rule_package import RULE_FAMILY_DEFINITIONS
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.exam_lab_fact_extraction import (
    SCHEMA_VERSION,
    build_exam_lab_text_projection,
    events_for_family,
    exam_reason_anchor_has_conflict,
)
from app.services.luxian_0609.native_exam_lab_execution import (
    execute_luxian_0609_native_exam_lab_rules,
)
from app.services.luxian_0609.native_package import (
    load_luxian_0609_dependency_inventory,
)
from app.services.luxian_0609.rule_contracts import (
    compile_luxian_0609_rule_contracts,
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from scripts.build_luxian_0609_runtime_manifest import build_runtime_manifest


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_RULE_CONTRACTS_JSON = _BACKEND_ROOT / "app" / "data" / "luxian_0609_rule_contracts_v1.json"
_ACCEPTANCE_MATRIX_JSON = _BACKEND_ROOT / "app" / "data" / "luxian_0609_acceptance_matrix.json"


def _horizon_snapshot(
    *,
    admission_datetime: str = "2026-08-01 08:00:00",
    discharge_datetime: str = "2026-08-15 10:00:00",
) -> dict[str, Any]:
    return {
        "institute_id": "INST",
        "patient_id": "PAT",
        "visit_id": "VIS",
        "record_scene": "final",
        "evaluation_basis": "discharge_datetime",
        "resolution_status": "resolved",
        "evaluation_horizon": discharge_datetime[:10],
        "admission_datetime": admission_datetime,
        "discharge_datetime": discharge_datetime,
        "discharge_time_precision": "datetime",
    }


def _build_session(
    *,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    truncated_sources: Sequence[str] = (),
    selected_rule_ids: Sequence[str] = ("LX0609-06-01-02",),
):
    truncated = set(truncated_sources)

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows_by_source.get(key, ()),
            truncated=key in truncated,
            limit_rows=5000,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=tuple(selected_rule_ids),
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        created_at="2026-08-20T10:00:00+08:00",
        row_reader=reader,
        evaluation_horizon_snapshot=_horizon_snapshot(),
    )


class _RecordingSequentialExamLabClient:
    """记录每次提示词并按序返回固定 JSON 的离线客户端。"""

    def __init__(self, payloads: Sequence[Mapping[str, Any]]) -> None:
        self._payloads = list(payloads)
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        if not self._payloads:
            raise AssertionError("unexpected extra LLM call")
        payload = self._payloads.pop(0)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "_api_time": 0.01,
        }


async def _run_06_01_02(
    *,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    llm_client: Any = None,
    truncated_sources: Sequence[str] = (),
) -> tuple[Any, Any, dict[str, Any]]:
    session = _build_session(
        rows_by_source=rows_by_source,
        truncated_sources=truncated_sources,
    )
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-06-01-02",),
        decision_rule_ids=("LX0609-06-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-06-01-02", "custom_prompt": "stub"}],
        evidence_payload={},
        llm_client=llm_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-06-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(
            "LX0609-06-01-02"
        ),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    return execution, reduced, final


# ---------------------------------------------------------------------------
# Finding #4: LX0609-06-01-02 Multi-Event Conflict Isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scenario_1_single_conflicted_early_ct_stays_data_gap_zero_llm() -> None:
    """场景 1（Codex R1 保留）：单一入院 24h 内但锚点时间冲突的 CT -> data_gap，0 次 LLM。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "exam_time": "2026-08-01 10:00:00",
                "report_time": "2026-08-01 12:00:00",
                "description": "双肺渗出影。",
            }
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-02 12:00:00",
                "description": "双肺渗出影。",
            }
        ],
        "daily_course_record": [],
    }
    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=None,
    )
    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "association_failed"


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("conflict_first", [False, True])
@pytest.mark.parametrize("with_out_of_window_note", [False, True])
async def test_scenario_2_conflicted_ct_does_not_mask_confirmed_non_compliant_ct_zero_llm(
    conflict_first: bool,
    with_out_of_window_note: bool,
) -> None:
    """场景 2（Codex R3 反例修复）：冲突 CT + 48h 窗内 0 病程的明确违规 CT -> non_compliant（0 LLM）。

    无论两事件在投影中的顺序是 [non_compliant, data_gap] 还是 [data_gap, non_compliant]、
    也不论病历是否存在 48h 窗口之外的病程记录，明确违规的 CT 都不得被冲突 CT 降级遮蔽；
    event_results 中同时保留冲突事件的 data_gap 状态。
    """

    clean_master = {
        "document_id": "EX-M-CLEAN",
        "exam_id": "E-CLEAN",
        "order_id": "ORD-CLEAN",
        "exam_type": "CT",
        "exam_name": "颅脑螺旋CT平扫",
        "report_time": "2026-08-05 14:00:00",
        "description": "未见明显急性出血。",
    }
    clean_report = {
        "document_id": "EX-R-CLEAN",
        "exam_id": "E-CLEAN",
        "exam_type": "CT",
        "exam_name": "颅脑螺旋CT平扫",
        "report_time": "2026-08-05 14:00:00",
        "description": "未见明显急性出血。",
    }
    conflict_master: dict[str, Any] = {
        "document_id": "EX-M-CONFLICT",
        "exam_id": "E-CONFLICT",
        "exam_type": "CT",
        "exam_name": "胸部螺旋CT平扫",
        "report_time": "2026-08-01 12:00:00" if conflict_first else "2026-08-06 12:00:00",
        "description": "双肺渗出影。",
    }
    if conflict_first:
        # 冲突事件带有更早的 exam_time（无 order_time、report_time 冲突）-> 排序在位置 1
        conflict_master["exam_time"] = "2026-08-01 10:00:00"
    conflict_report = {
        "document_id": "EX-R-CONFLICT",
        "exam_id": "E-CONFLICT",
        "exam_type": "CT",
        "exam_name": "胸部螺旋CT平扫",
        "report_time": "2026-08-02 12:00:00" if conflict_first else "2026-08-07 12:00:00",
        "description": "双肺渗出影。",
    }
    exam_masters = (
        [conflict_master, clean_master] if conflict_first else [clean_master, conflict_master]
    )
    exam_reports = (
        [conflict_report, clean_report] if conflict_first else [clean_report, conflict_report]
    )
    daily_course = (
        [
            {
                "document_id": "C-POST",
                "record_time": "2026-08-10 09:00:00",
                "record_content": "患者病情稳定，继续观察。",
            }
        ]
        if with_out_of_window_note
        else []
    )
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "inpat_nondrug_order.exam_lab_order": [
            {
                "document_id": "ORD-DOC-1",
                "order_id": "ORD-CLEAN",
                "order_name": "颅脑螺旋CT平扫",
                "prescribed_datetime": "2026-08-05 10:00:00",
                "order_status": "已执行",
            }
        ],
        "exam_master": exam_masters,
        "exam_item_report": exam_reports,
        "daily_course_record": daily_course,
    }

    projection = build_exam_lab_text_projection(rows_by_source=rows_by_source)
    events = events_for_family(projection, "exam")
    assert len(events) == 2
    assert sum(1 for ev in events if exam_reason_anchor_has_conflict(ev)) == 1

    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=None,
    )
    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"
    display_facts = final["customer_display_facts"]
    assert display_facts["event_count"] == 2
    statuses = [item["event_status"] for item in display_facts["event_results"]]
    assert statuses == (
        ["data_gap", "non_compliant"] if conflict_first else ["non_compliant", "data_gap"]
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scenario_2d_missing_anchor_ct_does_not_mask_confirmed_non_compliant_ct() -> None:
    """缺锚点时间的 CT 同样不得遮蔽另一条 0 窗内病程的明确 non_compliant CT（0 LLM）。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "颅脑CT平扫",
                "report_time": "2026-08-05 14:00:00",
                "description": "未见明显异常。",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "胸部CT平扫",
                "description": "双肺纹理增粗。",
            },
        ],
        "daily_course_record": [],
    }
    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=None,
    )
    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    assert [
        item["event_status"] for item in final["customer_display_facts"]["event_results"]
    ] == ["non_compliant", "data_gap"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scenario_3a_conflicted_ct_plus_compliant_ct_stays_data_gap_and_excludes_conflict_from_llm() -> None:
    """场景 3：冲突 CT + 合规 CT -> 规则级 data_gap（不得误判为 compliant），且冲突 CT 不进入 LLM 提示。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "exam_time": "2026-08-01 10:00:00",
                "report_time": "2026-08-01 12:00:00",
                "description": "CONFLICT_MARKER_ONLY_EVENT1 双肺渗出影。",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT平扫",
                "report_time": "2026-08-04 11:00:00",
                "description": "肝胆胰脾未见明显异常。",
            },
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-02 12:00:00",
                "description": "CONFLICT_MARKER_ONLY_EVENT1 双肺渗出影。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C1",
                "record_time": "2026-08-03 10:00:00",
                "record_content": "患者腹痛待查，拟完善腹部CT了解腹腔及肝胆情况。",
            }
        ],
    }
    client = _RecordingSequentialExamLabClient(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "facts": [
                    {
                        "rule_id": "LX0609-06-01-02",
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1],
                    }
                ],
            },
            {
                "schema_version": "lx0609-exam-reason-check-v1",
                "docs": [
                    {
                        "event_position": 1,
                        "course_doc_ref": "D06-01",
                        "quote_type": "reason_stated",
                        "quote": "拟完善腹部CT了解腹腔及肝胆情况",
                    }
                ],
            },
        ]
    )
    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )
    assert execution.llm_call_count == 2
    assert len(client.prompts) == 2
    # 冲突的 Event 1 绝不得送入 LLM 主抽取或专项核对
    assert all("CONFLICT_MARKER_ONLY_EVENT1" not in prompt for prompt in client.prompts)
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "association_failed"
    assert [
        item["event_status"] for item in final["customer_display_facts"]["event_results"]
    ] == ["data_gap", "compliant"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scenario_3b_conflicted_ct_plus_llm_non_compliant_ct_returns_non_compliant() -> None:
    """冲突 CT + 窗内仅有无关病程（经 LLM 确认未写原因）的 CT -> non_compliant。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-01 12:00:00",
                "description": "CONFLICT_MARKER_ONLY_EVENT1",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT平扫",
                "report_time": "2026-08-04 11:00:00",
                "description": "未见明显异常。",
            },
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-02 12:00:00",
                "description": "CONFLICT_MARKER_ONLY_EVENT1",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C1",
                "record_time": "2026-08-03 10:00:00",
                "record_content": "患者今日一般情况可，继续对症支持治疗。",
            }
        ],
    }
    client = _RecordingSequentialExamLabClient(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "facts": [
                    {
                        "rule_id": "LX0609-06-01-02",
                        "applicability": "applicable",
                        "semantic_state": "absent",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [],
                    }
                ],
            },
            {
                "schema_version": "lx0609-exam-reason-check-v1",
                "docs": [
                    {
                        "event_position": 1,
                        "course_doc_ref": "D06-01",
                        "quote_type": "none",
                        "quote": "",
                    }
                ],
            },
        ]
    )
    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )
    assert execution.llm_call_count == 2
    assert all("CONFLICT_MARKER_ONLY_EVENT1" not in prompt for prompt in client.prompts)
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"
    by_name = {
        item["exam_name"]: item["event_status"]
        for item in final["customer_display_facts"]["event_results"]
    }
    assert by_name == {
        "CT 腹部螺旋CT平扫": "non_compliant",
        "CT 胸部螺旋CT平扫": "data_gap",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scenario_3c_conflicted_ct_plus_24h_exempt_ct_stays_data_gap_zero_llm() -> None:
    """冲突 CT + 入院 24h 内豁免 CT -> data_gap（0 LLM），event_results 记录 data_gap + not_applicable。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-01 11:00:00",
                "description": "双肺渗出影。",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "颅脑螺旋CT平扫",
                "report_time": "2026-08-01 12:00:00",
                "description": "未见明显异常。",
            },
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-02 11:00:00",
                "description": "双肺渗出影。",
            }
        ],
        "daily_course_record": [],
    }
    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=None,
    )
    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "association_failed"
    by_name = {
        item["exam_name"]: item
        for item in final["customer_display_facts"]["event_results"]
    }
    assert by_name["CT 胸部螺旋CT平扫"]["event_status"] == "data_gap"
    assert by_name["CT 颅脑螺旋CT平扫"]["event_status"] == "not_applicable"
    assert by_name["CT 颅脑螺旋CT平扫"]["exempt_reason"] == "admission_window"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scenario_3d_truncated_course_source_never_marks_zero_note_ct_non_compliant() -> None:
    """病程来源被截断时，不可将 48h 窗内 0 病程的 CT 判为 non_compliant，必须降级 data_gap。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "颅脑螺旋CT平扫",
                "report_time": "2026-08-05 14:00:00",
                "description": "未见明显异常。",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-06 12:00:00",
                "description": "双肺渗出影。",
            },
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-07 12:00:00",
                "description": "双肺渗出影。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C-LATE",
                "record_time": "2026-08-10 09:00:00",
                "record_content": "患者病情稳定，继续观察。",
            }
        ],
    }
    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        truncated_sources=("daily_course_record",),
        llm_client=None,
    )
    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scenario_4_conflict_free_early_ct_exempts_cleanly_zero_llm() -> None:
    """场景 4：无冲突的入院 24h 内 CT -> not_applicable（admission_window_exempt），0 次 LLM。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "exam_time": "2026-08-01 10:00:00",
                "report_time": "2026-08-01 12:00:00",
                "description": "双肺渗出影。",
            }
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-01 12:00:00",
                "description": "双肺渗出影。",
            }
        ],
        "daily_course_record": [],
    }
    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=None,
    )
    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "not_applicable"
    assert final["status"] == "not_applicable"
    assert final["reason_code"] == "eligibility_not_met"


# ---------------------------------------------------------------------------
# Finding #5: Three-way parity for max_llm_calls_per_rule = 2
# ---------------------------------------------------------------------------


_RETRY_ALIGNED_RULE_IDS = (
    "LX0609-06-02-02",
    "LX0609-06-02-03",
    "LX0609-01-01-02",
)


@pytest.mark.unit
def test_three_way_parity_max_llm_calls_per_rule_for_retry_rules() -> None:
    """rule_contracts.py、luxian_0609_rule_contracts_v1.json 与 acceptance_matrix.json 三方严格一致为 2。"""

    compiled = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}
    raw_contracts_payload = json.loads(_RULE_CONTRACTS_JSON.read_text(encoding="utf-8"))
    raw_contracts = {item["rule_id"]: item for item in raw_contracts_payload["rules"]}
    matrix_payload = json.loads(_ACCEPTANCE_MATRIX_JSON.read_text(encoding="utf-8"))
    matrix_rules = {item["rule_id"]: item for item in matrix_payload["rules"]}

    for rule_id in _RETRY_ALIGNED_RULE_IDS:
        assert compiled[rule_id].decision_authority == "program_then_optional_llm"
        assert compiled[rule_id].max_llm_calls_per_rule == 2
        assert raw_contracts[rule_id]["max_llm_calls_per_rule"] == 2
        assert matrix_rules[rule_id]["max_llm_calls_per_rule"] == 2
        assert matrix_rules[rule_id]["semantic_contract"]["max_llm_calls_per_rule"] == 2

    # 运行时 manifest 也同步输出 2
    settings = SimpleNamespace(
        LUXIAN_0609_TRIGGER_GATE_ENABLED=True,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=True,
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=True,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=False,
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=False,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=True,
        LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LLM_MODEL="safe-model-name",
        LLM_ADJUDICATOR_MODEL="safe-adjudicator-name",
        LLM_API_KEY="must-not-leak",
        LLM_API_ENDPOINT="https://secret-endpoint.example/v1",
    )
    manifest = build_runtime_manifest(
        git_head="a" * 40,
        settings=settings,
        rule_catalog=load_luxian_0609_rules(),
        inventory=load_luxian_0609_dependency_inventory(),
        generated_at="2026-11-26T22:00:00Z",
    )
    by_rule = {item["rule_id"]: item for item in manifest["rules"]}
    for rule_id in _RETRY_ALIGNED_RULE_IDS:
        assert by_rule[rule_id]["max_llm_calls_per_rule"] == 2


@pytest.mark.unit
@pytest.mark.parametrize("rule_id", _RETRY_ALIGNED_RULE_IDS)
def test_rule_contract_compiler_rejects_stale_single_call_budget(rule_id: str) -> None:
    """防止合同退回：三项允许 1 次重试的规则若被改回 max_llm_calls_per_rule=1，编译期必须报错。"""

    payload = json.loads(_RULE_CONTRACTS_JSON.read_text(encoding="utf-8"))
    extension_path = (
        _BACKEND_ROOT
        / "app"
        / "data"
        / "luxian_0609_phase1_rule_contracts_extension_v1.json"
    )
    extension = json.loads(extension_path.read_text(encoding="utf-8"))
    drifted = deepcopy({**payload, "rules": [*payload["rules"], *extension]})
    for item in drifted["rules"]:
        if item["rule_id"] == rule_id:
            item["max_llm_calls_per_rule"] = 1
            break

    with pytest.raises(ValueError, match="invalid LX0609 LLM call budget"):
        compile_luxian_0609_rule_contracts(
            payload=drifted,
            rules=load_luxian_0609_rules(),
            family_definitions=RULE_FAMILY_DEFINITIONS,
        )
