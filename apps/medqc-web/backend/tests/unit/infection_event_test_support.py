"""从622054815抽取的合成夹具；不引入未整合台账规则的测试。"""
import pytest
from test_luxian_0609_death_record_timeliness import saved_roundtrip


@pytest.fixture(autouse=True)
def isolated_freeze(monkeypatch, tmp_path):
    for key in ("LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", "LUXIAN_0609_OPINION_FREEZE_DIR",
                "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR", "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR"):
        monkeypatch.setenv(key, str(tmp_path / key))


def _session(rules, rows, executor, *, day="2026-06-10", scene="running", discharge=None,
             admission="2026-06-01 08:00:00"):
    from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
    from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=tuple(rows.get(key, ())), truncated=False, limit_rows=50)

    frozen = {"institute_id": "I", "patient_id": "P", "visit_id": "V", "record_scene": "running",
              "evaluation_horizon": day, "evaluation_basis": "task_frozen_date", "resolution_status": "resolved"}
    if scene == "final":
        frozen.update(record_scene="final", evaluation_basis="discharge_datetime",
                      admission_datetime=admission, discharge_datetime=discharge or day,
                      evaluation_horizon=(discharge or day)[:10],
                      discharge_time_precision="datetime" if ":" in (discharge or day) else "date",
                      task_frozen_date="2026-07-01")
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=tuple(rules), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at=day + "T12:00:00+08:00", row_reader=reader,
        evaluation_as_of_date=day if scene == "running" else None,
        evaluation_horizon_policy="authoritative_discharge" if scene == "final" else "frozen_task_date",
        evaluation_horizon_snapshot=frozen,
        additional_source_keys=resolve_legacy_executor_material_source_keys((executor,), selected_rule_ids=tuple(rules)),
    )


def _finalize(rule, native, session):
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(native.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


def _loaded(final):
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == (final["status"], final["reason_code"])
    assert loaded.get("customer_display_facts") == final.get("customer_display_facts")
    assert loaded.get("findings") == final.get("findings")
    return loaded


def _prophylaxis_drug(order_id, start, stop=None):
    return {"order_id": order_id, "generic_name": "注射用头孢呋辛钠", "repeat_indicator": "长期",
            "drug_frequency": "Q12h", "planned_start_datetime": start, "stop_datetime": stop,
            "order_status": "停止" if stop else "执行"}


def _prophylaxis_rows(drugs, courses=None):
    return {
        "surgery_record": [{
            "document_id": "S1", "surgery_name": "腹腔镜下阑尾切除术", "surgeon": "甲", "surgeon_sign": "甲",
            "surgery_begin_time": "2026-06-02 08:00:00+08:00", "surgery_end_time": "2026-06-02 10:00:00+08:00",
            "record_time": "2026-06-02 11:00:00", "surgery_process": "手术经过：顺利。切口等级：Ⅱ类。",
            "record_content": "手术经过：顺利。切口等级：Ⅱ类。",
        }],
        "inpat_drug_order": drugs,
        "senior_course_record": courses or [{"document_id": "C1", "record_time": "2026-06-03 09:00:00",
                                             "record_content": "术后第一天，切口干燥，体温正常。"}],
    }


_STOPPED = _prophylaxis_drug("A", "2026-06-02 07:30:00", "2026-06-05 08:00:00")
