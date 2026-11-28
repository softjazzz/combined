"""架构治理 Batch 4 · Family #2（抗菌药规则族 05-01-02..06 / 05-03-01）一致性、缓存与边界测试。

验收覆盖三项核心目标：
1. 判定、原因码与证据引用一致：独立执行器 `execute_antimicrobial_family`、总入口
   `execute_luxian_0609_native_extended_document_rules` 与顺序组 `_execute_extended_document_group`
   产出完全一致的决策、精确文书引用与展示事实；
2. 共享事实抽取次数、模型预算、冻结回读与来源单次读取：
   - 05-01-02 与 05-01-05 共用一次理由抽取（1 次模型调用 / 15 tokens），冻结回读 0 次模型调用；
   - 05-01-06 授权专家审批首次 1 次模型调用，冻结回读 0 次模型调用，药师署名 0 次调用直接判缺陷；
   - 纯抗菌药组仅访问抗菌药自身来源且各来源仅读 1 次，不读取死亡/出院/交接/转出/输血等无关来源；
   - 混合顺序组通过共享 `SourceRowsCache` 保证共享来源仍只读 1 次；
3. AST 边界守卫：`native_extended_document_execution.py` 不再残留抗菌药实现与直接抽取调用，
   且 `antimicrobial_family.py` 不反向导入总调度模块。
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from app.services.luxian_0609.extended_document import antimicrobial_family as amf
from app.services.luxian_0609.extended_document.antimicrobial_family import (
    ANTIMICROBIAL_RULE_IDS,
    execute_antimicrobial_family,
)
from tests.unit.test_luxian_0609_antimicrobial_order_reason import (
    _ReasonClient,
    _course,
    _order,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import _session
from tests.unit.test_luxian_0609_s3_extended_doc_fixes import (
    _TargetedSpecialApprovalClient,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
LUXIAN_DIR = BACKEND_ROOT / "app" / "services" / "luxian_0609"
NED_PATH = LUXIAN_DIR / "native_extended_document_execution.py"
AMF_PATH = LUXIAN_DIR / "extended_document" / "antimicrobial_family.py"


class _ForbidLLMClient:
    async def generate_json(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("冻结回读不得再次触发模型调用")

    async def generate_text(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("冻结回读不得再次触发模型调用")


@pytest.mark.asyncio
async def test_shared_reason_054_057_calls_llm_once_and_replays_from_freeze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path / "freeze"))
    reason_text = "考虑细菌感染，予头孢曲松抗感染。"
    sources = {
        "inpat_registration": ({"admission_date": "2026-01-01", "discharge_date": "2026-01-05"},),
        "inpat_drug_order": (_order("order-1", "头孢曲松", "2026-01-02 10:00:00"),),
        "daily_course_record": (_course("course-1", "2026-01-02 11:00:00", reason_text),),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-01-06", "horizon_datetime": "2026-01-06 00:00:00"},
        ),
    }
    snapshot, materials = _session(sources)
    rules = ("LX0609-05-01-02", "LX0609-05-01-05")

    client = _ReasonClient({"头孢曲松": {"infection_judgment": reason_text}})
    cold = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=rules,
        decision_rule_ids=rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=client,
    )
    assert len(client.calls) == 1
    assert cold.llm_call_count == 1
    assert cold.total_tokens == 15
    assert [(d.rule_id, d.qc_direction.value, d.reason_code) for d in cold.decisions] == [
        ("LX0609-05-01-02", "satisfied", "requirement_satisfied"),
        ("LX0609-05-01-05", "defect", "requirement_violated"),
    ]

    # 冻结回读：禁止访问模型，判定、原因码、证据引用与展示事实保持完全一致
    frozen = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=rules,
        decision_rule_ids=rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=_ForbidLLMClient(),
    )
    assert frozen.llm_call_count == 0
    assert frozen.total_tokens == 0
    assert frozen.decisions == cold.decisions
    assert frozen.customer_display_facts == cold.customer_display_facts

    # 直接调用 execute_antimicrobial_family 也应命中同一冻结缓存并给出完全一致结果
    direct = await execute_antimicrobial_family(
        rule_ids=rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=_ForbidLLMClient(),
    )
    assert direct.llm_call_count == 0
    assert direct.decisions == cold.decisions
    assert direct.display_facts == cold.customer_display_facts


@pytest.mark.asyncio
async def test_special_058_authorized_expert_freeze_and_pharmacist_rejection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path / "freeze_058"))
    quote = "同意使用特殊级抗菌药物美罗培南抗感染治疗。"
    authorized_sources = {
        "inpat_registration": ({"admission_date": "2026-01-01", "discharge_date": "2026-01-05"},),
        "inpat_drug_order": (_order("order-sp1", "注射用美罗培南", "2026-01-02 10:00:00"),),
        "consultation_record": (
            {
                "document_id": "consult-auth",
                "record_time": "2026-01-02 09:30:00",
                "document_title": "感染科会诊记录",
                "record_content": f"感染科李主任医师会诊意见：{quote}",
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-01-06", "horizon_datetime": "2026-01-06 00:00:00"},
        ),
    }
    snap_auth, mat_auth = _session(authorized_sources)
    client = _TargetedSpecialApprovalClient({"美罗培南": quote})
    cold = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-05-01-06",),
        decision_rule_ids=("LX0609-05-01-06",),
        evidence_snapshot=snap_auth,
        evidence_materials=mat_auth,
        llm_client=client,
    )
    assert cold.llm_call_count == 1
    assert cold.total_tokens == 15
    assert cold.decisions[0].qc_direction.value == "satisfied"
    assert cold.decisions[0].reason_code == "requirement_satisfied"
    assert len(cold.decisions[0].fact_refs) == 2

    frozen = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-05-01-06",),
        decision_rule_ids=("LX0609-05-01-06",),
        evidence_snapshot=snap_auth,
        evidence_materials=mat_auth,
        llm_client=_ForbidLLMClient(),
    )
    assert frozen.llm_call_count == 0
    assert frozen.decisions == cold.decisions
    assert frozen.customer_display_facts == cold.customer_display_facts

    # 药师署名不具备授权专家资格：0 次模型调用即判缺失
    pharmacist_sources = {
        **authorized_sources,
        "consultation_record": (
            {
                "document_id": "consult-pharm",
                "record_time": "2026-01-02 09:30:00",
                "document_title": "临床药学会诊记录",
                "record_content": "感染科张三药师意见：同意使用特殊级抗菌药物美罗培南。",
            },
        ),
    }
    snap_ph, mat_ph = _session(pharmacist_sources)
    res_ph = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-05-01-06",),
        decision_rule_ids=("LX0609-05-01-06",),
        evidence_snapshot=snap_ph,
        evidence_materials=mat_ph,
        llm_client=_ForbidLLMClient(),
    )
    assert res_ph.llm_call_count == 0
    assert res_ph.decisions[0].qc_direction.value == "defect"
    assert res_ph.decisions[0].reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_antimicrobial_only_reads_only_own_sources_once_and_skips_unrelated_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只选抗菌药规则时：仅读取抗菌药自身所需来源（每张最多 1 次），不触碰死亡/出院/交接/转出/输血等表。"""
    sources = {
        "inpat_registration": ({"admission_date": "2026-01-01", "discharge_date": "2026-01-05"},),
        "inpat_drug_order": (),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-01-06", "horizon_datetime": "2026-01-06 00:00:00"},
        ),
    }
    snapshot, materials = _session(sources)
    read_counts: dict[str, int] = {}
    original_rows = type(materials).rows

    def _counting_rows(self, source_key: str):
        if self is materials:
            read_counts[source_key] = read_counts.get(source_key, 0) + 1
        return original_rows(self, source_key)

    monkeypatch.setattr(type(materials), "rows", _counting_rows)
    res = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=ANTIMICROBIAL_RULE_IDS,
        decision_rule_ids=ANTIMICROBIAL_RULE_IDS,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )
    assert tuple(d.rule_id for d in res.decisions) == ANTIMICROBIAL_RULE_IDS
    assert all(count == 1 for count in read_counts.values()), f"存在重复读取: {read_counts}"

    unrelated_tables = {
        "death_record",
        "death_discussion",
        "discharge_record",
        "discharge_record_diagnosis",
        "admission_record",
        "admission_record_diagnosis",
        "postsurg_firstcourse_record",
        "handoff_record",
        "handover_record",
        "physician_change_event",
        "transfer_out_record",
        "diagnosis",
        "diffcase_discussion_record",
        "crisis_value_record",
        "bloodtrans_record",
    }
    touched_unrelated = unrelated_tables.intersection(read_counts)
    assert touched_unrelated == set(), f"纯抗菌药组不应读取无关来源: {sorted(touched_unrelated)}"


