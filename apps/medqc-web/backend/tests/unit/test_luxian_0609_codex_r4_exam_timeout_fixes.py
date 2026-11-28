"""Codex Round-4 Finding #3 回归测试：LX0609-06-01-02 抽取失败分支保留已确诊缺陷并标明失败检查。

覆盖全部离线反例、负面 fail-closed 对照与展示契约校验：
1. 核心反例（无锚点冲突的正常多事件路径，正反序）：
   - 检查 1（48h 窗内 0 病程 -> 确定性 non_compliant）+ 检查 2（窗内有病程 -> 本地超时）
   -> 规则级 non_compliant，保留检查 1 缺陷，且 event_results 与 findings 显式标明检查 2 语义核对失败；
   - 仅检查 2 送入 LLM（检查 1 标记不进入模型提示词）。
2. 模型输出非法（model_invalid_output）、预算受限（budget_exceeded）与无客户端（llm_client=None）变体：
   - 均保留已确诊缺陷并准确标注失败检查及受控失败类别。
3. 三事件混合（Path B：确定性 non_compliant + 锚点时间冲突 data_gap + 语义核对超时）：
   - 规则级 non_compliant，三条事件状态分别保留 non_compliant / data_gap / technical_error，
     且 findings 明确区分“未记录检查原因”“资料待核实”“语义核对失败”。
4. Fail-closed 负面对照（无确定性 non_compliant 时绝不降级）：
   - 单次语义 CT 超时 -> technical_error（model_transport_error）
   - 入院 24h 豁免 CT + 语义 CT 超时 -> technical_error（model_transport_error）
   - 锚点冲突 CT + 语义 CT 超时 -> technical_error（model_transport_error）
   - 病程来源截断（course_projection_truncated）+ 0 病程 CT + 语义 CT -> data_gap（不得误判 non_compliant）
   - 病程时间缺失（course_time_incomplete）+ 0 病程 CT + 语义 CT 超时 -> technical_error（不得误判 non_compliant）
5. 正常成功对照：
   - 检查 1（0 病程 non_compliant）+ 检查 2（语义核对成功 compliant）-> non_compliant，无失败标记。
6. 客户展示事实严格校验与渲染合同：
   - safe_exam_lab_customer_display_facts 接受合法的 non_compliant + technical_error 组合；
   - 拒绝无 non_compliant 时的 technical_error、非法 verification_failure_reason、非 technical_error 携带失败原因、
     以及其他规则使用 technical_error 事件状态。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping, Sequence

import pytest

from app.services.llm_token_budget import BudgetError, BudgetVerdict
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.customer_renderer import (
    customer_finding_from_controlled_facts,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.exam_lab_fact_extraction import SCHEMA_VERSION
from app.services.luxian_0609.exam_lab_result_mapping import (
    safe_exam_lab_customer_display_facts,
)
from app.services.luxian_0609.native_exam_lab_execution import (
    execute_luxian_0609_native_exam_lab_rules,
)


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


class _ScriptedOrFailingExamLabClient:
    """支持按序返回 JSON、原始文本或抛出本地超时/预算异常的离线客户端。"""

    def __init__(self, responses: Sequence[Any]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("unexpected extra LLM call")
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        content = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": content},
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144},
            "_api_time": 0.02,
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


def _two_exam_normal_rows(*, zero_note_first: bool = True) -> dict[str, list[dict[str, Any]]]:
    """构造无锚点冲突的两事件 CT 病例：一个 48h 窗内 0 病程，另一个 48h 窗内有病程需语义核对。"""

    if zero_note_first:
        zero_order_time, zero_report_time = "2026-08-05 10:00:00", "2026-08-05 14:00:00"
        sem_order_time, sem_report_time = "2026-08-09 09:30:00", "2026-08-09 13:00:00"
        sem_course_time = "2026-08-08 15:00:00"
    else:
        sem_order_time, sem_report_time = "2026-08-05 09:30:00", "2026-08-05 13:00:00"
        sem_course_time = "2026-08-04 15:00:00"
        zero_order_time, zero_report_time = "2026-08-09 10:00:00", "2026-08-09 14:00:00"

    return {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "inpat_nondrug_order.exam_lab_order": [
            {
                "document_id": "ORD-DOC-ZERO",
                "order_id": "ORD-ZERO",
                "order_name": "胸部螺旋CT平扫",
                "prescribed_datetime": zero_order_time,
                "order_status": "已执行",
            },
            {
                "document_id": "ORD-DOC-SEM",
                "order_id": "ORD-SEM",
                "order_name": "腹部螺旋CT增强扫描",
                "prescribed_datetime": sem_order_time,
                "order_status": "已执行",
            },
        ],
        "exam_master": [
            {
                "document_id": "EX-M-ZERO",
                "exam_id": "E-ZERO",
                "order_id": "ORD-ZERO",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": zero_report_time,
                "description": "ZERO_NOTE_ONLY_MARKER 双肺纹理增粗。",
            },
            {
                "document_id": "EX-M-SEM",
                "exam_id": "E-SEM",
                "order_id": "ORD-SEM",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT增强扫描",
                "report_time": sem_report_time,
                "description": "肝胆胰脾未见明显占位。",
            },
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R-ZERO",
                "exam_id": "E-ZERO",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": zero_report_time,
                "description": "ZERO_NOTE_ONLY_MARKER 双肺纹理增粗。",
            },
            {
                "document_id": "EX-R-SEM",
                "exam_id": "E-SEM",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT增强扫描",
                "report_time": sem_report_time,
                "description": "肝胆胰脾未见明显占位。",
            },
        ],
        "daily_course_record": [
            {
                "document_id": "C-SEM",
                "record_time": sem_course_time,
                "record_content": "患者右上腹隐痛，拟完善腹部螺旋CT增强扫描明确肝胆胰脾情况。",
            }
        ],
    }


# ---------------------------------------------------------------------------
# 1. Core Codex Counterexample: Normal path (NO anchor conflict) + Local Timeout
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("zero_note_first", [True, False])
async def test_codex_r4_core_counterexample_timeout_preserves_confirmed_defect_and_names_failed_exam(
    zero_note_first: bool,
) -> None:
    """Codex R4 核心反例：无锚点冲突，检查 1 缺检查前病程 + 检查 2 注入本地超时 -> non_compliant 并标出失败检查。"""

    rows_by_source = _two_exam_normal_rows(zero_note_first=zero_note_first)
    client = _ScriptedOrFailingExamLabClient([asyncio.TimeoutError("local model timeout")])

    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    # 仅需语义核对的检查 2 调用模型，确定性 0 病程的检查 1 不送入模型。
    assert execution.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "ZERO_NOTE_ONLY_MARKER" not in client.prompts[0]

    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"

    display_facts = final["customer_display_facts"]
    assert safe_exam_lab_customer_display_facts(
        rule_id="LX0609-06-01-02", raw=display_facts
    ) is not None
    assert display_facts["event_count"] == 2

    by_name = {item["exam_name"]: item for item in display_facts["event_results"]}
    assert by_name["胸部螺旋CT平扫"]["event_status"] == "non_compliant"
    assert by_name["胸部螺旋CT平扫"]["response_record_count"] == 0
    assert by_name["腹部螺旋CT增强扫描"]["event_status"] == "technical_error"
    assert (
        by_name["腹部螺旋CT增强扫描"]["verification_failure_reason"]
        == "model_transport_error"
    )
    assert by_name["腹部螺旋CT增强扫描"]["response_record_count"] == 1

    findings = final["findings"]
    assert "共核对2次CT/MRI检查（其中1次未见检查前原因、1次语义核对失败）" in findings
    assert "胸部螺旋CT平扫" in findings
    assert "无病程记录，未记录检查原因" in findings
    assert "腹部螺旋CT增强扫描" in findings
    assert "本次检查语义核对失败（模型调用超时或连接异常），暂未完成检查原因核对" in findings


# ---------------------------------------------------------------------------
# 2. Invalid Output, Budget Exhaustion, and llm_client=None Variants
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_codex_r4_invalid_output_preserves_confirmed_defect_and_labels_failed_exam() -> None:
    """检查 2 返回非法 JSON/格式（首答+重试均失败）-> 保留检查 1 缺陷并标出检查 2 输出异常。"""

    rows_by_source = _two_exam_normal_rows(zero_note_first=True)
    client = _ScriptedOrFailingExamLabClient(["not-valid-json", "still-not-json"])

    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    assert execution.llm_call_count == 2
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    by_name = {
        item["exam_name"]: item
        for item in final["customer_display_facts"]["event_results"]
    }
    assert by_name["胸部螺旋CT平扫"]["event_status"] == "non_compliant"
    assert by_name["腹部螺旋CT增强扫描"]["event_status"] == "technical_error"
    assert (
        by_name["腹部螺旋CT增强扫描"]["verification_failure_reason"]
        == "model_invalid_output"
    )
    assert "腹部螺旋CT增强扫描" in final["findings"]
    assert "本次检查语义核对失败（模型返回结果异常），暂未完成检查原因核对" in final["findings"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_codex_r4_budget_exhaustion_preserves_confirmed_defect_and_labels_failed_exam() -> None:
    """检查 2 触发预算超限 -> 保留检查 1 缺陷并标出检查 2 预算受限。"""

    rows_by_source = _two_exam_normal_rows(zero_note_first=True)
    client = _ScriptedOrFailingExamLabClient(
        [
            BudgetError(
                BudgetVerdict(
                    status="BUDGET_EXHAUSTED",
                    reason="synthetic budget exhaustion",
                    profile="local",
                    model="local-test",
                )
            )
        ]
    )

    _, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    by_name = {
        item["exam_name"]: item
        for item in final["customer_display_facts"]["event_results"]
    }
    assert by_name["胸部螺旋CT平扫"]["event_status"] == "non_compliant"
    assert by_name["腹部螺旋CT增强扫描"]["event_status"] == "technical_error"
    assert (
        by_name["腹部螺旋CT增强扫描"]["verification_failure_reason"]
        == "budget_exceeded"
    )
    assert "本次检查语义核对失败（核对预算受限），暂未完成检查原因核对" in final["findings"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_codex_r4_llm_client_none_preserves_confirmed_defect_and_labels_failed_exam() -> None:
    """llm_client=None 时行为与抽取失败分支一致：保留检查 1 缺陷并标出检查 2 服务不可用。"""

    rows_by_source = _two_exam_normal_rows(zero_note_first=True)

    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=None,
    )

    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    by_name = {
        item["exam_name"]: item
        for item in final["customer_display_facts"]["event_results"]
    }
    assert by_name["胸部螺旋CT平扫"]["event_status"] == "non_compliant"
    assert by_name["腹部螺旋CT增强扫描"]["event_status"] == "technical_error"
    assert (
        by_name["腹部螺旋CT增强扫描"]["verification_failure_reason"]
        == "model_unavailable"
    )
    assert "本次检查语义核对失败（语义核对服务不可用），暂未完成检查原因核对" in final["findings"]


# ---------------------------------------------------------------------------
# 3. 3-Exam Mixed Variant (Path B: defect + anchor conflict + semantic timeout)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_codex_r4_three_exam_mixed_defect_conflict_and_timeout() -> None:
    """三事件混合：检查 1 缺检查前病程 + 检查 2 锚点时间冲突 + 检查 3 语义核对超时 -> 三种状态均完整保留。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "inpat_nondrug_order.exam_lab_order": [
            {
                "document_id": "ORD-DOC-1",
                "order_id": "ORD-1",
                "order_name": "颅脑螺旋CT平扫",
                "prescribed_datetime": "2026-08-05 10:00:00",
                "order_status": "已执行",
            },
            {
                "document_id": "ORD-DOC-3",
                "order_id": "ORD-3",
                "order_name": "腹部螺旋CT增强扫描",
                "prescribed_datetime": "2026-08-09 09:30:00",
                "order_status": "已执行",
            },
        ],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "order_id": "ORD-1",
                "exam_type": "CT",
                "exam_name": "颅脑螺旋CT平扫",
                "report_time": "2026-08-05 14:00:00",
                "description": "未见明显急性出血。",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-06 12:00:00",
                "description": "CONFLICT_EVENT2 双肺渗出影。",
            },
            {
                "document_id": "EX-M3",
                "exam_id": "E3",
                "order_id": "ORD-3",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT增强扫描",
                "report_time": "2026-08-09 13:00:00",
                "description": "肝胆胰脾未见异常。",
            },
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-07 12:00:00",
                "description": "CONFLICT_EVENT2 双肺渗出影。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C-3",
                "record_time": "2026-08-08 15:00:00",
                "record_content": "患者腹痛，拟完善腹部增强CT明确腹部情况。",
            }
        ],
    }
    client = _ScriptedOrFailingExamLabClient([TimeoutError("local timeout")])

    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    assert execution.llm_call_count == 1
    assert all("CONFLICT_EVENT2" not in prompt for prompt in client.prompts)
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"

    by_name = {
        item["exam_name"]: item
        for item in final["customer_display_facts"]["event_results"]
    }
    assert by_name["颅脑螺旋CT平扫"]["event_status"] == "non_compliant"
    assert by_name["CT 胸部螺旋CT平扫"]["event_status"] == "data_gap"
    assert by_name["腹部螺旋CT增强扫描"]["event_status"] == "technical_error"
    assert (
        by_name["腹部螺旋CT增强扫描"]["verification_failure_reason"]
        == "model_transport_error"
    )

    findings = final["findings"]
    assert "共核对3次CT/MRI检查（其中1次未见检查前原因、1次语义核对失败）" in findings
    assert "颅脑螺旋CT平扫" in findings
    assert "无病程记录，未记录检查原因" in findings
    assert "资料待核实，暂无法确认检查前是否记录检查原因" in findings
    assert "腹部螺旋CT增强扫描" in findings
    assert "本次检查语义核对失败（模型调用超时或连接异常），暂未完成检查原因核对" in findings


