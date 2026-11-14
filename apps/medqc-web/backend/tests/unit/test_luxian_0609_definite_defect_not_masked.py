"""根因B：一项/一台的未决（缺时间、正文未知、模型失败）不能掩盖另一项/一台已确认的缺陷。"""

import pytest

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from tests.unit.luxian_0609_course_body_test_facts import FrozenCourseBodyClient

ITEMS = ("ABO血型", "RH血型", "不规则抗体筛查", "乙肝表面抗原", "乙肝表面抗体", "乙肝e抗原",
         "乙肝e抗体", "乙肝核心抗体", "丙肝抗体", "HIV抗体", "梅毒螺旋体抗体", "谷丙转氨酶")


def _labs(*, drop=(), no_time=()):
    return [
        {"document_id": f"lab-{index}", "item_name": name, "result": "阴性",
         **({} if name in no_time else {"report_datetime": "2026-06-09 10:00:00"})}
        for index, name in enumerate(ITEMS)
        if name not in drop
    ]


@pytest.mark.parametrize(
    "times",
    [("2026-06-10 15:00:00",), ("2026-06-10 15:00:00", "2026-06-12 09:00:00")],
)
def test_missing_item_not_masked_by_other_item_missing_time(times):
    documents = {
        "performed_transfusion_events": [{"transfusion_start_time": value} for value in times],
        "labtest_item_report": _labs(drop=("HIV抗体",), no_time=("丙肝抗体",)),
        "__logical_source_states__": {"labtest_item_report": "available"},
    }
    status, reason, facts = transfusion.evaluate_pretransfusion_nine_items(documents)
    assert (status, reason) == ("non_compliant", "pretransfusion_items_incomplete")
    assert facts is not None and facts["failure_kind"] == "pretransfusion_items_incomplete"


def test_missing_time_alone_is_still_data_gap():
    documents = {
        "performed_transfusion_events": [{"transfusion_start_time": "2026-06-10 15:00:00"}],
        "labtest_item_report": _labs(no_time=("丙肝抗体",)),
        "__logical_source_states__": {"labtest_item_report": "available"},
    }
    status, reason, _ = transfusion.evaluate_pretransfusion_nine_items(documents)
    assert (status, reason) == ("data_gap", "authoritative_time_missing")


RULE_065 = "LX0609-04-05-02"
UNKNOWN_BODY = "一般病程。"


@pytest.fixture
def isolated_freeze(monkeypatch, tmp_path):
    monkeypatch.setenv("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", str(tmp_path))


def _surgery(day):
    return {"surgery_code": "01.2400X013", "surgery_name": "硬脑膜外血肿清除术",
            "document_id": f"S{day}",
            "surgery_begin_time": f"2026-06-{day:02d} 08:00:00+08:00",
            "surgery_end_time": f"2026-06-{day:02d} 10:00:00+08:00", "surgeon": "张医生",
            "surgery_process": "血肿已清除，手术完成。"}


async def _run_065(senior_day, client):
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-05-30 07:00:00"},),
        "surgery_record": (_surgery(1), _surgery(5)),
        "senior_course_record": ({
            "document_id": "SR", "record_time": f"2026-06-0{senior_day} 08:00:00",
            "author_name": "李主任", "record_content": UNKNOWN_BODY,
        },),
    }

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    frozen = {
        "institute_id": "I", "patient_id": "P", "visit_id": "V", "record_scene": "final",
        "evaluation_horizon": "2026-06-10", "evaluation_basis": "discharge_datetime",
        "resolution_status": "resolved", "admission_datetime": "2026-05-01 08:00:00",
        "discharge_datetime": "2026-06-10 12:00:00",
    }
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE_065,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-10T23:00:00+08:00", row_reader=reader,
        evaluation_as_of_date="2026-06-10", evaluation_horizon_policy="authoritative_discharge",
        evaluation_horizon_snapshot=frozen,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("extended_document",), selected_rule_ids=(RULE_065,)
        ),
    )
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE_065,), decision_rule_ids=(RULE_065,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=client,
    )
    return bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(RULE_065,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]


class _Failing:
    async def generate(self, *args, **kwargs):
        raise TimeoutError("synthetic gateway timeout")


@pytest.mark.asyncio
@pytest.mark.parametrize("senior_day", [6, 2], ids=["unknown_on_second", "unknown_on_first"])
async def test_065_definite_missing_surgery_not_masked_by_unknown_round(isolated_freeze, senior_day):
    item = await _run_065(senior_day, FrozenCourseBodyClient({UNKNOWN_BODY: ("unknown", None)}))
    assert (item.final_state.value, item.reason_code) == ("non_compliant", "required_document_missing")


@pytest.mark.asyncio
async def test_065_definite_missing_surgery_not_masked_by_model_failure(isolated_freeze):
    item = await _run_065(6, _Failing())
    assert item.final_state.value == "non_compliant"


def test_utc_report_time_is_converted_before_comparison():
    # 08:00Z 即本地 16:00，晚于 15:00 输血，不能当作输血前检查。
    labs = _labs()
    for row in labs:
        if row["item_name"] == "HIV抗体":
            row["report_datetime"] = "2026-06-10T08:00:00+00:00"
    documents = {
        "performed_transfusion_events": [{"transfusion_start_time": "2026-06-10 15:00:00"}],
        "labtest_item_report": labs,
        "__logical_source_states__": {"labtest_item_report": "available"},
    }
    status, reason, _ = transfusion.evaluate_pretransfusion_nine_items(documents)
    assert (status, reason) == ("non_compliant", "pretransfusion_tests_after_transfusion")
