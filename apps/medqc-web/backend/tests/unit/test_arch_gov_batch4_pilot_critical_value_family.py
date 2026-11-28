"""架构治理 Batch 4 Pilot #1（危急值规则族 06-04-01 / 06-04-02）拆分一致性与边界守卫测试。

核验三项拆分一致性与两项架构边界：
1. 同一组全合成材料下，独立规则族执行器 `execute_critical_value_family`、总入口
   `execute_luxian_0609_native_extended_document_rules` 与基线 938e33997 的
   判定（applicability / evidence_state / qc_direction / status）、原因码（reason_code）
   与证据引用（fact_refs / positive_document_refs / affirmative_applicability / display_facts）完全一致；
2. 混合规则顺序（如 06-04-02, 08-01-01, 06-04-01）下输出顺序与结果不变；
3. AST 边界守卫：`native_extended_document_execution.py` 不再残留危急值实现副本，
   且 `critical_value_family.py` / `family_runtime.py` 均不反向导入总调度模块。
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from app.services.luxian_0609.extended_document import critical_value_family as cvf
from app.services.luxian_0609.extended_document import family_runtime
from app.services.luxian_0609.extended_document_critical_value import (
    CRITICAL_VALUE_RULE_IDS,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import _session


BACKEND_ROOT = Path(__file__).resolve().parents[2]
LUXIAN_DIR = BACKEND_ROOT / "app" / "services" / "luxian_0609"
NED_PATH = LUXIAN_DIR / "native_extended_document_execution.py"
CVF_PATH = LUXIAN_DIR / "extended_document" / "critical_value_family.py"
RUNTIME_PATH = LUXIAN_DIR / "extended_document" / "family_runtime.py"

HORIZON_MATURE = (
    {"horizon_date": "2026-06-05", "horizon_datetime": "2026-06-05 18:00:00"},
)


def _lab(
    report_id: str,
    item_name: str,
    result: str,
    flag: str,
    report_time: str,
    doc_id: str | None = None,
) -> dict[str, Any]:
    return {
        "document_id": doc_id or f"lab-{report_id}",
        "report_id": report_id,
        "item_name": item_name,
        "result": result,
        "result_flag": flag,
        "report_time": report_time,
    }


def _master(report_id: str, report_time: str) -> dict[str, Any]:
    return {
        "document_id": f"master-{report_id}",
        "report_id": report_id,
        "report_time": report_time,
    }


def _crisis(
    report_id: str, record_time: str, content: str = "危急值已处置"
) -> dict[str, Any]:
    return {
        "document_id": f"crisis-{report_id}",
        "report_id": report_id,
        "record_time": record_time,
        "record_content": content,
    }


def _course(
    doc_id: str, record_time: str, title: str, content: str
) -> dict[str, Any]:
    return {
        "document_id": doc_id,
        "record_time": record_time,
        "document_title": title,
        "record_content": content,
    }


# 14 组基线（938e33997）合成场景 + 3 组显式 source unavailable 场景
SYNTHETIC_PARITY_CASES: list[tuple[str, dict[str, Any], set[str], dict[str, tuple[str, str, str, str, int]]]] = [
    (
        "01_timely_via_crisis_record",
        {
            "labtest_master": (_master("R1", "2026-06-01 08:00:00"),),
            "labtest_item_report": (_lab("R1", "血钾", "2.8", "PL", "2026-06-01 08:00:00"),),
            "crisis_value_record": (_crisis("R1", "2026-06-01 09:30:00"),),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("applicable", "sufficient", "satisfied", "requirement_within_threshold", 2),
            "LX0609-06-04-02": ("applicable", "sufficient", "satisfied", "requirement_satisfied", 2),
        },
    ),
    (
        "02_overdue_via_crisis_record",
        {
            "labtest_master": (_master("R2", "2026-06-01 08:00:00"),),
            "labtest_item_report": (_lab("R2", "血钾", "2.7", "PL", "2026-06-01 08:00:00"),),
            "crisis_value_record": (_crisis("R2", "2026-06-01 16:30:00"),),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("applicable", "sufficient", "defect", "threshold_exceeded", 2),
            "LX0609-06-04-02": ("applicable", "sufficient", "satisfied", "requirement_satisfied", 2),
        },
    ),
    (
        "03_timely_via_course_record_only",
        {
            "labtest_master": (_master("R3", "2026-06-01 08:00:00"),),
            "labtest_item_report": (_lab("R3", "血钾", "2.8", "PL", "2026-06-01 08:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (
                _course("C3", "2026-06-01 09:00:00", "日常病程记录", "检验报危急值血钾：2.8 mmol/L，立即予以10%氯化钾静脉补钾并复查电解质。"),
            ),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("applicable", "sufficient", "satisfied", "requirement_within_threshold", 2),
            "LX0609-06-04-02": ("applicable", "sufficient", "satisfied", "requirement_satisfied", 2),
        },
    ),
    (
        "04_negated_handling_in_course_unhandled",
        {
            "labtest_master": (_master("R4", "2026-06-01 08:00:00"),),
            "labtest_item_report": (_lab("R4", "血钾", "2.8", "PL", "2026-06-01 08:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (
                _course("C4", "2026-06-01 09:00:00", "日常病程记录", "血钾危急值 2.8，未予补钾。另因发热予以退热治疗。"),
            ),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("applicable", "sufficient", "defect", "threshold_exceeded", 1),
            "LX0609-06-04-02": ("applicable", "sufficient", "defect", "required_document_missing", 1),
        },
    ),
    (
        "05_planned_unexecuted_in_course_unhandled",
        {
            "labtest_master": (_master("R5", "2026-06-01 14:00:00"),),
            "labtest_item_report": (_lab("R5", "血钾", "6.7", "PH", "2026-06-01 14:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (
                _course("C5", "2026-06-01 14:30:00", "日常病程记录", "血钾 6.7，拟复查，尚未执行。"),
            ),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("applicable", "sufficient", "defect", "threshold_exceeded", 1),
            "LX0609-06-04-02": ("applicable", "sufficient", "defect", "required_document_missing", 1),
        },
    ),
    (
        "06_negated_then_executed_same_course",
        {
            "labtest_master": (_master("R6", "2026-06-01 15:00:00"),),
            "labtest_item_report": (_lab("R6", "血钾", "6.7", "PH", "2026-06-01 15:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (
                _course("C6", "2026-06-01 15:28:00", "日常病程记录", "血钾 6.7。初报时尚未处理。15:28 已针对本次完成心电图复查及病情评估。"),
            ),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("applicable", "sufficient", "satisfied", "requirement_within_threshold", 2),
            "LX0609-06-04-02": ("applicable", "sufficient", "satisfied", "requirement_satisfied", 2),
        },
    ),
    (
        "07_cross_report_isolation_two_events",
        {
            "labtest_master": (
                _master("R7A", "2026-06-01 08:00:00"),
                _master("R7B", "2026-06-01 12:00:00"),
            ),
            "labtest_item_report": (
                _lab("R7A", "血钾", "2.8", "PL", "2026-06-01 08:00:00", "lab-R7A"),
                _lab("R7B", "血钾", "6.7", "PH", "2026-06-01 12:00:00", "lab-R7B"),
            ),
            "crisis_value_record": (),
            "daily_course_record": (
                _course("C7", "2026-06-01 12:30:00", "日常病程记录", "08:00血钾2.8已予补钾治疗；另测血糖6.7 mmol/L。"),
            ),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("applicable", "sufficient", "defect", "threshold_exceeded", 3),
            "LX0609-06-04-02": ("applicable", "sufficient", "defect", "required_document_missing", 3),
        },
    ),
    (
        "08_window_not_mature_datetime",
        {
            "labtest_master": (_master("R8", "2026-06-01 10:00:00"),),
            "labtest_item_report": (_lab("R8", "血钾", "2.8", "PL", "2026-06-01 10:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": (
                {"horizon_date": "2026-06-01", "horizon_datetime": "2026-06-01 13:00:00"},
            ),
        },
        set(),
        {
            "LX0609-06-04-01": ("not_applicable", "sufficient", "unknown", "evaluation_window_not_mature", 2),
            "LX0609-06-04-02": ("applicable", "sufficient", "defect", "required_document_missing", 1),
        },
    ),
    (
        "09_window_not_mature_blocked_by_lab_master_unavailable",
        {
            "labtest_item_report": (_lab("R9", "血钾", "2.8", "PL", "2026-06-01 10:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": (
                {"horizon_date": "2026-06-01", "horizon_datetime": "2026-06-01 13:00:00"},
            ),
        },
        {"labtest_master"},
        {
            "LX0609-06-04-01": ("unknown", "data_gap", "unknown", "source_unavailable", 2),
            "LX0609-06-04-02": ("applicable", "sufficient", "defect", "required_document_missing", 1),
        },
    ),
    (
        "10_horizon_conflict",
        {
            "labtest_master": (_master("R10", "2026-06-01 10:00:00"),),
            "labtest_item_report": (_lab("R10", "血钾", "2.8", "PL", "2026-06-01 10:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": (
                {"horizon_date": "2026-06-02", "horizon_datetime": "2026-06-01 13:00:00"},
            ),
        },
        set(),
        {
            "LX0609-06-04-01": ("unknown", "data_gap", "unknown", "authoritative_time_conflict", 1),
            "LX0609-06-04-02": ("applicable", "sufficient", "defect", "required_document_missing", 1),
        },
    ),
    (
        "11_empty_lab_details_with_master_present",
        {
            "labtest_master": (_master("R11", "2026-06-01 10:00:00"),),
            "labtest_item_report": (),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("unknown", "data_gap", "unknown", "required_field_missing", 1),
            "LX0609-06-04-02": ("unknown", "data_gap", "unknown", "required_field_missing", 1),
        },
    ),
    (
        "12_no_critical_values_normal_labs",
        {
            "labtest_master": (_master("R12", "2026-06-01 10:00:00"),),
            "labtest_item_report": (_lab("R12", "血钾", "4.1", "N", "2026-06-01 10:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("not_applicable", "sufficient", "unknown", "trigger_absent_complete", 1),
            "LX0609-06-04-02": ("not_applicable", "sufficient", "unknown", "trigger_absent_complete", 1),
        },
    ),
    (
        "13_empty_labs_complete_negative",
        {
            "labtest_master": (),
            "labtest_item_report": (),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("not_applicable", "sufficient", "unknown", "trigger_absent_complete", 1),
            "LX0609-06-04-02": ("not_applicable", "sufficient", "unknown", "trigger_absent_complete", 1),
        },
    ),
    (
        "14_over_128_lab_rows_snapshot_ref_fallback",
        {
            "labtest_master": (_master("R14", "2026-06-01 10:00:00"),),
            "labtest_item_report": tuple(
                _lab(f"R14-{i}", f"项目{i}", "4.0", "N", "2026-06-01 10:00:00", f"lab-14-{i}")
                for i in range(135)
            ),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        set(),
        {
            "LX0609-06-04-01": ("not_applicable", "sufficient", "unknown", "trigger_absent_complete", 1),
            "LX0609-06-04-02": ("not_applicable", "sufficient", "unknown", "trigger_absent_complete", 1),
        },
    ),
    (
        "15_lab_item_report_unavailable",
        {
            "labtest_master": (_master("R15", "2026-06-01 10:00:00"),),
            "crisis_value_record": (),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        {"labtest_item_report"},
        {
            "LX0609-06-04-01": ("unknown", "data_gap", "unknown", "source_unavailable", 0),
            "LX0609-06-04-02": ("unknown", "data_gap", "unknown", "source_unavailable", 0),
        },
    ),
    (
        "16_crisis_value_record_unavailable_still_blocks_unhandled",
        {
            "labtest_master": (_master("R16", "2026-06-01 10:00:00"),),
            "labtest_item_report": (_lab("R16", "血钾", "2.8", "PL", "2026-06-01 10:00:00"),),
            "daily_course_record": (),
            "senior_course_record": (),
            "evaluation_context.horizon": HORIZON_MATURE,
        },
        {"crisis_value_record"},
        {
            "LX0609-06-04-01": ("unknown", "data_gap", "unknown", "source_unavailable", 1),
            "LX0609-06-04-02": ("unknown", "data_gap", "unknown", "source_unavailable", 1),
        },
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_name,sources,unavailable,expected_by_rule",
    SYNTHETIC_PARITY_CASES,
    ids=[row[0] for row in SYNTHETIC_PARITY_CASES],
)
async def test_critical_value_family_matches_native_executor_verdict_reason_and_evidence(
    case_name: str,
    sources: dict[str, Any],
    unavailable: set[str],
    expected_by_rule: dict[str, tuple[str, str, str, str, int]],
) -> None:
    snapshot, materials = _session(sources, unavailable_sources=unavailable)

    full_res = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=CRITICAL_VALUE_RULE_IDS,
        decision_rule_ids=CRITICAL_VALUE_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )
    horizon_rows, horizon_error = family_runtime.source_rows(
        materials, "evaluation_context.horizon"
    )
    direct = cvf.execute_critical_value_family(
        rule_ids=CRITICAL_VALUE_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        horizon_rows=horizon_rows,
        horizon_error=horizon_error,
    )

    assert full_res.decisions == direct.decisions
    assert full_res.customer_display_facts == direct.display_facts

    by_rule = {item.rule_id: item for item in full_res.decisions}
    for rule_id, (app_v, ev_v, dir_v, reason, ref_count) in expected_by_rule.items():
        decision = by_rule[rule_id]
        assert (
            decision.applicability.value,
            decision.evidence_state.value,
            decision.qc_direction.value,
            decision.reason_code,
            len(decision.fact_refs),
        ) == (app_v, ev_v, dir_v, reason, ref_count), f"{case_name} / {rule_id}"


@pytest.mark.asyncio
async def test_critical_value_family_preserves_mixed_rule_order_and_affirmative_horizon_refs() -> None:
    sources = {
        "inpat_registration": ({"admission_date": "2026-06-01", "discharge_date": "2026-06-05"},),
        "labtest_master": (_master("R-ORD", "2026-06-01 10:00:00"),),
        "labtest_item_report": (_lab("R-ORD", "血钾", "2.8", "PL", "2026-06-01 10:00:00"),),
        "crisis_value_record": (),
        "daily_course_record": (),
        "senior_course_record": (),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-06-01", "horizon_datetime": "2026-06-01 13:00:00"},
        ),
    }
    snapshot, materials = _session(sources)
    mixed_rules = ("LX0609-06-04-02", "LX0609-08-01-01", "LX0609-06-04-01")
    res = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=mixed_rules,
        decision_rule_ids=mixed_rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )
    assert res.planned_rule_ids == mixed_rules
    assert tuple(d.rule_id for d in res.decisions) == mixed_rules
    assert res.results == ()
    decision_052 = res.decisions[2]
    assert decision_052.reason_code == "evaluation_window_not_mature"
    assert decision_052.affirmative_applicability is True


def test_ast_guard_native_extended_executor_has_no_inline_critical_value_logic() -> None:
    tree = ast.parse(NED_PATH.read_text(encoding="utf-8"))
    defined_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)

    forbidden_prefixes = (
        "_CRITICAL_VALUE_",
        "_critical_value_",
        "_course_critical_value_",
        "_has_affirmative_critical_value_",
        "_has_affirmative_handling_for_critical_event",
        "_text_mentions_critical_",
        "_compile_lab_label_pattern",
    )
    leaked = sorted(
        name for name in defined_names if name.startswith(forbidden_prefixes)
    )
    assert leaked == [], f"危急值实现回流到总调度模块: {leaked}"

    # 确认总调度模块不再直接调用底层危急值判定内核，而是经 critical_value_family 委托
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "execute_critical_value_family" in called_names
    assert "evaluate_critical_value_rules" not in called_names
    assert "select_critical_value_fact_refs" not in called_names


@pytest.mark.parametrize("module_path", [CVF_PATH, RUNTIME_PATH])
def test_ast_guard_extracted_modules_never_import_monolith(module_path: Path) -> None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "native_extended_document_execution" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "native_extended_document_execution" not in mod
            for alias in node.names:
                assert alias.name != "native_extended_document_execution"


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable_sources", [set(), {"labtest_master"}, {"labtest_item_report"}])
async def test_critical_value_execution_reads_lab_sources_once_per_group(
    unavailable_sources: set[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一执行组内检验主表与明细表仅调用 materials.rows 读取一次，并复用错误状态。"""
    sources = {
        "labtest_master": (_master("R-ONCE", "2026-06-01 08:00:00"),),
        "labtest_item_report": (_lab("R-ONCE", "血钾", "2.8", "PL", "2026-06-01 08:00:00"),),
        "crisis_value_record": (),
        "daily_course_record": (),
        "senior_course_record": (),
        "evaluation_context.horizon": HORIZON_MATURE,
    }
    snapshot, materials = _session(sources, unavailable_sources=unavailable_sources)

    read_counts: dict[str, int] = {}
    original_rows = type(materials).rows

    def _counting_rows(self, source_key: str):
        if self is materials:
            read_counts[source_key] = read_counts.get(source_key, 0) + 1
        return original_rows(self, source_key)

    monkeypatch.setattr(type(materials), "rows", _counting_rows)
    res = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=CRITICAL_VALUE_RULE_IDS,
        decision_rule_ids=CRITICAL_VALUE_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )
    assert len(res.decisions) == 2
    assert read_counts.get("labtest_master") == 1
    assert read_counts.get("labtest_item_report") == 1
    assert read_counts.get("crisis_value_record") == 1


