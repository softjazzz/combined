"""Codex PR #90 复审回归单测：
- Issue #2: 单规则 vs 多规则执行等价性（06-03-05/06、05-01-04、06-02-02、06-04-01/02）与受控来源声明；
- Issue #3: LX0609-06-01-02 入院 24h 豁免绝不可遮蔽 report_time / exam_time / order_time 锚点时间冲突。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceUnavailable,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    ExamLabSingleEvent,
    ExamLabTextProjection,
    build_exam_lab_text_projection,
    events_for_family,
    exam_reason_anchor_has_conflict,
)
from app.services.luxian_0609.native_exam_lab_execution import (
    _single_text_fact_outcome,
    execute_luxian_0609_native_exam_lab_rules,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.native_tumor_pathology_execution import (
    _LX019_DECLARED_SURGERY_EVENT_SOURCES,
    _has_available_session_surgery_evidence,
    execute_luxian_0609_native_tumor_pathology_rules,
)
from app.services.luxian_0609.routine_lab_presence import (
    ITEM_SOURCE,
    OPTIONAL_ORDER_SOURCES,
)
from app.services.luxian_0609.source_registry import (
    resolve_luxian_0609_decision_support_source_keys,
)
from luxian_0609_pathology_test_facts import PathologyFactsClient, default_pathology_facts


def _horizon_snapshot(
    *,
    admission_datetime: str = "2026-08-01 08:00:00",
    discharge_datetime: str = "2026-08-10 10:00:00",
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
    selected_rule_ids: Sequence[str],
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    unavailable_sources: Sequence[str] = (),
    admission_datetime: str = "2026-08-01 08:00:00",
    discharge_datetime: str = "2026-08-10 10:00:00",
):
    unavailable = set(unavailable_sources)

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        key = kwargs["source_key"]
        if key in unavailable:
            raise SourceEvidenceUnavailable(f"synthetic unavailable: {key}")
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows_by_source.get(key, ()),
            truncated=False,
            limit_rows=5000,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=tuple(selected_rule_ids),
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        created_at="2026-08-15T10:00:00+08:00",
        row_reader=reader,
        evaluation_horizon_snapshot=_horizon_snapshot(
            admission_datetime=admission_datetime,
            discharge_datetime=discharge_datetime,
        ),
    )


def _scripted_not_documented_pathology_client() -> PathologyFactsClient:
    def script(
        sampling: bool,
        events: list[dict[str, Any]],
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        _ = default_pathology_facts(sampling, events, documents)
        return [
            {
                "event": event["event"],
                "state": "not_documented",
                "document": None,
                "quote": None,
            }
            for event in events
        ]

    return PathologyFactsClient(script)


# ---------------------------------------------------------------------------
# Issue #2A: source_registry.py declaration contracts
# ---------------------------------------------------------------------------


def test_source_registry_declares_all_parity_sources_independently() -> None:
    for rule_id in ("LX0609-06-03-05", "LX0609-06-03-06"):
        declared = set(resolve_luxian_0609_decision_support_source_keys((rule_id,)))
        assert set(OPTIONAL_ORDER_SOURCES).issubset(declared)
        assert "inpat_nondrug_order" in declared

    declared_054 = set(resolve_luxian_0609_decision_support_source_keys(("LX0609-05-01-04",)))
    assert "inpat_nondrug_order" in declared_054

    declared_019 = set(resolve_luxian_0609_decision_support_source_keys(("LX0609-06-02-02",)))
    assert set(_LX019_DECLARED_SURGERY_EVENT_SOURCES).issubset(declared_019)
    assert "postsurg_firstcourse_record" in declared_019
    assert "surgery_application" in declared_019
    assert "anesthesia_record" in declared_019
    assert "senior_course_record" not in declared_019
    assert "surgery_master" not in declared_019

    for rule_id in ("LX0609-06-04-01", "LX0609-06-04-02"):
        declared_cv = set(resolve_luxian_0609_decision_support_source_keys((rule_id,)))
        assert {"daily_course_record", "senior_course_record"}.issubset(declared_cv)
    assert "evaluation_context.horizon" in resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-06-04-01",)
    )
    assert "evaluation_context.horizon" not in resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-06-04-02",)
    )


# ---------------------------------------------------------------------------
# Issue #2B: Single-rule vs multi-rule parity for 06-03-05 & 06-03-06
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-06-03-05", "LX0609-06-03-06"])
async def test_routine_lab_solo_matches_multi_rule_batch_on_unsynced_labs(
    rule_id: str,
) -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "labtest_master": [],
        "labtest_item_report": [],
        ITEM_SOURCE: [],
        "inpat_nondrug_order": [
            {
                "order_id": "ORD-1",
                "order_name": "血常规" if rule_id.endswith("05") else "尿液分析",
                "order_type": "检验",
                "order_status": "执行",
            }
        ],
    }

    async def run(selected_rules: Sequence[str]) -> dict[str, Any]:
        session = _build_session(
            selected_rule_ids=selected_rules,
            rows_by_source=rows_by_source,
        )
        execution = await execute_luxian_0609_native_exam_lab_rules(
            rule_ids=(rule_id,),
            decision_rule_ids=(rule_id,),
            wrapper_rules=[{"rule_id": rule_id, "custom_prompt": "stub"}],
            evidence_payload={},
            llm_client=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions,
            expected_rule_ids=(rule_id,),
            snapshot=session.snapshot,
            evidence_materials=session.materials,
        )[0]
        return finalize_luxian_0609_reduced_customer_result(
            decision=reduced,
            raw_customer_display_facts=dict(execution.customer_display_facts).get(rule_id),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )

    solo_final = await run((rule_id,))
    batch_final = await run((rule_id, "LX0609-10-02-02", "LX0609-06-03-03"))

    assert solo_final["status"] == "data_gap"
    assert solo_final["reason_code"] == "source_empty"
    assert solo_final["status"] == batch_final["status"]
    assert solo_final["reason_code"] == batch_final["reason_code"]


@pytest.mark.asyncio
async def test_routine_lab_solo_handles_unavailable_optional_order_sources_cleanly() -> None:
    """合成单测省略非药医嘱表（抛出 SourceEvidenceUnavailable）时，06-03-05 仍按既有口径正常裁决。"""
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "labtest_master": [],
        "labtest_item_report": [],
        ITEM_SOURCE: [],
    }
    session = _build_session(
        selected_rule_ids=("LX0609-06-03-05",),
        rows_by_source=rows_by_source,
        unavailable_sources=OPTIONAL_ORDER_SOURCES,
    )
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-06-03-05",),
        decision_rule_ids=("LX0609-06-03-05",),
        wrapper_rules=[{"rule_id": "LX0609-06-03-05", "custom_prompt": "stub"}],
        evidence_payload={},
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-06-03-05",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    assert reduced.final_state.value == "non_compliant"


# ---------------------------------------------------------------------------
# Issue #2C: Single-rule vs multi-rule parity for 05-01-04
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_05_01_04_solo_matches_multi_rule_batch_on_unsynced_labs() -> None:
    rows_by_source = {
        "inpat_drug_order": [
            {
                "order_id": "D1",
                "generic_name": "注射用美罗培南",
                "drug_apply_method": "静脉滴注",
                "order_status": "执行",
                "planned_start_datetime": "2026-08-02 09:00:00",
            },
            {
                "order_id": "D2",
                "generic_name": "注射用盐酸万古霉素",
                "drug_apply_method": "静脉滴注",
                "order_status": "执行",
                "planned_start_datetime": "2026-08-02 10:00:00",
            },
        ],
        "labtest_master": [],
        "labtest_item_report": [],
        "inpat_nondrug_order": [
            {
                "order_id": "O1",
                "order_name": "全血需氧培养",
                "order_type": "检验",
                "order_status": "执行",
            }
        ],
    }

    async def run(selected_rules: Sequence[str]) -> dict[str, Any]:
        session = _build_session(
            selected_rule_ids=selected_rules,
            rows_by_source=rows_by_source,
        )
        execution = await execute_luxian_0609_native_extended_document_rules(
            rule_ids=("LX0609-05-01-04",),
            decision_rule_ids=("LX0609-05-01-04",),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            llm_client=None,
        )
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions,
            expected_rule_ids=("LX0609-05-01-04",),
            snapshot=session.snapshot,
            evidence_materials=session.materials,
        )[0]
        return finalize_luxian_0609_reduced_customer_result(
            decision=reduced,
            raw_customer_display_facts=dict(execution.customer_display_facts).get(
                "LX0609-05-01-04"
            ),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )

    solo_final = await run(("LX0609-05-01-04",))
    batch_final = await run(("LX0609-05-01-04", "LX0609-10-02-02"))

    assert solo_final["status"] == "data_gap"
    assert solo_final["reason_code"] == "source_unavailable"
    assert solo_final["status"] == batch_final["status"]
    assert solo_final["reason_code"] == batch_final["reason_code"]


# ---------------------------------------------------------------------------
# Issue #2D: Single-rule vs multi-rule parity for 06-02-02 (no undeclared peeking)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_06_02_02_solo_matches_multi_rule_batch_without_additional_source_keys() -> None:
    """复现 #23 场景：仅选单规则 LX0609-06-02-02（不传 additional_source_keys）与批量运行完全一致。"""
    rows_by_source = {
        "pathology_exam_master": [
            {
                "document_id": "m1",
                "pathology_exam_id": "P1",
                "specimen_name": "胆囊",
            }
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "胆囊",
                "diagnosis": "慢性胆囊炎",
                "report_datetime": "2026-08-05 10:00:00",
            }
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-08-03 09:00:00",
                "record_content": "患者一般情况可，生命体征平稳。",
            }
        ],
        "postsurg_firstcourse_record": [
            {
                "document_id": "pfc1",
                "record_time": "2026-08-02 20:00:00",
                "document_title": "术后首次病程记录",
                "record_content": "患者今日在全麻下行腹腔镜下胆囊切除术，安返病房。",
            }
        ],
        "surgery_application": [
            {
                "document_id": "sa1",
                "surgery_name": "腹腔镜下胆囊切除术",
                "order_status": "已执行",
            }
        ],
    }

    async def run(selected_rules: Sequence[str]) -> dict[str, Any]:
        session = _build_session(
            selected_rule_ids=selected_rules,
            rows_by_source=rows_by_source,
        )
        execution = await execute_luxian_0609_native_tumor_pathology_rules(
            rule_ids=("LX0609-06-02-02",),
            wrapper_rules=[],
            evidence_payload={},
            institute_id="INST",
            patient_id="PAT",
            visit_id="VIS",
            source_schema=None,
            llm_client=_scripted_not_documented_pathology_client(),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            decision_rule_ids=("LX0609-06-02-02",),
        )
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions,
            expected_rule_ids=("LX0609-06-02-02",),
            snapshot=session.snapshot,
            evidence_materials=session.materials,
        )[0]
        return finalize_luxian_0609_reduced_customer_result(
            decision=reduced,
            raw_customer_display_facts=dict(execution.customer_display_facts).get(
                "LX0609-06-02-02"
            ),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )

    solo_final = await run(("LX0609-06-02-02",))
    batch_final = await run(("LX0609-06-02-02", "LX0609-04-02-01", "LX0609-04-05-01"))

    assert solo_final["status"] == "data_gap"
    assert solo_final["reason_code"] == "source_empty"
    assert solo_final["status"] == batch_final["status"]
    assert solo_final["reason_code"] == batch_final["reason_code"]
    for final in (solo_final, batch_final):
        evidence_sources = {
            item["source_type"] for item in (final.get("customer_evidence") or [])
        }
        assert not evidence_sources.intersection(_LX019_DECLARED_SURGERY_EVENT_SOURCES)


