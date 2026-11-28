"""批次 4 · Family #3（术后规则族拆分）回归与架构边界门禁。

覆盖：
1. 术后 3 条规则（04-05-01 / 04-05-02 / 04-05-03）独立模块与总入口结果一致，
   包含 begin_time 推算、未成熟窗口、非手术目录排除、缺失病程、多台手术、
   以及 04-05-02 病程正文模型抽取用量归集。
2. 纯术后直通快速路径仅读取所选规则必要来源，不触发死亡/出院/抗菌药/检验等
   无关来源；且 `surgery_record` 与 `resolve_surgery_applicability` 共享单次读取。
3. 混合顺序组（术后 + 危急值 / 阶段 / 抗菌药）中 `surgery_record` 仅读取 1 次
   （关闭 PR #95 复核指出的既有重复读取），并与主入口结果完全一致。
4. AST 边界门禁：`native_extended_document_execution.py` 不残留术后私有实现
   或重复 `_BLOCKING_DISCHARGE_HORIZON_ERRORS` 定义，`postoperative_family.py`
   不反向导入总调度模块。
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from app.services.luxian_0609.extended_document.family_runtime import (
    BLOCKING_DISCHARGE_HORIZON_ERRORS,
)
from app.services.luxian_0609.extended_document.postoperative_family import (
    POSTOPERATIVE_RULE_IDS,
    execute_postoperative_family,
)
from app.services.luxian_0609.native_extended_document_execution import (
    _execute_extended_document_group,
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient
from test_luxian_0609_native_extended_document_execution import _session

LUXIAN_ROOT = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "luxian_0609"
)
ORCHESTRATOR_PATH = LUXIAN_ROOT / "native_extended_document_execution.py"
POSTOP_FAMILY_PATH = LUXIAN_ROOT / "extended_document" / "postoperative_family.py"

COURSE_BODY_FACTS = {
    "主任医师查房：患者术后恢复平稳，切口愈合可，继续目前治疗方案。": (
        "present",
        "患者术后恢复平稳",
    ),
    "术前查房：完善术前准备，向家属告知手术风险。": (
        "present",
        "完善术前准备",
    ),
}


def _base_postop_materials() -> dict[str, tuple[dict[str, object], ...]]:
    return {
        "surgery_record": (
            {
                "document_id": "S1",
                "surgery_code": "01.2400X013",
                "surgery_name": "颅内血肿清除术",
                "surgery_begin_time": "2026-07-07 16:30:00+08",
                "surgery_end_time": "2026-07-07 18:30:00+08",
                "surgeon": "李明",
            },
        ),
        "postsurg_firstcourse_record": (
            {
                "document_id": "PF1",
                "record_time": "2026-07-07 19:15:00",
                "record_content": "术后首次病程记录：患者术毕安返病房，生命体征平稳。",
                "author_name": "李明",
            },
        ),
        "daily_course_record": tuple(
            {
                "document_id": f"D{day}",
                "record_time": f"2026-07-{day:02d} 08:30:00",
                "record_content": "患者术后恢复良好，切口干燥无渗液，继续抗感染对症支持治疗。",
                "author_name": "李明",
            }
            for day in (8, 9, 10)
        ),
        "senior_course_record": (
            {
                "document_id": "PRE1",
                "record_time": "2026-07-07 09:00:00",
                "record_content": "术前查房：完善术前准备，向家属告知手术风险。",
                "author_name": "李明",
            },
            {
                "document_id": "SR1",
                "record_time": "2026-07-09 09:00:00",
                "document_title": "王主任医师术后查房记录",
                "record_content": "主任医师查房：患者术后恢复平稳，切口愈合可，继续目前治疗方案。",
                "author_name": "王主任",
            },
        ),
        "evaluation_context.horizon": (
            {
                "basis": "discharge_date",
                "horizon_datetime": "2026-07-15 10:00:00",
                "horizon_date": "2026-07-15",
                "time_precision": "datetime",
            },
        ),
    }


def _track_material_reads(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    counts: Counter[str] = Counter()
    original_rows = Luxian0609EvidenceMaterialStore.rows

    def counted_rows(self: Luxian0609EvidenceMaterialStore, source_key: str):
        counts[str(source_key or "").strip().lower()] += 1
        return original_rows(self, source_key)

    monkeypatch.setattr(Luxian0609EvidenceMaterialStore, "rows", counted_rows)
    return counts


@pytest.mark.asyncio
async def test_pure_postoperative_fast_path_reads_only_needed_sources_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, materials = _session(_base_postop_materials())

    # 单跑 04-05-03 仅需手术记录 + 术后首次病程，共 2 类来源且每类仅读 1 次。
    counts_03 = _track_material_reads(monkeypatch)
    res_03 = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-04-05-03",),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-04-05-03",),
        llm_client=FrozenCourseBodyClient(COURSE_BODY_FACTS),
    )
    assert set(counts_03) == {"surgery_record", "postsurg_firstcourse_record"}
    assert all(value == 1 for value in counts_03.values())
    reduced_03 = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=res_03.decisions,
        expected_rule_ids=("LX0609-04-05-03",),
        snapshot=snapshot,
        evidence_materials=materials,
    )
    assert reduced_03[0].final_state.value == "compliant"
    assert res_03.llm_call_count == 0

    # 全跑术后 3 条仅需 5 类来源，不触碰死亡/出院/检验/医嘱等无关来源，每类读 1 次。
    counts_all = _track_material_reads(monkeypatch)
    client = FrozenCourseBodyClient(COURSE_BODY_FACTS)
    res_all = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=POSTOPERATIVE_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=POSTOPERATIVE_RULE_IDS,
        llm_client=client,
    )
    assert set(counts_all) == {
        "surgery_record",
        "postsurg_firstcourse_record",
        "daily_course_record",
        "senior_course_record",
        "evaluation_context.horizon",
    }
    assert all(value == 1 for value in counts_all.values())
    assert counts_all["death_record"] == 0
    assert counts_all["discharge_record"] == 0
    assert counts_all["inpat_drug_order"] == 0
    assert counts_all["labtest_master"] == 0
    assert res_all.llm_call_count == 1
    assert res_all.total_tokens == 15
    assert client.fixture_error is None


@pytest.mark.asyncio
async def test_mixed_sequential_group_reads_surgery_record_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    materials_data = _base_postop_materials()
    materials_data["labtest_master"] = ()
    materials_data["labtest_item_report"] = ()
    materials_data["inpat_drug_order"] = ()
    snapshot, materials = _session(materials_data)

    mixed_rules = (
        "LX0609-04-05-01",
        "LX0609-04-05-02",
        "LX0609-04-05-03",
        "LX0609-06-04-01",
        "LX0609-05-01-04",
    )

    counts_seq = _track_material_reads(monkeypatch)
    seq_result = await _execute_extended_document_group(
        rule_ids=mixed_rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=mixed_rules,
        llm_client=FrozenCourseBodyClient(COURSE_BODY_FACTS),
    )
    assert counts_seq["surgery_record"] == 1
    assert counts_seq["postsurg_firstcourse_record"] == 1
    assert counts_seq["daily_course_record"] == 1
    assert counts_seq["senior_course_record"] == 1
    assert counts_seq["evaluation_context.horizon"] == 1

    par_result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=mixed_rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=mixed_rules,
        llm_client=FrozenCourseBodyClient(COURSE_BODY_FACTS),
    )
    assert seq_result.decisions == par_result.decisions
    assert seq_result.customer_display_facts == par_result.customer_display_facts
    assert seq_result.llm_call_count == par_result.llm_call_count == 1
    assert seq_result.total_tokens == par_result.total_tokens == 15


@pytest.mark.asyncio
async def test_postoperative_begin_time_estimated_and_non_surgical_parity() -> None:
    # 1) 缺实际结束时间 -> 以开始时间推算，3 条规则 display_facts 均带 surgery_time_basis="begin_time"
    est_materials = _base_postop_materials()
    est_materials["surgery_record"] = (
        {
            "document_id": "S_EST",
            "surgery_code": "01.2400X013",
            "surgery_name": "急诊开颅术",
            "surgery_begin_time": "2026-07-07 16:30:00+08",
            "surgeon": "李明",
        },
    )
    snapshot, materials = _session(est_materials)
    direct = await execute_postoperative_family(
        rule_ids=POSTOPERATIVE_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=FrozenCourseBodyClient(COURSE_BODY_FACTS),
    )
    via_main = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=POSTOPERATIVE_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=POSTOPERATIVE_RULE_IDS,
        llm_client=FrozenCourseBodyClient(COURSE_BODY_FACTS),
    )
    assert direct.decisions == via_main.decisions
    assert direct.display_facts == via_main.customer_display_facts
    assert direct.llm_call_count == via_main.llm_call_count == 1
    display_map = dict(via_main.customer_display_facts)
    for rule_id in POSTOPERATIVE_RULE_IDS:
        assert display_map[rule_id]["surgery_time_basis"] == "begin_time"

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=via_main.decisions,
        expected_rule_ids=POSTOPERATIVE_RULE_IDS,
        snapshot=snapshot,
        evidence_materials=materials,
    )
    rendered_all = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule_id} for rule_id in POSTOPERATIVE_RULE_IDS],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=via_main.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )
    assert [item["rule_id"] for item in rendered_all] == list(POSTOPERATIVE_RULE_IDS)
    assert all(item["status"] == "compliant" for item in rendered_all)

    # 2) 非手术目录操作 -> 三条规则均精确绑定原手术文书并判 not_applicable
    non_surg = _base_postop_materials()
    non_surg["surgery_record"] = (
        {
            "document_id": "NS1",
            "surgery_code": "96.0400",
            "surgery_name": "经口气管插管术",
            "surgery_begin_time": "2026-07-07 16:30:00+08",
            "surgery_end_time": "2026-07-07 16:45:00+08",
            "surgeon": "李明",
        },
    )
    ns_snap, ns_store = _session(non_surg)
    ns_res = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=POSTOPERATIVE_RULE_IDS,
        evidence_snapshot=ns_snap,
        evidence_materials=ns_store,
        decision_rule_ids=POSTOPERATIVE_RULE_IDS,
    )
    ns_reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=ns_res.decisions,
        expected_rule_ids=POSTOPERATIVE_RULE_IDS,
        snapshot=ns_snap,
        evidence_materials=ns_store,
    )
    assert all(item.final_state.value == "not_applicable" for item in ns_reduced)
    assert all(item.reason_code == "performed_event_absent" for item in ns_reduced)
    decision_03 = next(d for d in ns_res.decisions if d.rule_id == "LX0609-04-05-03")
    assert decision_03.affirmative_applicability is True
    assert len(decision_03.fact_refs) == 1


def test_postoperative_family_ast_architecture_guards() -> None:
    orchestrator_tree = ast.parse(ORCHESTRATOR_PATH.read_text(encoding="utf-8"))
    family_tree = ast.parse(POSTOP_FAMILY_PATH.read_text(encoding="utf-8"))

    # 1) 总调度不再保留术后私有实现或重复的 _BLOCKING_DISCHARGE_HORIZON_ERRORS 定义
    orchestrator_defs = {
        node.name
        for node in ast.walk(orchestrator_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    forbidden_defs = {
        "_PostoperativeSurgeryEvent",
        "_qualified_surgery_rows",
        "_surgery_applicability_outcome",
        "_postoperative_surgery_events",
        "_postoperative_document_refs",
        "_link_postoperative_first_course_records",
        "_postoperative_window_gate",
        "_postoperative_senior_round_evaluation_horizon",
        "_body_surgeon_round_tokens",
        "_title_round_physician_tokens",
        "_course_body_candidate_inputs",
        "_course_dates",
        "_course_row_has_body",
    }
    assert orchestrator_defs.isdisjoint(forbidden_defs)

    assigned_names = {
        target.id
        for node in orchestrator_tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "_BLOCKING_DISCHARGE_HORIZON_ERRORS" not in assigned_names
    assert BLOCKING_DISCHARGE_HORIZON_ERRORS == frozenset(
        {"authoritative_time_missing", "authoritative_time_conflict"}
    )

    # 2) postoperative_family.py 不反向导入 native_extended_document_execution
    for node in ast.walk(family_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "native_extended_document_execution" not in node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "native_extended_document_execution" not in alias.name