# ---------------------------------------------------------------------------
# 4. Fail-Closed Negative Controls
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fail_closed_single_semantic_ct_timeout_stays_technical_error() -> None:
    """负面对照 1：单一需语义核对的 CT 超时 -> 规则级 technical_error（model_transport_error）。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT平扫",
                "report_time": "2026-08-05 12:00:00",
                "description": "肝胆未见异常。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-04 10:00:00",
                "record_content": "患者腹痛，拟完善腹部CT。",
            }
        ],
    }
    client = _ScriptedOrFailingExamLabClient([asyncio.TimeoutError("local timeout")])

    _, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    assert reduced.final_state.value == "technical_error"
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_timeout"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fail_closed_24h_exempt_plus_semantic_ct_timeout_stays_technical_error() -> None:
    """负面对照 2：检查 1 为入院 24h 豁免 + 检查 2 语义核对超时 -> technical_error，不得降级。"""

    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "急诊胸部CT平扫",
                "report_time": "2026-08-01 11:00:00",
                "description": "双肺渗出。",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT增强扫描",
                "report_time": "2026-08-06 12:00:00",
                "description": "肝胆未见异常。",
            },
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-05 10:00:00",
                "record_content": "拟完善腹部CT了解腹腔情况。",
            }
        ],
    }
    client = _ScriptedOrFailingExamLabClient([asyncio.TimeoutError("local timeout")])

    _, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    assert reduced.final_state.value == "technical_error"
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_timeout"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fail_closed_anchor_conflict_plus_semantic_ct_timeout_stays_technical_error() -> None:
    """负面对照 3：检查 1 为锚点冲突 + 检查 2 语义核对超时 -> technical_error，不得降级为 data_gap。"""

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
                "description": "双肺渗出。",
            },
            {
                "document_id": "EX-M2",
                "exam_id": "E2",
                "exam_type": "CT",
                "exam_name": "腹部螺旋CT增强扫描",
                "report_time": "2026-08-06 12:00:00",
                "description": "肝胆未见异常。",
            },
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "report_time": "2026-08-02 12:00:00",
                "description": "双肺渗出。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C-1",
                "record_time": "2026-08-05 10:00:00",
                "record_content": "拟完善腹部CT了解腹腔情况。",
            }
        ],
    }
    client = _ScriptedOrFailingExamLabClient([asyncio.TimeoutError("local timeout")])

    _, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    assert reduced.final_state.value == "technical_error"
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_timeout"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fail_closed_truncated_course_source_never_preserves_zero_note_defect() -> None:
    """负面对照 4：病程来源截断时，0 窗内病程不能视作已确诊缺陷，必须 fail-closed 返回 data_gap。"""

    rows_by_source = _two_exam_normal_rows(zero_note_first=True)
    client = _ScriptedOrFailingExamLabClient([asyncio.TimeoutError("should not call")])

    execution, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        truncated_sources=("daily_course_record",),
        llm_client=client,
    )

    assert execution.llm_call_count == 0
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fail_closed_incomplete_course_time_never_preserves_zero_note_defect_on_timeout() -> None:
    """负面对照 5：病程存在缺失时间（course_time_incomplete）时，超时不得将 0 病程检查误判为已确诊 non_compliant。"""

    rows_by_source = _two_exam_normal_rows(zero_note_first=True)
    rows_by_source["daily_course_record"].append(
        {
            "document_id": "C-NO-TIME",
            "record_content": "患者拟行胸部CT检查明确肺部情况，时间字段缺失。",
        }
    )
    client = _ScriptedOrFailingExamLabClient([asyncio.TimeoutError("local timeout")])

    _, reduced, final = await _run_06_01_02(
        rows_by_source=rows_by_source,
        llm_client=client,
    )

    assert reduced.final_state.value == "technical_error"
    assert final["status"] == "technical_error"
    assert final["reason_code"] == "model_timeout"


# ---------------------------------------------------------------------------
# 5. Normal Success Control
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_normal_success_control_zero_note_defect_plus_compliant_semantic_ct() -> None:
    """正向对照：检查 1 缺检查前病程 + 检查 2 语义核对成功合规 -> non_compliant 且无任何失败标记。"""

    rows_by_source = _two_exam_normal_rows(zero_note_first=True)
    client = _ScriptedOrFailingExamLabClient(
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
                        "quote": "拟完善腹部螺旋CT增强扫描明确肝胆胰脾情况",
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
    assert reduced.final_state.value == "non_compliant"
    assert final["status"] == "non_compliant"
    by_name = {
        item["exam_name"]: item
        for item in final["customer_display_facts"]["event_results"]
    }
    assert by_name["胸部螺旋CT平扫"]["event_status"] == "non_compliant"
    assert by_name["腹部螺旋CT增强扫描"]["event_status"] == "compliant"
    assert "verification_failure_reason" not in by_name["腹部螺旋CT增强扫描"]
    assert "语义核对失败" not in final["findings"]
    assert "共核对2次CT/MRI检查（其中1次未见检查前原因）" in final["findings"]


# ---------------------------------------------------------------------------
# 6. Display-Facts Strict Contract & Renderer Validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_display_facts_contract_and_renderer_for_failed_semantic_exam() -> None:
    """校验 safe_exam_lab_customer_display_facts 对 06-01-02 失败事件的严格白名单与拒绝边界。"""

    valid_facts = {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "reason_before_order",
        "event_phase": "order",
        "checked_sources": ["exam_lab_order", "course_record"],
        "applicable": True,
        "requirement_met": False,
        "positive_state": "not_relevant",
        "reviewed_record_scope": "检查前48小时内病程记录",
        "response_record_count": 0,
        "event_count": 2,
        "event_position": 1,
        "exam_name": "胸部螺旋CT平扫",
        "order_time": "2026-08-05 10:00:00",
        "window_start_time": "2026-08-03 10:00:00",
        "window_end_time": "2026-08-05 14:00:00",
        "event_results": [
            {
                "event_position": 1,
                "event_status": "non_compliant",
                "exam_name": "胸部螺旋CT平扫",
                "order_time": "2026-08-05 10:00:00",
                "window_start_time": "2026-08-03 10:00:00",
                "window_end_time": "2026-08-05 14:00:00",
                "response_record_count": 0,
                "applicable": True,
                "requirement_met": False,
            },
            {
                "event_position": 2,
                "event_status": "technical_error",
                "verification_failure_reason": "model_transport_error",
                "exam_name": "腹部螺旋CT增强扫描",
                "order_time": "2026-08-09 09:30:00",
                "window_start_time": "2026-08-07 09:30:00",
                "window_end_time": "2026-08-09 13:00:00",
                "response_record_count": 1,
            },
        ],
    }

    safe = safe_exam_lab_customer_display_facts(
        rule_id="LX0609-06-01-02", raw=valid_facts
    )
    assert safe is not None
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-06-01-02", facts=safe
    )
    assert "胸部螺旋CT平扫（开立时间 2026-08-05 10:00:00）" in finding
    assert "腹部螺旋CT增强扫描（开立时间 2026-08-09 09:30:00）" in finding
    assert "本次检查语义核对失败（模型调用超时或连接异常），暂未完成检查原因核对" in finding

    # 拒绝：非法 verification_failure_reason
    bad_reason = {
        **valid_facts,
        "event_results": [
            valid_facts["event_results"][0],
            {**valid_facts["event_results"][1], "verification_failure_reason": "raw_traceback"},
        ],
    }
    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-02", raw=bad_reason) is None

    # 拒绝：非 technical_error 事件携带 verification_failure_reason
    bad_attached = {
        **valid_facts,
        "event_results": [
            {**valid_facts["event_results"][0], "verification_failure_reason": "model_transport_error"},
            valid_facts["event_results"][1],
        ],
    }
    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-02", raw=bad_attached) is None

    # 拒绝：没有 non_compliant 事件时出现 technical_error（防止纯技术错误混入合规/资料不足）
    no_defect = {
        **valid_facts,
        "event_results": [
            {**valid_facts["event_results"][0], "event_status": "compliant", "requirement_met": True},
            valid_facts["event_results"][1],
        ],
    }
    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-02", raw=no_defect) is None

    # 拒绝：其他规则（如 06-01-04）不允许 event_status == "technical_error"
    other_rule_facts = {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "result_recording_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "event_count": 2,
        "event_position": 1,
        "event_results": [
            {"event_position": 1, "event_status": "non_compliant"},
            {"event_position": 2, "event_status": "technical_error"},
        ],
    }
    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-04", raw=other_rule_facts) is None