def test_06_02_02_surgery_evidence_helper_never_reads_undeclared_surgery_master() -> None:
    class _FakeMaterials:
        def has_source(self, source_key: str) -> bool:
            return source_key == "surgery_master"

        def bounded_rows(self, source_key: str) -> tuple[Mapping[str, Any], ...]:
            if source_key == "surgery_master":
                return ({"surgery_name": "腹腔镜下胆囊切除术", "order_status": "已执行"},)
            return ()

    assert _has_available_session_surgery_evidence(_FakeMaterials()) is False  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_06_02_02_solo_handles_unavailable_aux_surgery_sources_without_breakage() -> None:
    rows_by_source = {
        "pathology_exam_master": [
            {"document_id": "m1", "pathology_exam_id": "P1", "specimen_name": "胃窦黏膜"}
        ],
        "pathology_exam_report": [
            {
                "document_id": "r1",
                "pathology_exam_id": "P1",
                "specimen_name": "胃窦黏膜",
                "diagnosis": "慢性浅表性胃炎",
                "report_datetime": "2026-08-05 10:00:00",
            }
        ],
        "surgery_record": [],
        "daily_course_record": [
            {
                "document_id": "c1",
                "record_time": "2026-08-03 09:00:00",
                "record_content": "胃镜检查顺利，无不适。",
            }
        ],
    }
    session = _build_session(
        selected_rule_ids=("LX0609-06-02-02",),
        rows_by_source=rows_by_source,
        unavailable_sources=_LX019_DECLARED_SURGERY_EVENT_SOURCES,
    )
    execution = await execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-06-02-02",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="INST",
        patient_id="PAT",
        visit_id="VIS",
        source_schema=None,
        llm_client=_scripted_not_documented_pathology_client(),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-06-02-02",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-06-02-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    assert reduced.final_state.value == "non_compliant"


