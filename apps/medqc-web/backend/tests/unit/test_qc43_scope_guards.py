"""正式材料范围未覆盖时，仅阻断依赖缺失的结论；阳性事实不丢弃。"""
import pytest
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
from test_luxian_0609_native_extended_document_execution import FrozenInvasiveProcedureClient, _075_ORDER


@pytest.mark.asyncio
@pytest.mark.parametrize("rule,source", (("LX0609-04-01-01", "presurg_summary"),
                                        ("LX0609-04-05-03", "postsurg_firstcourse_record"),
                                        ("LX0609-10-03-01", "daily_course_record")))
@pytest.mark.parametrize("present", (False, True))
async def test_unknown_supply_does_not_prove_absence_but_keeps_positive(rule, source, present):
    rows = {
        "surgery_record": ({"document_id": "s1", "surgery_name": "胃部分切除术", "surgery_code": "43.6000",
            "surgery_begin_time": "2026-06-01 08:00:00+08:00", "surgery_end_time": "2026-06-01 10:00:00+08:00"},),
        "inpat_nondrug_order": (_075_ORDER,),
    }
    if rule == "LX0609-10-03-01":
        rows["surgery_record"] = ()
    if present:
        rows[source] = ({"document_id": "doc1", "record_time": "2026-06-01 11:00:00", "surgery_name": "胃部分切除术",
            "record_content": "今日胃镜下行胃窦息肉圈套切除，过程顺利。"},)
    def read(source_key, **_kwargs):
        return SnapshotSourceRows.create(source_key=source_key, rows=rows.get(source_key, ()), truncated=False, limit_rows=100,
            material_scope={"can_judge_clinical_absence": False} if source_key == source else None)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-06-10T08:00:00+08:00", evaluation_as_of_date="2026-06-10", row_reader=read,
    )
    client = FrozenInvasiveProcedureClient(mapping={_075_ORDER["order_name"]: "内镜下胃息肉切除术"},
        records={"内镜下胃息肉切除术": ("documented", "胃镜下行胃窦息肉圈套切除")} if present else {})
    kwargs = dict(rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
                  evidence_materials=session.materials, llm_client=client)
    if rule == "LX0609-04-01-01":
        result = await execute_luxian_0609_native_surgery_document_rules(**kwargs, wrapper_rules=[], evidence_payload=None)
    else:
        result = await execute_luxian_0609_native_extended_document_rules(**kwargs)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials)[0]
    assert reduced.final_state == ("compliant" if present else "data_gap")