@pytest.mark.asyncio
async def test_mixed_sequential_group_reuses_source_cache_without_duplicate_reads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """混合顺序执行组中，共享来源（医嘱/病程/检验/登记/终点）经 SourceRowsCache 仅读取 1 次，且与并行组一致。"""
    reason_text = "考虑细菌感染，予头孢曲松抗感染。"
    sources = {
        "inpat_registration": ({"admission_date": "2026-01-01", "discharge_date": "2026-01-05"},),
        "inpat_drug_order": (_order("order-1", "头孢曲松", "2026-01-02 10:00:00"),),
        "daily_course_record": (_course("course-1", "2026-01-02 11:00:00", reason_text),),
        "labtest_master": ({"document_id": "lm-1", "report_id": "R1", "report_time": "2026-01-02 08:00:00"},),
        "labtest_item_report": (
            {"document_id": "li-1", "report_id": "R1", "item_name": "血钾", "result": "4.0", "result_flag": "N", "report_time": "2026-01-02 08:00:00"},
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-01-06", "horizon_datetime": "2026-01-06 00:00:00"},
        ),
    }
    snapshot, materials = _session(sources)
    mixed_rules = ("LX0609-05-01-02", "LX0609-06-04-01", "LX0609-05-01-05", "LX0609-08-01-01")

    read_counts: dict[str, int] = {}
    original_rows = type(materials).rows

    def _counting_rows(self, source_key: str):
        if self is materials:
            read_counts[source_key] = read_counts.get(source_key, 0) + 1
        return original_rows(self, source_key)

    monkeypatch.setattr(type(materials), "rows", _counting_rows)
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path / "seq"))
    sequential = await ned._execute_extended_document_group(
        rule_ids=mixed_rules,
        decision_rule_ids=mixed_rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=_ReasonClient({"头孢曲松": {"infection_judgment": reason_text}}),
    )
    assert all(count == 1 for count in read_counts.values()), f"混合顺序组存在重复读取: {read_counts}"

    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path / "par"))
    parallel = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=mixed_rules,
        decision_rule_ids=mixed_rules,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=_ReasonClient({"头孢曲松": {"infection_judgment": reason_text}}),
    )
    assert replace(parallel, api_time=0) == replace(sequential, api_time=0)
    assert tuple(d.rule_id for d in parallel.decisions) == mixed_rules


