"""根因D：病程来源截断或读取失败不能当作“没有输血病程”或“没有输血”。"""

import json

import pytest

from app.services.luxian_0609 import native_transfusion_execution as native
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.source_evidence_reader import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
)

ORDER = "输注去白悬浮红细胞2U"
COURSE_RULES = ("LX0609-07-02-01", "LX0609-07-02-02")


@pytest.fixture(autouse=True)
def isolated_freeze(monkeypatch, tmp_path):
    for key in (
        "LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", "LUXIAN_0609_OPINION_FREEZE_DIR",
        "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR", "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR",
    ):
        monkeypatch.setenv(key, str(tmp_path))


def _session(rules, rows, executor, *, truncated=(), failing=()):
    def reader(**kwargs):
        key = kwargs["source_key"]
        if key in failing:
            raise SourceEvidenceQueryError("synthetic source failure")
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=key in truncated, limit_rows=5000
        )

    frozen = {
        "institute_id": "I", "patient_id": "P", "visit_id": "V", "record_scene": "running",
        "evaluation_horizon": "2026-06-10", "evaluation_basis": "task_frozen_date",
        "resolution_status": "resolved",
    }
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=rules, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-10T23:00:00+08:00", row_reader=reader,
        evaluation_as_of_date="2026-06-10", evaluation_horizon_policy="frozen_task_date",
        evaluation_horizon_snapshot=frozen,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            (executor,), selected_rule_ids=rules
        ),
    )


class _OrderLabelClient:
    """只回答医嘱触发与病程类型两种协议；病程一律标为非输血病程。"""

    async def generate(self, prompt, **kwargs):
        payload = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        kind = next(iter(payload))
        if kind == "orders":
            return self._reply({
                "schema_version": "lx0609-transfusion-order-trigger-v1",
                "orders": [
                    {"index": row["index"],
                     "classification": "transfusion" if row["name"] == ORDER else "other",
                     "cancelled": False, "quote": row["name"]}
                    for row in payload["orders"]
                ],
            })
        if kind == "records":
            return self._reply({
                "schema_version": "lx0609-transfusion-course-presence-v1",
                "records": [
                    {"index": row["index"], "kind": "other", "quote": row["content"]}
                    for row in payload["records"]
                ],
            })
        raise AssertionError("unexpected protocol " + kind)

    @staticmethod
    def _reply(obj):
        return {"content": json.dumps(obj, ensure_ascii=False), "_api_time": 0.1,
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


class _NoCallModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("来源失败时不应调用模型")


async def _course_states(rows, **kwargs):
    session = _session(COURSE_RULES, rows, "transfusion", **kwargs)
    execution = await native.execute_luxian_0609_native_transfusion_rules(
        rule_ids=COURSE_RULES, wrapper_rules=[{"rule_id": rule} for rule in COURSE_RULES],
        decision_rule_ids=COURSE_RULES, evidence_payload=None, institute_id="I",
        patient_id="P", visit_id="V", source_schema=None, llm_client=_OrderLabelClient(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=COURSE_RULES,
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    return {item.rule_id: item.final_state.value for item in reduced}


def _order_rows():
    return {
        "inpat_nondrug_order": [{
            "order_id": "o-1", "order_name": ORDER, "order_status": "新开",
            "start_datetime": "2026-06-08 15:00:00",
        }],
        "inpat_drug_order": [], "bloodtrans_record": [], "senior_course_record": [],
        "daily_course_record": [{
            "document_id": "c-1", "record_time": "2026-06-09 09:00:00",
            "document_title": "日常病程", "record_content": "患者一般情况可。",
        }],
    }


@pytest.mark.asyncio
async def test_truncated_daily_course_is_not_missing_transfusion_course():
    states = await _course_states(_order_rows(), truncated=("daily_course_record",))
    assert states == {"LX0609-07-02-01": "data_gap", "LX0609-07-02-02": "data_gap"}


@pytest.mark.asyncio
async def test_senior_course_query_error_is_not_missing_transfusion_course():
    states = await _course_states(_order_rows(), failing=("senior_course_record",))
    assert states["LX0609-07-02-01"] == "technical_error"
    assert states["LX0609-07-02-02"] == "technical_error"


@pytest.mark.asyncio
async def test_complete_course_without_transfusion_record_is_still_missing():
    states = await _course_states(_order_rows())
    assert states["LX0609-07-02-01"] == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failing",
    [("daily_course_record", "senior_course_record"), ("inpat_nondrug_order",)],
)
async def test_070_failed_fallback_source_is_not_trigger_absent(failing):
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    rule = "LX0609-07-01-03"
    session = _session((rule,), {}, "extended_document", failing=failing)
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=_NoCallModel(),
    )
    item = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    assert item.final_state.value == "data_gap", (item.final_state.value, item.reason_code)


@pytest.mark.asyncio
async def test_070_complete_empty_sources_remain_not_applicable():
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    rule = "LX0609-07-01-03"
    session = _session((rule,), {}, "extended_document")
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=_NoCallModel(),
    )
    item = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    assert item.final_state.value == "not_applicable"