# ---------------------------------------------------------------------------
# Issue #2E: Single-rule vs multi-rule parity for 06-04-01 & 06-04-02
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-06-04-01", "LX0609-06-04-02"])
async def test_critical_value_solo_loads_course_records_and_matches_multi_rule_batch(
    rule_id: str,
) -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "labtest_master": [
            {"test_id": "T-CV1", "report_datetime": "2026-08-02 08:00:00"}
        ],
        "labtest_item_report": [
            {
                "document_id": "LAB-1",
                "test_id": "T-CV1",
                "item_name": "血清钾",
                "result": "6.8",
                "abnormal_indicator": "PH",
                "report_time": "2026-08-02 08:00:00",
            }
        ],
        "crisis_value_record": [],
        "daily_course_record": [
            {
                "document_id": "DC-1",
                "document_title": "危急值处理记录",
                "record_time": "2026-08-02 09:00:00",
                "record_content": "接检验科报危急值：血清钾 6.8mmol/L，立即予葡萄糖酸钙静推及胰岛素降钾处理，复查电解质。",
            }
        ],
        "senior_course_record": [],
    }

    async def run(selected_rules: Sequence[str]) -> dict[str, Any]:
        session = _build_session(
            selected_rule_ids=selected_rules,
            rows_by_source=rows_by_source,
        )
        assert session.materials.has_source("daily_course_record")
        assert session.materials.has_source("senior_course_record")
        execution = await execute_luxian_0609_native_extended_document_rules(
            rule_ids=(rule_id,),
            decision_rule_ids=(rule_id,),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            llm_client=None,
        )
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions,
            expected_rule_ids=(rule_id,),
            snapshot=session.snapshot,
            evidence_materials=session.materials,
        )[0]
        return finalize_luxian_0609_reduced_customer_result(
            decision=reduced,
            raw_customer_display_facts=dict(execution.customer_display_facts).get(rule_id),
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )

    solo_final = await run((rule_id,))
    batch_final = await run((rule_id, "LX0609-02-01-01", "LX0609-02-01-04"))

    assert solo_final["status"] == "compliant"
    assert solo_final["status"] == batch_final["status"]
    assert solo_final["reason_code"] == batch_final["reason_code"]


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-06-04-01", "LX0609-06-04-02"])
async def test_critical_value_solo_tolerates_unavailable_course_sources_in_synthetic_tests(
    rule_id: str,
) -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "labtest_master": [
            {"test_id": "T-CV1", "report_datetime": "2026-08-02 08:00:00"}
        ],
        "labtest_item_report": [
            {
                "document_id": "LAB-1",
                "test_id": "T-CV1",
                "item_name": "血钾",
                "result": "6.8",
                "abnormal_indicator": "PH",
                "report_time": "2026-08-02 08:00:00",
            }
        ],
        "crisis_value_record": [
            {
                "document_id": "CV-1",
                "test_id": "T-CV1",
                "record_time": "2026-08-02 09:00:00",
                "record_content": "已予降钾处理并复查。",
            }
        ],
    }
    session = _build_session(
        selected_rule_ids=(rule_id,),
        rows_by_source=rows_by_source,
        unavailable_sources=("daily_course_record", "senior_course_record"),
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule_id,),
        decision_rule_ids=(rule_id,),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=None,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    assert reduced.final_state.value == "compliant"