def test_ast_guard_native_extended_executor_has_no_inline_antimicrobial_logic() -> None:
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
        "_LX0609_058_",
        "_SPECIAL_ANTIMICROBIAL_",
        "_LAB_ORDER_",
        "_antimicrobial_",
        "_has_performed_antimicrobial_",
        "_exclude_unperformed_antimicrobial_",
        "_055_treatment_orders",
        "_lx0609_058_",
        "_has_authorized_special_antimicrobial_",
        "_authorized_special_antimicrobial_",
        "_is_governed_by_non_authorized_speaker",
        "_special_approval_by_authorized_expert",
        "_is_pathogen_lab",
        "_has_unsynced_lab_orders",
        "_is_prophylactic_antimicrobial_clause",
        "_pathogen_basis_state",
        "_order_reason_rule_outcome",
    )
    leaked = sorted(name for name in defined_names if name.startswith(forbidden_prefixes))
    assert leaked == [], f"抗菌药逻辑回流至总调度模块: {leaked}"

    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "execute_antimicrobial_family" in called_names
    for forbidden_call in (
        "extract_antimicrobial_reasons",
        "extract_special_antimicrobial_approvals",
        "extract_antimicrobial_effects",
        "extract_antimicrobial_effect_pairs",
        "derive_antimicrobial_use_events",
    ):
        assert forbidden_call not in called_names, f"总调度不得直接调用 {forbidden_call}"


def test_ast_guard_antimicrobial_family_never_imports_monolith() -> None:
    tree = ast.parse(AMF_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "native_extended_document_execution" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "native_extended_document_execution" not in mod
            for alias in node.names:
                assert alias.name != "native_extended_document_execution"