@pytest.mark.asyncio
async def test_critical_value_cross_report_evidence_refs_bind_exact_documents() -> None:
    """跨报告隔离场景直接断言 fact_refs 精确指向两份检验报告与命中的病程文书，不含无关病程。"""
    sources = {
        "labtest_master": (
            _master("R7A", "2026-06-01 08:00:00"),
            _master("R7B", "2026-06-01 12:00:00"),
        ),
        "labtest_item_report": (
            _lab("R7A", "血钾", "2.8", "PL", "2026-06-01 08:00:00", "lab-R7A"),
            _lab("R7B", "血钾", "6.7", "PH", "2026-06-01 12:00:00", "lab-R7B"),
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            _course("C7-MATCH", "2026-06-01 12:30:00", "日常病程记录", "08:00血钾2.8已予补钾治疗；另测血糖6.7 mmol/L。"),
            _course("C7-UNRELATED", "2026-06-01 13:00:00", "日常病程记录", "患者一般情况可，继续目前治疗。"),
        ),
        "senior_course_record": (),
        "evaluation_context.horizon": HORIZON_MATURE,
    }
    snapshot, materials = _session(sources)
    res = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=CRITICAL_VALUE_RULE_IDS,
        decision_rule_ids=CRITICAL_VALUE_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )

    ref_to_doc_id: dict[str, str] = {}
    for source_key in ("labtest_item_report", "daily_course_record"):
        for ref, row in materials.document_rows(source_key, snapshot=snapshot):
            ref_to_doc_id[ref] = str(row["document_id"])

    by_rule = {item.rule_id: item for item in res.decisions}
    for rule_id in CRITICAL_VALUE_RULE_IDS:
        decision = by_rule[rule_id]
        assert decision.qc_direction.value == "defect"
        cited_doc_ids = {ref_to_doc_id[ref] for ref in decision.fact_refs}
        assert cited_doc_ids == {"lab-R7A", "lab-R7B", "C7-MATCH"}
        assert "C7-UNRELATED" not in cited_doc_ids