# ---------------------------------------------------------------------------
# Issue #3: LX0609-06-01-02 24h admission exemption must NOT shadow anchor conflicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exam_master_extra,exam_report_extra",
    [
        # Codex exact counterexample #1: no order_time, exam_time within 24h, conflicting report_time 1 day apart
        (
            {"exam_time": "2026-08-01 10:00:00", "report_time": "2026-08-01 12:00:00"},
            {"report_time": "2026-08-02 12:00:00"},
        ),
        # Counterexample #2: no order_time, no exam_time, conflicting report_time 1 day apart (one within 24h)
        (
            {"report_time": "2026-08-01 12:00:00"},
            {"report_time": "2026-08-02 12:00:00"},
        ),
        # Counterexample #3: no order_time, conflicting exam_time 1 day apart, single report_time within 24h
        (
            {"exam_time": "2026-08-01 10:00:00", "report_time": "2026-08-01 12:00:00"},
            {"exam_time": "2026-08-02 10:00:00", "report_time": "2026-08-01 12:00:00"},
        ),
    ],
)
async def test_06_01_02_conflicting_anchor_time_never_exempts_within_24h(
    exam_master_extra: dict[str, str],
    exam_report_extra: dict[str, str],
) -> None:
    rows_by_source = {
        "inpat_registration": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "admission_record": [{"admission_datetime": "2026-08-01 08:00:00"}],
        "exam_master": [
            {
                "document_id": "EX-M1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "description": "双肺渗出影。",
                **exam_master_extra,
            }
        ],
        "exam_item_report": [
            {
                "document_id": "EX-R1",
                "exam_id": "E1",
                "exam_type": "CT",
                "exam_name": "胸部螺旋CT平扫",
                "description": "双肺渗出影。",
                **exam_report_extra,
            }
        ],
        "daily_course_record": [],
    }
    projection = build_exam_lab_text_projection(rows_by_source=rows_by_source)
    event = events_for_family(projection, "exam")[0]
    assert event.order_time is None
    assert exam_reason_anchor_has_conflict(event) is True
    assert event.within_admission_window is False

    session = _build_session(
        selected_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
    )
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-06-01-02",),
        decision_rule_ids=("LX0609-06-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-06-01-02", "custom_prompt": "stub"}],
        evidence_payload={},
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
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
    assert reduced.final_state.value == "data_gap"
    assert final["status"] == "data_gap"
    assert final["status"] != "not_applicable"
    assert final["reason_code"] == "association_failed"


@pytest.mark.parametrize(
    "order_time,conflict_roles",
    [
        (None, frozenset({"report_time"})),
        (None, frozenset({"exam_time"})),
        (datetime(2026, 8, 1, 10, 0, 0), frozenset({"order_time"})),
    ],
)
def test_single_text_fact_outcome_checks_anchor_conflict_before_admission_exemption(
    order_time: datetime | None,
    conflict_roles: frozenset[str],
) -> None:
    """防御深度校验：即使手工构造 within_admission_window=True 且带锚点冲突，也必须先返回 data_gap。"""
    event = ExamLabSingleEvent(
        family="exam",
        document_refs=("E01-01",),
        exam_time=datetime(2026, 8, 1, 10, 0, 0),
        report_time=datetime(2026, 8, 1, 12, 0, 0),
        order_time=order_time,
        within_admission_window=True,
        conflict_roles=conflict_roles,
        positive_hint="unknown",
        target_confirmed=True,
        target_explicitly_absent=False,
        readable_text=True,
        result_text_available=True,
        identity_text="CT 胸部螺旋CT平扫",
    )
    projection = ExamLabTextProjection(
        context="",
        document_refs=("E01-01",),
        course_times={},
        imaging_event=event,
        culture_event=None,
        imaging_events=(event,),
        culture_events=(),
        safe_refs={"E01-01": "a" * 64},
    )
    fact = ExamLabEventFact(
        rule_id="LX0609-06-01-02",
        applicability="applicable",
        semantic_state="absent",
        positive_state="not_relevant",
        event_position=1,
        evidence_refs=("E01-01",),
        course_doc_refs=(),
    )

    outcome = _single_text_fact_outcome(
        rule_id="LX0609-06-01-02",
        fact=fact,
        projection=projection,
    )
    assert outcome.status == "data_gap"
    assert outcome.reason_code == "multiple_event_or_time_conflict"


@pytest.mark.asyncio
async def test_06_01_02_multi_event_conflicted_early_ct_prevents_silent_exemption() -> None:
    """多检查事件中若存在任一锚点冲突的早期 CT，整条规则仍必须降级 data_gap 而非豁免该事件。"""
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
                "description": "双肺渗出影。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "C1",
                "record_time": "2026-08-03 10:00:00",
                "record_content": "拟完善腹部CT了解腹腔情况。",
            }
        ],
    }
    session = _build_session(
        selected_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
    )
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-06-01-02",),
        decision_rule_ids=("LX0609-06-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-06-01-02", "custom_prompt": "stub"}],
        evidence_payload={},
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-06-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    assert reduced.final_state.value == "data_gap"
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_06_01_02_conflict_free_early_ct_within_24h_still_exempts_cleanly() -> None:
    """正向控制：无时间冲突的入院 24h 内 CT 仍正常豁免为 not_applicable。"""
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
    projection = build_exam_lab_text_projection(rows_by_source=rows_by_source)
    event = events_for_family(projection, "exam")[0]
    assert exam_reason_anchor_has_conflict(event) is False
    assert event.within_admission_window is True

    session = _build_session(
        selected_rule_ids=("LX0609-06-01-02",),
        rows_by_source=rows_by_source,
    )
    execution = await execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-06-01-02",),
        decision_rule_ids=("LX0609-06-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-06-01-02", "custom_prompt": "stub"}],
        evidence_payload={},
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
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
    assert reduced.final_state.value == "not_applicable"
    assert final["status"] == "not_applicable"
    assert final["reason_code"] == "eligibility_not_met"
